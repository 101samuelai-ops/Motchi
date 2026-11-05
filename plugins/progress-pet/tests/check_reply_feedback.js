/* Execute the shipped UI functions with a virtual clock and minimal DOM. */
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(require('path').join(__dirname,'../android/app/src/main/assets/app.js'),'utf8');
const elements=new Map(),timers=new Map();let now=0,next=1;
function node(id){if(!elements.has(id))elements.set(id,{textContent:'',hidden:true,style:{},attrs:{},
 classList:{add(){},remove(){}},setAttribute(k,v){this.attrs[k]=v;},
 querySelector(){return node(id+'-summary');}});return elements.get(id);}
const context={console,Date:{now:()=>now},wakeState:{language:'auto'},pendingReply:null,replyTimer:null,
 voiceReplyPending:false,wakeUntil:0,waveFrame:null,microphoneLevel:0,waveLevel:0,
 state:{},selected:null,selection:null,renderWorkDraft(){},prepareWork(){},
 document:{querySelector:()=>node('companion'),querySelectorAll:()=>[]},$:node,
 setInterval(fn){const id=next++;timers.set(id,fn);return id;},clearInterval:id=>timers.delete(id),
 cancelAnimationFrame(){},clear:n=>{n.textContent='';return n;}};
vm.createContext(context);
for(const name of ['stopReply','replyFeedback','startReply','resetAssessment','companion','showAnswer','stopWave','voiceProcessing']){
 const start=source.indexOf(' function '+name+'('),end=source.indexOf('\n function ',start+2);
 assert(start>=0&&end>start,name+' exists in shipped UI');vm.runInContext(source.slice(start,end),context);
}
function advance(ms){now+=ms;[...timers.values()].forEach(fn=>fn());}
context.voiceProcessing('项目还有哪些没完成？','first');
assert(node('greeting').textContent==='问题已收到');
assert(node('companion-finish').hidden&&node('reply-status').textContent.includes('准备回答'));
advance(4000);assert(node('reply-status').textContent.includes('4 秒'));
advance(4000);assert(node('reply-status').textContent.includes('整理回答'));
assert.equal(timers.size,1);
context.voiceProcessing('项目还有哪些没完成？','first');
assert.equal(context.pendingReply.at,0,'Repeated processing events do not restart the wait clock');
context.showAnswer({scope:'project',text:'One device check remains.'},'What remains?');
assert(node('reply-status').hidden&&timers.size===0);
advance(8000);assert.equal(node('voice-live-reply').textContent,'One device check remains.');
context.startReply('old','Old question',false);context.startReply('new','New question',false);
assert.equal(context.stopReply('old'),false,'Old request completion cannot stop the new request feedback');
assert.equal(context.pendingReply.id,'new');advance(4000);
assert(node('reply-status').textContent.includes('4s elapsed'));
context.stopReply('new');assert.equal(timers.size,0);
context.wakeState.language='zh';context.startReply('cancelled','问题',true);context.stopReply();
advance(5000);assert(node('reply-status').hidden,'Cancelled feedback stays stopped');
console.log('Reply feedback: bilingual cadence, repeated events, final answer, cancellation and replacement passed');
