from fixture_identity import userscript
"""Mock-only regression: resume original paper, then learn from exploratory answers."""
import json
import hashlib
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = userscript(ROOT)
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
EXAM = 'https://studentexamcomh5.zhihuishu.com'
COURSE, CLS, POINT = '1000000000000000001', '200001', '31'
HOME = f'{HOST}/singleCourse/knowledgeStudy/{COURSE}/{CLS}'
URL = f'{EXAM}/studentReviewTestOrExam/17/1/1/{COURSE}/name?point=1&pointId=31&classId={CLS}&examPaperId=801'
BRIDGE = r'''
globalThis.unsafeWindow=window;
const state=window.name?JSON.parse(window.name):__SEED__;
window.name=JSON.stringify(state);
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
const nativeFetch=fetch.bind(window);
globalThis.fetch=(u,o)=>String(u).startsWith('https://api.deepseek.com/')?nativeFetch('/__ai',o).then(async r=>new Response(await r.text(),{status:r.status})):nativeFetch(u,o);
globalThis.GM_xmlhttpRequest=o=>{nativeFetch('/__ai',{method:'POST',body:o.data}).then(async r=>o.onload({status:r.status,responseText:await r.text()}));return {abort(){}}};
Math.random=()=>0;
'''


def seed(paused=True, phase='answering', answered=None, fallback=True):
    return {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'localLogs': False, 'guessFallback': fallback},
            'mastery-auto': {'enabled': True, 'status': 'paused' if paused else 'running', 'taskId': 'resume-trial'},
            'mastery-task': {'id': 'resume-trial', 'course': COURSE, 'cls': CLS, 'active': not paused, 'paused': paused,
                'phase': phase, 'examKey': '801:17', 'examUrl': URL, 'actor': 'previous-document', 'lease': 0,
                'expires': int(time.time()*1000)+60000, 'enteredAfter': 0, 'launchedAt': 0, 'index': 0, 'limit': 3,
                'answered': answered or [], 'count': 1, 'confirms': 0, 'lastConfirm': 0, 'results': [],
                'queue': [{'point': POINT, 'name': '本地恢复与解析回归', 'high': 96, 'rounds': 1}]}}


def run(browser, case):
    resume = case in ('paused-course', 'stale-course', 'refresh-paper', 'later-question', 'submit-unknown', 'sealed-recovery')
    blanks = case.startswith('blank-')
    reference = ['存在纯虚根', '用正无穷小取代 0元']
    partial_reference = case == 'blank-partial'
    commits, saves, calls, errors, visits = [], [], [], [], []
    state_seed = seed(paused=case in ('paused-course', 'refresh-paper', 'later-question', 'submit-unknown'),
                      phase='submitting' if case == 'submit-unknown' else 'answering',
                      answered=['50001'] if resume and case != 'submit-unknown' else [], fallback=case != 'fallback-off')
    if resume:
        state_seed['mastery-task']['count'] = 2
    if case == 'submit-unknown':
        state_seed['mastery-task']['answered'] = ['50001', '50002']
    if case in ('sealed-recovery', 'abandon-point'):
        account = hashlib.sha256(b'zhihuishu-uuid:fixture-account-1').hexdigest()
        state_seed['mastery-task'].update(account=account, memoryVersion=1, paperInstance='sealed-paper', phase='verify' if case == 'abandon-point' else 'answering')
        if case == 'abandon-point':
            state_seed['mastery-task']['queue'][0]['rounds'] = 10
            state_seed['mastery-task']['limit'] = 10
        definition = {'content': '<p>选择正确答案</p>', 'type': [None, '单选题'], 'options': ['["错误项",[]]', '["正确项",[]]'], 'blanks': []}
        scope = {'task': 'resume-trial', 'account': account, 'course': COURSE, 'cls': CLS, 'point': POINT}
        records = {str(50001+i): {'id': str(50001+i), 'fingerprint': 'same-version', 'definition': definition,
                   'kind': 'choice', 'answers': ['["正确项",[]]'], 'saved': True} for i in range(2)}
        state_seed['mastery-current-point-v1'] = {'schema': 1, 'scope': scope, 'rounds': [],
            'questions': {'same-version': {'definition': definition, 'answers': {}}}, 'papers': {'sealed-paper':
                {'id': 'sealed-paper', 'key': '801:17', 'round': 1, 'status': 'submitted', 'questions': records,
                 'feedback': {}, 'results': [], 'count': 2, 'submittedAt': int(time.time()*1000)-1000}}}
    if case == 'choice-exhausted':
        state_seed[f'point:{COURSE}:{CLS}:31:rejected'] = {'50001': [['["错误项",[]]'], ['["正确项",[]]']]}

    def fixture(route):
        path = urlsplit(route.request.url).path
        if path == '/__ai':
            calls.append(1)
            if case == 'unauthorized': return route.fulfill(status=401, json={'error': {'message': 'invalid'}})
            answer = '["B"]' if resume else '' if case == 'blank-trial' else '["5","0"]' if blanks else '这道题我无法判断'
            return route.fulfill(json={'choices': [{'message': {'content': answer}}]})
        if path.endswith('/getExamQuestionInfo'):
            index = '1' if 'index=1' in route.request.url else '0'
            return route.fulfill(json={'data': {'id': '50002' if index == '1' else '50001',
                'content': '<p>填写数值</p>' if blanks else '<p>选择正确答案</p>', 'questionTypeName': '填空题' if blanks else '单选题',
                'optionVos': [{'id': '31', 'content': ''}, {'id': '32', 'content': ''}] if blanks else
                [{'id': '10', 'content': '<p>错误项</p>'}, {'id': '11', 'content': '<p>正确项</p>'}]}})
        if path.endswith('/getExamSheetInfo'):
            return route.fulfill(json={'data': {'questionCount': 2 if resume else 1}})
        if path.endswith('/saveAnswer'):
            saves.append(route.request.post_data if blanks else 1)
            return route.fulfill(json={'code': 200, 'data': True})
        if path == '/__new_round':
            visits.append('new-round')
            return route.fulfill(json={'ok': True})
        if path == '/__submit':
            commits.append(route.request.post_data)
            return route.fulfill(json={'ok': True})
        if path.endswith('/questions-paper-result-page'):
            count = 2 if resume else 1
            items = [{'id': str(50001+i), 'analysisDto': {'analyze': '<p>官方解析</p>'},
                      'userAnswerDtos': [{'isCorrect': 1 if resume or len(commits)>1 else 0}],
                      'optionDtos': [{'content': '<p>正确项</p>', 'isCorrect': 1}]} for i in range(count)]
            if blanks:
                values = ['5', '0'] if case == 'blank-contradiction' else reference[:1] if partial_reference else reference
                items[0]['content'] = '<p>填写数值</p>'
                items[0]['questionTypeName'] = '填空题'
                items[0]['userAnswerDtos'][0]['answer'] = '#@#'.join(json.loads(commits[-1]))
                items[0]['optionDtos'] = [{'content': '错误项', 'isCorrect': 0}] + [
                    {'content': f'<span>{value}</span>', 'isCorrect': '1' if i else 1} for i, value in enumerate(values)]
            return route.fulfill(json={'data': {'aiExamQuestionInfo': items}})
        if path.endswith('/get-node-master-max'):
            return route.fulfill(json={'code': 200, 'data': {'masteryMax': 96 if case == 'abandon-point' else 100 if resume or len(commits) >= 2 else 96}})
        if path.endswith('/questions-paper'):
            return route.fulfill(json={'data': {'questionNum': 1, 'highMasteryScore': 96 if case == 'abandon-point' else 100 if resume or len(commits)>1 else 96}})
        if path.startswith('/studentReviewTestOrExam/'):
            visits.append('exam')
            html = '''<meta charset="utf-8"><div class="questionContent"></div><button class="next-topic next-t">下一题</button>
<button class="reviewDone">交卷</button><script>
let index=__START__;
// These synthetic questions intentionally share their stem. Model the native
// current-question ID so the fixture can identify them without trusting the
// most recent response. Unknown duplicate stems remain a separate pause case.
const owner={
 $route:{params:{examTestId:'17',recruitId:'1000000000000000001'},query:{examPaperId:'801',point:'1',pointId:'31',classId:'200001'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{},reviewTopicData:{},userAnswer:'',
 saveAnswer(){return fetch('/answer/saveAnswer',{method:'POST',body:this.userAnswer})}
};
function render(){
 const root=document.querySelector('.questionContent');
 root.__vue__={$parent:owner};owner.currentQues={questionId:String(50001+index)};owner.reviewTopicData={id:String(50001+index)};
 root.innerHTML='<div class="centent-pre"><pre class="preStyle">__STEM__</pre></div>';
 root.innerHTML+=__INPUT__;
 root.querySelectorAll('li').forEach(n=>n.onclick=()=>{root.querySelectorAll('li').forEach(x=>x.classList.remove('active'));n.classList.add('active');owner.userAnswer=n.textContent==='正确项'?'11':'10';fetch('/answer/saveAnswer',{method:'POST'})});
 const inputs=Array.from(root.querySelectorAll('input'));
 inputs.forEach(input=>input.addEventListener('change',()=>{owner.userAnswer=inputs.map(el=>el.value).join('#@#')}));
 document.querySelector('.next-topic').hidden=__ONE__;
 document.querySelector('.next-topic').disabled=!!index;
 fetch('/question/getExamQuestionInfo?index='+index);
}
document.querySelector('.next-topic').onclick=()=>{index=1;render()};
document.querySelector('.reviewDone').onclick=async()=>{await fetch('/__submit',{method:'POST',body:JSON.stringify(Array.from(document.querySelectorAll('.questionContent input'),el=>el.value))});location.href='__RESULT__'};
render();fetch('/getExamSheetInfo');</script>'''
            inputs = '<input><input>' if blanks else '<ul class="radio-view"><li class="clearfix"><pre class="preStyle">错误项</pre></li><li class="clearfix"><pre class="preStyle">正确项</pre></li></ul>'
            # Only the initial manual later-question page starts at the last question.
            start = '1' if case == 'later-question' and len(visits) == 1 else '0'
            html = html.replace('__START__', start).replace('__STEM__', '填写数值' if blanks else '选择正确答案').replace('__INPUT__', json.dumps(inputs))
            html = html.replace('__ONE__', 'false' if resume else 'true').replace('__RESULT__', f'{HOST}/point/{COURSE}/801/17/31/{CLS}')
        elif path.startswith('/examPreview/'):
            html = '<script>fetch("/stu/exam/questions-paper-result-page")</script>'
        elif path.startswith('/learnPage/'):
            html = f'<button class="simplified-mastery__action" onclick="location.href=\'/masteryHistory/{COURSE}/{CLS}/31\'">提升</button><script>fetch("/stu/exam/questions-paper")</script>'
        elif path.startswith('/masteryHistory/'):
            html = '<button class="improve-btn" onclick="fetch(&quot;/__new_round&quot;);window.open('+json.dumps(URL).replace('"', '&quot;')+')">提升</button>'
            html += '<script>fetch("/mastery-statistics/get-node-master-max")</script>'
        elif path.startswith('/point/'):
            visits.append('read-result')
            html = '<h1>原试卷结果</h1>'
        else:
            html = '<meta charset="utf-8"><h1>课程页 / 隔离数据</h1>'
        return route.fulfill(body=html, content_type='text/html; charset=utf-8')

    context = browser.new_context(viewport={'width': 1280, 'height': 920})
    context.route('**/*', fixture)
    context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(state_seed))+SOURCE)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{HOST}/learnPage/{COURSE}/31/{CLS}' if case == 'abandon-point' else HOME if case in ('paused-course', 'stale-course', 'submit-unknown') else URL)
    panel = page.locator('#zhihuishu-mastery-assistant')
    if case in ('paused-course', 'refresh-paper', 'later-question', 'submit-unknown'):
        page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
    if case == 'refresh-paper':
        page.reload()
    if case in ('paused-course', 'stale-course', 'refresh-paper', 'later-question', 'submit-unknown'):
        panel.get_by_role('button', name='继续任务', exact=True).click()
    if case in ('unauthorized', 'fallback-off', 'blank-trial'):
        page.wait_for_function("JSON.parse(window.name||'{}')['mastery-task']?.paused")
        assert not saves and not commits
        assert 'trialAnswers' not in json.dumps(json.loads(page.evaluate('window.name')))
    elif case in ('blank-partial', 'blank-contradiction'):
        page.wait_for_function("JSON.parse(window.name||'{}')['mastery-task']?.paused")
        task = json.loads(page.evaluate('window.name'))['mastery-task']
        assert task['phase'] == 'preview' and '逐空参考答案未能核对' in task['message'], task
        assert task['queue'][0]['rounds'] == 1 and 'new-round' not in visits
        assert saves == ['5#@#0'] and list(map(json.loads, commits)) == [['5', '0']] and len(calls) == 1
        if case == 'blank-partial':
            partial_reference = False
            page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
            panel.get_by_role('button', name='继续任务', exact=True).click()
            page.wait_for_function("JSON.parse(window.name||'{}')['mastery-auto']?.status==='completed'")
            assert list(map(json.loads, commits)) == [['5', '0'], reference] and len(calls) == 1
            assert saves == ['5#@#0', '#@#'.join(reference)] and visits.count('new-round') == 1
    else:
        try:
            page.wait_for_function("JSON.parse(window.name||'{}')['mastery-auto']?.status==='completed'", timeout=25000)
        except Exception:
            current = json.loads(page.evaluate('window.name') or '{}')
            print(json.dumps({'case': case, 'url': page.url, 'calls': len(calls), 'saves': len(saves), 'commits': len(commits),
                              'task': current.get('mastery-task'), 'errors': errors}, ensure_ascii=False), flush=True)
            raise
        state = json.loads(page.evaluate('window.name'))
        task = state['mastery-task']
        if case == 'abandon-point':
            assert task['results'][0]['high'] == 96 and task['results'][0]['rounds'] == 10
            assert '10' in task['results'][0]['reason'] and state.get('mastery-current-point-v1') is None
            assert not calls and not saves and not commits and not errors
            print('Resume/trial regression passed: ten-round abandonment clears all point answers without opening another paper', flush=True)
            context.close(); return
        assert not task['paused'] and task['results'][0]['high'] == 100
        if resume:
            assert not any(v == 'new-round' for v in visits), visits
            assert len(commits) == (0 if case in ('submit-unknown', 'sealed-recovery') else 1)
            assert len(calls) == (0 if case in ('submit-unknown', 'sealed-recovery') else 2), calls  # Legacy task has no verifiable per-paper save receipts
            assert task['queue'][0]['rounds'] == 1
        else:
            assert len(commits) == 2 and len(calls) == 1  # Old rejected records are deliberately not read
            if case == 'blank-reference':
                assert list(map(json.loads, commits)) == [['5', '0'], reference]
                assert saves == ['5#@#0', '#@#'.join(reference)]
            assert task['queue'][0]['rounds'] == 2
            assert state.get('mastery-current-point-v1') is None
            assert state.get(f'point:{COURSE}:{CLS}:31:bank') is None
            assert '官方解析' not in json.dumps(state, ensure_ascii=False), 'Point feedback must be cleared at completion'
    assert not errors, errors
    print('Resume/trial regression passed:', case, flush=True)
    context.close()


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        for case in sys.argv[1:] or ('paused-course', 'stale-course', 'refresh-paper', 'later-question', 'submit-unknown',
                                    'choice-trial', 'blank-trial', 'blank-reference', 'blank-partial', 'blank-contradiction',
                                    'unauthorized', 'fallback-off'):
            run(browser, case)
        browser.close()
