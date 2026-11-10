from fixture_identity import userscript
"""Exercise delayed selection, replaced Vue nodes, stale CSS and a nonfunctional control."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SOURCE=userscript(ROOT)
EXAM='https://studentexamcomh5.zhihuishu.com'
COURSE,CLS,POINT,PAPER,ATTEMPT='1000000000000000001','200001','31','801','17'
URL=f'{EXAM}/studentReviewTestOrExam/{ATTEMPT}/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId={PAPER}'
BRIDGE=r'''
globalThis.unsafeWindow=window;
const state=JSON.parse(window.name||'__SEED__');
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_xmlhttpRequest=()=>{throw Error('Unexpected extension transport')};
'''
HTML=r'''<div class="questionContent"><div class="centent-pre"><pre class="preStyle">选择正确特性</pre></div><div class="choices"></div></div>
<span class="reviewDone">提交作业</span><script>
const mode='__CASE__', root=document.querySelector('.questionContent');
let selected=new Set(), resetScheduled=false;
window.actions=0;
const owner={
 $route:{params:{examTestId:'17',recruitId:'1000000000000000001'},query:{examPaperId:'801',point:'1',pointId:'31',classId:'200001'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{questionId:'50001'},reviewTopicData:{id:'50001'},userAnswer:null,
 saveAnswer(flag,saveMode){
   if(flag!==undefined||saveMode!=='backflag')throw Error('Wrong save mode');
   return fetch('/gateway/t/v1/answer/saveAnswer',{method:'POST',body:JSON.stringify({questionId:'50001',answer:this.userAnswer})});
 }
};
root.__vue__={$parent:owner};
function update(){owner.userAnswer=Array.from(selected).join('#@#')||null;window.actualSelected=Array.from(selected).sort()}
function render(){
 root.querySelector('.choices').innerHTML='<div class="checkbox-views">'+[['12','静态类型'],['10','跨平台'],['11','没有类型']].map(([id,text])=>
  '<label class="el-checkbox '+(mode==='stale_class'?'is-checked':'')+'"><span class="el-checkbox__input"><input type="checkbox" value="'+id+'" '+(selected.has(id)?'checked':'')+'></span><pre class="preStyle">'+text+'</pre></label>').join('')+'</div>';
 root.querySelectorAll('input').forEach(input=>{
   input.onclick=event=>{
     window.actions++;
     GM_setValue('fixture-clicks',GM_getValue('fixture-clicks',0)+1);
     if(mode==='never_applies'||mode==='recovers'&&window.actions===1){event.preventDefault();return}
     if(mode==='delayed'){
       const wanted=input.checked;event.preventDefault();
       setTimeout(()=>{input.checked=wanted;wanted?selected.add(input.value):selected.delete(input.value);update()},500);
     }
   };
   input.onchange=()=>{
     if(mode==='delayed'||mode==='never_applies')return;
     input.checked?selected.add(input.value):selected.delete(input.value);update();
     if((mode==='replace_reset'||mode==='duplicate_before_save')&&!resetScheduled){
       resetScheduled=true;
       setTimeout(()=>{
         root.querySelectorAll('input').forEach(node=>node.checked=false);
         selected=new Set();render();update();
         if(mode==='duplicate_before_save')fetch('/gateway/t/v1/question/getExamQuestionInfo');
       },mode==='duplicate_before_save'?525:250);
     }
   };
 });
}
render();update();
document.querySelector('.reviewDone').onclick=async()=>{
 await fetch('/__submit',{method:'POST',body:JSON.stringify(window.actualSelected)});window.ended=true;
};
fetch('/gateway/t/v1/question/getExamQuestionInfo');fetch('/gateway/t/v1/exam/user/getExamSheetInfo');
</script>'''

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    for case in ('replace_reset','duplicate_before_save','delayed','stale_class','recovers','legacy_pause','never_applies'):
        saves,submits,errors=[],[],[]
        seed={'mastery-ai':{'key':'fixture-only','model':'deepseek-flash','localLogs':False},
              'mastery-task':{'id':'selection-update','course':COURSE,'cls':CLS,'active':True,'paused':False,'phase':'exam',
              'actor':None,'enteredAfter':0,'launchedAt':0,'expires':int(time.time()*1000)+60000,'limit':10,
              'queue':[{'point':POINT,'name':'动态选项','high':98,'rounds':2}],'index':0,'results':[]}}
        if case=='never_applies':
            seed['mastery-task']['queue'].append({'point':'32','name':'自动接续点','high':95,'rounds':0})
        if case=='legacy_pause':
            seed['mastery-task'].update(active=False,paused=True,phase='answering',examKey='801:17',message='页面选中状态与预期不一致，请检查当前题。')
            seed['mastery-auto']={'enabled':True,'status':'paused','target':{'course':COURSE,'cls':CLS},'taskId':'selection-update'}
        context=browser.new_context()

        def fixture(route):
            request=route.request;path=urlsplit(request.url).path
            if urlsplit(request.url).hostname=='api.deepseek.com':
                headers={'Access-Control-Allow-Origin':EXAM,'Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'POST'}
                if request.method=='OPTIONS':return route.fulfill(status=204,headers=headers)
                return route.fulfill(headers=headers,json={'choices':[{'message':{'content':'["A","C"]'}}]})
            if path.endswith('/getExamQuestionInfo'):
                return route.fulfill(json={'data':{'id':'50001','content':'<p>选择正确特性</p>','questionTypeName':'多选题',
                    'optionVos':[{'id':id,'content':f'<p>{text}</p>'} for id,text in (('10','跨平台'),('11','没有类型'),('12','静态类型'))]}})
            if path.endswith('/getExamSheetInfo'):return route.fulfill(json={'data':{'questionCount':1}})
            if path.endswith('/get-node-master-max'):
                return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100}})
            if path.endswith('/questions-paper'):return route.fulfill(json={'data':{'questionNum':1,'highMasteryScore':100}})
            if path.startswith('/masteryHistory/'):
                return route.fulfill(body='<script>fetch("/mastery-statistics/get-node-master-max")</script>',content_type='text/html')
            if path.startswith('/learnPage/'):
                return route.fulfill(body='<span class="simplified-mastery__percent">100%</span><script>fetch("/stu/exam/questions-paper")</script>',content_type='text/html')
            if path.endswith('/saveAnswer'):
                saves.append(json.loads(request.post_data));return route.fulfill(json={'code':0,'data':True})
            if path=='/__submit':
                submits.append(json.loads(request.post_data));return route.fulfill(json={'ok':True})
            return route.fulfill(body=HTML.replace('__CASE__',case),content_type='text/html; charset=utf-8')

        context.route('**/*',fixture);context.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed))+SOURCE)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(URL)
        if case=='legacy_pause':
            page.wait_for_function("JSON.parse(window.name || '{}')['mastery-task']?.legacySelectionRecovered===true")
        page.wait_for_function("window.ended || JSON.parse(window.name || '{}')['mastery-task']?.active===false",timeout=20000)
        task=json.loads(page.evaluate('window.name'))['mastery-task']
        if case=='never_applies':
            assert not task['paused'] and not saves and not submits
            assert task['index']==2 and len(task['results'])==2
            assert task['results'][0]['high']==98 and '连续 3 次' in task['results'][0]['reason']
            assert task['results'][1]['high']==100
            assert json.loads(page.evaluate('window.name'))['fixture-clicks']==3
        else:
            assert submits==[['10','12']],(case,task.get('message'),submits)
            assert len(saves)==1 and set(saves[0]['answer'].split('#@#'))=={'10','12'}
            assert page.evaluate('window.actions')<=5
        assert not errors,errors
        print(f'Selection {case}: passed; clicks={json.loads(page.evaluate("window.name"))["fixture-clicks"]}; submissions={len(submits)}')
        context.close()
    browser.close()
