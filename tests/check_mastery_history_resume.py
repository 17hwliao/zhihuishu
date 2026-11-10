"""Replay resume on the mastery history page without a real account or paper."""
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://ai-smart-course-student-pro.zhihuishu.com/masteryHistory/101/202/32?isFreeExam=0'
BRIDGE = '''
globalThis.unsafeWindow=window;
const state=JSON.parse(window.name||__SEED__);
window.name=JSON.stringify(state);
globalThis.GM_getValue=(key,otherwise)=>structuredClone(key in state?state[key]:otherwise);
globalThis.GM_setValue=(key,value)=>{state[key]=structuredClone(value);window.name=JSON.stringify(state)};
globalThis.GM_xmlhttpRequest=()=>{throw Error('No extension requests expected')};
'''
MAXIMUM = '/mastery-statistics/get-node-master-max'
LEGACY = '/stu/exam/questions-paper'


def run(browser, source, case, baseline):
    loads, entries, errors = [], [], []
    queue = [{'point': '31', 'name': '前一知识点', 'high': 100, 'rounds': 1},
             {'point': '32', 'name': '当前知识点', 'high': 0, 'rounds': 0}]
    task = {'id': 'history-resume', 'course': '101', 'cls': '202', 'active': False, 'paused': True,
            'phase': 'learn', 'actor': None, 'index': 1, 'limit': 10, 'expires': int(time.time() * 1000) + 60000,
            'queue': queue, 'results': [queue[0]], 'message': '自动模式已关闭'}
    seed = {'mastery-task': task, 'mastery-ai': {'key': 'fixture-only', 'localLogs': False}}

    def fixture(route):
        path = urlsplit(route.request.url).path
        if path == MAXIMUM:
            value = {'null': None, 'empty': '', 'preserve': '100', 'reload': 84, 'invalid': 'NaN'}[case]
            return route.fulfill(json={'code': 200, 'data': {'masteryMax': value}})
        if path == LEGACY:
            return route.fulfill(json={'code': 200, 'data': {'questionNum': 6, 'highMasteryScore': None}})
        if path == '/__entry':
            entries.append(True)
            return route.fulfill(status=204)
        if path.startswith('/masteryHistory/'):
            loads.append(path)
            script = '' if case == 'reload' and len(loads) == 1 else f'fetch("{MAXIMUM}");'
            if case == 'preserve':
                script += f'setTimeout(()=>fetch("{LEGACY}"),90);'
            html = '<button class="improve-btn" onclick="fetch(\'/__entry\')">去提升</button><script>' + script + '</script>'
            return route.fulfill(body=html, content_type='text/html; charset=utf-8')
        return route.fulfill(status=404)

    with browser.new_context() as context:
        context.route('**/*', fixture)
        context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(json.dumps(seed))) + source)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL)
        if case != 'reload':
            page.wait_for_function('''expected=>Object.entries(JSON.parse(window.name)).some(([key,log])=>
                key.startsWith('mastery-panel-log-v2:')&&log.some(e=>e.event==='mastery.captured'&&e.data.source===expected))''',
                arg='questions-paper' if case == 'preserve' and not baseline else 'mastery-history')
            if case == 'preserve' and baseline:
                page.wait_for_function("performance.getEntriesByName(location.origin+'/stu/exam/questions-paper').length===1")
        page.get_by_role('alertdialog').get_by_role('button', name='继续自动处理').click()
        if baseline or case == 'invalid':
            reason = 'mastery-response-missing' if baseline else 'mastery-response-invalid'
            page.wait_for_function('''reason=>Object.entries(JSON.parse(window.name)).some(([key,log])=>
                key.startsWith('mastery-panel-log-v2:')&&log.some(e=>e.event==='task.wait'&&e.data.reason===reason))''', arg=reason)
            assert not entries
        elif case == 'preserve':
            page.wait_for_function("JSON.parse(window.name)['mastery-task']?.results?.length===2")
            task = json.loads(page.evaluate('window.name'))['mastery-task']
            assert task['results'][-1]['high'] == 100 and task['results'][-1]['rounds'] == 0 and not entries
        else:
            page.wait_for_function("performance.getEntriesByName(location.origin+'/__entry').length===1")
            task = json.loads(page.evaluate('window.name'))['mastery-task']
            assert task['id'] == 'history-resume' and task['index'] == 1 and task['queue'][1]['rounds'] == 1
            assert task['queue'][1]['high'] == (84 if case == 'reload' else 0) and len(entries) == 1
        assert len(loads) == (2 if not baseline and case in ('reload', 'invalid') else 1), loads
        assert not errors, errors
    print(f'{"Baseline reproduced" if baseline else "History resume passed"}: {case}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    source = (args.baseline or ROOT / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        with p.chromium.launch(channel='msedge', headless=True) as browser:
            for case in ('null', 'empty', 'preserve', 'reload') + (() if args.baseline else ('invalid',)):
                run(browser, source, case, bool(args.baseline))
