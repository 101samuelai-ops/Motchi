/* Exercise shipped popup rendering, including attention, replay and routing. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../skills/completion-pet/scripts/dialog.html'),'utf8');
const nodes=new Map();
function element(){return {textContent:'',hidden:false,value:0,dataset:{},children:[],scrollHeight:500,scrollTop:0,
 append(...children){this.children.push(...children)},replaceChildren(...children){this.children=children}};}
function node(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);}
const context={desktopVoiceState:{},desktopVoiceEvent:null,processingSince:0,
 voiceSelection:'project-a',voiceTurn:'',selected:'project-a',savedVoiceTurns:new Map(),conversations:new Map(),
 items:[{id:'project-a',questions:[{id:'pending-user-question'}]},{id:'project-b'}],
 current:()=>context.items.find(i=>i.id===context.selected),busy:()=>false,editing:()=>false,
 selectProject:key=>context.selected=key,send(){},autoFollow:true,$:node,Date,
 document:{body:{dataset:{},classList:{toggle(){}}},querySelector:node,createElement:element,createTextNode:text=>({textContent:text})}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function keepChatBottom(){'),html.indexOf('function renderChecklist(')),context);
vm.runInContext(html.slice(html.indexOf('function renderPetSpeech(){'),html.indexOf("$('desktopMic').onclick")),context);
let checks=0;function check(condition,message){assert(condition,message);checks++;}
context.desktopVoiceState={enabled:true,running:true,stage:'listening',rms:900};
context.receiveVoice({turnId:'one',partial:true,transcript:'莫奇，项目还有什么没完成？',text:'项目还有什么没完成？'});
context.renderPetSpeech();
check(!node('voiceCaption').hidden&&node('voiceCaption').textContent.includes('项目'),'Pending requests cannot suppress live captions');
check(!node('voiceInput').hidden&&node('voiceLevel').value===.5,'Active capture shows the real sound level');
check(!node('desktopFinish').hidden,'Active questions retain the manual fallback');
check(!node('greeting').textContent.includes('没完成'),'Partial speech is not repeated as Motchi’s answer');
check(context.conversations.size===0,'Partial recognition does not become permanent chat');
context.desktopVoiceState.stage='processing';context.renderPetSpeech();
check(node('greeting').textContent.includes('回答你')&&node('voiceInput').hidden,'Processing stays inside the conversation with pending attention');
context.desktopVoiceState.stage='answered';
const answer={turnId:'one',text:'One check remains.',heard:'What remains?',selection:'project-a'};
context.receiveVoice(answer);context.renderPetSpeech();
check(context.conversations.get('project-a').length===2,'Final speech creates one user/assistant pair');
check(node('liveSpeech').hidden&&node('voiceCaption').hidden,'Stored replies do not also appear as a duplicate live bubble');
context.receiveVoice(answer);
check(context.conversations.get('project-a').length===2,'Native event replay does not duplicate the answer');
context.receiveVoice({...answer,text:'Two checks remain.'});
check(context.conversations.get('project-a').length===2&&context.conversations.get('project-a')[1].text==='Two checks remain.','Same turn correction replaces the original pair');
context.receiveVoice({turnId:'two',partial:true,transcript:'What next?'});
context.receiveVoice({turnId:'two',heard:'What next?',text:'Test the microphone.',selection:'project-a'});
check(context.conversations.get('project-a').length===4,'The next voice question preserves the previous conversation');
context.receiveVoice({turnId:'three',partial:true,transcript:'How is project B?'});
context.receiveVoice({turnId:'three',heard:'How is project B?',text:'Project B is ready.',selection:'project-b'});
check(context.conversations.get('project-b').length===2&&context.conversations.get('project-a').length===4,'Explicit routing keeps replies in the right project');
check(context.selected==='project-a','Pending attention retains the current project');
context.renderPetSpeech();check(node('voiceCaption').hidden,'Other-project speech does not leak into the selected conversation');
context.receiveVoice({turnId:'unknown',heard:'Where?',text:'Unavailable.',selection:'missing'});
check(!context.conversations.has('missing')&&context.conversations.get('project-a').length===4,'An unavailable exact project cannot silently fall back');
node('chatScroll').dataset.reading='true';node('chatScroll').scrollTop=17;context.redrawMessages();
check(node('chatScroll').scrollTop===17,'Background refresh does not drag the user away from older messages');
context.desktopVoiceState={enabled:false};context.desktopVoiceEvent=null;context.renderPetSpeech();
check(node('voiceInput').hidden&&node('voiceCaption').hidden&&node('desktopFinish').hidden,'Pause hides stale recording affordances');
context.busy=()=>true;context.renderPetSpeech();
check(!node('liveSpeech').hidden&&node('greeting').textContent.includes('think'),'Typed questions use the same in-thread processing reply');
console.log(`${checks} desktop conversation checks passed`);
