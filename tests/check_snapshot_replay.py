from fixture_identity import userscript
"""Replay knowledge cards from a user-exported DOM snapshot without account/API access."""
import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('report', type=Path)
parser.add_argument('--expect-pending', type=int)
parser.add_argument('--expect-total', type=int)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = userscript(ROOT)
report = json.loads(args.report.read_text(encoding='utf-8-sig'))
snapshot = report['snapshot']
nodes = snapshot['elements']
children = defaultdict(list)
for i, node in enumerate(nodes):
    children[node.get('parent')].append(i)
roots = [i for i, node in enumerate(nodes) if re.fullmatch(r'knowledgeId-\d+', node.get('id', '')) and 'item-content' in node.get('classes', '').split()]


def descendants(index):
    yield index
    for child in children[index]:
        yield from descendants(child)


def render(index):
    node = nodes[index]
    tag = node['tag']
    if tag in ('script', 'iframe', 'style', 'input', 'textarea'):
        return ''
    attributes = {k: node[k] for k in ('id',) if node.get(k)}
    attributes['class'] = node.get('classes', '')
    if node.get('id', '').startswith('knowledgeId-'):
        attributes['style'] = 'display:inline-block;width:280px;min-height:180px;vertical-align:top'
    attrs = ''.join(f' {k}="{html.escape(str(v), quote=True)}"' for k, v in attributes.items())
    text = html.escape(node.get('text', ''))
    return f'<{tag}{attrs}>' + text + ''.join(render(child) for child in children[index]) + f'</{tag}>'


expected = {}
for index in roots:
    branch = list(descendants(index))
    gauge = next((i for i in branch if 'item-top-right' in nodes[i].get('classes', '').split()), None)
    if gauge is None:
        continue
    text = ''.join(nodes[i].get('text', '') for i in descendants(gauge))
    match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    assert match, 'Snapshot mastery indicator has no readable percentage'
    if float(match[1]) < 100:
        expected[nodes[index]['id'].split('-', 1)[1]] = float(match[1])
if args.expect_total is not None:
    assert len(roots) == args.expect_total
if args.expect_pending is not None:
    assert len(expected) == args.expect_pending
assert expected
route = snapshot['route']
course, cls = route['course'], route['cls']
home = snapshot['page']
old_course = '9000000000000000002'
seed = {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'limit': 10, 'localLogs': False},
        'mastery-task': {'id': 'old-paused-task', 'course': old_course, 'cls': '90002', 'active': False, 'paused': True,
                         'phase': 'catalog', 'queue': None, 'results': [], 'index': 0, 'limit': 10, 'actor': None}}
BRIDGE = r'''
globalThis.unsafeWindow = window;
const gmState = JSON.parse(window.name || '__SEED__');
globalThis.GM_getValue = (key, fallback) => structuredClone(key in gmState ? gmState[key] : fallback);
globalThis.GM_setValue = (key, value) => { gmState[key] = structuredClone(value); window.name = JSON.stringify(gmState); };
globalThis.GM_xmlhttpRequest = () => { throw Error('No external request is allowed in snapshot replay'); };
'''.replace('__SEED__', json.dumps(seed))
content = '<meta charset="utf-8"><h1>真实知识点卡片结构回放（不连接账号）</h1>' + ''.join(render(index) for index in roots)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    for mode in ('native', 'fallback', 'broken-api'):
        errors = []
        context = browser.new_context(viewport={'width': 1280, 'height': 900})

        def fixture(intercept):
            path = urlsplit(intercept.request.url).path
            if path.endswith('/list-knowledge-theme'):
                # A missing API field must be recoverable from this exact real card.
                point = next(iter(expected))
                return intercept.fulfill(json={'data': {'courseThemeList': [{'subThemeList': [{'knowledgeList': [{'knowledgeId': point}]}]}]}})
            if path.startswith('/singleCourse/'):
                script = ''
                if mode != 'fallback':
                    prefix = f'https://ai-smart-course-student-pro.zhihuishu.com/learnPage/{course}/'
                    suffix = f'/{cls}?catalogActiveTab=personal'
                    script = '<script>document.querySelectorAll(".item-content[id^=knowledgeId-]").forEach(card=>card.onclick=()=>location.assign(' + json.dumps(prefix) + '+card.id.slice(12)+' + json.dumps(suffix) + '));</script>'
                if mode == 'broken-api':
                    script += '<script>fetch("/stu/knowledge-study/list-knowledge-theme");</script>'
                return intercept.fulfill(body=content + script, content_type='text/html; charset=utf-8')
            return intercept.fulfill(body='<meta charset="utf-8"><h1>目标知识点；本测试在此暂停，不生成试卷</h1>', content_type='text/html; charset=utf-8')

        context.route('**/*', fixture)
        context.add_init_script(script=BRIDGE + SCRIPT)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(home)
        panel = page.locator('#zhihuishu-mastery-assistant')
        panel.get_by_role('button', name='开始本课程').wait_for()
        assert panel.get_by_role('button', name='开始本课程').is_enabled(), 'A paused different course must not block this course'
        panel.locator('.catalog-preview summary').click()
        page.wait_for_function("document.querySelector('#zhihuishu-mastery-assistant').shadowRoot.querySelector('.plan-text').textContent.includes('未满 " + str(len(expected)) + "')")
        if mode == 'native':
            page.screenshot(path=str(ROOT / '.local' / 'real-card-plan-replay.png'))
        panel.get_by_role('button', name='开始本课程').click()
        page.wait_for_url('**/learnPage/**')
        panel.wait_for()
        state = json.loads(page.evaluate('window.name'))
        task = state['mastery-task']
        assert task['course'] == course and task['cls'] == cls
        assert len(task['queue']) == len(expected)
        assert {point['point'] for point in task['queue']} == set(expected), 'Missing or unwanted knowledge points in queue'
        assert all(point['high'] == expected[point['point']] for point in task['queue'])
        assert task['catalogUnresolved'] == []
        assert state['mastery-task-history'][-1]['course'] == old_course
        assert task['catalogSource'] == ('api+dom' if mode == 'broken-api' else 'dom')
        assert f'/{task["queue"][0]["point"]}/' in page.url
        entries = [entry for key, value in state.items() if key.startswith('mastery-panel-log-v2:') for entry in value]
        assert any(entry['event'] == 'navigation.card-click' for entry in entries)
        if mode == 'fallback':
            assert any(entry['event'] == 'navigation.card-fallback' for entry in entries)
        assert not errors, errors
        print(f'{mode}: all {len(expected)} pending points from {len(roots)} real cards queued exactly; stale course archived; next page reached.')
        context.close()
    browser.close()
