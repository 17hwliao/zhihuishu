from fixture_identity import userscript
"""Reproduce state-only Vue selection and native save-before-submit, including rejection guards."""
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SOURCE=userscript(ROOT)
HOST='https://ai-smart-course-student-pro.zhihuishu.com'
EXAM='https://studentexamcomh5.zhihuishu.com'
COURSE,CLS,POINT,PAPER,ATTEMPT='1000000000000000001','200001','31','801','17'
URL=f'{EXAM}/studentReviewTestOrExam/{ATTEMPT}/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId={PAPER}'
BRIDGE=r'''
globalThis.unsafeWindow=window;
const gmState=JSON.parse(window.name||'__SEED__');
globalThis.GM_getValue=(key,otherwise)=>structuredClone(key in gmState?gmState[key]:otherwise);
globalThis.GM_setValue=(key,value)=>{gmState[key]=structuredClone(value);window.name=JSON.stringify(gmState)};
globalThis.GM_xmlhttpRequest=()=>{throw Error('This fixture requires browser transport with local logging disabled')};
'''
HTML=r'''<div class="questionContent"><div class="centent-pre"><pre class="preStyle">选择正确特性</pre></div>
<div class="checkbox-views"><label class="el-checkbox"><input type="checkbox" checked><pre class="preStyle">跨平台</pre></label>
<label class="el-checkbox"><input type="checkbox" checked><pre class="preStyle">面向对象</pre></label>
<label class="el-checkbox"><input type="checkbox"><pre class="preStyle">没有类型</pre></label></div></div>
<span class="reviewDone">提交作业</span><script>
const root=document.querySelector('.questionContent');
const owner={
 $route:{params:{examTestId:'__ATTEMPT__',recruitId:'__COURSE__'},query:{examPaperId:'__PAPER__',point:'1',pointId:'31',classId:'200001'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{questionId:'50001'},reviewTopicData:{id:'50001'},userAnswer:'10#@#11',
 saveAnswer(flag,mode){
  if(flag!==undefined || mode!=='backflag')throw Error('Unexpected native save mode');
  window.nativeCalls=(window.nativeCalls||0)+1;
  return fetch('/gateway/t/v1/answer/saveAnswer',{method:'POST',body:JSON.stringify({questionId:this.currentQues.questionId,answer:this.userAnswer})});
 }
};
root.__vue__={$parent:owner};
if('__CASE__'==='wrong_exam')owner.$route.params.examTestId='999';
if('__CASE__'==='wrong_binding')owner.userAnswer='12';
document.querySelectorAll('input').forEach(input=>input.onchange=()=>{
 // Selection updates Vue only; the platform does not send saveAnswer here.
 owner.userAnswer=Array.from(document.querySelectorAll('input')).flatMap((n,i)=>n.checked?[String(i+10)]:[]).join('#@#');
});
document.querySelector('.reviewDone').onclick=async()=>{
 window.submitClicks=(window.submitClicks||0)+1;
 await fetch('/__submit',{method:'POST'});location.href='__RESULT__';
};
fetch('/gateway/t/v1/question/getExamQuestionInfo');fetch('/gateway/t/v1/exam/user/getExamSheetInfo');
</script>'''.replace('__COURSE__',COURSE).replace('__ATTEMPT__',ATTEMPT).replace('__PAPER__',PAPER).replace('__RESULT__',f'{HOST}/point/{COURSE}/{PAPER}/{ATTEMPT}/{POINT}/{CLS}')

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    for case in ('success','false_save','wrong_binding','wrong_exam'):
        saves,submits,errors=[],[],[]
        seed={'mastery-ai':{'key':'fixture-only','model':'deepseek-flash','localLogs':False},
              'mastery-auto':{'enabled':True,'status':'running','taskId':'native-save'},
              'mastery-task':{'id':'native-save','course':COURSE,'cls':CLS,'active':True,'paused':False,'phase':'exam',
              'actor':None,'enteredAfter':0,'launchedAt':0,'expires':int(time.time()*1000)+60000,'limit':10,
              'queue':[{'point':POINT,'name':'多选原生保存','high':98,'rounds':1}],'index':0,'results':[]}}
        context=browser.new_context()

        def fixture(route):
            request=route.request
            path=urlsplit(request.url).path
            if urlsplit(request.url).hostname=='api.deepseek.com':
                headers={'Access-Control-Allow-Origin':EXAM,'Access-Control-Allow-Headers':'authorization,content-type','Access-Control-Allow-Methods':'POST'}
                if request.method=='OPTIONS':return route.fulfill(status=204,headers=headers)
                return route.fulfill(headers=headers,json={'choices':[{'message':{'content':'["A","B"]'}}]})
            if path.endswith('/getExamQuestionInfo'):
                return route.fulfill(json={'data':{'id':'50001','content':'<p>选择正确特性</p>','questionTypeName':'多选题',
                    'optionVos':[{'id':str(i+10),'content':f'<p>{text}</p>'} for i,text in enumerate(('跨平台','面向对象','没有类型'))]}})
            if path.endswith('/getExamSheetInfo'):return route.fulfill(json={'data':{'questionCount':1}})
            if path.endswith('/saveAnswer'):
                saves.append(json.loads(request.post_data))
                return route.fulfill(json={'code':0,'data':case!='false_save'})
            if path=='/__submit':
                submits.append(1)
                return route.fulfill(json={'ok':True})
            if path.endswith('/questions-paper-result-page'):
                return route.fulfill(json={'data':{'aiExamQuestionInfo':[{'id':'50001','userAnswerDtos':[{'isCorrect':1}],
                    'optionDtos':[{'content':'<p>跨平台</p>','isCorrect':1},{'content':'<p>面向对象</p>','isCorrect':1}]}]}})
            if path.endswith('/get-node-master-max'):
                return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100}})
            if path.endswith('/questions-paper'):return route.fulfill(json={'data':{'questionNum':1,'highMasteryScore':100}})
            if path.startswith('/studentReviewTestOrExam/'):body=HTML.replace('__CASE__',case)
            elif path.startswith('/examPreview/'):body='<script>fetch("/stu/exam/questions-paper-result-page")</script>'
            elif path.startswith('/masteryHistory/'):
                body = '<script>fetch("/mastery-statistics/get-node-master-max")</script>'
            elif path.startswith('/learnPage/'):body='<span class="simplified-mastery__percent">100%</span><script>fetch("/stu/exam/questions-paper")</script>'
            else:body='<h1>官方结果</h1>'
            return route.fulfill(body=body,content_type='text/html; charset=utf-8')

        context.route('**/*',fixture)
        context.add_init_script(script=BRIDGE.replace('__SEED__',json.dumps(seed))+SOURCE)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(URL)
        page.wait_for_function("JSON.parse(window.name || '{}')['mastery-task']?.active===false",timeout=18000)
        state=json.loads(page.evaluate('window.name'))['mastery-task']
        if case=='success':
            assert not state['paused'] and submits==[1]
            assert saves==[{'questionId':'50001','answer':'10#@#11'}]
            assert state['results'][0]['high']==100 and state['results'][0]['rounds']==1
        else:
            assert state['paused'] and not submits
            assert len(saves)==(1 if case=='false_save' else 0)
            assert state['answered']==[] and state['queue'][0]['rounds']==1
        assert not errors,errors
        print(f'Native save {case}: passed; save requests={len(saves)}, submissions={len(submits)}')
        context.close()
    browser.close()
