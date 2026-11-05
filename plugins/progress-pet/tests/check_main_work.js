/* Execute the shipped main-conversation draft and transport functions. */
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'../android/app/src/main/assets/app.js'),'utf8');
let nodes=new Map(),sent=[],confirmations=[],next=0;
function node(tag){return {tag,set id(value){nodes.set(value,this);},children:[],textContent:'',value:'',hidden:false,attrs:{},appendChild(n){this.children.push(n);return n;},setAttribute(k,v){this.attrs[k]=v;}};}
function $(id){if(!nodes.has(id))nodes.set(id,node(id));return nodes.get(id);}
const project={id:'alpha',name:'Alpha',selection:'a-chat',chats:[{id:'a-chat',title:'Active implementation',canSend:true,status:'active'},{id:'review',title:'Desktop review',canSend:false,status:'idle'}]};
const context={console,Date,Promise,Object,String,Number,C:{identity:()=>`operation-${++next}`},
 state:{operations:[],drafts:{}},snapshot:{projects:[project,{id:'beta',name:'Beta',selection:'b-chat',chats:[{id:'b-chat',title:'Beta implementation',canSend:true}]}]},
 selected:'alpha',selection:'a-chat',workControls:true,online:true,workOffer:null,$,
 el:(tag,text,cls)=>Object.assign(node(tag),{textContent:text||'',className:cls}),
 button:(text,fn,cls)=>Object.assign(node('button'),{textContent:text,onclick:fn,className:cls}),
 clear:n=>{n.children=[];n.textContent='';return n;},save(){},addMessage(){},renderOperations(){},connected(){return context.online;},
 confirmAction:(title,text,fn)=>confirmations.push({title,text,fn}),
 callNative:(action,payload)=>{if(action==='submit')sent.push(payload.request);return Promise.resolve(action==='submit'?{status:'queued'}:{status:'done',result:{text:'Codex accepted the additional instruction.',deliveryStatus:'accepted'}});},
 finishJob(o,job){o.status=job.status;o.result=job.result||{};},poll(o){return Promise.resolve(o);}
};
vm.createContext(context);
for(const name of ['prepareWork','syncWorkControls','renderWorkDraft','sendWorkDraft','submit']){
 const start=source.indexOf(' function '+name+'('),end=source.indexOf('\n function ',start+2);
 assert(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
}
function text(n){return n.textContent+' '+n.children.map(text).join(' ');}
(async()=>{
 context.prepareWork({text:'Add a smaller button',projectId:'alpha',selection:'a-chat'});
 assert.equal(sent.length,0,'Drafting never sends work');
 assert(text($('work-draft')).includes('ongoing task'));
 $('work-instruction').value='Add a smaller accessible button';$('work-instruction').oninput();
 context.selected='beta';context.selection='b-chat';
 context.sendWorkDraft();context.sendWorkDraft();await Promise.resolve();
 assert.equal(sent.length,1,'Double click cannot duplicate the operation');
 assert.equal(sent[0].projectId,'alpha');assert.equal(sent[0].selection,'a-chat');
 assert.equal(sent[0].text,'Add a smaller accessible button','The edited instruction reaches the original exact target after a UI switch');
 context.state.operations[0].status='uncertain';context.renderWorkDraft();
 assert(text($('work-draft')).includes('not be sent again automatically'));
 context.sendWorkDraft();assert.equal(sent.length,1,'Uncertain delivery cannot be replayed by Send');
 context.prepareWork({text:'Fix this layout',projectId:'alpha',selection:'review'});context.sendWorkDraft();
 assert.equal(sent.length,1,'Tracked chat requires confirmation');
 assert(confirmations[0].text.includes('new connected chat'));
 context.selected='beta';confirmations[0].fn();await Promise.resolve();
 assert.equal(sent[1].action,'start');assert.equal(sent[1].projectId,'alpha');assert(sent[1].confirmed);
 context.prepareWork({text:'Add export',projectId:'alpha',selection:'a-chat'});context.workControls=false;context.sendWorkDraft();
 assert.equal(sent.length,2,'Read-only preview cannot send even through a direct handler call');
 context.workControls=true;context.online=false;context.sendWorkDraft();assert.equal(sent.length,2,'Offline work remains an editable draft');
 context.syncWorkControls();assert($('work-send').disabled);
 context.online=true;context.syncWorkControls();assert(!$('work-send').disabled,'Reconnecting enables a restored draft without replacing edited input');
 context.online=true;context.prepareWork({text:'Add export',projectId:'alpha',selection:'missing'});context.sendWorkDraft();
 assert.equal(sent.length,2,'Missing or stale chat never silently changes destination');
 context.prepareWork({text:'Fix duplicate submission',projectId:'alpha',selection:'a-chat'});context.sendWorkDraft();await Promise.resolve();
 const request=sent.at(-1);await context.submit('send',request.text,request);
 assert.equal(sent.length,3,'Existing stable operation is checked, never resubmitted by the UI');
 context.prepareWork({text:'Add tests to all projects',projectId:null,selection:null});
 assert.equal(context.state.workDraft.projectId,'','An ambiguous/macro proposal never adopts an old selected project');
 console.log('Main conversation work controls: inert draft, edited exact target, confirmation, receipts, duplicate and offline checks passed');
})().catch(e=>{console.error(e);process.exit(1);});
