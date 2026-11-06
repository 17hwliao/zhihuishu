const assert = require('node:assert/strict');
const {upgradeTask, upgradeMemory, scopeEqual, createMemory} = require('../zhihuishu-mastery.user.js');
const scope = {task:'original-task', course:'101', cls:'202', point:'303'};
const task = {id:scope.task, course:scope.course, cls:scope.cls, account:'old-digest', accountKind:'uuid',
  active:false, paused:true, phase:'submitting', queue:[{point:scope.point,rounds:7}], index:0,
  examKey:'801:17', examUrl:'https://example.invalid/original-paper', submissionId:'round-7',
  paperInstance:'round-7', answered:['50001'], limit:10, count:1, pauseId:'original-pause', memoryVersion:1};
const original = structuredClone(task);
const upgraded = upgradeTask(task);
const {account, accountKind, ...expected} = original;
assert.deepEqual(upgraded, expected);
assert.deepEqual(task, original, 'Upgrade cannot mutate a captured old task');
assert.equal(upgradeTask(upgraded), upgraded, 'Migration is idempotent');
assert.equal(upgradeTask(null), null);
const legacy = {schema:1, scope:{...scope,account:'old-digest'}, questions:{q:{answers:{a:{values:['  x();  ']}}}},
  papers:{'round-7':{id:'round-7',key:'801:17',round:7,status:'submitted',submittedAt:123,questions:{}}}, rounds:[{key:'801:17'}]};
const before = structuredClone(legacy);
const memory = upgradeMemory(legacy, scope);
assert.deepEqual(memory, {...before,schema:2,scope});
assert.deepEqual(legacy, before);
assert.equal(upgradeMemory(memory,scope), memory);
for (const field of ['task','course','cls','point']) {
  const other = {...scope,[field]:'different'};
  assert.equal(scopeEqual(scope,other),false);
  assert.equal(upgradeMemory(legacy,other),legacy,'Never rebind memory from a different task or point');
}
assert.equal(scopeEqual({},{}),false);
assert.equal(scopeEqual(scope,{...scope,account:'ignored-legacy-field'}),true);
assert.equal(createMemory(scope).schema,2);
console.log('No-account upgrade passed: seventh round, paused submission, exact evidence, idempotence and four-part isolation.');
