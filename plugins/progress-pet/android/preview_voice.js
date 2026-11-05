/* Local Mac test transport. No pairing token or microphone audio enters the page. */
(function(){
 'use strict';
 var nonce=document.querySelector('meta[name="motchi-preview"]').content,turn='',revision=0,audio=null,audioUrl=null,speaking=false,playback=null;
 function request(action,extra){var controller=new AbortController(),timeout=setTimeout(function(){controller.abort();},15000);return fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Motchi-Preview':nonce},body:JSON.stringify(Object.assign({action:action},extra||{})),cache:'no-store',signal:controller.signal}).then(function(response){return response.json();}).then(function(result){if(!result.ok)throw new Error(result.error||'Mac unavailable.');return result.data;}).catch(function(error){throw new Error(error.name==='AbortError'?'The Mac connection timed out. Please reconnect.':error.message);}).finally(function(){clearTimeout(timeout);});}
 // Send completion immediately, even if an earlier start acknowledgement is
 // slow. Exact, single-use tickets make a late start harmless on the Mac.
 function reportPlayback(value,identity){if(!identity)return;return request('voiceInfo',Object.assign({speaking:value},identity)).catch(function(){});}
 function stop(){revision++;if(audio){audio.pause();audio.src='';audio=null;}if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null;}if(playback)reportPlayback(false,playback);speaking=false;playback=null;}
 function play(event){stop();var ticket=revision,eventTurn=event.turnId,identity={playbackTurnId:eventTurn,playbackOperationId:event.operationId};return request('voiceAudio',{id:event.operationId}).then(function(result){if(ticket!==revision||eventTurn&&eventTurn!==turn)return;if(!result.wav){reportPlayback(false,identity);return;}var raw=atob(result.wav),bytes=new Uint8Array(raw.length);for(var i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);audioUrl=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));audio=new Audio(audioUrl);var current=audio;speaking=true;playback=identity;reportPlayback(true,playback);audio.onended=function(){if(audio===current)stop();};audio.onerror=function(){if(audio===current)stop();};return audio.play().catch(function(){if(audio===current)stop();});}).catch(function(){if(ticket===revision){stop();reportPlayback(false,identity);}});}
 window.callNative=function(action,extra){extra=extra||{};
  if(action==='listenNow'||action==='wakeListening'&&!extra.enabled)stop();
  if(action==='voiceInfo')extra=Object.assign({},extra,{speaking:speaking},playback||{});
  if(action==='voiceEvents')return request(action,extra).then(function(result){var visible=[];(result.events||[]).forEach(function(event){if(event.turnId&&turn&&event.turnId!==turn)return;if(event.stopPlayback||!event.audioOnly&&!event.partial&&!event.processing)stop();if(event.spokenReply)play(event);if(!event.audioOnly)visible.push(event);});return {events:visible};});
  return request(action,extra).then(function(result){if(action==='voiceInfo'||action==='listenNow'||action==='wakeListening'||action==='finishVoice'){if(result.turnId&&result.turnId!==turn){turn=result.turnId;stop();}result.speaking=speaking||result.speaking===true;}return result;});
 };
 window.addEventListener('pagehide',function(){stop();fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Motchi-Preview':nonce},body:JSON.stringify({action:'releaseVoice'}),keepalive:true}).catch(function(){});});
})();
