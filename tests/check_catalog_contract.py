from fixture_identity import userscript
"""Exercise actual XHR text decoding, exempt nodes and malformed catalog diagnosis."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = userscript(ROOT)
HOME = 'https://ai-smart-course-student-pro.zhihuishu.com/singleCourse/knowledgeStudy/1000000000000000001/200001'
EXACT_ID = '9223372036854775807'
BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmState = JSON.parse(window.name || '{"mastery-ai":{"localLogs":true}}');
const nativeGMFetch = fetch.bind(window);
globalThis.GM_getValue = (key, fallback) => structuredClone(key in gmState ? gmState[key] : fallback);
globalThis.GM_setValue = (key, value) => { gmState[key] = structuredClone(value); window.name = JSON.stringify(gmState); };
globalThis.GM_xmlhttpRequest = options => {
  nativeGMFetch(options.url.endsWith('/snapshot') ? '/__snapshot' : '/__debug', {method:'POST', body:options.data})
    .then(async response => options.onload({status:response.status, responseText:await response.text()}));
  return {abort() {}};
};
'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    for case in ('mixed', 'exempt', 'missing'):
        snapshots, events, errors = [], [], []
        context = browser.new_context()

        def fixture(route):
            path = urlsplit(route.request.url).path
            if path == '/__debug':
                events.extend(json.loads(route.request.post_data)['events'])
                return route.fulfill(status=204)
            if path == '/__snapshot':
                snapshots.append(json.loads(route.request.post_data)['snapshot'])
                return route.fulfill(status=204)
            if path.endswith('/list-knowledge-theme'):
                nodes = [{'knowledgeId': '29', 'knowledgeName': '免考', 'masteryPercentage': None}]
                if case == 'mixed':
                    nodes.append({'knowledgeId': EXACT_ID, 'knowledgeName': '可计分', 'masteryPercentage': 96})
                if case == 'missing':
                    nodes.append({'knowledgeId': '30', 'knowledgeName': '字段缺失'})
                data = {'data': {'courseThemeList': [{'subThemeList': [{'knowledgeList': nodes}]}]}}
                raw = json.dumps(data, ensure_ascii=False).replace('"' + EXACT_ID + '"', EXACT_ID)
                return route.fulfill(body=raw, content_type='application/json; charset=utf-8')
            if path.startswith('/singleCourse/'):
                return route.fulfill(content_type='text/html; charset=utf-8', body='''<h1>目录验证</h1><p>完整页面应被采集</p>
                    <script>const xhr=new XMLHttpRequest();xhr.open('GET','/stu/knowledge-study/list-knowledge-theme');xhr.send();</script>''')
            return route.fulfill(content_type='text/html; charset=utf-8', body='<h1>长编号知识点</h1>')

        context.route('**/*', fixture)
        context.add_init_script(script=BRIDGE + SCRIPT)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(HOME)
        panel = page.locator('#zhihuishu-mastery-assistant')
        panel.get_by_role('button', name='开始本课程').click()
        if case == 'mixed':
            page.wait_for_url('**/masteryHistory/1000000000000000001/200001/' + EXACT_ID + '?**')
            task = json.loads(page.evaluate('window.name'))['mastery-task']
            assert task['queue'][0]['point'] == EXACT_ID and len(task['queue']) == 1
        else:
            page.wait_for_function("JSON.parse(window.name)['mastery-task']?.active === false")
            task = json.loads(page.evaluate('window.name'))['mastery-task']
            if case == 'exempt':
                assert not task['paused'] and '免考' in task['message'] and '100%' not in task['message']
            else:
                assert task['paused'] and 'mastery-field-missing' in task['message']
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if (any(item['source'] == 'task-failed' for item in snapshots)
                            and any(item['event'] == 'catalog.node-check' and item['data'].get('reason') == 'mastery-field-missing' for item in events)):
                        break
                    page.wait_for_timeout(200)
                assert any(item['source'] == 'task-failed' and item['totalElements'] >= 3 for item in snapshots)
                assert any(item['event'] == 'catalog.node-check' and item['data'].get('reason') == 'mastery-field-missing' for item in events)
        assert not errors, errors
        print(f'Catalog {case}: passed')
        context.close()
    browser.close()
