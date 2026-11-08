const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {createMemory, saveMemoryAnswer, sealMemoryPaper, applyMemoryGrade, confirmedAnswers, failedAnswers,
  answerKey, memoryDefinition, fillValues, exactIndices, streak, appendOutbox, acknowledgeOutbox, submittedEchoMatches} = require('../zhihuishu-mastery.user.js');

const scope = {task:'task-1', course:'1', cls:'2', point:'3'};
const memory = createMemory(scope);
const definition = memoryDefinition({content:'题干 <code>a  b</code>', questionTypeName:'单选题', optionVos:[{content:'A'},{content:'B'}]}, ['A','B'], []);
const fingerprint = createHash('sha256').update(JSON.stringify(definition)).digest('hex');
const save = (id, round, answers, fp=fingerprint, def=definition) => {
  saveMemoryAnswer(memory,{id,key:`paper:${id}`,round},{id:'q1',fingerprint:fp,definition:def,answers,kind:'choice',source:'ai'});
  sealMemoryPaper(memory,id,1,round*100);
};
const grade = (id, row, digest=id, context={}) => applyMemoryGrade(memory,
  {scope,submissionId:id,key:`paper:${id}`,requestedAt:10000,...context}, [{id:'q1',solution:null,feedback:'仅本题反馈',...row}],digest);

save('old',1,['A']);
save('new',2,['B']);
grade('old',{verdict:'wrong'});
assert.deepEqual(failedAnswers(memory.questions[fingerprint]).map(e=>e.answers),[['A']], 'Old grading belongs to the immutable old answer, never the latest B');
grade('new',{verdict:'correct'});
assert.deepEqual(confirmedAnswers(memory.questions[fingerprint]),['B']);
assert.equal(grade('new',{verdict:'correct'}).duplicate,true);
assert.equal(memory.rounds.length,2);
assert.equal(streak(memory.rounds),1);
assert.equal(grade('new',{verdict:'correct',feedback:'补充题目解析'}).duplicate,true);
assert.equal(memory.rounds.length,2);
assert(memory.papers.new.feedback.q1.feedback.includes('补充题目解析'));
const clone=JSON.stringify(memory);
assert.equal(grade('new',{verdict:'wrong'},'unrelated',{scope:{...scope,course:'another-course'}}).accepted,false);
assert.equal(JSON.stringify(memory),clone);
assert.equal(grade('new',{verdict:'wrong'},'unrelated',{scope:{...scope,task:'another-task'}}).accepted,false);
assert.equal(grade('new',{verdict:'wrong'},'unrelated',{scope:{...scope,point:'another-point'}}).accepted,false);
assert.equal(grade('old',{verdict:'wrong'},'too-early',{requestedAt:0}).accepted,false);
// A late old failure cannot deny a newer verified correct answer of the same version.
save('same-answer-old',3,['A']);
save('same-answer-new',4,['A']);
grade('same-answer-new',{verdict:'correct'});
grade('same-answer-old',{verdict:'wrong'});
assert.deepEqual(confirmedAnswers(memory.questions[fingerprint]),['A']);
assert.equal(memory.questions[fingerprint].answers[answerKey(['A'],'choice')].evidence['same-answer-old:q1:submitted'].verdict,'wrong');
// A newer real contradiction is attached to that submission and needs correction.
save('new-contradiction',5,['A']);grade('new-contradiction',{verdict:'wrong'});
assert.deepEqual(confirmedAnswers(memory.questions[fingerprint]),['B']);
assert.equal(failedAnswers(memory.questions[fingerprint]).length,1, 'Failures deduplicate by exact answer');
save('round-six',6,['B']);grade('round-six',{verdict:'correct'});
save('round-seven',7,['A']);grade('round-seven',{verdict:'wrong'});
assert.equal(Object.keys(memory.papers).length,7);
assert.deepEqual(confirmedAnswers(memory.questions[fingerprint]),['B']);
assert.equal(failedAnswers(memory.questions[fingerprint]).length,1,'Seventh round retains both correct and failed evidence');
assert.equal(failedAnswers({answers:{a:{values:['A'],evidence:{newest:{round:7,verdict:'wrong',feedback:'newest feedback'},
    lateOld:{round:1,verdict:'wrong',feedback:'late old feedback'}}}}})[0].feedback,'newest feedback');
const roundCount=memory.rounds.length;
grade('round-seven',{verdict:'wrong'});
assert.equal(memory.rounds.length,roundCount);
const changed = memoryDefinition({content:'完全不同的题干',questionTypeName:'单选题',optionVos:[{content:'A'},{content:'B'}]},['A','B'],[]);
assert.notEqual(JSON.stringify(changed),JSON.stringify(definition));
const reordered = memoryDefinition({content:'题干 <code>a  b</code>',questionTypeName:'单选题',optionVos:[{content:'B'},{content:'A'}]},['B','A'],[]);
assert.deepEqual(reordered,definition);
assert.deepEqual(exactIndices(['B','A'],['B'],false),[0]);
assert.deepEqual(fillValues(['  int X = 2;  '],1),['  int X = 2;  ']);
assert.equal(submittedEchoMatches({kind:'choice',answers:['B'],optionIds:{10:'A',11:'B'}},[{answer:'10',isCorrect:0}]),false);
assert.equal(submittedEchoMatches({kind:'choice',answers:['B'],optionIds:{10:'A',11:'B'}},[{answer:'11',isCorrect:1}]),true);
assert.equal(submittedEchoMatches({kind:'blank',answers:['  int X = 2;  ']},[{answer:'int X = 2;'}]),false);
assert.equal(submittedEchoMatches({kind:'blank',answers:['  int X = 2;  ']},[{answer:'  int X = 2;  '}]),true);
assert.equal(submittedEchoMatches({kind:'blank',answers:['x']},[{isCorrect:0}]),null);
const differentOptionSpace = memoryDefinition({content:definition.content,questionTypeName:'单选题',optionVos:[{content:'A '},{content:'B'}]},['A','B'],[]);
assert.notDeepEqual(differentOptionSpace,definition);
const blanks=memoryDefinition({content:'<input> + <input>',questionTypeName:'填空题'},[],[['INPUT','text',false],['INPUT','text',false]]);
assert.notDeepEqual(blanks,memoryDefinition({content:'<input> - <input>',questionTypeName:'填空题'},[],blanks.blanks));
// Missing question/version linkage never writes answers.
save('mismatch',8,['A']);
const before=JSON.stringify(memory.questions);
grade('mismatch',{verdict:'correct',solution:['A'],definitionMismatch:true});
assert.equal(JSON.stringify(memory.questions),before);
// A second, contradictory result for the same immutable submission is not accepted as a new truth.
const beforeConflict=JSON.stringify(memory.questions);
assert.equal(grade('new',{verdict:'wrong'},'contradicting-same-result').conflicts,1);
assert.equal(JSON.stringify(memory.questions),beforeConflict);
// Reloading an older result can fill a previously missing reference for the
// same verdict, without accepting a contradiction or opening another paper.
save('enriched',9,['A']);
grade('enriched',{verdict:'wrong'},'before-reference');
assert.equal(grade('enriched',{verdict:'wrong',solution:['B']},'with-reference').conflicts,0);
assert.deepEqual(memory.papers.enriched.feedback.q1.solution,['B']);
assert.equal(grade('enriched',{verdict:'wrong',solution:['A']},'different-reference').conflicts,1);
assert.equal(grade('enriched',{verdict:'wrong',solution:['A']},'different-reference').conflicts,1,'Reload must keep the conflict hold');

const event=n=>({documentId:'page-a',seq:n,time:'test',event:'answer.saved',data:{source:'ai'}});
let outbox=appendOutbox(null,Array.from({length:9},(_,i)=>event(i+1)),{count:5,bytes:4096});
assert.equal(outbox.events.length,5);assert.equal(outbox.dropped,4);
const sent=outbox.events.slice(0,2);
outbox=appendOutbox(outbox,[{...event(1),documentId:'page-b'}],{count:6,bytes:4096});
outbox=acknowledgeOutbox(outbox,sent,123);
assert.equal(outbox.events.length,4);assert.equal(outbox.lastDeliveredAt,123);
assert(outbox.events.some(e=>e.documentId==='page-b'));
const unconfirmed=JSON.stringify(outbox);
// Offline/failure has no acknowledgement and removes nothing.
assert.equal(JSON.stringify(outbox),unconfirmed);
outbox=appendOutbox(outbox,[{...event(999),data:{source:'x'.repeat(1000)}}],{count:100,bytes:500});
assert(new TextEncoder().encode(JSON.stringify(outbox.events)).length<=500);
assert(outbox.dropped>4);
console.log('Point memory passed: exact submission binding, late/duplicate/conflicting grading, seven-round retention, version/option/blank checks, whitespace and bounded acknowledged outbox.');
