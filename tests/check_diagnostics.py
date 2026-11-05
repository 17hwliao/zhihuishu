"""Exercise the unknown-page UI, drag, export, XHR discovery and real local log receiver."""
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
HOST = 'https://onlineweb.zhihuishu.com'
COURSE_HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
SECRET = 'diagnostic-provider-secret-42'
events = []
errors = []

BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmState = JSON.parse(window.name || '{}');
const nativeGMFetch = fetch.bind(window);
globalThis.GM_getValue = (key, fallback) => structuredClone(key in gmState ? gmState[key] : fallback);
globalThis.GM_setValue = (key, value) => { gmState[key] = structuredClone(value); window.name = JSON.stringify(gmState); };
globalThis.GM_xmlhttpRequest = options => {
  nativeGMFetch(options.url.endsWith('/snapshot') ? '/__snapshot' : '/__debug', {method:'POST', body:options.data})
    .then(async response => options.onload({status:response.status, responseText:await response.text()}))
    .catch(() => options.onerror?.());
  return {abort() { options.onabort?.(); }};
};
'''


def fixture(route):
    path = urlsplit(route.request.url).path
    if path == '/__snapshot':
        payload = json.loads(route.request.post_data)
        with urlopen(Request('http://127.0.0.1:8790/zhihuishu-debug/v1/snapshot', data=json.dumps(payload).encode('utf-8'),
                             headers={'Content-Type': 'application/json', 'X-Zhihuishu-Debug': '1'}, method='POST'), timeout=3) as response:
            assert response.status == 204
        return route.fulfill(status=204)
    if path == '/__debug':
        payload = json.loads(route.request.post_data)
        for event in payload['events']:
            event['testFixture'] = True
            events.append(event)
        # The hub cannot reach the collector. Its successor page must resend
        # retained events from the GM outbox rather than losing the last step.
        if urlsplit(route.request.url).hostname == 'onlineweb.zhihuishu.com':
            return route.fulfill(status=503)
        request = Request('http://127.0.0.1:8790/zhihuishu-debug/v1/logs',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json', 'X-Zhihuishu-Debug': '1'}, method='POST')
        with urlopen(request, timeout=3) as response:
            assert response.status == 204
        return route.fulfill(status=204)
    if path.endswith('/course-list'):
        return route.fulfill(json={'code': 200, 'data': {'completeCourseList': [], 'studyCourseList': [
            {'courseId': '1000000000000000001', 'classId': '200001', 'courseName': '诊断课程', 'newFlag': True, 'courseType': 0}]}})
    if path == '/api/new-endpoint':
        return route.fulfill(json={'data': {'newContract': {'token': SECRET}}})
    if path.startswith('/singleCourse/'):
        # Intentionally omit the catalog response to reproduce silent waiting.
        return route.fulfill(body='<h1>诊断课程：没有目录响应</h1>', content_type='text/html; charset=utf-8')
    if path == '/unknown-portal':
        return route.fulfill(body=f'''<h1>课程列表</h1>
            <input type="password" value="{SECRET}"><textarea>{SECRET}</textarea>
            <a href="https://example.com/help?ticket=url-secret">帮助</a>
            {''.join(f'<div class="element-{n}">元素{n}</div>' for n in range(180))}
            <script>
              const xhr = new XMLHttpRequest(); xhr.open('GET', '/run/gateway/t/stu/center/course-list'); xhr.send();
              fetch('/api/new-endpoint');
            </script>''', content_type='text/html; charset=utf-8')
    return route.fulfill(status=404)


with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 960}, accept_downloads=True)
    context.route('**/*', fixture)
    context.add_init_script(script=BRIDGE + SOURCE)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(HOST + '/unknown-portal')
    panel = page.locator('#zhihuishu-mastery-assistant')
    panel.get_by_role('button', name='开始所选课程').wait_for()
    page.wait_for_function("document.querySelector('#zhihuishu-mastery-assistant').shadowRoot.querySelector('select[name=course]').options.length === 1")
    panel.locator('input[name=key]').fill(SECRET)
    panel.locator('input[name=localLogs]').check()
    panel.get_by_role('button', name='保存设置').click()
    before = panel.bounding_box()
    header = panel.locator('header').bounding_box()
    page.mouse.move(header['x'] + 60, header['y'] + 14)
    page.mouse.down()
    page.mouse.move(250, 100, steps=8)
    page.mouse.up()
    after = panel.bounding_box()
    assert abs(before['x'] - after['x']) > 50 and abs(before['y'] - after['y']) > 50
    position = json.loads(page.evaluate('window.name'))['mastery-panel-position']
    page.reload()
    panel.wait_for()
    restored = panel.bounding_box()
    assert abs(restored['x'] - position['x']) < 2 and abs(restored['y'] - position['y']) < 2
    page.set_viewport_size({'width': 520, 'height': 540})
    page.wait_for_timeout(100)
    bounds = panel.bounding_box()
    assert bounds['x'] >= 0 and bounds['y'] >= 0 and bounds['x'] + bounds['width'] <= 520
    page.evaluate("dispatchEvent(new ErrorEvent('error', {message:'fixture token=secret-value'}))")
    panel.locator('.diagnostics summary').click()
    with page.expect_download() as download:
        panel.get_by_role('button', name='导出诊断包').click()
    export = Path(tmp) / 'diagnostic.json'
    download.value.save_as(export)
    raw = export.read_text(encoding='utf-8')
    report = json.loads(raw)
    assert report['snapshot']['totalElements'] > 180
    assert len(report['snapshot']['elements']) > 180
    assert SECRET not in raw and 'url-secret' not in raw and 'secret-value' not in raw
    all_events = [event for doc in report['pages'] for event in doc['events']]
    assert any(event['event'] == 'runtime.error' for event in all_events)
    assert any(event['event'] == 'courses.discovered' for event in all_events)
    assert any(event['event'] == 'network.schema' for event in all_events)
    panel.get_by_role('button', name='开始所选课程').click()
    page.wait_for_url(COURSE_HOST + '/singleCourse/knowledgeStudy/1000000000000000001/200001')
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        page.wait_for_timeout(400)
        if any(event['event'] == 'task.wait' and event['data']['reason'] == 'catalog-response-missing' for event in events):
            break
    else:
        raise AssertionError('Missing catalog must produce an explicit wait reason')
    panel.get_by_role('button', name='结束任务').click()
    page.goto(COURSE_HOST + '/singleCourse/masteryAnalysis/1000000000000000001/200001')
    panel.get_by_role('button', name='开始本课程').click()
    page.wait_for_url(COURSE_HOST + '/singleCourse/knowledgeStudy/1000000000000000001/200001')
    assert not errors, errors
    assert SECRET not in json.dumps(events)
    data = [json.loads(line) for line in (ROOT / '.local' / 'runtime.jsonl').read_text(encoding='utf-8').splitlines()]
    docs = {event['documentId'] for event in events}
    assert any(event.get('testFixture') and event['documentId'] in docs and event['event'] == 'task.wait' for event in data)
    hub_docs = {event['documentId'] for event in events if event['event'] == 'runtime.boot' and event['page'].startswith(HOST)}
    assert hub_docs
    assert all(any(event['documentId'] == doc and event['event'] == 'runtime.boot' for event in data) for doc in hub_docs), 'Pending hub logs were not replayed after navigation'
    snapshots = [json.loads(file.read_text(encoding='utf-8')) for file in (ROOT / '.local' / 'snapshots').glob('*.json')]
    assert any(item['documentId'] in docs and len(item['snapshot']['elements']) > 180 for item in snapshots)
    page.screenshot(path=str(ROOT / '.local' / 'diagnostics-panel-check.png'))
    print(f'Diagnostics passed: unknown-page panel, current course-list XHR contract, masteryAnalysis entry, drag/persistence/resize, {len(report["snapshot"]["elements"])} DOM elements, credential redaction, missing-catalog reason, outbox replay, real loopback log and DOM snapshot delivery.')
    browser.close()
