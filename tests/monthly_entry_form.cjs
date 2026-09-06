// Verify that editing uses the occurrence date, and add mode is fully reset.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {};
const entry = {id:7, description:'April only', category_id:4, amount:75,
  entry_date:'2026-04-15', source_entry_date:'2026-01-31', person_id:3,
  recurring_monthly:true, entry_type:'expense'};
const form = {dataset:{monthEnd:'2026-04-30'}, month:{value:'2026-04'},
  description:{}, category_id:{}, amount:{}, entry_date:{}, person_id:{}, recurring_monthly:{},
  querySelector:()=>({}), reset:()=>{}};
const dialog = {addEventListener:(name,fn)=>{handlers[name]=fn;},showModal:()=>{handlers.opened=true;}};
const nodes = {entryForm:form, entryDialog:dialog, entryRepeat:{}, entryMonthNote:{}, entryTitle:{}, entrySubmit:{}};
const button = {dataset:{entry:JSON.stringify(entry)},addEventListener:(_,fn)=>{handlers.edit=fn;}};
const document = {body:{dataset:{}}, querySelector:()=>null, getElementById:id=>nodes[id] || null,
  querySelectorAll:selector=>selector==='.edit'?[button]:[]};
vm.runInNewContext(fs.readFileSync('static/app.js','utf8'),{document, window:{addEventListener:()=>{}}});
handlers.edit();
assert.equal(form.entry_date.value,'2026-04-15');
assert.equal(form.entry_date.min,'2026-04-01');
assert.equal(form.entry_date.max,'2026-04-30');
assert.equal(form.recurring_monthly.disabled,true);
assert.equal(nodes.entryMonthNote.hidden,false);
assert.equal(nodes.entryRepeat.hidden,true);
handlers.close();
assert.equal(form.action,'/entries');
assert.equal(form.entry_date.min,'');
assert.equal(form.entry_date.max,'');
assert.equal(form.recurring_monthly.disabled,false);
assert.equal(nodes.entryRepeat.hidden,false);
assert.equal(nodes.entryMonthNote.hidden,true);
console.log('Occurrence edit and add-form reset checks passed.');
