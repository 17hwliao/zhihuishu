"""Offline: saved answers are visible, while Vue's parent binding is empty/stale.

Use the platform's reviewTopic.chooseAnswer -> update:userAnswer event contract.
The exact live failure cause is not inferred from the user's compact log.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL='https://studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/17/1/1/101/name?point=1&pointId=31&classId=202&examPaperId=801'
BRIDGE=r'''
globalThis.unsafeWindow=window;
const state=__SEED__;window.name=JSON.stringify(state);
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state)};
globalThis.GM_deleteValue=k=>{delete state[k];window.name=JSON.stringify(state)};
globalThis.GM_listValues=()=>Object.keys(state);
globalThis.GM_xmlhttpRequest=()=>{throw Error('Unexpected extension request')};
'''
HTML=r'''<meta charset="utf-8"><div class="questionContent"><div class="centent-pre"><pre class="preStyle">__STEM__</pre></div>__INPUTS__</div>
<button class="reviewDone">交卷</button><script>
window.syncCalls=0;
const expected=__VALUES__,kind=__KIND__,mode=__MODE__,root=document.querySelector('.questionContent');
const owner={
 $route:{params:{examTestId:'17',recruitId:'101'},query:{point:'1',pointId:'31',classId:'202',examPaperId:'801'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{questionId:'50001'},reviewTopicData:__QUESTION__,userAnswer:null,
 saveAnswer(flag,mode){
  if(flag!==undefined||mode!=='backflag')throw Error('Unexpected native save');
  return fetch('/answer/saveAnswer',{method:'POST',body:JSON.stringify({questionId:this.currentQues.questionId,answer:this.userAnswer})});
 }
};
const child={
 $options:{name:'reviewTopic',methods:{chooseAnswer(){}}},$parent:owner,$route:owner.$route,
 reviewTopicData:owner.reviewTopicData,currentQues:owner.currentQues,combination:false,
 chooseAnswer(value,data){
  if(data!==this.reviewTopicData||String(data.id)!=='50001')throw Error('Wrong native question');
  window.syncCalls++;this.$emit('update:userAnswer',value);
 },
 $emit(event,value){if(event!=='update:userAnswer')throw Error('Unexpected event');owner.userAnswer=value},
 $nextTick(){return Promise.resolve()}
};
root.__vue__={$parent:owner};owner.$refs={reviewTopics:child};
if(mode==='wrong-child')child.reviewTopicData={...owner.reviewTopicData,id:'99999'};
if(mode==='sync-refused')child.$emit=()=>{};
if(mode==='delayed')setTimeout(()=>{owner.userAnswer=expected.join('#@#')},1200);
if(mode==='dom-changed')setTimeout(()=>{if(kind==='blank')root.querySelector('input').value='changed';else root.querySelector('input').checked=false},1000);
document.querySelector('.reviewDone').onclick=()=>fetch('/__submit',{method:'POST'});
fetch('/question/getExamQuestionInfo');fetch('/getExamSheetInfo');
</script>'''

def run(browser,source,kind,mode,baseline):
    blank=kind=='blank';stem='填写两个代码空位' if blank else '选择正确特性'
    raw_options=[{'id':'701','content':'空一'},{'id':'702','content':'空二'}] if blank else [
      {'id':str(10+i),'content':'<p>'+text+'</p>'} for i,text in enumerate(['跨平台','面向对象','无类型'])]
    question={'id':'50001','content':'<p>'+stem+'</p>','questionTypeName':'填空题' if blank else '多选题','optionVos':raw_options}
    encode=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':'))
    content_options=[] if blank else [encode([text,[]]) for text in ['跨平台','面向对象','无类型']]
    values=['  int X = 2;  ','main()'] if blank else ['10','11']
    stored=values if blank else content_options[:2]
    definition={'content':question['content'],'type':[None,question['questionTypeName']],
      'options':sorted(content_options),'optionVersions':sorted(o['content'] for o in raw_options),
      'blanks':[['INPUT','text',False],['INPUT','text',False]] if blank else [],'files':[]}
    fp=hashlib.sha256(encode(definition).encode()).hexdigest()
    entry={'definition':definition,'answers':{encode(stored if blank else sorted(stored)):{'values':stored,
       'evidence':{'old-correct':{'round':1,'verdict':'correct'}}}}}
    task={'id':'binding-test','course':'101','cls':'202','phase':'exam','active':True,'paused':False,'actor':None,'lease':0,
      'enteredAfter':0,'launchedAt':0,'expires':int(time.time()*1000)+60000,'paperInstance':'original-paper','memoryVersion':2,
      'index':0,'limit':10,'results':[],'queue':[{'point':'31','name':'原生绑定恢复','high':80,'rounds':2}]}
    seed={'mastery-task':task,'mastery-ai':{'key':'fixture-only','model':'fixture','localLogs':False},
      'mastery-current-point-v1':{'schema':2,'scope':{'task':'binding-test','course':'101','cls':'202','point':'31'},
        'questions':{fp:entry},'papers':{},'rounds':[]}}
    inputs='<input value="  int X = 2;  "><input value="main()">' if blank else '<div class="checkbox-views">'+''.join(
      '<label class="el-checkbox"><input type="checkbox" '+('checked' if i<2 else '')+'><pre class="preStyle">'+text+'</pre></label>'
       for i,text in enumerate(['跨平台','面向对象','无类型']))+'</div>'
    saves=[];submits=[];calls=[];errors=[]
    def fixture(route):
        req=route.request;path=urlsplit(req.url).path
        if urlsplit(req.url).hostname=='api.deepseek.com':
            calls.append(1);return route.abort()
        if path.endswith('/getExamQuestionInfo'):return route.fulfill(json={'data':question})
        if path.endswith('/getExamSheetInfo'):return route.fulfill(json={'data':{'questionCount':1}})
        if path.endswith('/saveAnswer'):
            value=json.loads(req.post_data);saves.append(value)
            assert value=={'questionId':'50001','answer':'#@#'.join(values)},value
            return route.fulfill(json={'code':0,'data':True})
        if path=='/__submit':submits.append(1);return route.fulfill(json={'ok':True})
        html=HTML.replace('__STEM__',stem).replace('__INPUTS__',inputs).replace('__VALUES__',encode(values)).replace('__KIND__',encode(kind)).replace('__MODE__',encode(mode)).replace('__QUESTION__',encode(question))
        return route.fulfill(body=html,content_type='text/html; charset=utf-8')
    ctx=browser.new_context();ctx.route('**/*',fixture);ctx.add_init_script(script=BRIDGE.replace('__SEED__',encode(seed))+source)
    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(URL)
    page.wait_for_function("()=>{const t=JSON.parse(window.name)['mastery-task'];return t.paused||t.phase==='submitting'}",timeout=12000)
    result=json.loads(page.evaluate('window.name'))['mastery-task'];syncs=page.evaluate('window.syncCalls')
    if baseline or mode in ('wrong-child','sync-refused','dom-changed'):
        assert result['paused'] and not saves and not submits,(result,saves,submits)
        if baseline:assert '页面答案绑定与选填结果不一致' in result['message'],result
        if mode in ('wrong-child','dom-changed'):assert syncs==0,syncs
        if mode=='sync-refused' and not baseline:assert syncs==1,syncs
    else:
        assert result['phase']=='submitting' and len(saves)==len(submits)==1,(result,saves,submits)
        assert syncs==(0 if mode=='delayed' else 1),syncs
        assert result['answered']==['50001'] and result['queue'][0]['rounds']==2
    assert not calls and not errors,(calls,errors)
    print('Binding regression passed:',kind,mode,'baseline='+str(baseline),f'sync={syncs} save={len(saves)} submit={len(submits)}',flush=True)
    ctx.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'zhihuishu-mastery.user.js');p.add_argument('--baseline',action='store_true');args=p.parse_args()
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(channel='msedge',headless=True)
        for kind in ('blank','choice'):
            for mode in (('stale',) if args.baseline else ('stale','delayed','wrong-child','sync-refused','dom-changed')):
                run(browser,args.source.read_text(encoding='utf-8'),kind,mode,args.baseline)
        browser.close()
