"""Exercise deferred answers and update settings through the panel in isolated Edge."""
import json
import time
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import TimeoutError, sync_playwright

from check_blank_prefetch import BRIDGE, ROOT, URL

SOURCE = (ROOT / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
GITHUB = 'https://api.github.com/repos/17hwliao/zhihuishu/releases/latest'
RELEASES = 'https://github.com/17hwliao/zhihuishu/releases'
DOWNLOAD = f'{RELEASES}/download/'
QUESTIONS = [{'id': str(50001 + i), 'content': f'<p>空位题 {i + 1}</p>', 'questionType': 3,
              'questionTypeName': '填空题', 'optionVos': []} for i in range(2)]
HTML = r'''<meta charset="utf-8"><div class="questionContent"></div>
<button class="pre-topic pre-t">上一题</button><button class="next-topic next-t">下一题</button>
<button class="reviewDone">交卷</button><script>
const questions=__QUESTIONS__,root=document.querySelector('.questionContent');
let index=GM_getValue('fixture-index',0);
const owner={$route:{params:{examTestId:'17',recruitId:'101'},query:{point:'1',pointId:'31',classId:'202',examPaperId:'801'}},
 $options:{methods:{saveAnswer(){}}},saveAnswer(){
  const question=this.currentQues.questionId,answer=this.userAnswer;
  return fetch('/answer/saveAnswer',{method:'POST',body:JSON.stringify({question,answer})}).then(r=>r.json()).then(data=>{
    if(data.data===true)GM_setValue('fixture-saved',{...GM_getValue('fixture-saved',{}),[question]:answer});
  });
 }};
root.__vue__={$parent:owner};
const next=document.querySelector('.next-topic'),prev=document.querySelector('.pre-topic');
function render(){
 GM_setValue('fixture-index',index);
 const q=questions[index];owner.currentQues={questionId:q.id};owner.reviewTopicData=q;
 root.innerHTML='<div class="centent-pre"><pre class="preStyle">'+q.content.replace(/<[^>]+>/g,'')+'</pre></div><input type="text" class="el-input__inner">';
 const input=root.querySelector('input');input.value=owner.userAnswer=GM_getValue('fixture-saved',{})[q.id]||'';
 input.onkeyup=()=>{owner.userAnswer=input.value};
 prev.disabled=index===0;next.disabled=index===1;
 fetch('/question/getExamQuestionInfo?i='+index);
}
next.onclick=()=>{index++;render()};prev.onclick=()=>{index--;render()};
document.querySelector('.reviewDone').onclick=()=>fetch('/__submit',{method:'POST'});
render();fetch('/getExamSheetInfo');
</script>'''
GM = BRIDGE.split('const nativeFetch=')[0] + r'''
const nativeFetch=fetch.bind(window);
async function requestAI(body){
 const response=await nativeFetch('/__ai?i='+GM_getValue('fixture-index',0),{method:'POST',body});
 return new Response(await response.text(),{status:response.status});
}
globalThis.fetch=(url,opts)=>String(url).startsWith('https://api.deepseek.com/')?requestAI(opts.body):nativeFetch(url,opts);
globalThis.GM_xmlhttpRequest=o=>{
 if((o.url!==__GITHUB__&&!o.url.startsWith(__RELEASES__))||o.method!=='GET'||!o.anonymous||o.headers.Authorization||o.data)throw Error('Unexpected request');
 nativeFetch('/__github?url='+encodeURIComponent(o.url)).then(async r=>o.onload({status:r.status,responseText:await r.text(),
    finalUrl:r.headers.get('fixture-final-url')||o.url})).catch(o.onerror);
 return {abort(){}};
};
'''


def context_for(browser, seed, fixture):
    context = browser.new_context()
    context.route('**/*', fixture)
    context.add_init_script(script=GM.replace('__SEED__', json.dumps(seed)).replace('__GITHUB__', json.dumps(GITHUB))
                            .replace('__RELEASES__', json.dumps(RELEASES)) + SOURCE)
    return context


def check_defer(browser, automatic):
    saves, submits, calls = [], [], []
    task = {'id': 'defer-test', 'course': '101', 'cls': '202', 'active': True, 'paused': False,
            'phase': 'exam', 'actor': None, 'enteredAfter': 0, 'launchedAt': 0, 'expires': int(time.time() * 1000) + 60000,
            'limit': 10, 'index': 0, 'results': [], 'queue': [{'point': '31', 'name': '暂缓题目', 'high': 80, 'rounds': 2}]}
    seed = {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'localLogs': False},
            'mastery-task': task, 'mastery-defer-unanswered': automatic}

    def fixture(route):
        url = urlsplit(route.request.url)
        index = int(parse_qs(url.query).get('i', [0])[0])
        if url.path.endswith('/getExamQuestionInfo'):
            return route.fulfill(json={'data': QUESTIONS[index]})
        if url.path.endswith('/getExamSheetInfo'):
            return route.fulfill(json={'data': {'questionCount': 2}})
        if url.path.endswith('/saveAnswer'):
            saves.append(json.loads(route.request.post_data))
            return route.fulfill(json={'code': 200, 'data': True})
        if url.path == '/__submit':
            submits.append(True)
            return route.fulfill(json={'ok': True})
        if url.path == '/__ai':
            calls.append(index)
            return route.fulfill(json={'choices': [{'message': {'content': '["第二空"]' if index else '[]'}}]})
        return route.fulfill(body=HTML.replace('__QUESTIONS__', json.dumps(QUESTIONS)), content_type='text/html; charset=utf-8')

    with context_for(browser, seed, fixture) as context:
        page = context.new_page()
        page.goto(URL)
        if not automatic:
            page.get_by_role('alertdialog').get_by_role('button', name='跳过当前题').click(timeout=15000)
        try:
            page.wait_for_function("JSON.parse(window.name)['mastery-task']?.message?.includes('本卷已暂缓 1 道题')", timeout=15000)
        except TimeoutError:
            state = json.loads(page.evaluate('window.name'))
            events = [(item['event'], item['data']) for key, log in state.items() if key.startswith('mastery-panel-log-v2:') for item in log]
            raise AssertionError((state['mastery-task'], events[-18:], calls, saves)) from None
        state = json.loads(page.evaluate('window.name'))
        task = state['mastery-task']
        assert task['paused'] and task['answered'] == ['50002'] and task['queue'][0]['rounds'] == 2
        assert saves == [{'question': '50002', 'answer': '第二空'}] and not submits, (saves, submits)
        calls_before = list(calls)
        page.evaluate('''question=>{
            const memory=GM_getValue('mastery-current-point-v1');
            memory.reviews={'previous':[ {...question,optionDtos:[{id:'1',content:'第一空',isCorrect:1}]} ]};
            GM_setValue('mastery-current-point-v1',memory);
        }''', QUESTIONS[0])
        page.get_by_role('alertdialog').get_by_role('button', name='继续自动处理').click()
        page.wait_for_function("JSON.parse(window.name)['mastery-task']?.phase==='submitting'", timeout=15000)
        page.wait_for_function("performance.getEntriesByName(location.origin+'/__submit').length===1")
        assert saves[-1] == {'question': '50001', 'answer': '第一空'} and len(saves) == 2 and len(submits) == 1
        assert calls == calls_before, calls
    print(f'Defer passed: {"automatic" if automatic else "manual"}; same paper recovered before submit', flush=True)


def check_release(browser):
    requests = []
    version = 'v2.5.7'
    valid_asset = True
    rate_limited = False

    def fixture(route):
        request = urlsplit(route.request.url)
        if request.path == '/__github':
            target = parse_qs(request.query)['url'][0]
            requests.append(target)
            asset = f'{DOWNLOAD}{version}/zhihuishu-mastery.user.js' if valid_asset else 'https://example.invalid/zhihuishu-mastery.user.js'
            if target == f'{RELEASES}/latest':
                return route.fulfill(body='<h1>Release</h1>', headers={'fixture-final-url': f'{RELEASES}/tag/{version}'})
            if target == f'{RELEASES}/expanded_assets/{version}':
                return route.fulfill(body=f'<a href="{urlsplit(asset).path}">Download</a>')
            if rate_limited:
                return route.fulfill(status=403)
            return route.fulfill(json={'tag_name': version, 'draft': False, 'prerelease': False, 'assets': [
                {'name': 'zhihuishu-mastery.user.js', 'state': 'uploaded', 'browser_download_url': asset}]})
        return route.fulfill(body='<meta charset="utf-8"><h1>答题页</h1>', content_type='text/html')

    with context_for(browser, {'mastery-ai': {'localLogs': False}}, fixture) as context:
        page = context.new_page()
        page.goto(URL)
        panel = page.locator('#zhihuishu-mastery-assistant')
        panel.get_by_text('跳题与脚本更新', exact=True).click()
        button = panel.get_by_role('button', name='检查 GitHub 更新', exact=True)
        status = panel.locator('.release-status')
        link = panel.locator('.release-install')
        assert not requests and link.is_hidden()
        button.click()
        status.get_by_text('比 GitHub 稳定版 v2.5.7 更新', exact=False).wait_for()
        assert link.is_hidden() and len(requests) == 1
        version = 'v2.5.100'
        button.click()
        status.get_by_text('可更新至 v2.5.100', exact=True).wait_for()
        assert link.get_attribute('href') == f'{DOWNLOAD}{version}/zhihuishu-mastery.user.js'
        valid_asset = False
        button.click()
        status.get_by_text('GitHub 稳定版缺少可安装的脚本附件', exact=True).wait_for()
        assert link.is_hidden()
        page.evaluate("GM_setValue('mastery-release-attempt',0)")
        valid_asset = True
        panel.locator('[name=autoRelease]').check()
        status.get_by_text('可更新至 v2.5.100', exact=True).wait_for()
        page.reload()
        panel.get_by_text('跳题与脚本更新', exact=True).click()
        assert panel.locator('[name=autoRelease]').is_checked() and len(requests) == 4
        rate_limited = True
        button.click()
        status.get_by_text('可更新至 v2.5.100', exact=True).wait_for()
        assert link.get_attribute('href') == f'{DOWNLOAD}{version}/zhihuishu-mastery.user.js'
        assert requests[-3:] == [GITHUB, f'{RELEASES}/latest', f'{RELEASES}/expanded_assets/{version}']
    print('GitHub check passed: older/newer, invalid asset, opt-in cooldown and API rate-limit fallback', flush=True)


if __name__ == '__main__':
    with sync_playwright() as p:
        with p.chromium.launch(channel='msedge', headless=True) as browser:
            check_defer(browser, automatic=False)
            check_defer(browser, automatic=True)
            check_release(browser)
