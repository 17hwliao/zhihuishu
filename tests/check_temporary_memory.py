"""Isolated lifecycle, seventh-round resume, answer reuse and offline queue regression."""
import copy
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright
from fixture_identity import userscript

ROOT = Path(__file__).resolve().parents[1]
SOURCE = userscript(ROOT)
HOST = 'https://ai-smart-course-student-pro.zhihuishu.com'
EXAM = 'https://studentexamcomh5.zhihuishu.com'
COURSE, CLS, POINT = '1000000000000000001', '200001', '31'
MEMORY = 'mastery-current-point-v1'
OUTBOX = 'mastery-log-outbox-v2'
SEED = {'mastery-ai': {'key': 'fixture-only', 'model': 'fixture-model', 'limit': 10, 'localLogs': True},
        'mastery-auto': {'enabled': True, 'status': 'running', 'taskId': 'memory-flow'},
        'mastery-task': {'id': 'memory-flow', 'course': COURSE, 'cls': CLS, 'active': True, 'paused': False,
                        'phase': 'exam', 'actor': None, 'enteredAfter': 0, 'launchedAt': 0,
                        'expires': int(time.time()*1000)+60000, 'index': 0, 'limit': 10, 'results': [],
                        'queue': [{'point': POINT, 'name': '临时记忆回归', 'high': 96, 'rounds': 1}]},
        f'point:{COURSE}:{CLS}:{POINT}:bank': {'50001': ['POISON_OLD_BANK']},
        f'point:{COURSE}:{CLS}:{POINT}:notes': 'UNRELATED_SETTING'}
BRIDGE = r'''
globalThis.unsafeWindow=window;
const state=window.name?JSON.parse(window.name):__SEED__;
window.name=JSON.stringify(state);
globalThis.GM_getValue=(k,d)=>structuredClone(k in state?state[k]:d);
globalThis.GM_listValues=()=>Object.keys(state);
globalThis.GM_deleteValue=k=>{delete state[k];window.name=JSON.stringify(state);if(k==='mastery-current-point-v1')void window.reportMemory(null).catch(()=>{})};
globalThis.GM_setValue=(k,v)=>{state[k]=structuredClone(v);window.name=JSON.stringify(state);if(k==='mastery-current-point-v1')void window.reportMemory(structuredClone(v)).catch(()=>{})};
const nativeFetch=fetch.bind(window);
globalThis.fetch=(url,options)=>{
 if(String(url).startsWith('https://api.deepseek.com/'))return nativeFetch('/__ai',options).then(async r=>{
  const text=await r.text();
  if(window.fixtureRound===7 && JSON.parse(options.body).messages[1].content.includes('CODE_VALUE')){
   window.fixtureWaiting=true;await new Promise(resolve=>setTimeout(resolve,1400));
  }
  return new Response(text,{status:r.status});
 });
 return nativeFetch(url,options);
};
globalThis.GM_xmlhttpRequest=o=>{
 nativeFetch(o.url.startsWith('http://127.0.0.1')?'/__offline':'/__ai',{method:'POST',body:o.data})
  .then(async r=>o.onload?.({status:r.status,responseText:await r.text()})).catch(()=>o.onerror?.());
 return {abort(){o.onabort?.()}};
};
Math.random=()=>0;
'''


def exam_url(round_number):
    return f'{EXAM}/studentReviewTestOrExam/{16+round_number}/1/1/{COURSE}/name?point=1&pointId=31&classId={CLS}&examPaperId=801'


def wait_state(page, predicate, timeout=30000):
    page.wait_for_function("s=>{const v=JSON.parse(window.name||'{}');return Function('v','return '+s)(v)}", arg=predicate, timeout=timeout)
    return json.loads(page.evaluate('window.name'))


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        submissions, calls, snapshots, errors, memory_states = [], [], [], [], []

        def fixture(route):
            req = route.request; parts = urlsplit(req.url); path = parts.path
            round_number = int(path.split('/')[2])-16 if path.startswith('/studentReviewTestOrExam/') else len(submissions)+1
            if path == '/__offline':
                return route.fulfill(status=507)
            if path == '/__ai':
                request = json.loads(req.post_data); data = json.loads(request['messages'][1]['content'])
                calls.append({'round': len(submissions)+1, **data})
                assert len(data['previouslyIncorrect']) <= 3
                assert len(json.dumps(data, ensure_ascii=False)) < 3000
                values = ['  wrong();  '] if data['blanks'] else ['B' if len(submissions) == 0 else 'A']
                return route.fulfill(json={'choices': [{'message': {'content': json.dumps(values)}}]})
            if path.endswith('/getExamQuestionInfo'):
                index = int(parse_qs(parts.query)['index'][0]); round_number = int(parse_qs(parts.query)['round'][0])
                options = [{'id': '10', 'content': '<p>错误项</p>'}, {'id': '11', 'content': '<p>正确项</p>'}]
                if round_number > 1: options.reverse()
                return route.fulfill(json={'data': {'id': str(50001+index), 'content': '<p>CODE_VALUE</p>' if index else '<p>CLASSIFY_JS</p>',
                    'questionTypeName': '填空题' if index else '单选题', 'optionVos': [] if index else options}})
            if path.endswith('/getExamSheetInfo'):
                return route.fulfill(json={'data': {'questionCount': 2}})
            if path.endswith('/saveAnswer'):
                return route.fulfill(json={'code': 200, 'data': True})
            if path == '/__submit':
                submissions.append(json.loads(req.post_data))
                if len(submissions) == 8: assert submissions[-1] == ['  int X = 2;  ']
                return route.fulfill(json={'ok': True})
            if path.endswith('/questions-paper-result-page'):
                rows = [{'id': '50001', 'userAnswerDtos': [{'isCorrect': 1}],
                         'optionDtos': [{'content': '<p>正确项</p>', 'isCorrect': 1}]},
                        {'id': '50002', 'analysis': 'numeric/code feedback for this question only',
                         'userAnswerDtos': [{'isCorrect': 1 if len(submissions) == 8 else 0}]}]
                if len(submissions) >= 7: rows[1]['result'] = '  int X = 2;  '
                return route.fulfill(json={'data': {'aiExamQuestionInfo': rows}})
            if path.endswith('/get-node-master-max'):
                return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100 if len(submissions) >= 8 else 96}})
            if path.endswith('/questions-paper'):
                return route.fulfill(json={'data': {'highMasteryScore': 100 if len(submissions) >= 8 else 96, 'questionNum': 2}})
            if path.startswith('/studentReviewTestOrExam/'):
                options = ['错误项', '正确项'] if round_number == 1 else ['正确项', '错误项']
                html = '''<meta charset="utf-8"><div class="questionContent"></div><button class="next-topic next-t">下一题</button>
<button class="reviewDone">交卷</button><script>
window.fixtureRound=__ROUND__;let index=0;
function render(){const root=document.querySelector('.questionContent');
root.innerHTML='<div class="centent-pre"><pre class="preStyle">'+(index?'CODE_VALUE':'CLASSIFY_JS')+'</pre></div>';
root.innerHTML+=index?'<input>':__OPTIONS__;
root.querySelectorAll('li').forEach(n=>n.onclick=()=>{root.querySelectorAll('li').forEach(x=>x.classList.remove('active'));n.classList.add('active');fetch('/answer/saveAnswer',{method:'POST'})});
root.querySelector('input')?.addEventListener('change',()=>fetch('/answer/saveAnswer',{method:'POST'}));
document.querySelector('.next-topic').disabled=!!index;fetch('/question/getExamQuestionInfo?index='+index+'&round='+window.fixtureRound)};
document.querySelector('.next-topic').onclick=()=>{index=1;render()};
document.querySelector('.reviewDone').onclick=async()=>{await fetch('/__submit',{method:'POST',body:JSON.stringify(Array.from(document.querySelectorAll('.questionContent input'),i=>i.value))});location.href='__RESULT__'};
render();fetch('/getExamSheetInfo');</script>'''
                option_html = '<ul class="radio-view">'+''.join(f'<li class="clearfix"><pre class="preStyle">{o}</pre></li>' for o in options)+'</ul>'
                html = html.replace('__ROUND__', str(round_number)).replace('__OPTIONS__', json.dumps(option_html))
                html = html.replace('__RESULT__', f'{HOST}/point/{COURSE}/801/{16+round_number}/31/{CLS}')
            elif path.startswith('/point/'):
                html = '<h1>平台结果</h1>'
            elif path.startswith('/examPreview/'):
                html = '<script>fetch("/stu/exam/questions-paper-result-page")</script>'
            elif path.startswith('/learnPage/'):
                html = f'<button class="simplified-mastery__action" onclick="location.href=\'/masteryHistory/{COURSE}/{CLS}/31\'">提升</button><script>fetch("/stu/exam/questions-paper")</script>'
            elif path.startswith('/masteryHistory/'):
                html = '<button class="improve-btn" onclick="window.open('+json.dumps(exam_url(len(submissions)+1)).replace('"', '&quot;')+')">提升</button>'
                html += '<script>fetch("/mastery-statistics/get-node-master-max")</script>'
            else:
                html = '<meta charset="utf-8"><h1>隔离平台夹具</h1>'
            return route.fulfill(body=html, content_type='text/html; charset=utf-8')

        context = browser.new_context()
        context.expose_binding('reportMemory', lambda source, value: memory_states.append(copy.deepcopy(value)))
        context.route('**/*', fixture)
        context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(SEED))+SOURCE)
        page = context.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(exam_url(1))
        page.wait_for_function('window.fixtureRound===7 && window.fixtureWaiting===true', timeout=90000)
        panel = page.locator('#zhihuishu-mastery-assistant')
        panel.get_by_role('button', name='暂停', exact=True).click()
        page.wait_for_timeout(1600)
        before = json.loads(page.evaluate('window.name'))
        paused_seventh = copy.deepcopy(before)
        assert before['mastery-task']['queue'][0]['rounds'] == 7 and before['mastery-task']['paused']
        assert len(before[MEMORY]['papers']) == 7
        assert len(before[MEMORY]['questions']) == 2
        assert any(len(q['answers']) >= 2 for q in before[MEMORY]['questions'].values())
        page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
        page.reload(); panel.wait_for(); page.wait_for_timeout(500)
        after = json.loads(page.evaluate('window.name'))
        assert after[MEMORY] == before[MEMORY], 'Pause/reload must keep all seventh-round evidence and correction budget'
        assert after['mastery-task']['queue'][0]['rounds'] == 7
        assert '已确认正确 1' in panel.locator('.memory-summary').text_content()
        assert '待纠错 1' in panel.locator('.memory-summary').text_content()
        panel.locator('.scan-actions button').evaluate('(button)=>{for(let i=0;i<750;i++)button.click()}')
        page.wait_for_timeout(700)
        state = json.loads(page.evaluate('window.name'))
        assert len(state[OUTBOX]['events']) <= 600 and state[OUTBOX]['dropped'] > 0
        assert len(state[OUTBOX]['events']) > 150, 'Outbox must be independent of the 150-row display cache'
        assert not state[OUTBOX]['lastDeliveredAt'], 'Enabling logs is not proof of disk delivery'
        assert '丢失' in panel.locator('.log-count').text_content()
        assert '尚未送达' in panel.locator('.log-count').text_content()
        panel.get_by_role('button', name='继续任务', exact=True).click()
        final = wait_state(page, "v['mastery-auto']?.status==='completed'", 35000)
        assert len(submissions) == 8 and final['mastery-task']['results'][0]['high'] == 100
        assert final['mastery-task']['results'][0]['rounds'] == 8
        assert MEMORY not in final, 'Completion must delete all point answers and feedback'
        assert f'point:{COURSE}:{CLS}:{POINT}:bank' not in final
        assert final[f'point:{COURSE}:{CLS}:{POINT}:notes'] == 'UNRELATED_SETTING'
        assert final['mastery-ai']['key'] == 'fixture-only'
        assert len([c for c in calls if not c['blanks']]) == 1, 'Verified reordered choice must reuse content, not call AI'
        assert all(len([c for c in calls if c['blanks'] and c['round'] == r]) <= 3 for r in range(1, 9))
        assert not [c for c in calls if c['round'] == 8], 'Official fill answer must preserve spaces and avoid another model call'
        log_data = json.dumps({k:v for k,v in final.items() if k.startswith('mastery-panel-log-v2:') or k == OUTBOX})
        for private_text in ('CLASSIFY_JS', 'CODE_VALUE', 'wrong();', 'int X = 2;'):
            assert private_text not in log_data
        assert not errors, errors
        print('Lifecycle passed: seven rounds retained, pause/reload, reordered reuse, persistent correction bound, offline/overflow, whitespace, exact 100% cleanup and targeted migration.', flush=True)
        context.close()

        for scenario in ('end-task',):
            context = browser.new_context()
            context.expose_binding('reportMemory', lambda source, value: None)
            context.route('**/*', lambda r: r.fulfill(body='<meta charset="utf-8"><h1>隔离恢复页</h1>', content_type='text/html; charset=utf-8'))
            script = BRIDGE.replace('__SEED__', json.dumps(paused_seventh))+SOURCE
            context.add_init_script(script=script)
            page = context.new_page(); page.goto(exam_url(7))
            if scenario == 'end-task':
                page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
                page.locator('#zhihuishu-mastery-assistant').get_by_role('button', name='结束任务').click()
            state = wait_state(page, "v['mastery-task']?.cancelled===true")
            assert MEMORY not in state and state['mastery-ai']['key'] == 'fixture-only'
            assert not state['mastery-task']['active'] and not state['mastery-task']['paused']
            print('Lifecycle passed:', scenario, flush=True)
            context.close()
        browser.close()
