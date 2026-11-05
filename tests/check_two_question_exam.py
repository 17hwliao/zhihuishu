"""Verify two-question practice, disabled last-next control and pause/resume during AI."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
EXAM = 'https://studentexamcomh5.zhihuishu.com'
COURSE, CLS, POINT, PAPER, ATTEMPT = '1000000000000000001', '200001', '31', '801', '17'
URL = f'{EXAM}/studentReviewTestOrExam/{ATTEMPT}/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId={PAPER}'
QUESTIONS = [
    {'id': '50001', 'content': '<p>选择跨平台特性</p>', 'questionTypeName': '单选题',
     'optionVos': [{'id': '10', 'content': '<p>无类型</p>'}, {'id': '11', 'content': '<p>跨平台</p>'}]},
    {'id': '50002', 'content': '<p>填写代码和方法名</p>', 'questionTypeName': '填空题', 'optionVos': []},
]
BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmState = JSON.parse(window.name || '__SEED__');
const nativeGMFetch = fetch.bind(window);
globalThis.GM_getValue = (key, fallback) => structuredClone(key in gmState ? gmState[key] : fallback);
globalThis.GM_setValue = (key, value) => { gmState[key] = structuredClone(value); window.name = JSON.stringify(gmState); };
function fixtureAI(data) {
  const blank = JSON.parse(data).messages[1].content.includes('填写代码和方法名');
  const delayed = __PAUSE__ && blank && !window.fillAIRequested;
  if (blank) window.fillAIRequested = true;
  return nativeGMFetch('/__ai', {method:'POST', body:data}).then(async response => {
    const text = await response.text();
    // The real platform re-reads the same question during AI analysis, yielding a new object.
    setTimeout(() => {
      if(__CHANGE__ && !blank) document.querySelector('.centent-pre pre').textContent='题目已经更新';
      fetch('/gateway/t/v1/question/getExamQuestionInfo?index='+(blank ? 1:0)+(__CHANGE__ ? '&changed=1':''));
    }, 80);
    await new Promise(resolve=>setTimeout(resolve, delayed ? 1500:400));
    return new Response(text,{status:response.status});
  });
}
globalThis.fetch=(input, options)=>['https://api.deepseek.com/chat/completions','https://relay.invalid/v1/chat/completions'].includes(String(input))
  ? fixtureAI(options.body):nativeGMFetch(input,options);
globalThis.GM_xmlhttpRequest = options => {
  if (options.url.startsWith('http://127.0.0.1')) throw Error('Local log transport should be disabled in this fixture');
  fixtureAI(options.data).then(async response=>options.onload({status:response.status,responseText:await response.text()}));
  return {abort() { options.onabort?.(); }};
};
'''

EXAM_HTML = r'''<meta charset="utf-8"><div class="questionContent"></div>
<button class="next-topic next-t">下一题</button><span class="reviewDone">提交作业</span>
<script>
let index=0;
const root=document.querySelector('.questionContent');
const next=document.querySelector('.next-topic');
const save=()=>fetch('/gateway/t/v1/answer/saveAnswer',{method:'POST'});
const owner={
 $route:{params:{examTestId:'17',recruitId:'1000000000000000001'},query:{examPaperId:'801',point:'1',pointId:'31',classId:'200001'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{},reviewTopicData:{},userAnswer:null,
 saveAnswer(flag,mode){if(flag!==undefined||mode!=='backflag')throw Error('Wrong native save mode');return save();}
};
if(__NATIVE__)root.__vue__={$parent:owner};
function render(){
  owner.currentQues={questionId:String(50001+index)};owner.reviewTopicData={id:String(50001+index)};owner.userAnswer=null;
  root.innerHTML='<div class="centent-pre"><pre class="preStyle">'+(index ? '填写代码和方法名':'选择跨平台特性')+'</pre></div>';
  if(index){
    root.innerHTML+='<div class="input-ques"><div class="fillAnswer"><input class="el-input__inner"><input class="el-input__inner"></div></div>';
    root.querySelectorAll('input').forEach(input=>{
      input.onchange=()=>{if(!__NATIVE__)save()};
      input.onkeyup=()=>{owner.userAnswer=Array.from(root.querySelectorAll('input'),n=>n.value).join('#@#')};
    });
    next.disabled=true;
  }else{
    root.innerHTML+='<ul class="radio-view"><li class="clearfix"><i class="checkIcon"></i><pre class="preStyle">跨平台</pre></li><li class="clearfix"><i class="checkIcon"></i><pre class="preStyle">无类型</pre></li></ul>';
    root.querySelectorAll('li').forEach(li=>li.onclick=()=>{
      root.querySelectorAll('li').forEach(node=>node.classList.remove('active'));
      li.classList.add('active');owner.userAnswer=li.textContent==='跨平台'?'11':'10';if(!__NATIVE__)save();
    });
  }
  fetch('/gateway/t/v1/question/getExamQuestionInfo?index='+index);
}
next.onclick=()=>{index=1;render()};
document.querySelector('.reviewDone').onclick=()=>{
  const dialog=document.createElement('div');dialog.className='el-message-box';
  dialog.innerHTML='<p>确认提交作业？</p><button>取消</button><button class="confirm">确认提交</button>';
  dialog.querySelector('.confirm').onclick=async()=>{
    const chosen=root.querySelectorAll('input');
    await fetch('/__submit',{method:'POST',body:JSON.stringify(Array.from(chosen,input=>input.value))});
    location.href='__POINT_URL__';
  };
  document.body.append(dialog);
};
render();fetch('/gateway/t/v1/exam/user/getExamSheetInfo');
</script>'''.replace('__POINT_URL__', f'{HOST}/point/{COURSE}/{PAPER}/{ATTEMPT}/{POINT}/{CLS}')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    for pause_case, changed_case, native_case, relay_case in ((False, False, False, False), (True, False, False, False), (False, True, False, False), (False, False, True, False), (False, False, True, True)):
        submits, saves, calls, errors = [], [], [], []
        context = browser.new_context()
        seed = {'mastery-ai': {'key': 'fixture-key', 'model': 'fixture-model', 'limit': 1, 'localLogs': False},
                'mastery-task': {'id': 'two-question-run', 'course': COURSE, 'cls': CLS, 'active': True, 'paused': False,
                'phase': 'exam', 'actor': None, 'enteredAfter': 0, 'launchedAt': 0, 'expires': int(time.time()*1000)+60000,
                'limit': 1, 'queue': [{'point': POINT, 'name': '两题练习', 'high': 96, 'rounds': 1}], 'index': 0, 'results': []}}
        if relay_case:
            seed['mastery-ai'].update(provider='custom',baseUrl='https://relay.invalid/v1',model='vendor/code-model')

        def fixture(route):
            parts = urlsplit(route.request.url)
            path = parts.path
            if path == '/__ai':
                payload=json.loads(route.request.post_data)
                if relay_case:
                    assert payload['model']=='vendor/code-model' and 'thinking' not in payload and 'temperature' not in payload
                data = json.loads(json.loads(route.request.post_data)['messages'][1]['content'])
                calls.append(data)
                answer = ['int x=2;', 'main'] if data['blanks'] else ['B']
                return route.fulfill(json={'choices': [{'message': {'content': json.dumps(answer)}}]})
            if path.endswith('/getExamQuestionInfo'):
                if 'changed' in parse_qs(parts.query):
                    return route.fulfill(json={'data': {**QUESTIONS[0], 'content': '<p>题目已经更新</p>'}})
                return route.fulfill(json={'data': QUESTIONS[int(parse_qs(parts.query)['index'][0])]})
            if path.endswith('/getExamSheetInfo'):
                return route.fulfill(json={'data': {'questionCount': 2}})
            if path.endswith('/saveAnswer'):
                saves.append(1)
                return route.fulfill(json={'code': 200, 'data': True})
            if path == '/__submit':
                submits.append(json.loads(route.request.post_data))
                return route.fulfill(json={'ok': True})
            if path.endswith('/questions-paper-result-page'):
                return route.fulfill(json={'data': {'aiExamQuestionInfo': [
                    {'id': '50001', 'userAnswerDtos': [{'isCorrect': 1}], 'optionDtos': [{'content': '<p>跨平台</p>', 'isCorrect': 1}]},
                    {'id': '50002', 'userAnswerDtos': [{'isCorrect': 1}], 'result': 'int x=2;#@#main'}]}})
            if path.endswith('/questions-paper'):
                return route.fulfill(json={'data': {'questionNum': 2, 'highMasteryScore': 100}})
            if path.startswith('/studentReviewTestOrExam/'):
                body = EXAM_HTML.replace('__NATIVE__', str(native_case).lower())
            elif path.startswith('/examPreview/'):
                body = '<script>fetch("/stu/exam/questions-paper-result-page")</script>'
            elif path.startswith('/learnPage/'):
                body = '<span class="simplified-mastery__percent">100%</span><script>fetch("/stu/exam/questions-paper")</script>'
            else:
                body = '<h1>平台结果</h1>'
            return route.fulfill(body=body, content_type='text/html; charset=utf-8')

        context.route('**/*', fixture)
        context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(seed)).replace('__PAUSE__', str(pause_case).lower())
                                .replace('__CHANGE__', str(changed_case).lower()) + SCRIPT)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL)
        if changed_case:
            page.wait_for_function("JSON.parse(window.name || '{}')['mastery-task']?.paused")
            state = json.loads(page.evaluate('window.name'))['mastery-task']
            assert not submits and not saves, 'Changed question must not accept the previous AI answer'
            assert state['answered'] == [] and '题目已变化' in state['message']
            assert not errors, errors
            print('Changed question with identical ID: stale AI answer blocked, no writes or submission.')
            context.close()
            continue
        if pause_case:
            page.wait_for_function('window.fillAIRequested === true')
            panel = page.locator('#zhihuishu-mastery-assistant')
            panel.get_by_role('button', name='暂停', exact=True).click()
            page.wait_for_timeout(1700)
            assert page.locator('.questionContent input').evaluate_all('(inputs)=>inputs.every(input=>input.value === "")')
            state = json.loads(page.evaluate('window.name'))['mastery-task']
            assert state['answered'] == ['50001'] and state['paused']
            page.get_by_role('alertdialog').get_by_role('button', name='继续自动处理', exact=True).click()
        deadline = time.monotonic() + 20
        state = seed['mastery-task']
        while time.monotonic() < deadline:
            page.wait_for_timeout(300)
            try:
                raw = page.evaluate('window.name')
                if not raw:
                    continue
                state = json.loads(raw)['mastery-task']
            except Exception as error:
                if 'Execution context was destroyed' in str(error):
                    continue
                raise
            if not state['active']:
                break
        assert not state['active'] and not state['paused'], state
        assert submits == [['int x=2;', 'main']], submits
        assert len(saves) == (2 if native_case else 3), saves
        assert len([call for call in calls if not call['blanks']]) == 1
        assert state['results'][0]['high'] == 100
        assert not errors, errors
        print(f'Two-question exam pause={pause_case}, native_save={native_case}, relay={relay_case}: exact choice, two blanks, save receipts, disabled last-next, one confirmed submission, official result and mastery verification passed.')
        context.close()
    browser.close()
