"""Check native browser requests, extension fallback, and failure classification without real credentials."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
HOST='https://ai-smart-course-student-pro.zhihuishu.com'
BRIDGE=r'''
globalThis.unsafeWindow=window;
const gmState={'mastery-ai':{key:'fixture-only-api',model:'deepseek-flash',localLogs:false}};
const nativeFetch=fetch.bind(window);
globalThis.GM_getValue=(key,otherwise)=>structuredClone(key in gmState?gmState[key]:otherwise);
globalThis.GM_setValue=(key,value)=>{gmState[key]=structuredClone(value);window.fixtureCheck=gmState['mastery-api-check']};
globalThis.GM_xmlhttpRequest=options=>{
 if(options.url!=='https://api.deepseek.com/chat/completions')throw Error('Unexpected destination');
 nativeFetch('/__extension',{method:'POST',headers:options.headers,body:options.data})
  .then(async r=>options.onload({status:r.status,responseText:await r.text(),finalUrl:options.url})).catch(()=>options.onerror?.());
 return {abort(){options.onabort?.()}};
};
'''

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    for native_status, extension_status, expected_transport in (
        (200,401,'browser'),(401,200,'extension'),('network',200,'extension'),(401,401,None),(402,200,None),('invalid',200,None)
    ):
        attempts,errors=[],[]
        context=browser.new_context()

        def fixture(route):
            request=route.request
            parts=urlsplit(request.url)
            if parts.hostname=='api.deepseek.com' or parts.path=='/__extension':
                headers={'Access-Control-Allow-Origin':HOST,'Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'POST'}
                if request.method=='OPTIONS':
                    return route.fulfill(status=204,headers=headers)
                native=parts.hostname=='api.deepseek.com'
                attempts.append('browser' if native else 'extension')
                assert request.headers.get('authorization')=='Bearer fixture-only-api'
                body=json.loads(request.post_data)
                assert body['model']=='deepseek-flash' and body['thinking']=={'type':'disabled'}
                assert body['max_tokens']==16 and body['messages']==[{'role':'user','content':'Reply with OK only.'}]
                status=native_status if native else extension_status
                if status=='network':
                    return route.abort('failed')
                if status=='invalid':
                    return route.fulfill(status=200,body='<html>unrelated gateway</html>',headers=headers)
                return route.fulfill(status=status,headers=headers,json={'choices':[{'message':{'content':'OK'}}]} if status==200 else {'error':{'message':'Authentication failed'}})
            return route.fulfill(body='<meta charset="utf-8"><h1>隔离接口检测页</h1>',content_type='text/html')

        context.route('**/*',fixture)
        context.add_init_script(script=BRIDGE+SOURCE)
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(HOST+'/myCourses')
        panel=page.locator('#zhihuishu-mastery-assistant')
        panel.locator('.settings').evaluate('(element)=>element.open=true')
        panel.get_by_role('button',name='测试 API 连接',exact=True).click()
        page.wait_for_function('window.fixtureCheck != null')
        result=page.evaluate('window.fixtureCheck')
        assert result['ok']==(expected_transport is not None),result
        if expected_transport:
            assert result['transport']==expected_transport
            assert len(result['mark'])==12
        else:
            assert result['status']==(native_status if type(native_status) is int else None)
        assert attempts==(['browser','extension'] if native_status in (401,'network') else ['browser']),attempts
        assert not errors,errors
        print(f'Native={native_status}, extension={extension_status}: {expected_transport or "paused"}; attempts={len(attempts)}')
        context.close()
    browser.close()
