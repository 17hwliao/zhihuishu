"""Review regressions against an optional frozen userscript; all network traffic is mocked."""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright
from fixture_identity import IDENTITY

ROOT = Path(__file__).resolve().parents[1]
COURSE, CLS, POINT = '1000000000000000001', '200001', '31'
URL = f'https://studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/17/1/1/{COURSE}/name?point=1&pointId=31&classId={CLS}&examPaperId=801'
MEMORY, OUTBOX = 'mastery-current-point-v1', 'mastery-log-outbox-v2'
ACCOUNT = hashlib.sha256(b'zhihuishu-uuid:fixture-account-1').hexdigest()
OPTIONS = ['["错误项",[]]', '["正确项",[]]']


def definition(index):
    return {'content': f'<p>Q{index+1}</p>', 'type': [None, '单选题'], 'options': sorted(OPTIONS),
            'optionVersions': sorted(['<p>错误项</p>', '<p>正确项</p>']), 'blanks': [], 'files': []}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def initial(case):
    task = {'id': 'review-run', 'course': COURSE, 'cls': CLS, 'account': ACCOUNT, 'memoryVersion': 1,
            'active': True, 'paused': False, 'phase': 'answering', 'actor': None, 'lease': 0,
            'enteredAfter': 0, 'launchedAt': 0, 'expires': int(time.time()*1000)+60000,
            'paperInstance': 'current-paper', 'examKey': '801:17', 'examUrl': URL, 'answered': [],
            'queue': [{'point': POINT, 'name': 'Review 隔离回归', 'high': 98, 'rounds': 2}],
            'limit': 10, 'index': 0, 'results': []}
    state = {'mastery-task': task, 'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'localLogs': True},
             'mastery-auto': {'enabled': True, 'status': 'running', 'taskId': task['id']}}
    if case.startswith('full-draft'):
        memory = {'schema': 1, 'scope': {'task': task['id'], 'account': ACCOUNT, 'course': COURSE, 'cls': CLS, 'point': POINT},
                  'questions': {}, 'papers': {}, 'rounds': []}
        records = {}
        for index in range(2):
            desc = definition(index); fp = fingerprint(desc); qid = str(50001+index)
            records[qid] = {'id': qid, 'fingerprint': fp, 'definition': desc, 'answers': [OPTIONS[1]], 'kind': 'choice',
                            'source': 'ai', 'saved': True, 'optionIds': {'10': OPTIONS[0], '11': OPTIONS[1]}}
            memory['questions'][fp] = {'definition': desc, 'answers': {}}
            if index == 0 and case == 'full-draft-known-failure':
                memory['questions'][fp]['answers'][json.dumps([OPTIONS[1]], ensure_ascii=False, separators=(',', ':'))] = {
                    'values': [OPTIONS[1]], 'evidence': {'old': {'submission': 'old', 'round': 1, 'verdict': 'wrong', 'feedback': 'verified while paused'}}}
        memory['papers']['current-paper'] = {'id': 'current-paper', 'key': '801:17', 'round': 2, 'status': 'draft',
                                             'questions': records, 'feedback': {}, 'results': []}
        state[MEMORY] = memory
        task['answered'] = list(records)
    return state


BRIDGE = r'''
globalThis.unsafeWindow=window;
const state=__SEED__;
const caseName=__CASE__;
window.name=JSON.stringify(state);
globalThis.GM_listValues=()=>Object.keys(state);
globalThis.GM_deleteValue=k=>{delete state[k];window.name=JSON.stringify(state)};
globalThis.GM_setValue=(k,v)=>{if(caseName==='log-write'&&k==='mastery-log-outbox-v2')throw Error('fixture optional log write failure');state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_getValue=(k,d)=>{
 if((caseName==='log-storage'||caseName==='log-storage-recovery'&&!window.reviewStorageRecovered) && k==='mastery-log-outbox-v2')throw Error('fixture: optional log storage unavailable');
 const result=structuredClone(k in state?state[k]:d);
 if(['cancel-before-seal','feedback-before-seal','replace-before-seal'].includes(caseName) && k==='mastery-current-point-v1'
     && state['mastery-task'].answered?.length===1 && !window.reviewInterleaved){
  window.reviewInterleaved=true;
  queueMicrotask(()=>{
   if(caseName==='cancel-before-seal'){
    state['mastery-task']={...state['mastery-task'],active:false,paused:false,cancelled:true};
    state['mastery-auto']={enabled:false,status:'off'};delete state['mastery-current-point-v1'];
   }else if(caseName==='feedback-before-seal'){
    const memory=state['mastery-current-point-v1']; const fp=Object.keys(memory.questions)[0];
    memory.questions[fp].answers['["older-failed"]']={values:['older-failed'],evidence:{old:{submission:'old',round:1,verdict:'wrong',feedback:'late verified feedback'}}};
   }else{
    const root=document.querySelector('.questionContent'), replacement=root.cloneNode(true);
    replacement.querySelectorAll('li').forEach(n=>n.classList.remove('active'));
    replacement.querySelector('li').classList.add('active');root.replaceWith(replacement);
   }
   window.name=JSON.stringify(state);
  });
 }
 return result;
};
const nativeFetch=fetch.bind(window);
globalThis.fetch=(url,options)=>{
 if(String(url).startsWith('https://api.deepseek.com/')){
  if(caseName==='log-storage-recovery')window.reviewStorageRecovered=true;
  if(caseName==='late-failure' && !window.reviewLateFeedback){
   window.reviewLateFeedback=true;
   // A second page's verified late result updates shared GM memory while this request is pending.
   const memory=state['mastery-current-point-v1'],fp=Object.keys(memory.papers['current-paper'].aiRequests)[0];
   memory.questions[fp]={definition:__DEFINITION__,answers:{}};
   memory.questions[fp].answers[JSON.stringify(['["正确项",[]]'])]={values:['["正确项",[]]'],evidence:{old:{submission:'old',round:1,verdict:'wrong',feedback:'verified failure arrived during model request'}}};
   state['mastery-current-point-v1']=memory;window.name=JSON.stringify(state);
  }
  return nativeFetch('/__ai',options).then(async r=>new Response(await r.text(),{status:r.status}));
 }
 return nativeFetch(url,options);
};
globalThis.GM_xmlhttpRequest=o=>{nativeFetch('/__logs',{method:'POST',body:o.data}).then(()=>o.onerror?.());return {abort(){}}};
Math.random=()=>0;
'''
HTML = r'''<meta charset="utf-8"><div class="questionContent"></div><button class="next-topic next-t">下一题</button>
<button class="reviewDone">交卷</button><script>
let index=0;
function render(){
 const root=document.querySelector('.questionContent');
 root.innerHTML='<div class="centent-pre"><pre class="preStyle">Q'+(index+1)+(index&&__CHANGED__?' revised':'')+'</pre></div>';
 root.innerHTML+='<ul class="radio-view"><li class="clearfix"><pre class="preStyle">错误项</pre></li><li class="clearfix"><pre class="preStyle">正确项</pre></li></ul>';
 if(__SELECTED__ && index===0)root.querySelectorAll('li')[1].classList.add('active');
 root.querySelectorAll('li').forEach(n=>n.onclick=()=>{
  root.querySelectorAll('li').forEach(el=>el.classList.remove('active'));n.classList.add('active');fetch('/answer/saveAnswer',{method:'POST'});
 });
 document.querySelector('.next-topic').hidden=__COUNT__===1;
 document.querySelector('.next-topic').disabled=!!index;
 fetch('/question/getExamQuestionInfo?index='+index);
}
document.querySelector('.next-topic').onclick=()=>{index=1;render()};
document.querySelector('.reviewDone').onclick=()=>fetch('/__submit',{method:'POST'});
render();fetch('/getExamSheetInfo');
</script>'''


def run(browser, source, case):
    calls, captures, saves, commits = [], [], [], []
    count = 2 if case.startswith('full-draft') else 1
    html = HTML.replace('__COUNT__', str(count)).replace('__CHANGED__', str(case == 'full-draft-changed').lower())
    html = html.replace('__SELECTED__', str(case in ('full-draft-changed', 'full-draft-known-failure')).lower())

    def fixture(route):
        path = urlsplit(route.request.url).path
        if path == '/__ai':
            calls.append(json.loads(json.loads(route.request.post_data)['messages'][1]['content']))
            return route.fulfill(json={'choices': [{'message': {'content': '["B"]'}}]})
        if path.endswith('/getExamQuestionInfo'):
            index = int(parse_qs(urlsplit(route.request.url).query)['index'][0]); captures.append(index)
            content = f'<p>Q{index+1}'+(' revised' if index and case == 'full-draft-changed' else '')+'</p>'
            return route.fulfill(json={'data': {'id': str(50001+index), 'content': content, 'questionTypeName': '单选题',
                'optionVos': [{'id': '10', 'content': '<p>错误项</p>'}, {'id': '11', 'content': '<p>正确项</p>'}]}})
        if path.endswith('/getExamSheetInfo'):
            return route.fulfill(json={'data': {'questionCount': count}})
        if path.endswith('/saveAnswer'):
            saves.append(1); return route.fulfill(json={'code': 200, 'data': True})
        if path == '/__submit':
            commits.append(1); return route.fulfill(json={'ok': True})
        if path == '/__logs':
            return route.fulfill(status=507)
        return route.fulfill(body=html, content_type='text/html; charset=utf-8')

    context = browser.new_context(); context.route('**/*', fixture)
    bridge = BRIDGE.replace('__SEED__', json.dumps(initial(case))).replace('__CASE__', json.dumps(case)).replace('__DEFINITION__', json.dumps(definition(0)))
    context.add_init_script(script=bridge+IDENTITY+source)
    page = context.new_page(); page.goto(URL)
    try:
        page.wait_for_function("()=>{const t=JSON.parse(window.name||'{}')['mastery-task'];return t?.phase==='submitting'||t?.paused||t?.cancelled}", timeout=5500)
    except Exception:
        pass
    page.wait_for_timeout(100)
    state = json.loads(page.evaluate('window.name')); task = state['mastery-task']
    try:
        if case == 'cancel-before-seal':
            assert task.get('cancelled') and state.get(MEMORY) is None and not commits, 'Cancellation resurrected memory or submitted'
        elif case == 'replace-before-seal':
            assert task.get('paused') and not commits, 'Sealing trusted detached old option nodes'
        else:
            assert task['phase'] == 'submitting' and len(commits) == 1, f'No normal submit; phase={task["phase"]}, paused={task.get("paused")}'
            if case == 'log-storage-recovery':
                assert '数量未知' not in page.locator('#zhihuishu-mastery-assistant .log-count').text_content()
                assert '队列不可读' not in page.locator('#zhihuishu-mastery-assistant .log-count').text_content()
            if case == 'late-failure':
                assert len(calls) == 3, f'Expected bounded correction using late feedback, got {len(calls)} model calls'
                record = state[MEMORY]['papers']['current-paper']['questions']['50001']
                assert record['answers'] == [OPTIONS[0]] and record['source'] == 'trial'
                assert calls[-1]['previouslyIncorrect'], 'Latest feedback was not sent to the correction request'
            if case == 'feedback-before-seal':
                assert any('late verified feedback' in json.dumps(q) for q in state[MEMORY]['questions'].values()), 'Sealing erased newer grading evidence'
            if case.startswith('full-draft'):
                assert captures == [0, 1], f'Every resumed question version must be checked, visited {captures}'
                assert len(calls) == (3 if case == 'full-draft-known-failure' else 1 if case == 'full-draft-changed' else 0), 'Saved drafts must check version and fresh grading before reuse'
                if case == 'full-draft-known-failure':
                    assert state[MEMORY]['papers']['current-paper']['questions']['50001']['answers'] == [OPTIONS[0]]
        print('PASS', case, flush=True)
        return True
    except AssertionError as error:
        print('FAIL', case, str(error), flush=True)
        return False
    finally:
        context.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source', type=Path, default=ROOT/'zhihuishu-mastery.user.js')
    parser.add_argument('--cases', default='log-storage,late-failure,full-draft-empty,full-draft-changed,full-draft-known-failure,cancel-before-seal,feedback-before-seal,replace-before-seal')
    args = parser.parse_args(); source = args.source.read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        results = [run(browser, source, case) for case in args.cases.split(',')]
        browser.close()
    raise SystemExit(0 if all(results) else 1)
