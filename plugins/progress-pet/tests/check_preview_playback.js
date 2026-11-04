/* Runs the shipped transport: exact playback completion, errors and replacement. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../android/preview_voice.js'),'utf8');
let calls=[],events=[],turn='first-turn',players=[],denied=false,missing=false,holdStart=false,releaseStart;
class Audio {
 constructor(url){this.src=url;players.push(this);}
 play(){return denied?Promise.reject(new Error('autoplay denied')):Promise.resolve();}
 pause(){this.paused=true;}
}
const window={addEventListener(){}};
const context={window,document:{querySelector:()=>({content:'test-nonce'})},Audio,AbortController,
 setTimeout,clearTimeout,Blob,Uint8Array,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
 atob:x=>Buffer.from(x,'base64').toString('binary'),
 fetch:async (url,options)=>{
  const body=JSON.parse(options.body);calls.push(body);
  let data={};
  if(body.action==='voiceInfo'){
   data={enabled:true,turnId:turn};
   if(holdStart&&body.speaking===true)await new Promise(resolve=>{releaseStart=resolve;});
  }
  if(body.action==='voiceAudio')data=missing?{}:{wav:Buffer.from('RIFFtest').toString('base64')};
  if(body.action==='voiceEvents'){data={events};events=[];}
  return {json:async()=>({ok:true,data})};
 }};
vm.runInNewContext(source,context);
const flush=async()=>{for(let i=0;i<15;i++)await new Promise(resolve=>setImmediate(resolve));};
const receipt=(id,value)=>calls.filter(c=>c.action==='voiceInfo'&&c.playbackOperationId===id&&c.speaking===value);
let checks=0;
function check(value,label){assert.ok(value,label);checks++;}
async function play(id){events=[{wake:true,audioOnly:true,spokenReply:true,turnId:turn,operationId:id}];await window.callNative('voiceEvents');await flush();}
(async()=>{
 await window.callNative('voiceInfo');await play('answer-one');
 check(receipt('answer-one',true).length===1,'Starting audio reports its exact turn and operation');
 let heartbeat=await window.callNative('voiceInfo');
 check(heartbeat.speaking&&calls.at(-1).playbackTurnId===turn,'Playback polling retains exact identity');
 players.at(-1).onended();await flush();
 check(receipt('answer-one',false).length===1,'Natural audio completion immediately releases microphone muting');
 holdStart=true;await play('answer-slow-start');players.at(-1).onended();await flush();
 check(receipt('answer-slow-start',false).length===1,
       'Completion is sent without waiting for a delayed playback-start acknowledgement');
 holdStart=false;releaseStart();await flush();
 await play('answer-two');players.at(-1).onerror();await flush();
 check(receipt('answer-two',false).length===1,'Audio failure also releases microphone muting');
 denied=true;await play('answer-denied');denied=false;
 check(receipt('answer-denied',false).length===1,'Blocked autoplay cannot strand follow-up capture');
 missing=true;await play('answer-missing');missing=false;
 check(receipt('answer-missing',false).length===1,'Missing audio falls back to text and releases capture');
 await play('old-answer');const old=players.at(-1);
 turn='second-turn';await window.callNative('voiceInfo');await flush();
 await play('current-answer');const current=players.at(-1);old.onended();await flush();
 check(!current.paused,'An obsolete playback callback cannot stop the next answer');
 check(receipt('old-answer',false).every(c=>c.playbackTurnId==='first-turn'),
       'Replacement receipts keep the old turn identity');
 await window.callNative('listenNow');await flush();
 check(current.paused&&receipt('current-answer',false).length===1,'Explicit Talk stops and acknowledges current audio');
 console.log(`${checks} actual preview playback completion and replacement checks passed`);
})().catch(error=>{console.error(error);process.exitCode=1;});
