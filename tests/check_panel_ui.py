from fixture_identity import userscript
"""Check the local panel's layout, grip dragging, collapse and settings drafts."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = userscript(ROOT)
SEED = {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'localLogs': False},
        'mastery-auto': {'enabled': False},
        'mastery-task': {'id': 'ui-only', 'course': '1000000000000000001', 'cls': '200001',
                        'paused': True, 'active': False, 'phase': 'learn', 'index': 3, 'limit': 10,
                        'message': '任务已暂停，当前进度保留', 'results': [],
                        'queue': [{'point': str(i+30), 'name': 'Java 知识点', 'high': 98, 'rounds': 2} for i in range(8)]}}
BRIDGE = '''globalThis.unsafeWindow=window;
const state=__SEED__;
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_xmlhttpRequest=()=>{throw Error('UI fixture cannot call APIs')};'''


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 920})
        context.route('**/*', lambda r: r.fulfill(body='<meta charset="utf-8"><style>body{background:#eef0f4}</style>', content_type='text/html; charset=utf-8'))
        context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(SEED))+SOURCE)
        page = context.new_page(); errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('https://ai-smart-course-student-pro.zhihuishu.com/learnPage/1000000000000000001/33/200001')
        page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
        panel = page.locator('#zhihuishu-mastery-assistant')
        (ROOT / '.local').mkdir(exist_ok=True)
        panel.screenshot(path=str(ROOT / '.local/ui-macos-panel.png'))
        panel.locator('.settings').evaluate('(n)=>n.open=true')
        panel.locator('input[name=model]').fill('draft-model')
        panel.get_by_role('button', name='收起', exact=True).click()
        assert panel.locator('.content').is_hidden()
        assert panel.locator('.collapse').get_attribute('aria-expanded') == 'false'
        panel.get_by_role('button', name='展开', exact=True).click()
        assert panel.locator('input[name=model]').input_value() == 'draft-model'
        panel.locator('.settings').evaluate('(n)=>n.open=false')
        before = panel.bounding_box(); grip = panel.locator('.drag-grip').bounding_box()
        page.mouse.move(grip['x']+12, grip['y']+3); page.mouse.down()
        # The extra settings section raises the bottom-anchored panel.
        page.mouse.move(300, 35, steps=8); page.mouse.up()
        after = panel.bounding_box()
        assert abs(after['x']-before['x']) > 100 and abs(after['y']-before['y']) > 100
        assert 'mastery-panel-position' in json.loads(page.evaluate('window.name'))
        panel.locator('header').focus(); page.keyboard.press('ArrowRight')
        assert panel.bounding_box()['x'] == after['x']+10
        page.set_viewport_size({'width': 390, 'height': 650})
        page.wait_for_function("""() => {
            const r=document.querySelector('#zhihuishu-mastery-assistant').getBoundingClientRect();
            return r.x>=0 && r.right<=innerWidth && r.y>=0 && r.bottom<=innerHeight;
        }""")
        bounds = panel.bounding_box()
        assert bounds['x'] >= 0 and bounds['x']+bounds['width'] <= 391
        assert bounds['y'] >= 0 and bounds['y']+bounds['height'] <= 651
        panel.locator('.settings').evaluate('(n)=>n.open=true')
        assert panel.locator('.content').evaluate('(n)=>n.scrollWidth<=n.clientWidth')
        assert panel.locator('input[name=guessFallback]').is_checked()
        panel.screenshot(path=str(ROOT / '.local/ui-macos-narrow.png'))
        assert not errors, errors
        print('Panel UI passed: grip dragging, persisted position, keyboard move, collapse, preserved drafts and narrow-screen layout.')
        browser.close()
