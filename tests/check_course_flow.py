from fixture_identity import userscript
"""Exercise the userscript's normal UI through mocked course and exam pages."""
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

SOURCE = userscript(Path(__file__).resolve().parents[1])
COURSE = '1000000000000000001'
CLASS = '200001'
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
EXAM = 'https://studentexamcomh5.zhihuishu.com'
HOME = f'{HOST}/singleCourse/knowledgeStudy/{COURSE}/{CLASS}'
store = {}
submits = {'31': 0, '32': 0}
ai_calls = []
pages_errors = []
debug_events = []

BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmFetch = fetch.bind(window);
// These fixture hosts are same-site. window.name keeps the fake GM state across
// their same-tab navigations without synchronous HTTP calls inside DOM events.
// This bridge does not simulate multi-tab storage synchronization or isolation.
const gmState = JSON.parse(window.name || '{"mastery-ai":{"localLogs":true}}');
globalThis.GM_getValue = (key, value) => structuredClone(key in gmState ? gmState[key] : value);
globalThis.GM_setValue = (key, value) => {
    gmState[key] = structuredClone(value);
    window.name = JSON.stringify(gmState);
};
globalThis.GM_xmlhttpRequest = options => {
    let aborted = false;
    const endpoint = options.url.endsWith('/snapshot') ? '/__snapshot' : options.url.startsWith('http://127.0.0.1:8790/') ? '/__debug' : '/__ai';
    gmFetch(endpoint, {method:'POST', body:options.data}).then(async r => ({status:r.status, responseText:await r.text()}))
      .then(response => { if (!aborted) options.onload(response); }).catch(() => options.onerror?.());
    return { abort() { aborted = true; options.onabort?.(); } };
};
// Shorter UI polling makes this fixture faster while preserving all waits and leases.
const nativeInterval = setInterval;
globalThis.setInterval = (fn, delay) => nativeInterval(fn, delay === 400 ? 100 : delay);
'''


def body_script(script):
    return '<script>' + script + '</script>'


def native_fetch(path):
    return f"fetch({json.dumps(path)}).then(r => r.json());"


def fixture(route):
    req = route.request
    url = urlsplit(req.url)
    query = parse_qs(url.query)
    path = url.path
    if path == '/__snapshot':
        return route.fulfill(status=204)
    if path == '/__debug':
        debug_events.extend(json.loads(req.post_data)['events'])
        return route.fulfill(status=204)
    if path == '/__ai' or (url.hostname == 'api.deepseek.com' and path == '/chat/completions'):
        payload = json.loads(req.post_data)
        data = json.loads(payload['messages'][1]['content'])
        ai_calls.append(data)
        answer = ['int x=2;'] if data['blanks'] else ['A']
        return route.fulfill(json={'choices': [{'message': {'content': json.dumps(answer)}}]})
    if path.endswith('/list-knowledge-theme'):
        return route.fulfill(json={'data': {'courseThemeList': [{'subThemeList': [{'knowledgeList': [
            {'knowledgeId': '30', 'knowledgeName': '已满分', 'masteryPercentage': 100},
            {'knowledgeId': '29', 'knowledgeName': '免考不应阻断', 'masteryPercentage': None},
            {'knowledgeId': '31', 'knowledgeName': '一直判错的填空', 'masteryPercentage': 96},
            {'knowledgeId': '32', 'knowledgeName': '连续三次全对', 'masteryPercentage': 90},
        ]}]}]}})
    if path.startswith('/singleCourse/'):
        html = '<h1>测试课程</h1>' + body_script(native_fetch('/stu/list-knowledge-theme'))
    elif path.startswith('/learnPage/'):
        point = path.split('/')[3]
        high = 100 if point == '32' and submits[point] >= 3 else 96 if point == '31' else 90
        html = '<h1>测试知识点</h1><span class="simplified-mastery__percent">' + str(high) + '%</span>'
        html += f'<button class="simplified-mastery__action" onclick="location.href=\'/masteryHistory/{COURSE}/{CLASS}/{point}\'">去提升</button>'
        html += body_script(native_fetch('/stu/exam/questions-paper?point=' + point))
    elif path.endswith('/get-node-master-max'):
        return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100 if query.get('knowledgeId', [''])[0] == '32' and submits['32'] >= 3 else 96 if query.get('knowledgeId', [''])[0] == '31' else 90}})
    elif path.endswith('/questions-paper'):
        point = query['point'][0]
        high = 100 if point == '32' and submits[point] >= 3 else 96 if point == '31' else 90
        return route.fulfill(json={'data': {'highMasteryScore': high, 'questionNum': 1}})
    elif path.startswith('/masteryHistory/'):
        point = path.split('/')[-1]
        paper = str(8000 + submits[point])
        exam_url = f'{EXAM}/studentReviewTestOrExam/17/1/1/{COURSE}/name?point=1&pointId={point}&classId={CLASS}&examPaperId={paper}'
        html = f'<button class="improve-btn" onclick="window.open(\'{exam_url}\',\'_blank\')">去提升</button>'
        html += body_script(native_fetch('/mastery-statistics/get-node-master-max?knowledgeId=' + point))
    elif path.startswith('/studentReviewTestOrExam/'):
        point, paper = query['pointId'][0], query['examPaperId'][0]
        fill = point == '31'
        html = '<div class="questionContent"><div class="centent-pre"><pre class="preStyle">' + ('填写代码' if fill else 'Java 特性') + '</pre></div>'
        if fill:
            html += '<input id="answer">'
        else:
            html += '<ul class="radio-view"><li class="clearfix"><i class="checkIcon"></i><pre class="preStyle">无类型</pre></li><li class="clearfix"><i class="checkIcon"></i><pre class="preStyle">跨平台</pre></li></ul>'
        html += '</div><span class="reviewDone">提交作业</span>'
        point_url = f'{HOST}/point/{COURSE}/{paper}/17/{point}/{CLASS}'
        html += body_script(f'''
          const save = () => fetch('/gateway/t/v1/answer/saveAnswer', {{method:'POST'}});
          document.querySelector('#answer')?.addEventListener('change', save);
          document.querySelectorAll('li').forEach(li => li.onclick = () => {{
            document.querySelectorAll('li').forEach(node => node.classList.remove('active'));
            li.classList.add('active'); save();
          }});
          document.querySelector('.reviewDone').onclick = async () => {{
            await fetch('/__submit?point={point}', {{method:'POST'}});
            location.href={json.dumps(point_url)};
          }};
          {native_fetch('/gateway/t/v1/question/getExamQuestionInfo?point=' + point)}
          {native_fetch('/gateway/t/v1/exam/user/getExamSheetInfo')}
        ''')
    elif path.endswith('/getExamQuestionInfo'):
        point = query['point'][0]
        data = {'id': '500' + point, 'content': '<p>填写代码</p>' if point == '31' else '<p>Java 特性</p>',
                'questionTypeName': '填空题' if point == '31' else '单选题', 'optionVos': []}
        if point != '31':
            data['optionVos'] = [{'content': '<p>跨平台</p>'}, {'content': '<p>无类型</p>'}]
        return route.fulfill(json={'data': data})
    elif path.endswith('/getExamSheetInfo'):
        return route.fulfill(json={'data': {'questionCount': 1}})
    elif path.endswith('/saveAnswer'):
        return route.fulfill(json={'code': 200, 'data': True})
    elif path == '/__submit':
        submits[query['point'][0]] += 1
        return route.fulfill(json={'ok': True})
    elif path.startswith('/point/'):
        html = '<p>提交后的平台结果</p>'
    elif path.startswith('/examPreview/'):
        point = path.split('/')[-2]
        html = '<p>平台解析</p>' + body_script(native_fetch('/stu/exam/questions-paper-result-page?point=' + point))
    elif path.endswith('/questions-paper-result-page'):
        point = query['point'][0]
        q = {'id': '500' + point, 'userAnswerDtos': [{'isCorrect': 0 if point == '31' else 1}]}
        if point == '31':
            q['result'] = 'int x=2;'
        else:
            q['optionDtos'] = [{'content': '<p>跨平台</p>', 'isCorrect': 1}, {'content': '<p>无类型</p>', 'isCorrect': 0}]
        return route.fulfill(json={'data': {'aiExamQuestionInfo': [q]}})
    else:
        return route.fulfill(status=404, body='')
    return route.fulfill(content_type='text/html; charset=utf-8', body=html)


with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context()
    context.route('**/*', fixture)
    context.add_init_script(script=BRIDGE + SOURCE)
    context.on('page', lambda page: page.on('pageerror', lambda error: pages_errors.append(str(error))))
    context.on('console', lambda message: print('BROWSER:', message.type, message.text, flush=True)
               if message.type in ('warning', 'error') else None)
    page = context.new_page()
    page.goto(HOME)
    panel = page.locator('#zhihuishu-mastery-assistant')
    panel.locator('input[name=key]').fill('sk-offline-fixture')
    panel.locator('input[name=model]').fill('fixture-model')
    panel.get_by_role('button', name='保存设置').click()
    store = json.loads(page.evaluate('window.name'))
    assert store['mastery-ai']['key'] == 'sk-offline-fixture'
    panel.get_by_role('button', name='开始本课程').click()
    deadline = time.monotonic() + 150
    last_debug = 0
    while time.monotonic() < deadline:
        page.wait_for_timeout(600)
        try:
            store = json.loads(page.evaluate('window.name'))
        except Exception as error:
            if 'Execution context was destroyed' in str(error):
                continue
            raise
        task = store.get('mastery-task', {})
        if time.monotonic() - last_debug > 5:
            print('PAGES:', [tab.url for tab in context.pages], 'task:', task.get('phase'), flush=True)
            last_debug = time.monotonic()
        if task and not task.get('active'):
            break
    task = store['mastery-task']
    assert not pages_errors, (pages_errors, task, submits)
    assert not task.get('paused') and not task['active'], json.dumps(task, ensure_ascii=False)
    assert submits == {'31': 10, '32': 3}, (submits, task)
    assert task['index'] == 2
    assert len(task['results']) == 2
    assert store.get('mastery-current-point-v1') is None, 'Abandonment and final completion must clear temporary answers'
    assert task['results'][0]['high'] == 96 and task['results'][0]['rounds'] == 10
    assert task['results'][1]['high'] == 100 and task['results'][1]['rounds'] == 3
    assert '一直判错的填空' in page.locator('#zhihuishu-mastery-assistant').locator('.unresolved-results').text_content()
    assert '10 轮' in page.locator('#zhihuishu-mastery-assistant').locator('.unresolved-results').text_content()
    assert any(call['previouslyIncorrect'] for call in ai_calls)
    assert any(event['event'] == 'question.captured' for event in debug_events)
    assert any(event['event'] == 'task.state' for event in debug_events)
    assert not any(event['event'] in ('runtime.error', 'runtime.rejection', 'scheduler.failed') for event in debug_events)
    assert 'sk-offline-fixture' not in json.dumps(debug_events)
    assert len(context.pages) == 1, 'Course task should reuse its tab instead of accumulating practice tabs'
    screenshot = Path(__file__).resolve().parents[1] / '.local' / 'mastery-panel-check.png'
    screenshot.parent.mkdir(exist_ok=True)
    context.pages[-1].screenshot(path=str(screenshot))
    print('Full userscript flow passed: API settings, course discovery, same-tab handoff, ten failed fill rounds, three perfect rounds, automatic submission, results and live score verification.')
    print(f'Native submit counts {submits}; AI calls {len(ai_calls)}; browser tabs {len(context.pages)}.')
    browser.close()
