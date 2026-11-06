from fixture_identity import userscript
"""Verify the real modal, focus, Escape, dismissal persistence, settings/logs and task resume."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SOURCE=userscript(ROOT)
URL='https://studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/17/1/1/1000000000000000001/name?point=1&pointId=31&classId=200001&examPaperId=801'
seed={'mastery-ai':{'key':'fixture-only','model':'deepseek-flash','localLogs':False},
      'mastery-task':{'id':'pause-ui','course':'1000000000000000001','cls':'200001','active':False,'paused':True,
        'phase':'answering','examKey':'801:17','launchedAt':0,'enteredAfter':0,'actor':None,'index':0,'limit':10,'results':[],
        'message':'当前保存结果尚未确认，请查看日志后继续。','queue':[{'point':'31','name':'散列映射','high':98,'rounds':2}]}}
BRIDGE=r'''
globalThis.unsafeWindow=window;
const state=JSON.parse(window.name||'__SEED__');
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_xmlhttpRequest=()=>{throw Error('External requests are disabled in this UI fixture')};
'''
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1280,'height':900})
    context.route('**/*',lambda route:route.fulfill(body='<meta charset="utf-8"><h1>掌握度练习</h1><p>隔离测试：没有账号请求或实际提交。</p>',content_type='text/html; charset=utf-8'))
    context.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed))+SOURCE)
    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(URL)
    dialog=page.get_by_role('alertdialog',name='掌握度任务已暂停')
    dialog.wait_for()
    assert dialog.evaluate('(node)=>node.matches(":modal")')
    assert '当前保存结果尚未确认' in dialog.text_content()
    assert '散列映射' in dialog.text_content() and '第 2 轮' in dialog.text_content()
    assert dialog.get_by_role('button',name='继续自动处理',exact=True).evaluate('(node)=>node===node.getRootNode().activeElement')
    (ROOT/'.local').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'.local/pause-notice-check.png'))
    dialog.screenshot(path=str(ROOT/'.local/pause-notice-dialog.png'))
    page.keyboard.press('Escape')
    page.wait_for_timeout(800)
    assert dialog.count()==0
    assert json.loads(page.evaluate('window.name'))['mastery-task']['paused']
    page.reload();page.wait_for_timeout(900)
    assert dialog.count()==0, 'Dismissed incident must not reopen on reload'
    panel=page.locator('#zhihuishu-mastery-assistant')
    panel.get_by_role('button',name='暂停原因',exact=True).click()
    dialog.get_by_role('button',name='查看设置',exact=True).click()
    assert dialog.count()==0 and panel.locator('.settings').get_attribute('open') is not None
    panel.get_by_role('button',name='暂停原因',exact=True).click()
    dialog.get_by_role('button',name='查看日志',exact=True).click()
    assert dialog.count()==0 and panel.locator('.diagnostics').get_attribute('open') is not None
    panel.get_by_role('button',name='暂停原因',exact=True).click()
    dialog.get_by_role('button',name='稍后处理',exact=True).click()
    assert json.loads(page.evaluate('window.name'))['mastery-task']['paused']
    panel.get_by_role('button',name='暂停原因',exact=True).click()
    dialog.get_by_role('button',name='继续自动处理',exact=True).click()
    page.wait_for_function("JSON.parse(window.name)['mastery-task'].active")
    assert dialog.count()==0
    assert json.loads(page.evaluate('window.name'))['mastery-task']['queue'][0]['rounds']==2
    panel.get_by_role('button',name='暂停',exact=True).click()
    dialog.wait_for()
    assert '任务已暂停' in dialog.text_content(), 'A new incident must display a fresh modal'
    page.set_viewport_size({'width':390,'height':650})
    bounds=dialog.bounding_box()
    assert bounds['x']>=0 and bounds['x']+bounds['width']<=391
    assert not errors,errors
    print('Pause modal passed: visible reason/progress, native focus trap, Escape, dismissal persistence, reopen, settings/logs, resume, new incident and narrow screen.')
    browser.close()
