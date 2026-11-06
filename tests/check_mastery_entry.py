"""No UUID or working profile endpoint: complete only the mastery workflow.

All accounts, IDs, questions and keys here are synthetic. No authenticated service
is contacted. Pass --baseline PATH to reproduce the old identity-gate failure
on the original practice page. Baseline failures are evidence, not a pass for
the current script.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
EXAM_HOST = 'https://studentexamcomh5.zhihuishu.com'
COURSE, CLS, POINT = '1000000000000000001', '200001', '31'
EXAM = f'{EXAM_HOST}/studentReviewTestOrExam/17/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId=801'
BRIDGE = r'''
globalThis.unsafeWindow=window;
const state=window.name?JSON.parse(window.name):__SEED__;
window.name=JSON.stringify(state);
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_deleteValue=k=>{delete state[k];window.name=JSON.stringify(state)};
globalThis.GM_listValues=()=>Object.keys(state);
globalThis.GM_xmlhttpRequest=()=>{throw Error('No extension network expected')};
HTMLMediaElement.prototype.play=function(){throw Error('Mastery must never start media')};
'''


def run(browser, source, case, baseline=False):
    events = {'profile': 0, 'save': 0, 'submit': 0, 'entry': 0, 'lessons': 0, 'api': 0}
    errors, forbidden, history_urls = [], [], []
    account = hashlib.sha256(b'zhihuishu-user-id:600001').hexdigest()
    task = {'id': 'native-profile-regression', 'course': COURSE, 'cls': CLS,
            'active': True, 'paused': False, 'phase': 'learn', 'actor': None,
            'lease': 0, 'enteredAfter': 0, 'expires': int(time.time()*1000)-60000,
            'launchedAt': 0, 'index': 0, 'limit': 10, 'results': [], 'memoryVersion': 1,
            'queue': [{'point': POINT, 'name': '临时回归 + Java / 测试', 'high': 97, 'rounds': 6}]}
    task.update(account=account, accountKind='user-id')
    seed = {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'localLogs': False},
            'mastery-task': task}
    if case == 'catalog':
        task.update(phase='catalog', queue=[], expires=int(time.time()*1000)+60000)
    if case in ('exam', 'paused-exam', 'empty-profile'):
        task.update(phase='exam', examUrl=EXAM, examKey='801:17', paperInstance='original-seventh-paper',
                    expires=int(time.time()*1000)+60000)
        task['queue'][0]['rounds'] = 7
    if case == 'paused-exam':
        task.update(active=False, paused=True, message='无法确认当前平台账号')

    def fixture(route):
        req = route.request; url = urlsplit(req.url); path = url.path
        headers = {'Access-Control-Allow-Origin': req.headers.get('origin', HOST),
                   'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Headers': 'authorization,content-type'}
        if req.method == 'OPTIONS': return route.fulfill(status=204, headers=headers)
        if path.endswith('/menuTree') or path.endswith('/getLoginUserInfo'):
            events['profile'] += 1
            if case == 'empty-profile':
                return route.fulfill(headers=headers, json={'code': 200, 'data': {}})
            return route.fulfill(status=503, headers=headers)
        if path.endswith('/get-node-master-max'):
            return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100 if events['submit'] else 97}})
        if path.endswith('/list-knowledge-theme'):
            return route.fulfill(json={'data': {'courseThemeList': [{'subThemeList': [{'knowledgeList': [
                {'knowledgeId': '30', 'knowledgeName': '免考', 'masteryPercentage': None},
                {'knowledgeId': POINT, 'knowledgeName': task.get('queue', [{}])[0].get('name', '待提升') if task['queue'] else '待提升', 'masteryPercentage': 97}
            ]}]}]}})
        if path == '/chat/completions':
            events['api'] += 1
            return route.fulfill(headers=headers, json={'choices': [{'message': {'content': '["B"]'}}]})
        if path.endswith('/getExamQuestionInfo'):
            return route.fulfill(json={'data': {'id': '50001', 'content': '<p>Java 特性</p>',
                'questionTypeName': '单选题', 'optionVos': [{'id': '10', 'content': '<p>无类型</p>'}, {'id': '11', 'content': '<p>跨平台</p>'}]}})
        if path.endswith('/getExamSheetInfo'): return route.fulfill(json={'data': {'questionCount': 1}})
        if path.endswith('/saveAnswer'):
            events['save'] += 1
            return route.fulfill(json={'code': 200, 'data': True})
        if path == '/__entry':
            events['entry'] += 1
            return route.fulfill(json={'ok': True})
        if path == '/__submit':
            events['submit'] += 1
            assert json.loads(req.post_data)['answer'] == '11', 'Submit the actually selected correct option'
            return route.fulfill(json={'ok': True})
        if path.endswith('/questions-paper-result-page'):
            return route.fulfill(json={'data': {'aiExamQuestionInfo': [{'id': '50001',
                'userAnswerDtos': [{'isCorrect': 1}], 'optionDtos': [{'content': '<p>跨平台</p>', 'isCorrect': 1}]}]}})
        if any(word in path.lower() for word in ('studyrecord', 'learningreport', 'playvideo')):
            forbidden.append(path); return route.abort()
        if path.startswith('/learnPage/'):
            events['lessons'] += 1
            html = '<h1>学习资源页（不得点资源）</h1><button class="simplified-mastery__action" onclick="throw Error(\'Legacy resource navigation\')">去提升</button>'
        elif path.startswith('/singleCourse/'):
            html = '<h1>全部知识点</h1><script>fetch("/stu/list-knowledge-theme")</script>'
        elif path.startswith('/masteryHistory/'):
            history_urls.append(req.url)
            if not baseline:
                import base64
                from urllib.parse import unquote
                name = json.loads(unquote(base64.b64decode(parse_qs(url.query)['nodeName'][0]).decode()))
                assert isinstance(name, str) and name
            html = '<h1>掌握度历史</h1><button class="improve-btn">去提升</button><script>fetch("/mastery-statistics/get-node-master-max");'
            html += 'document.querySelector("button").onclick=async()=>{await fetch("/__entry");location.href=' + json.dumps(EXAM) + '};</script>'
        elif path.startswith('/studentReviewTestOrExam/'):
            html = '''<div class="questionContent"><div class="centent-pre"><pre class="preStyle">Java 特性</pre></div>
            <ul class="radio-view"><li class="clearfix"><pre class="preStyle">无类型</pre></li><li class="clearfix"><pre class="preStyle">跨平台</pre></li></ul></div>
            <button class="reviewDone">交卷</button><script>
            document.querySelectorAll('li').forEach(n=>n.onclick=()=>{document.querySelectorAll('li').forEach(x=>x.classList.remove('active'));n.classList.add('active');fetch('/answer/saveAnswer',{method:'POST'})});
            document.querySelector('.reviewDone').onclick=async()=>{const answer=document.querySelector('li.active')?.textContent==='跨平台'?'11':'10';await fetch('/__submit',{method:'POST',body:JSON.stringify({answer})});location.href='__RESULT__'};
            fetch('/question/getExamQuestionInfo');fetch('/getExamSheetInfo');</script>'''.replace('__RESULT__', f'{HOST}/point/{COURSE}/801/17/{POINT}/{CLS}')
        elif path.startswith('/examPreview/'):
            html = '<script>fetch("/stu/exam/questions-paper-result-page")</script>'
        else: html = '<h1>平台结果</h1>'
        # Real learner store has no UUID; a classmate prop must not become account identity.
        html += '<script>document.body.__vue_app__={config:{globalProperties:{$store:{state:{baseData:{realName:"fixture"}}}}}};document.body.__vueParentComponent={setupState:{userId:"wrong-classmate"}};</script>'
        return route.fulfill(body='<meta charset="utf-8"><body>'+html, content_type='text/html; charset=utf-8')

    context = browser.new_context()
    context.route('**/*', fixture)
    context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(seed))+source)
    page = context.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
    initial = f'{HOST}/singleCourse/knowledgeStudy/{COURSE}/{CLS}' if case == 'catalog' else EXAM if case in ('exam','paused-exam','empty-profile') else f'{HOST}/learnPage/{COURSE}/{POINT}/{CLS}'
    page.goto(initial)
    if baseline:
        page.wait_for_function("JSON.parse(window.name)['mastery-task']?.paused===true", timeout=22000)
        state = json.loads(page.evaluate('window.name'))
        assert state['mastery-task']['phase'] == 'exam' and state['mastery-task']['queue'][0]['rounds'] == 7
        assert '无法确认当前平台账号' in state['mastery-task']['message']
        assert events['entry'] == events['save'] == events['submit'] == 0
        assert '/studentReviewTestOrExam/' in page.url and events['profile'] > 0
        print('2.5.2 baseline reproduced: question captured, profile unavailable, account gate pauses before AI/save/submit.', flush=True)
    else:
        if case == 'paused-exam':
            page.get_by_role('alertdialog').get_by_role('button', name='继续自动处理', exact=True).click()
        page.wait_for_function("JSON.parse(window.name)['mastery-task']?.active===false", timeout=30000)
        state = json.loads(page.evaluate('window.name')); final = state['mastery-task']
        assert not final['paused'], final
        assert events['lessons'] == (1 if case == 'resource' else 0), 'Never navigate back to learning resources'
        assert final['results'][0]['high'] == 100 and final['results'][0]['rounds'] == (1 if case == 'catalog' else 7)
        assert 'account' not in final and 'accountKind' not in final
        assert events['profile'] == 0, 'No proactive profile requests, even with failing or ID-less endpoints'
        assert events['submit'] == events['api'] == 1 and events['save'] >= 1
        assert events['entry'] == (1 if case in ('catalog','resource') else 0), 'Resume the original seventh-round paper without reopening'
        assert 'mastery-current-point-v1' not in state
        assert len(history_urls) == (2 if case in ('catalog','resource') else 1)
        assert not forbidden and not errors, (forbidden, errors)
        print('Native mastery entry passed:', case, events, flush=True)
    context.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--case', action='append', choices=['resource','catalog','exam','paused-exam','empty-profile'])
    args = parser.parse_args()
    source = (args.baseline or ROOT/'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        for case in (['exam'] if args.baseline else args.case or ['resource', 'catalog', 'exam', 'paused-exam', 'empty-profile']):
            run(browser, source, case, bool(args.baseline))
        browser.close()
