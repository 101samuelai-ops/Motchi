/* Exercise the shipped native popup while a real request card is pending. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../skills/completion-pet/scripts/dialog.html'),'utf8');
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,value:0});return nodes.get(id);}
const context={desktopVoiceState:{},desktopVoiceEvent:null,processingSince:0,
 current:()=>({questions:[{id:'pending-user-question'}]}),busy:()=>false,$:node,Date,
 document:{body:{dataset:{},classList:{toggle(){}}}}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function renderPetSpeech(){'),html.indexOf("$('desktopMic').onclick")),context);
context.desktopVoiceState={enabled:true,running:true,stage:'listening',rms:900};
context.desktopVoiceEvent={partial:true,transcript:'莫奇，项目还有什么没完成？',text:'I’m listening.'};
context.renderPetSpeech();
assert(!node('voiceCaption').hidden&&node('voiceCaption').textContent.includes('项目'),'Pending questions cannot suppress live captions');
assert(!node('voiceInput').hidden&&node('voiceLevel').value===.5,'Active capture shows the real sound level');
assert(!node('desktopFinish').hidden,'An active question retains a manual fallback');
context.desktopVoiceState.stage='processing';context.renderPetSpeech();
assert(node('greeting').textContent.includes('回答你')&&node('voiceInput').hidden,'Processing speaks in the bubble even with pending attention');
context.desktopVoiceState.stage='answered';context.desktopVoiceEvent={text:'One check remains.',heard:'What remains?'};context.renderPetSpeech();
assert(node('greeting').textContent==='One check remains.'&&node('voiceCaption').textContent==='You · What remains?','Completed replies replace processing and retain the question');
context.desktopVoiceState={enabled:false};context.desktopVoiceEvent=null;context.renderPetSpeech();
assert(node('voiceInput').hidden&&node('voiceCaption').hidden&&node('desktopFinish').hidden,'Pause hides stale recording affordances');
console.log('6 desktop voice UI checks passed');
