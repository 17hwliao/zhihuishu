"""Reproduce the real 401 pause, then check connection testing and resume without reopening a paper."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
COURSE, CLS, POINT, PAPER, ATTEMPT = '1000000000000000001', '200001', '31', '801', '17'
URL = f'https://studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/{ATTEMPT}/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId={PAPER}'
BRIDGE = r'''
globalThis.unsafeWindow=window;
const gmState=JSON.parse(window.name||'__SEED__');
const nativeFetch=fetch.bind(window);
globalThis.GM_getValue=(k,d)=>structuredClone(k in gmState?gmState[k]:d);
globalThis.GM_setValue=(k,v)=>{gmState[k]=structuredClone(v);window.name=JSON.stringify(gmState)};
function fixtureAI(data,headers){
  return nativeFetch('/__ai',{method:'POST',headers,body:data}).then(async r=>{
    const text=await r.text();
    const test=JSON.parse(data).max_tokens===16;
    if(!test && r.status===200) setTimeout(()=>fetch('/gateway/t/v1/question/getExamQuestionInfo'),80);
    await new Promise(resolve=>setTimeout(resolve,test?0:400));
    return new Response(text,{status:r.status});
  });
}
globalThis.fetch=(input,options)=>String(input)==='https://api.deepseek.com/chat/completions'
  ? fixtureAI(options.body,options.headers):nativeFetch(input,options);
globalThis.GM_xmlhttpRequest=options=>{
  fixtureAI(options.data,options.headers).then(async r=>options.onload({status:r.status,responseText:await r.text()}))
    .catch(()=>options.onerror?.());return {abort(){}};
};
'''
HTML = '''<div class="questionContent"><div class="centent-pre"><pre class="preStyle">选择 Java 特性</pre></div>
<div class="checkbox-views">
<label class="el-checkbox"><input type="checkbox"><span class="preStyle">跨平台</span></label>
<label class="el-checkbox"><input type="checkbox"><span class="preStyle">面向对象</span></label>
<label class="el-checkbox"><input type="checkbox"><span class="preStyle">没有类型</span></label>
</div></div><span class="reviewDone">提交作业</span>
<script>
document.querySelectorAll('input').forEach(input=>input.onchange=()=>fetch('/gateway/t/v1/answer/saveAnswer',{method:'POST'}));
document.querySelector('.reviewDone').onclick=()=>{
 const dialog=document.createElement('div');dialog.className='el-message-box';dialog.innerHTML='<p>确认提交作业？</p><button>确认提交</button>';
 dialog.querySelector('button').onclick=async()=>{await fetch('/__submit',{method:'POST',body:JSON.stringify(Array.from(document.querySelectorAll('input'),n=>n.checked))});location.href='__RESULT__'};
 document.body.append(dialog);
};
fetch('/gateway/t/v1/question/getExamQuestionInfo');fetch('/gateway/t/v1/exam/user/getExamSheetInfo');
</script>'''.replace('__RESULT__', f'{HOST}/point/{COURSE}/{PAPER}/{ATTEMPT}/{POINT}/{CLS}')
QUESTION = {'id': '50001', 'content': '<p>选择 Java 特性</p>', 'questionTypeName': '多选题',
            'optionVos': [{'id': str(i), 'content': f'<p>{content}</p>'} for i, content in enumerate(('跨平台', '面向对象', '没有类型'))]}
seed = {'mastery-ai': {'key': 'sk-fixture-invalid', 'model': 'deepseek-flash', 'localLogs': False},
        'mastery-auto': {'enabled': True, 'status': 'running', 'taskId': 'auth-case'},
        'mastery-task': {'id': 'auth-case', 'course': COURSE, 'cls': CLS, 'active': True, 'paused': False,
        'phase': 'exam', 'actor': None, 'enteredAfter': 0, 'launchedAt': 0, 'expires': int(time.time()*1000)+60000,
        'limit': 10, 'queue': [{'point': POINT, 'name': '接口恢复验证', 'high': 98, 'rounds': 1}], 'index': 0, 'results': []}}
submits, saves, requests, errors = [], [], [], []

def fixture(route):
    request=route.request
    path=urlsplit(request.url).path
    if path=='/__ai':
        body=json.loads(request.post_data)
        assert body['model']=='deepseek-flash' and body['thinking']=={'type':'disabled'}
        test=body['max_tokens']==16
        requests.append('test' if test else 'answer')
        if request.headers.get('authorization')=='Bearer sk-fixture-invalid':
            return route.fulfill(status=401,json={'error':{'message':'The key sk-fixture-invalid was rejected','code':'invalid_api_key'}})
        assert request.headers.get('authorization')=='Bearer sk-fixture-recovery'
        return route.fulfill(json={'choices':[{'message':{'content':'OK' if test else '["A","B"]'}}]})
    if path.endswith('/getExamQuestionInfo'):
        return route.fulfill(json={'data':QUESTION})
    if path.endswith('/getExamSheetInfo'):
        return route.fulfill(json={'data':{'questionCount':1}})
    if path.endswith('/saveAnswer'):
        saves.append(1)
        return route.fulfill(json={'code':200,'data':True})
    if path=='/__submit':
        submits.append(json.loads(request.post_data))
        return route.fulfill(json={'ok':True})
    if path.endswith('/questions-paper-result-page'):
        return route.fulfill(json={'data':{'aiExamQuestionInfo':[{'id':'50001','userAnswerDtos':[{'isCorrect':1}],
                    'optionDtos':[{'content':'<p>跨平台</p>','isCorrect':1},{'content':'<p>面向对象</p>','isCorrect':1}]}]}})
    if path.endswith('/questions-paper'):
        return route.fulfill(json={'data':{'questionNum':1,'highMasteryScore':100}})
    if path.startswith('/studentReviewTestOrExam/'):
        html=HTML
    elif path.startswith('/examPreview/'):
        html='<script>fetch("/stu/exam/questions-paper-result-page")</script>'
    elif path.startswith('/learnPage/'):
        html='<span class="simplified-mastery__percent">100%</span><script>fetch("/stu/exam/questions-paper")</script>'
    else:
        html='<h1>官方结果</h1>'
    return route.fulfill(body=html,content_type='text/html; charset=utf-8')

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context()
    context.route('**/*',fixture)
    context.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed))+SCRIPT)
    page=context.new_page()
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(URL)
    page.wait_for_function("JSON.parse(window.name || '{}')['mastery-task']?.paused")
    state=json.loads(page.evaluate('window.name'))
    assert '鉴权未通过' in state['mastery-task']['message']
    assert state['mastery-task']['answered']==[] and state['mastery-task']['queue'][0]['rounds']==1
    assert not submits and not saves
    panel=page.locator('#zhihuishu-mastery-assistant')
    assert panel.locator('.settings').get_attribute('open') is not None
    page.get_by_role('alertdialog').get_by_role('button',name='查看设置',exact=True).click()
    panel.locator('input[name=key]').fill('"Bearer sk-fixture-recovery"')
    panel.get_by_role('button',name='测试 API 连接',exact=True).click()
    page.wait_for_function("JSON.parse(window.name)['mastery-api-check']?.ok === true")
    assert not submits and not saves, 'Connection testing must not modify or submit the question'
    panel.get_by_role('button',name='继续任务',exact=True).click()
    page.wait_for_function("JSON.parse(window.name)['mastery-auto']?.status === 'completed'",timeout=20000)
    state=json.loads(page.evaluate('window.name'))
    assert submits==[[True,True,False]] and len(saves)==2
    assert state['mastery-task']['results'][0]['rounds']==1
    assert requests==['answer','answer','test','answer']
    diagnostic=json.dumps({k:v for k,v in state.items() if k.startswith('mastery-debug:')})
    assert 'sk-fixture-invalid' not in diagnostic and 'sk-fixture-recovery' not in diagnostic
    assert not errors,errors
    print('Passed: official-model 401 pause, clear error, quoted Bearer key cleanup, harmless connection test, duplicate question response, multi-select saves and one submission after resume; round remains 1.')
    browser.close()
