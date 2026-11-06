"""Offline boundary check: leave formal exams and unrelated response bodies alone."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SOURCE = (Path(__file__).resolve().parents[1] / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
BRIDGE = r'''
globalThis.unsafeWindow=window;
window.writes=[];window.requests=[];window.bodyReads=[];window.clicks=[];
globalThis.GM_getValue=(k,d)=>d;
globalThis.GM_setValue=(k,v)=>window.writes.push(k);
globalThis.GM_deleteValue=k=>window.writes.push(k);
globalThis.GM_listValues=()=>[];
globalThis.GM_xmlhttpRequest=o=>{window.requests.push(o.url);throw Error('Unexpected extension request')};
const nativeFetch=fetch.bind(window);
globalThis.fetch=(u,...args)=>{window.requests.push(String(u));return nativeFetch(u,...args)};
window.beforeFetch=fetch;window.beforeOpen=window.open;
const originalClone=Response.prototype.clone;
Response.prototype.clone=function(){window.bodyReads.push(this.url);return originalClone.call(this)};
document.addEventListener('click',e=>window.clicks.push(e.target.className),true);
'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    for case, url in [
        ('formal-exam','https://studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/17/1/1/101/name?point=0&pointId=31&classId=202&examPaperId=801'),
        ('unrelated-course-feature','https://ai-smart-course-student-pro.zhihuishu.com/singleCourse/taskAndExam/101/202'),
    ]:
        ctx=browser.new_context();errors=[]
        def fixture(route):
            if any(path in route.request.url for path in ('/unrelated-feature','/exam/user/submit','/answer/saveAnswer')):
                return route.fulfill(json={'data':{'privateFeature':'must-not-be-read'}})
            return route.fulfill(body='<meta charset="utf-8"><body><video></video><button class="reviewDone">正式交卷</button><button class="improve-btn">其他操作</button><script>fetch("/unrelated-feature");fetch("/exam/user/submit");fetch("/answer/saveAnswer")</script>',content_type='text/html')
        ctx.route('**/*',fixture)
        ctx.add_init_script(script=BRIDGE+SOURCE)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.wait_for_timeout(1300)
        state=page.evaluate('({writes,requests,bodyReads,clicks,sameFetch:fetch===beforeFetch,sameOpen:open===beforeOpen})')
        assert not errors and not state['clicks'] and not state['bodyReads'], (errors,state)
        assert state['requests']==['/unrelated-feature','/exam/user/submit','/answer/saveAnswer'],state
        assert 'mastery-task' not in state['writes'],state
        if case=='formal-exam':
            assert state['writes']==[] and state['sameFetch'] and state['sameOpen'],state
            assert page.locator('#zhihuishu-mastery-assistant').count()==0
        print('Mastery scope passed:',case,flush=True)
        ctx.close()
    browser.close()
