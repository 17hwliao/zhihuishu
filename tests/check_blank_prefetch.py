"""Offline regression for late question responses while an actual blank is being answered.

The six-question paper, Vue owner, API and platform are synthetic. No real course
or API is contacted. A frozen source can reproduce the reported 2.5.3 pause.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://studentexamcomh5.zhihuishu.com'
URL = HOST + '/studentReviewTestOrExam/17/1/1/101/name?point=1&pointId=31&classId=202&examPaperId=801'
QUESTIONS = [{'id':str(50001+i), 'content':'<p>'+('相同题干' if i in (2,3) else f'代码填空 {i+1}')+'</p>',
              'questionTypeName':'填空题','optionVos':[]} for i in range(6)]
ANSWERS = {str(50001+i):[f'  int X{i} = {i};  ', f'method{i}()'] for i in range(6)}
BRIDGE = r'''
globalThis.unsafeWindow=window;
const state=window.name?JSON.parse(window.name):__SEED__;
window.name=JSON.stringify(state);
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_deleteValue=k=>{delete state[k];window.name=JSON.stringify(state)};
globalThis.GM_listValues=()=>Object.keys(state);
const nativeFetch=fetch.bind(window);
function requestAI(body){
 return nativeFetch('/__ai',{method:'POST',body}).then(async r=>{
  const text=await r.text();window.aiPending=true;
  if(__CASE__==='prefetch' || __CASE__==='xhr-prefetch'){
   await window.otherQuestion(__CASE__==='xhr-prefetch');
  }else if(__CASE__==='same-node-replaced'){
   window.replaceBlankNodes();
  }else if(__CASE__==='changed-question'){
   window.moveQuestion();
  }else if(__CASE__==='same-id-revised'){
   window.reviseQuestion();await new Promise(resolve=>setTimeout(resolve,120));
  }else if(__CASE__==='ambiguous-no-owner'){
   await window.identicalOtherQuestion();
  }else if(__CASE__==='pause'){
   await new Promise(resolve=>setTimeout(resolve,1200));
  }
  await new Promise(resolve=>setTimeout(resolve,160));
  return new Response(text,{status:r.status});
 });
}
globalThis.fetch=(u,o)=>String(u).startsWith('https://api.deepseek.com/')?requestAI(o.body):nativeFetch(u,o);
globalThis.GM_xmlhttpRequest=o=>{requestAI(o.data).then(async r=>o.onload({status:r.status,responseText:await r.text()}));return {abort(){o.onabort?.()}}};
'''
HTML = r'''<meta charset="utf-8"><div class="questionContent"></div>
<button class="pre-topic pre-t">上一题</button><button class="next-topic next-t">下一题</button><button class="reviewDone">交卷</button><script>
const questions=__QUESTIONS__;let index=__START__;window.saved=__SAVED__;window.mismatches=[];window.navigations=[];
const root=document.querySelector('.questionContent'),next=document.querySelector('.next-topic');
const owner={
 $route:{params:{examTestId:'17',recruitId:'101'},query:{point:'1',pointId:'31',classId:'202',examPaperId:'801'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{},reviewTopicData:{},userAnswer:'',
 saveAnswer(flag,mode){
  if(flag!==undefined||mode!=='backflag')throw Error('Wrong save mode');
  const id=this.currentQues.questionId,values=Array.from(root.querySelectorAll('input'),n=>n.value);
  return fetch('/answer/saveAnswer',{method:'POST',body:JSON.stringify({id,values})})
   .then(r=>r.json()).then(body=>{if(body.data===true)window.saved[id]=values});
 }
};
if(__CASE__!=='ambiguous-no-owner')root.__vue__={$parent:owner};
function request(index,xhr=false,extra=''){
 const path='/question/getExamQuestionInfo?index='+index+extra;
 if(xhr)return new Promise(resolve=>{const x=new XMLHttpRequest();x.open('GET',path);x.onload=()=>setTimeout(resolve,70);x.send()});
 return fetch(path).then(r=>r.text()).then(()=>new Promise(resolve=>setTimeout(resolve,70)));
}
function bindInputs(){
 root.querySelectorAll('input').forEach(el=>{
  el.onkeyup=()=>{owner.userAnswer=Array.from(root.querySelectorAll('input'),n=>n.value).join('#@#')};
  if(__CASE__==='ambiguous-no-owner')el.onchange=()=>fetch('/answer/saveAnswer',{method:'POST',body:JSON.stringify({id:owner.currentQues.questionId,values:Array.from(root.querySelectorAll('input'),n=>n.value)})});
 });
}
function render(){
 owner.currentQues={questionId:questions[index].id};owner.reviewTopicData=questions[index];owner.userAnswer='';
 root.innerHTML='<div class="centent-pre"><pre class="preStyle">'+questions[index].content.replace(/<[^>]+>/g,'')+'</pre></div><input><input>';
 if(window.saved[questions[index].id]){
  root.querySelectorAll('input').forEach((el,i)=>el.value=window.saved[questions[index].id][i]);
  owner.userAnswer=window.saved[questions[index].id].join('#@#');
 }
 bindInputs();next.disabled=index===5;next.className='next-topic '+(index===5?'noNext':'next-t');
 const previous=document.querySelector('.pre-topic');previous.disabled=index===0;previous.className='pre-topic '+(index===0?'nopre':'pre-t');
 if(__CASE__==='missing-previous')previous.hidden=true;
 request(index);
}
window.otherQuestion=async xhr=>{await request((index+1)%6,xhr);if(index>0)await request(index-1,xhr)};
window.identicalOtherQuestion=()=>request(index,false,'&same=1');
window.replaceBlankNodes=()=>{root.querySelectorAll('input').forEach(el=>el.replaceWith(el.cloneNode(true)));bindInputs()};
window.moveQuestion=()=>{index=1;render()};
window.reviseQuestion=()=>{root.querySelector('pre').textContent='题目版本已修改';request(index,false,'&revised=1')};
next.onclick=()=>{window.navigations.push('next');index++;render()};
document.querySelector('.pre-topic').onclick=()=>{window.navigations.push('previous');index--;render()};
document.querySelector('.reviewDone').onclick=()=>fetch('/__submit',{method:'POST',body:JSON.stringify(window.saved)});
render();fetch('/getExamSheetInfo');
</script>'''


def run(browser, source, case, expected_block=False, expected_record_error=False, expected_short_paper=False):
    saves, commits, calls, errors = [], [], [], []
    seed={'mastery-ai':{'key':'fixture-only','model':'fixture-model','localLogs':False},
          'mastery-task':{'id':'prefetch-paper','course':'101','cls':'202','active':True,'paused':False,
            'phase':'exam','actor':None,'lease':0,'enteredAfter':0,'launchedAt':0,
            'expires':int(time.time()*1000)+60000,'limit':10,'index':0,'results':[],
            'queue':[{'point':'31','name':'填空异步回归','high':79,'rounds':2}]}}
    first_fingerprint = None
    if case == 'resume-blank-options':
        task=seed['mastery-task']
        task.update(active=False,paused=True,phase='answering',paperInstance='original-partial-paper',
                    examKey='801:17',examUrl=URL,answered=[],memoryVersion=2,
                    message="Cannot read properties of undefined (reading '0')")
        definition={'content':QUESTIONS[0]['content'],'type':[None,'填空题'],'options':[],
                    'optionVersions':['空一','空二'],'blanks':[['INPUT','text',False],['INPUT','text',False]],'files':[]}
        first_fingerprint=hashlib.sha256(json.dumps(definition,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        seed['mastery-current-point-v1']={'schema':2,'scope':{'task':task['id'],'course':'101','cls':'202','point':'31'},
          'questions':{},'rounds':[],'papers':{'original-partial-paper':{'id':'original-partial-paper','key':'801:17',
          'round':2,'status':'draft','questions':{},'feedback':{},'results':[],'aiRequests':{first_fingerprint:1}}}}
    if case=='resume-short-paper':
        task=seed['mastery-task']
        task.update(active=False,paused=True,phase='answering',paperInstance='original-short-paper',examKey='801:17',examUrl=URL,
                    answered=list(ANSWERS)[2:],memoryVersion=2,message='本次核对 4/6 题，请返回第一题后继续')
        records={};questions={};requests={}
        for q in QUESTIONS[2:]:
            definition={'content':q['content'],'type':[None,'填空题'],'options':[],'optionVersions':['空一','空二'],
                        'blanks':[['INPUT','text',False],['INPUT','text',False]],'files':[]}
            fp=hashlib.sha256(json.dumps(definition,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            records[q['id']]={'id':q['id'],'fingerprint':fp,'definition':definition,'answers':ANSWERS[q['id']],
                             'kind':'blank','saved':True,'source':'ai','optionIds':{}}
            questions[fp]={'definition':definition,'answers':{}};requests[fp]=requests.get(fp,0)+1
        seed['mastery-current-point-v1']={'schema':2,'scope':{'task':task['id'],'course':'101','cls':'202','point':'31'},
          'questions':questions,'rounds':[],'papers':{'original-short-paper':{'id':'original-short-paper','key':'801:17',
          'round':2,'status':'draft','questions':records,'feedback':{},'results':[],'aiRequests':requests}}}
    order=[2,3,4,5,1,0] if case in ('start-middle','missing-previous') else [5,4,3,2,1,0] if case=='start-last' else [1,0] if case=='resume-short-paper' else list(range(6))

    def fixture(route):
        req=route.request;u=urlsplit(req.url);path=u.path;query=parse_qs(u.query)
        if path=='/__ai':
            calls.append(json.loads(req.post_data))
            qid=QUESTIONS[order[len(calls)-1]]['id']
            return route.fulfill(json={'choices':[{'message':{'content':json.dumps(ANSWERS[qid])}}]})
        if path.endswith('/getExamQuestionInfo'):
            data=dict(QUESTIONS[int(query['index'][0])])
            if case in ('blank-options','resume-blank-options','start-middle','start-last','resume-short-paper','missing-previous'):
                # The payload can retain blank/answer slots in optionVos. A blank
                # DOM has inputs and deliberately has no choice-option array.
                data['optionVos']=[{'id':'701','content':'空一'},{'id':'702','content':'空二'}]
            if 'same' in query:data['id']='90001'
            if 'revised' in query:data['content']='<p>题目版本已修改</p>'
            return route.fulfill(json={'data':data})
        if path.endswith('/getExamSheetInfo'):return route.fulfill(json={'data':{'questionCount':6}})
        if path.endswith('/saveAnswer'):
            payload=json.loads(req.post_data);saves.append(payload)
            assert payload['values']==ANSWERS[payload['id']],payload
            return route.fulfill(json={'code':200,'data':True})
        if path=='/__submit':
            commits.append(json.loads(req.post_data));return route.fulfill(json={'ok':True})
        saved={'50001':ANSWERS['50001']} if case=='resume-blank-options' else {k:v for k,v in ANSWERS.items() if k in list(ANSWERS)[2:]} if case=='resume-short-paper' else {}
        start=2 if case in ('start-middle','missing-previous') else 5 if case in ('start-last','resume-short-paper') else 0
        html=HTML.replace('__QUESTIONS__',json.dumps(QUESTIONS)).replace('__CASE__',json.dumps(case)).replace('__SAVED__',json.dumps(saved)).replace('__START__',str(start))
        return route.fulfill(body=html,content_type='text/html; charset=utf-8')

    ctx=browser.new_context();ctx.route('**/*',fixture)
    ctx.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed)).replace('__CASE__',json.dumps(case))+source)
    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL)
    if case in ('resume-blank-options','resume-short-paper'):
        assert page.locator('.questionContent input').evaluate_all('(els)=>els.map(el=>el.value)')==ANSWERS['50006' if case=='resume-short-paper' else '50001']
        page.get_by_role('alertdialog').get_by_role('button',name='继续自动处理',exact=True).click()
    if case=='pause':
        page.wait_for_function('window.aiPending===true')
        page.locator('#zhihuishu-mastery-assistant').get_by_role('button',name='暂停',exact=True).click()
        page.wait_for_timeout(1500)
    page.wait_for_function("()=>{const t=JSON.parse(window.name)['mastery-task'];return t.paused||t.phase==='submitting'}",timeout=20000)
    state=json.loads(page.evaluate('window.name'));task=state['mastery-task']
    if expected_short_paper:
        assert task['paused'] and not commits and len(saves)==4,task
        assert '本次核对 4/6 题' in task['message'],task
        assert task['answered']==list(ANSWERS)[2:]
        print('2.5.5 reproduced: start at question 3, save four, reach noNext, pause at 4/6 despite a working previous button.',flush=True)
    elif case=='missing-previous':
        assert task['paused'] and not commits and len(saves)==4,task
        assert '未找到唯一可用的上一题入口' in task['message'],task
        assert task['queue'][0]['rounds']==2
        print('Missing previous control: retain original paper and four confirmed answers, no incomplete submit.',flush=True)
    elif expected_record_error:
        assert task['paused'] and not commits and len(saves)==1,task
        assert task['message']=="Cannot read properties of undefined (reading '0')",task
        assert task['answered']==[] and saves[0]=={'id':'50001','values':ANSWERS['50001']}
        assert page.evaluate('window.saved')=={'50001':ANSWERS['50001']}
        print('2.5.4 reproduced: platform save succeeded, then blank optionIds recording throws undefined[0].',flush=True)
    elif expected_block or case in ('changed-question','same-id-revised','ambiguous-no-owner','pause'):
        assert task['paused'] and not commits and not saves,task
        assert page.locator('.questionContent input').evaluate_all('(els)=>els.every(el=>el.value==="")')
        assert task['queue'][0]['rounds']==2
        if expected_block:assert '填空题已变化' in task['message'],task
        print('Blocked stale/ambiguous fill as expected:',case,task['message'],flush=True)
    else:
        assert task['phase']=='submitting' and not task['paused'],task
        assert len(commits)==1 and commits[0]==ANSWERS,commits
        expected_ids=[QUESTIONS[i]['id'] for i in order]
        assert len(saves)==len(order) and [r['id'] for r in saves]==expected_ids,saves
        assert set(task['answered'])==set(ANSWERS)
        assert task['queue'][0]['rounds']==2
        paper=state['mastery-current-point-v1']['papers'][task['paperInstance']]
        assert paper['count']==6 and paper['status']!='draft'
        for qid,values in ANSWERS.items():
            assert paper['questions'][qid]['answers']==values
            assert paper['questions'][qid]['kind']=='blank'
            assert paper['questions'][qid]['optionIds']=={}, 'Blank slots must not become choice mappings'
        if case=='resume-blank-options':
            assert task['paperInstance']=='original-partial-paper'
            assert paper['aiRequests'][first_fingerprint]==2,'Resume must retain the original request budget'
        if case=='resume-short-paper':
            assert task['paperInstance']=='original-short-paper'
            assert len(calls)==2,'Already saved answers must be checked without asking AI again'
            assert all(paper['aiRequests'][k]==v for k,v in requests.items()),'Existing request budgets must be unchanged'
        print('Six-question paper passed:',case,f'{len(saves)} native saves, {len(calls)} model calls, six verified records, one submit',flush=True)
    assert not errors,errors
    ctx.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'zhihuishu-mastery.user.js')
    parser.add_argument('--case',action='append');parser.add_argument('--expect-block',action='store_true')
    parser.add_argument('--expect-record-error',action='store_true');parser.add_argument('--expect-short-paper',action='store_true');args=parser.parse_args()
    source=args.source.read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        for case in args.case or ['start-middle','start-last','resume-short-paper','missing-previous','blank-options','resume-blank-options','prefetch','xhr-prefetch','same-node-replaced','changed-question','same-id-revised','ambiguous-no-owner','pause']:
            run(browser,source,case,args.expect_block,args.expect_record_error,args.expect_short_paper)
        browser.close()
