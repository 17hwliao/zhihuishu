const assert = require('node:assert/strict');
const { safeUrl, redact, route, discoverCourses, fillValues, exactIndices, parsePlatformJSON, catalogPoints, cardCatalog, normalizeAPIKey, apiFailure, questionSignature, resolveAIEndpoint, chatPayload } = require('../zhihuishu-mastery.user.js');

const secret = 'arbitrary-provider-credential';
const sanitized = JSON.stringify(redact({
  apiKey: secret, nested: { Authorization: 'Bearer hidden', note: `value ${secret} token=hidden sk-hidden` },
  url: 'https://user:password@example.com/path?token=hidden&classId=200001#secret',
}, [secret]));
assert(!sanitized.includes(secret));
assert(!sanitized.includes('hidden'));
assert(!sanitized.includes('user:password'));
assert(sanitized.includes('classId=200001'));
assert.equal(safeUrl('javascript:alert(1)'), '[javascript:]');
assert.equal(route('https://ai-smart-course-student-pro.zhihuishu.com/#/learnPage/1000000000000000001/31/200001').point, '31');
assert.equal(route('https://ai-smart-course-student-pro.zhihuishu.com/singleCourse/masteryAnalysis/1000000000000000001/200001').kind, 'course-entry');
assert.deepEqual(discoverCourses({ data: [{ courseId: '1000000000000000001', classId: '200001', courseName: 'course' }] }),
  [{ course: '1000000000000000001', cls: '200001', name: 'course' }]);
assert.equal(discoverCourses({ courseId: Number.MAX_SAFE_INTEGER + 1, classId: 2 }).length, 0);
assert.equal(discoverCourses({ courseId: '1', classId: '2', newFlag: false, courseType: 0 }).length, 0);
assert.equal(discoverCourses({ courseId: '1', classId: '2', newFlag: true, courseType: 9 }).length, 0);
assert.deepEqual(fillValues(['int x=2;'], 1), ['int x=2;']);
assert.deepEqual(exactIndices(['B content', 'A content'], ['A content'], false), [1]);
const exact = parsePlatformJSON('{"id":9223372036854775807,"negative":-9223372036854775807,"safe":9007199254740991,"float":1.5,"exp":1e3,"text":"9223372036854775807","escaped":"quote \\" 9223372036854775807"}');
assert.equal(exact.id, '9223372036854775807');
assert.equal(exact.negative, '-9223372036854775807');
assert.equal(exact.safe, Number.MAX_SAFE_INTEGER);
assert.equal(exact.float, 1.5);
assert.equal(exact.exp, 1000);
assert.equal(exact.escaped, 'quote " 9223372036854775807');
const catalog = { courseThemeList: [{ subThemeList: [{ knowledgeList: [
  { knowledgeId: '29', knowledgeName: 'exempt', masteryPercentage: null },
  { knowledgeId: exact.id, knowledgeName: 'graded', masteryPercentage: 96 },
] }] }] };
const checks = [];
const points = catalogPoints(catalog, entry => checks.push(entry));
assert.equal(points.length, 1);
assert.equal(points[0].point, exact.id);
assert.equal(checks[0].status, 'exempt');
const missing = { courseThemeList: [{ subThemeList: [{ knowledgeList: [{ knowledgeId: '30' }] }] }] };
assert.throws(() => catalogPoints(missing), /mastery-field-missing/);
const cards = cardCatalog([
  { point: '1', name: 'partial', hasMastery: true, masteryText: '96%', masteryLabel: true },
  { point: '2', name: 'full', hasMastery: true, masteryText: '100%', masteryLabel: true },
  { point: '3', name: 'ungraded', hasMastery: false },
  { point: '4', name: 'loading', hasMastery: true, masteryText: '--%', masteryLabel: true },
]);
assert.equal(cards.points.length, 2);
assert.equal(cards.points.filter(point => point.high < 100).length, 1);
assert.deepEqual(cards.excluded, ['3']);
assert.equal(cards.problems[0].reason, 'card-mastery-unreadable');
assert.equal(normalizeAPIKey('  "Bearer sk-fixture"  '), 'sk-fixture');
assert.equal(normalizeAPIKey("Bearer 'sk-fixture'"), 'sk-fixture');
assert.throws(() => normalizeAPIKey('sk-one\ntwo'), /不可见字符/);
assert(apiFailure(401).includes('鉴权未通过'));
assert(apiFailure(402).includes('余额不足'));
const question = { id: '123', content: '<p>Question</p>', questionTypeName: '多选题', optionVos: [{ id: '1', content: 'A' }] };
assert.equal(questionSignature(question), questionSignature({ ...question, userAnswerVo: [{ answer: '1' }] }));
assert.notEqual(questionSignature(question), questionSignature({ ...question, content: '<p>Different</p>' }));
assert.notEqual(questionSignature(question), questionSignature({ ...question, optionVos: [{ id: '1', content: 'B' }] }));
assert.equal(resolveAIEndpoint('deepseek'), 'https://api.deepseek.com/chat/completions');
assert.equal(resolveAIEndpoint('custom', 'https://relay.example'), 'https://relay.example/v1/chat/completions');
assert.equal(resolveAIEndpoint('custom', 'https://relay.example/v1/'), 'https://relay.example/v1/chat/completions');
assert.equal(resolveAIEndpoint('custom', 'https://relay.example/api/v1/chat/completions/'), 'https://relay.example/api/v1/chat/completions');
assert.equal(resolveAIEndpoint('custom', 'http://127.0.0.1:11434/v1'), 'http://127.0.0.1:11434/v1/chat/completions');
assert.throws(() => resolveAIEndpoint('custom', 'https://user:pass@relay.example/v1'));
assert.throws(() => resolveAIEndpoint('custom', 'https://relay.example/v1?api_key=hidden'));
assert.throws(() => resolveAIEndpoint('custom', 'javascript:alert(1)'));
assert.throws(() => resolveAIEndpoint('custom', 'http://relay.example/v1'));
assert.deepEqual(chatPayload({provider:'custom',model:'vendor/model'},[{role:'user',content:'q'}],2048),
  {model:'vendor/model',messages:[{role:'user',content:'q'}],max_tokens:2048});
assert.deepEqual(chatPayload({provider:'custom',model:'vendor/model',tokenParameter:'max_completion_tokens'},[],512),
  {model:'vendor/model',messages:[],max_completion_tokens:512});
assert.deepEqual(chatPayload({provider:'deepseek',model:'deepseek-flash'},[],16).thinking,{type:'disabled'});
console.log('Helper checks passed: credential removal, safe URLs, hash routes, course IDs, exact choices and fill punctuation.');
