"""Verify image-only question reuse and safe pauses on an isolated Edge profile."""
import hashlib
import base64
import json
import sys
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import TimeoutError, sync_playwright

from check_resume_and_trials import BRIDGE, CLS, COURSE, EXAM, HOST, POINT, SOURCE, seed

IMAGE_BASE = 'https://image.zhihuishu.com/zhs/fixture/'
MEDIA = [IMAGE_BASE + f'{name}.png' for name in ('stem', 'incorrect', 'correct', 'other', 'last')]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD5sAAAAASUVORK5CYII=')
EXPORT = 'https://hike-export.oss-cn-hangzhou.aliyuncs.com/paper/dev/20260228/'
DIAGRAM = 'https://image.zhihuishu.com/zhs/question-import/formula/202502/diagram.png'
PREVIEW = f'{HOST}/examPreview/{COURSE}/801/17/{POINT}/{CLS}'
LEARN = f'{HOST}/learnPage/{COURSE}/{POINT}/{CLS}'
NEXT_EXAM = f'{EXAM}/studentReviewTestOrExam/18/1/1/{COURSE}/name?point=1&pointId={POINT}&classId={CLS}&examPaperId=802'
NEXT_RESULT = f'{HOST}/point/{COURSE}/802/18/{POINT}/{CLS}'
IMAGE_BRIDGE = '''
const gmTextRequest=GM_xmlhttpRequest;
GM_xmlhttpRequest=o=>{
 if(o.method!=='GET') return gmTextRequest(o);
 nativeFetch('/__fixture_png?url='+encodeURIComponent(o.url)).then(async r=>
   o.onload({status:r.status,response:await r.arrayBuffer(),finalUrl:o.url})).catch(()=>o.onerror());
 return {abort(){}};
};
const fixtureRandom=crypto.getRandomValues.bind(crypto);
crypto.getRandomValues=array=>{
 if(array instanceof Uint32Array && array.length===1) {array[0]=123456;return array;}
 return fixtureRandom(array);
};
'''


def image(i, wrapped=False):
    html = f'<img src="{MEDIA[i]}"' + (' width="320" data-tag-offset="2">' if wrapped else '>')
    return '<p>' + html + '</p>' if wrapped else html


def exported_stem(number, diagram=DIAGRAM):
    return (f'<div>比较图中的信号关系<img src="{EXPORT}{number:08d}-0000-0000-0000-000000000000.png">'
            f'（ ）<br><img src="{diagram}"></div>')


def run(browser, case):
    vision = case.startswith('vision-')
    history = case in ('history-then-trial', 'history-reference', 'history-reference-wrong-id')
    trial_cases = ('trial-new-later', 'trial-seen', 'trial-then-review')
    trial = case in trial_cases
    fresh = case == 'no-reference' or vision or history or trial
    changed_stem = case == 'changed-stem'
    formula = case.startswith('formula-export') or history
    mixed = case in ('presentation', 'changed-preview-text')
    original_stem = '<div>读图＿</div>' + image(0) if mixed else image(0)
    display_stem = '<figure><figcaption>读图_</figcaption>' + image(0).replace(
        '<img ', '<img style="height:180px; width:320px; vertical-align:middle" ') + '</figure>' if mixed else image(0, True)
    if formula:
        original_stem = display_stem = exported_stem(1)
    choices = list(range(1, 5 if formula else 3))
    config = seed(paused=not fresh or history, phase='answering' if fresh else 'submitting',
                  fallback=case not in ('no-reference', 'vision-probe-failed', 'vision-read-failed'))
    task = config['mastery-task']
    task.update(count=1, paperInstance='first', submissionId=None if fresh else 'first')
    if fresh:
        task.update(examKey='802:18', examUrl=NEXT_EXAM)
        if vision:
            config['mastery-ai']['visionTarget'] = '["https://api.deepseek.com/chat/completions","fixture-model"]'
            config['mastery-ai']['visionAuto'] = case == 'vision-auto'
        if history:
            config['mastery-current-point-v1'] = {'schema': 2, 'scope': {'task': task['id'], 'course': COURSE,
                'cls': CLS, 'point': POINT}, 'questions': {}, 'papers': {}, 'rounds': []}
        if case in ('trial-new-later', 'trial-seen'):
            earlier = '50001' if case == 'trial-seen' else '50999'
            task['queue'][0]['rounds'] = 2
            config['mastery-current-point-v1'] = {'schema': 2, 'scope': {'task': task['id'], 'course': COURSE,
                'cls': CLS, 'point': POINT}, 'questions': {}, 'rounds': [], 'papers': {'earlier': {'id': 'earlier',
                'status': 'graded', 'questions': {earlier: {'id': earlier, 'kind': 'choice', 'source': 'vision-trial', 'saved': True,
                    'fingerprint': 'earlier', 'definition': {'type': [1, '单选题'], 'content': image(4),
                    'options': [], 'optionVersions': []}}}}}}
    else:
        keys = [json.dumps(['', [MEDIA[i]]], separators=(',', ':')) for i in choices]
        definition = {'content': original_stem, 'type': [1, '单选题'], 'options': sorted(keys),
                      'optionVersions': sorted(image(i) for i in choices), 'blanks': [], 'files': []}
        fingerprint = hashlib.sha256(json.dumps(definition, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        scope = {'task': task['id'], 'course': COURSE, 'cls': CLS, 'point': POINT}
        config['mastery-current-point-v1'] = {'schema': 2, 'scope': scope, 'rounds': [],
            'questions': {fingerprint: {'definition': definition, 'answers': {}}},
            'papers': {'first': {'id': 'first', 'key': '801:17', 'status': 'submitted', 'count': 1, 'round': 1,
                'submittedAt': 1, 'feedback': {}, 'results': [], 'questions': {'50001': {
                    'id': '50001', 'kind': 'choice', 'source': 'trial', 'fingerprint': fingerprint, 'saved': True,
                    'definition': definition, 'answers': [keys[0]],
                    'optionIds': {str(9+i): key for i, key in zip(choices, keys)}
                }}}}}
        if case in ('presentation', 'formula-export'):
            task.update(phase='preview', limit=10)
            task['queue'][0]['rounds'] = 9
            paper = config['mastery-current-point-v1']['papers']['first']
            old_digest = hashlib.sha256(b'[["50001","wrong",null,true]]').hexdigest()
            paper.update(status='graded', round=9, verdict='unknown', results=[old_digest])

    saves, submits, ai, visits, errors, image_reads = [], [], [], [], [], []

    def exam_option(i, wrapped=False, shuffled=False):
        markup = image(i, wrapped)
        return markup.replace('.png"', '.png?copy=review"') if shuffled else markup

    def fixture(route):
        url = urlsplit(route.request.url)
        path = url.path
        if path == '/__fixture_png' or path.endswith('.png'):
            asset = parse_qs(url.query)['url'][0] if path == '/__fixture_png' else route.request.url
            if path == '/__fixture_png':
                image_reads.append((asset, bool(submits)))
                if case == 'vision-read-failed':
                    return route.fulfill(status=404)
            name = urlsplit(asset).path.rsplit('/', 1)[-1]
            marker = 'formula' if asset.startswith(EXPORT) else name + urlsplit(asset).query.removeprefix('copy=review')
            if name == 'stem-relocated.png':
                marker = 'stem.png'
            if case == 'vision-hash-changed' and submits and name == 'correct.png':
                marker += 'changed'
            return route.fulfill(body=PNG + marker.encode(), content_type='image/png')
        if path.endswith('/questions-paper-result-page'):
            initial = not submits
            correct = {'id': '11' if initial else '21', 'isCorrect': 1}
            shuffled = case == 'trial-then-review' and len(submits) > 1
            if case != 'id-only' or not initial:
                correct['content'] = exam_option(2, True, shuffled)
            if case == 'changed-reference':
                correct['content'] = correct['content'].replace('correct.png', 'different.png')
            stem = display_stem
            if initial and case in ('empty-preview', 'incomplete-preview'):
                stem = '<p>&nbsp;</p>'
            if initial and case == 'changed-preview-image':
                stem = stem.replace('stem.png', 'stem.png?crop=1')
            if initial and case == 'changed-preview-text':
                stem = stem.replace('读图_', '按另一条件读图_')
            if initial and formula:
                diagram = DIAGRAM.replace('diagram.png', 'other-diagram.png') if case == 'formula-export-changed-diagram' else DIAGRAM
                stem = exported_stem(2, diagram)
            if not initial and case == 'vision-hash-relocated':
                stem = stem.replace('stem.png', 'stem-relocated.png')
            row = {'id': '50001', 'content': stem, 'questionType': 1, 'questionTypeName': '单项选择题',
                   'userAnswerDtos': [{'answer': ['99' if case == 'wrong-echo' else '10' if initial else submits[-1]],
                                       'isCorrect': int(not initial and submits[-1] == '21')}], 'optionDtos': [correct]}
            if initial and case == 'empty-preview':
                row['optionDtos'].append({'id': '10', 'content': image(1, True), 'isCorrect': 0})
            if initial and formula and case != 'formula-export-incomplete':
                row['optionDtos'].extend({'id': str(9+i), 'content': image(i, True), 'isCorrect': 0} for i in choices if i != 2)
                if case == 'formula-export-changed-option':
                    row['optionDtos'][-1]['content'] = image(0, True)
                if history:
                    for option in row['optionDtos']:
                        option['content'] = option['content'].replace('.png"', '.png?copy=review"')
                if case in ('history-reference', 'history-reference-wrong-id'):
                    # The platform returned a full reference, without the user's grade.
                    row.pop('userAnswerDtos')
                    if case == 'history-reference-wrong-id':
                        row['id'] = '50999'
            if not initial:
                row['optionDtos'].extend({'id': str(19+i), 'content': exam_option(i, True, shuffled), 'isCorrect': 0}
                                         for i in choices if i != 2)
            return route.fulfill(json={'data': {'aiExamQuestionInfo': [row]}})
        if path.endswith('/get-node-master-max'):
            reached = len(submits) >= (2 if case == 'trial-then-review' else 1)
            return route.fulfill(json={'code': 200, 'data': {'masteryMax': 100 if reached else 80}})
        if path.endswith('/getExamQuestionInfo'):
            stem = display_stem.replace('stem.png', 'new-stem.png') if changed_stem else display_stem
            shuffled = case == 'trial-then-review' and bool(submits)
            question = {'id': '50001', 'questionType': 1, 'questionTypeName': '单选题',
                        'content': stem, 'optionVos': [{'id': str(19+i), 'content': exam_option(i, True, shuffled)}
                                                       for i in reversed(choices)]}
            return route.fulfill(json={'data': question})
        if path.endswith('/getExamSheetInfo'):
            return route.fulfill(json={'data': {'questionCount': 1}})
        if path.endswith('/saveAnswer'):
            saves.append(route.request.post_data)
            return route.fulfill(json={'code': 200, 'data': True})
        if path == '/__submit':
            submits.append(route.request.post_data)
            return route.fulfill(json={'ok': True})
        if path == '/__ai':
            data = json.loads(route.request.post_data)
            ai.append(data)
            if not vision:
                return route.fulfill(status=500)
            parts = data['messages'][-1]['content']
            if len(ai) == 1:
                assert len(parts) == 2 and parts[1]['type'] == 'image_url'
                answer = '000000' if case == 'vision-probe-failed' else '123456'
            else:
                labels = [part['text'] for part in parts if part['type'] == 'text' and '第 1 张图片' in part['text']]
                assert labels == ['题干第 1 张图片', 'A 选项第 1 张图片', 'B 选项第 1 张图片']
                images = [part['image_url']['url'] for part in parts if part['type'] == 'image_url']
                assert len(images) == 3 and all(url.startswith('data:image/png;base64,') for url in images)
                assert [base64.b64decode(url.split(',', 1)[1])[len(PNG):] for url in images] == [
                    b'stem.png', b'incorrect.png', b'correct.png']
                answer = '["B"]'
            return route.fulfill(json={'choices': [{'message': {'content': answer}}]})
        if path.startswith('/examPreview/'):
            html = '<script>fetch("/stu/exam/questions-paper-result-page")</script>'
        elif path.startswith('/learnPage/'):
            html = '<h1>知识点</h1>'
        elif path.startswith('/point/'):
            html = '<h1>已交卷</h1>'
        elif path.startswith('/masteryHistory/'):
            html = '<button class="improve-btn">提升</button><script>document.querySelector("button").onclick=()=>window.open('
            html += json.dumps(NEXT_EXAM) + ');fetch("/mastery-statistics/get-node-master-max")</script>'
        elif path.startswith('/studentReviewTestOrExam/'):
            visits.append('exam')
            stem = display_stem.replace('stem.png', 'new-stem.png') if changed_stem else display_stem
            shuffled = case == 'trial-then-review' and bool(submits)
            shown_choices = list(reversed(choices)) if shuffled else choices
            html = '<div class="questionContent"><div class="centent-pre"><pre class="preStyle">' + stem + '</pre></div>'
            html += '<ul class="radio-view">' + ''.join(
                f'<li class="clearfix" data-id="{19+i}"><pre class="preStyle">{exam_option(i, shuffled=shuffled)}</pre></li>'
                for i in shown_choices) + '</ul></div><button class="reviewDone">交卷</button>'
            html += '''<script>
const root=document.querySelector('.questionContent');
const owner={
 $route:{params:{examTestId:'18',recruitId:'1000000000000000001'},query:{examPaperId:'802',point:'1',pointId:'31',classId:'200001'}},
 $options:{methods:{saveAnswer(){}}},currentQues:{questionId:'50001'},reviewTopicData:{id:'50001'},userAnswer:'',
 saveAnswer(){return fetch('/answer/saveAnswer',{method:'POST',body:this.userAnswer})}
};
root.__vue__={$parent:owner};
root.querySelectorAll('li').forEach(node=>node.onclick=()=>{
 root.querySelectorAll('li').forEach(n=>n.classList.remove('active'));node.classList.add('active');owner.userAnswer=node.dataset.id;
});
document.querySelector('.reviewDone').onclick=async()=>{
 await fetch('/__submit',{method:'POST',body:owner.userAnswer});location.href=__RESULT__;
};
fetch('/question/getExamQuestionInfo');fetch('/getExamSheetInfo');
</script>'''.replace('__RESULT__', json.dumps(NEXT_RESULT))
        else:
            return route.fulfill(status=404)
        return route.fulfill(body='<meta charset="utf-8">' + html, content_type='text/html; charset=utf-8')

    context = browser.new_context()
    context.route('**/*', fixture)
    rng = 'Math.random=()=>0.99;\n' if history or case == 'trial-then-review' else ''
    context.add_init_script(script=BRIDGE.replace('__SEED__', json.dumps(config)) + IMAGE_BRIDGE + rng + SOURCE)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(PREVIEW if history else NEXT_EXAM if fresh else LEARN if case == 'presentation' else PREVIEW)
    if case == 'formula-export':
        page.wait_for_function("""Object.entries(JSON.parse(window.name)).some(([key, log]) =>
            key.startsWith('mastery-panel-log-v2:') && log?.some(event => event.event === 'memory.formula-export-matched'))""")
    if history:
        page.wait_for_function("Object.keys(JSON.parse(window.name)['mastery-current-point-v1']?.reviews ?? {}).length===1")
        page.goto(NEXT_EXAM)
    if not fresh or history:
        page.get_by_role('alertdialog').get_by_role('button', name='稍后处理').click()
        page.locator('#zhihuishu-mastery-assistant').get_by_role('button', name='继续任务', exact=True).click()
    if case in ('vision-confirm', 'vision-stale', 'vision-hash-changed', 'vision-hash-relocated'):
        modal = page.get_by_role('alertdialog')
        button = modal.get_by_role('button', name='采用候选并保存')
        button.wait_for()
        assert modal.get_by_text('视觉候选：B').is_visible()
        assert not saves and not submits and len(ai) == 2
        if case == 'vision-stale':
            page.locator('.centent-pre img').evaluate('(img)=>img.src=img.src.replace("stem.png","new-stem.png")')
            button.wait_for(state='hidden')
        else:
            button.click()
    if case in ('reuse', 'id-only', 'presentation', 'empty-preview', 'formula-export', 'history-then-trial',
                'history-reference', 'history-reference-wrong-id',
                'trial-new-later', 'trial-then-review', 'vision-confirm', 'vision-auto', 'vision-hash-relocated'):
        try:
            page.wait_for_function("['completed','paused'].includes(JSON.parse(window.name)['mastery-auto']?.status)", timeout=15000)
        except TimeoutError:
            current = json.loads(page.evaluate('window.name'))
            events = [(e['event'], e['data']) for key, log in current.items() if key.startswith('mastery-panel-log-v2:') for e in (log or [])]
            print(case, page.url, current['mastery-task'], events[-22:], errors, flush=True)
            raise
        state = json.loads(page.evaluate('window.name'))
        assert state['mastery-auto']['status'] == 'completed', (page.url, state['mastery-task']['message'], errors)
        expected_visits = ['exam', 'exam'] if history or case == 'trial-then-review' else ['exam']
        expected_answers = ['20'] if case == 'history-reference-wrong-id' else ['20', '21'] if case == 'trial-then-review' else ['21']
        assert saves == submits == expected_answers and visits == expected_visits, (saves, submits, visits)
        if case in ('presentation', 'formula-export'):
            assert state['mastery-task']['results'][0]['rounds'] == 10
        if case == 'vision-hash-relocated':
            assert (MEDIA[0].replace('stem.png', 'stem-relocated.png'), True) in image_reads
            assert (MEDIA[0], True) not in image_reads
    elif case == 'trial-seen':
        page.wait_for_function("JSON.parse(window.name)['mastery-task']?.message?.includes('这道图题已作答')")
        assert not saves and not submits and visits == ['exam']
    elif case == 'vision-hash-changed':
        page.wait_for_function("JSON.parse(window.name)['mastery-task']?.message?.includes('参考答案未能核对')")
        assert saves == submits == ['21'] and visits == ['exam']
    elif vision:
        if case == 'vision-probe-failed':
            page.wait_for_function("JSON.parse(window.name)['mastery-task']?.message?.includes('视觉接口检测未通过')")
            assert len(ai) == 1 and not image_reads
        if case == 'vision-read-failed':
            page.wait_for_function("JSON.parse(window.name)['mastery-task']?.message?.includes('题图读取失败')")
            assert len(ai) == 1 and image_reads
        assert not saves and not submits and visits == ['exam']
    else:
        expected = '图题缺少可核对的参考答案' if fresh or changed_stem else '参考答案未能核对'
        page.wait_for_function("expected=>JSON.parse(window.name)['mastery-task']?.message?.includes(expected)", arg=expected)
        assert not saves and not submits and visits == (['exam'] if fresh or changed_stem else [])
    assert not errors and (vision or not ai), (errors, ai)
    print('Image review passed:', case, flush=True)
    context.close()


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        for case in sys.argv[1:] or ('reuse', 'id-only', 'presentation', 'empty-preview', 'incomplete-preview',
                     'changed-preview-image', 'changed-preview-text', 'changed-reference', 'changed-stem', 'wrong-echo', 'no-reference',
                     'formula-export', 'formula-export-incomplete', 'formula-export-changed-diagram', 'formula-export-changed-option',
                     'history-then-trial', 'history-reference', 'history-reference-wrong-id', 'trial-new-later', 'trial-seen', 'trial-then-review',
                     'vision-confirm', 'vision-auto', 'vision-stale', 'vision-probe-failed',
                     'vision-read-failed', 'vision-hash-changed', 'vision-hash-relocated'):
            run(browser, case)
        browser.close()
