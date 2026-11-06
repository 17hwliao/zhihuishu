from fixture_identity import userscript
"""Verify relay configuration, endpoint-scoped keys, payload options, CORS fallback and redacted export."""
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SOURCE=userscript(ROOT)
HOST='https://ai-smart-course-student-pro.zhihuishu.com'
OFFICIAL='https://api.deepseek.com/chat/completions'
RELAY='https://relay.invalid/v1/chat/completions'
SECOND='https://second-relay.invalid/proxy/v1/chat/completions'
SECRETS={'api.deepseek.com':'fixture-official-private','relay.invalid':'fixture-relay-private','second-relay.invalid':'fixture-second-private'}
BRIDGE=r'''
globalThis.unsafeWindow=window;
const state=JSON.parse(window.name||'__SEED__');
const nativeFetch=fetch.bind(window);
globalThis.fetch=(input,options)=>nativeFetch(input,options).then(async response=>{
 if(window.fixtureDelayAPI && String(input).startsWith('https://relay.invalid/')){
  window.fixtureAPIReady=true;await new Promise(resolve=>setTimeout(resolve,900));
 }
 return response;
});
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_xmlhttpRequest=options=>{
 if(options.url.startsWith('http://127.0.0.1'))throw Error('Debug transport must stay disabled');
 if(options.redirect!=='error')throw Error('Redirects must not carry credentials');
 nativeFetch('/__extension',{method:'POST',headers:options.headers,body:JSON.stringify({destination:options.url,payload:JSON.parse(options.data)})})
  .then(async r=>options.onload({status:r.status,responseText:await r.text(),finalUrl:options.url})).catch(()=>options.onerror?.());
 return {abort(){}};
};
'''
calls,errors=[],[]

def fixture(route):
    req=route.request;parts=urlsplit(req.url)
    if parts.hostname in SECRETS or parts.path=='/__extension':
        headers={'Access-Control-Allow-Origin':HOST,'Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'POST'}
        if req.method=='OPTIONS':
            return route.fulfill(status=403 if parts.hostname=='second-relay.invalid' else 204,headers={} if parts.hostname=='second-relay.invalid' else headers)
        if parts.hostname=='second-relay.invalid':
            return route.abort('failed')
        data=json.loads(req.post_data)
        url=data['destination'] if parts.path=='/__extension' else req.url
        body=data['payload'] if parts.path=='/__extension' else data
        target=urlsplit(url).hostname
        assert req.headers.get('authorization')=='Bearer '+SECRETS[target]
        calls.append({'url':url,'body':body,'transport':'extension' if parts.path=='/__extension' else 'browser'})
        if target=='relay.invalid' and 'max_tokens' in body:
            return route.fulfill(status=400,headers=headers,json={'error':{'message': 'Unsupported parameter max_tokens. Use max_completion_tokens instead.'}})
        return route.fulfill(headers=headers,json={'choices':[{'message':{'content':'OK'}}]})
    return route.fulfill(body='<meta charset="utf-8"><h1>隔离接口配置测试</h1>',content_type='text/html; charset=utf-8')

with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(accept_downloads=True)
    seed={'mastery-ai':{'key':SECRETS['api.deepseek.com'],'model':'deepseek-flash','localLogs':False,'limit':10}}
    context.route('**/*',fixture);context.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed))+SOURCE)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(HOST+'/myCourses')
    panel=page.locator('#zhihuishu-mastery-assistant');panel.wait_for();panel.locator('.settings').evaluate('(n)=>n.open=true')

    def state():return json.loads(page.evaluate('window.name'))
    def save():panel.get_by_role('button',name='保存设置',exact=True).click()
    def test(expected=1):
        count=len(calls)
        panel.get_by_role('button',name='测试 API 连接',exact=True).click()
        page.wait_for_function("JSON.parse(window.name)['mastery-api-check']?.ok===true")
        assert len(calls)==count+expected

    panel.locator('select[name=provider]').select_option('custom')
    panel.locator('input[name=baseUrl]').fill('https://relay.invalid/v1/')
    panel.locator('input[name=model]').fill('vendor/model:latest')
    save()
    assert state()['mastery-ai']['key']=='' and not calls, 'A new endpoint must never inherit the official key'
    assert state()['mastery-ai-profiles'][OFFICIAL]['key']==SECRETS['api.deepseek.com']
    assert panel.locator('[name=tokenParameter],[name=sendTemperature],[name=disableThinking]').count()==0
    assert panel.locator('input[name=baseUrl]').is_visible()
    panel.locator('input[name=key]').fill('Bearer '+SECRETS['relay.invalid'])
    test(expected=2)
    assert calls[-1]['body']['max_completion_tokens']==512 and 'max_tokens' not in calls[-1]['body']
    assert len(state()['mastery-api-compat-v1'])==1
    assert calls[-1]['url']==RELAY and calls[-1]['body']['model']=='vendor/model:latest'
    assert 'thinking' not in calls[-1]['body'] and 'temperature' not in calls[-1]['body']

    panel.locator('select[name=provider]').select_option('deepseek')
    assert panel.locator('input[name=baseUrl]').is_hidden()
    test()
    assert calls[-1]['url']==OFFICIAL and calls[-1]['body']['model']=='deepseek-flash'
    assert calls[-1]['body']['thinking']=={'type':'disabled'}

    panel.locator('select[name=provider]').select_option('custom')
    test()
    assert calls[-1]['url']==RELAY and calls[-1]['body']['max_completion_tokens']==512
    assert 'max_tokens' not in calls[-1]['body'] and 'thinking' not in calls[-1]['body']

    panel.locator('input[name=baseUrl]').fill(SECOND)
    save()
    assert state()['mastery-ai']['key']=='' and state()['mastery-api-check'] is None
    panel.locator('input[name=key]').fill(SECRETS['second-relay.invalid'])
    test()
    assert calls[-1]['url']==SECOND and calls[-1]['transport']=='extension'
    assert state()['mastery-api-check']['endpoint']==SECOND

    panel.locator('.diagnostics').evaluate('(n)=>n.open=true')
    panel.locator('input[name=model]').fill('unsaved-draft')
    panel.locator('input[name=localLogs]').check()
    assert state()['mastery-ai']['model']!='unsaved-draft', 'Log toggle must not save an unrelated API draft'
    panel.locator('input[name=localLogs]').uncheck()
    panel.get_by_role('button',name='连接本机调试',exact=True).click()
    assert state()['mastery-ai']['model']!='unsaved-draft', 'Debug connection must not commit API drafts'
    panel.locator('input[name=localLogs]').uncheck()
    panel.locator('input[name=localDebug]').uncheck()
    with page.expect_download() as pending:
        panel.get_by_role('button',name='导出诊断包',exact=True).click()
    file=Path(tmp)/'report.json';pending.value.save_as(file)
    report=file.read_text(encoding='utf-8')
    for key in SECRETS.values():assert key not in report
    assert 'mastery-ai-profiles' not in report
    panel.get_by_role('button',name='清除 Key',exact=True).click()
    assert state()['mastery-ai']['key']=='' and state()['mastery-ai-profiles'][SECOND]['key']==''
    assert state()['mastery-ai-profiles'][OFFICIAL]['key']==SECRETS['api.deepseek.com']
    panel.locator('input[name=baseUrl]').fill('https://relay.invalid/v1')
    panel.locator('input[name=model]').focus()
    save()
    assert state()['mastery-ai']['key']==SECRETS['relay.invalid']
    before=len(calls)
    page.evaluate('window.fixtureDelayAPI=true')
    panel.get_by_role('button',name='测试 API 连接',exact=True).click()
    page.wait_for_function('window.fixtureAPIReady===true')
    panel.locator('input[name=baseUrl]').fill(SECOND)
    save()
    page.wait_for_timeout(1100)
    assert state()['mastery-api-check'] is None and state()['mastery-ai']['key']==''
    assert len(calls)==before+1, 'Changed configuration must not retry the old provider or leak its key'
    assert '接口配置已变化' in panel.locator('.status').text_content()
    assert not errors,errors
    print('Custom API passed: URL normalization, slash/colon model IDs, endpoint-scoped keys, official/relay profile switching, automatic bounded token compatibility, no advanced controls, independent log toggles, CORS fallback to same relay, credential-free export and per-profile key removal.')
    browser.close()
