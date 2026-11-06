from fixture_identity import userscript
"""Check course-entry auto start and the restricted local channel in a simulated browser."""
import importlib.util
import json
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
COURSE, CLS = '1000000000000000001', '200001'
HOME = f'{HOST}/singleCourse/knowledgeStudy/{COURSE}/{CLS}'
spec = importlib.util.spec_from_file_location('collector', ROOT / 'tools/debug_collector.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmState = JSON.parse(window.name || '__SEED__');
const nativeFetch = fetch.bind(window);
globalThis.GM_getValue = (key, fallback) => structuredClone(key in gmState ? gmState[key] : fallback);
globalThis.GM_setValue = (key, value) => { gmState[key] = structuredClone(value); window.name = JSON.stringify(gmState); };
globalThis.GM_xmlhttpRequest = options => {
    nativeFetch(options.url, {method:'POST', headers:options.headers, body:options.data})
      .then(async r => options.onload?.({status:r.status, responseText:await r.text()}))
      .catch(() => options.onerror?.());
    return {abort(){}};
};
'''

with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
    server = module.Collector(Path(tmp) / 'events.jsonl', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    source = userscript(ROOT).replace('http://127.0.0.1:8790', base)

    def controller(command=None):
        request = Request(base + ('/control/clients' if command is None else '/control/commands'),
                          data=None if command is None else json.dumps(command).encode(),
                          headers={'X-Zhihuishu-Control': server.control_secret, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def fixture(route):
        parts = urlsplit(route.request.url)
        path = parts.path
        if parts.hostname == '127.0.0.1':
            request = Request(route.request.url, data=route.request.post_data.encode(),
                              headers={k: v for k, v in route.request.headers.items() if k.startswith('x-zhihuishu')}, method='POST')
            with urlopen(request, timeout=3) as response:
                return route.fulfill(status=response.status, body=response.read(), content_type='application/json')
        if path.endswith('/list-knowledge-theme'):
            return route.fulfill(json={'data': {'courseThemeList': [{'subThemeList': [{'knowledgeList': [
                {'knowledgeId': '31', 'knowledgeName': '点一', 'masteryPercentage': 96},
                {'knowledgeId': '32', 'knowledgeName': '点二', 'masteryPercentage': 95},
                {'knowledgeId': '33', 'knowledgeName': '免考', 'masteryPercentage': None}]}]}]}})
        if path.endswith('/get-node-master-max'):
            return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100}})
        if path.endswith('/questions-paper'):
            return route.fulfill(json={'data': {'questionNum': 1, 'highMasteryScore': 100}})
        if path.startswith('/singleCourse/'):
            html = '<h1>课程目录</h1><script>fetch("/stu/list-knowledge-theme")</script>'
        elif path.startswith('/masteryHistory/'):
            html = '<script>fetch("/mastery-statistics/get-node-master-max")</script>'
        elif path.startswith('/learnPage/'):
            html = '<h1>官方已达标</h1><span class="simplified-mastery__percent">100%</span><script>fetch("/stu/exam/questions-paper")</script>'
        else:
            html = f'<h1>全部课程</h1><a href="{HOME}">进入课程</a>'
        return route.fulfill(body=html, content_type='text/html; charset=utf-8')

    browser = p.chromium.launch(channel='msedge', headless=True)
    try:
        for debug in (False, True):
            seed = {'mastery-ai': {'key': 'private-fixture-key', 'localLogs': False, 'localDebug': debug},
                    'mastery-task': {'id': 'old-paused', 'course': '999', 'cls': '888', 'active': False, 'paused': True, 'phase': 'catalog'}}
            context = browser.new_context()
            context.route('**/*', fixture)
            context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(seed)) + source)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(HOME if debug else HOST + '/myCourses')
            panel = page.locator('#zhihuishu-mastery-assistant')
            panel.wait_for()
            if not debug:
                panel.get_by_role('button', name='开启进入课程自动启动').click()
                assert json.loads(page.evaluate('window.name'))['mastery-auto']['status'] == 'armed'
                page.get_by_role('link', name='进入课程').click()
            else:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    page.wait_for_timeout(200)
                    clients = [c for c in controller()['clients'] if c.get('route', {}).get('kind') == 'course']
                    if clients:
                        break
                assert clients, 'No browser handshake'
                client = clients[-1]
                assert client['keyConfigured'] and client['version'] == '2.5.2'
                assert 'private-fixture-key' not in json.dumps(client)
                controller({'documentId': client['documentId'], 'course': COURSE, 'cls': CLS, 'action': 'start', 'stopAfter': 1})
                page.wait_for_function("JSON.parse(window.name)['mastery-task']?.id !== 'old-paused' && JSON.parse(window.name)['mastery-task']?.paused")
                state = json.loads(page.evaluate('window.name'))['mastery-task']
                assert state['index'] == 1 and len(state['queue']) == 2
                # The pause must survive refresh; no automatic restart and no reset of point budgets.
                page.reload()
                page.wait_for_timeout(1700)
                assert json.loads(page.evaluate('window.name'))['mastery-task']['paused']
                page.get_by_role('alertdialog').get_by_role('button', name='继续自动处理', exact=True).click()
                # Explicit UI resume retains the bound; it completes the remaining last point here.
            page.wait_for_function("JSON.parse(window.name)['mastery-auto']?.status === 'completed'", timeout=15000)
            state = json.loads(page.evaluate('window.name'))['mastery-task']
            assert len(state['results']) == 2 and all(x['high'] == 100 for x in state['results'])
            assert not state['paused'] and not state['active']
            assert not errors, errors
            print('Passed: ' + ('authenticated debug start, bounded pause and resume' if debug else 'all-courses auto arm, native course entry and full queue'))
            context.close()
    finally:
        browser.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
