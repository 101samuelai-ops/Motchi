var result=document.getElementById('result');
function show(value){result.textContent=typeof value==='string'?value:JSON.stringify(value,null,2);}
document.getElementById('pair').onclick=function(){callNative('pair',{ticket:document.getElementById('ticket').value}).then(function(){return callNative('snapshot');}).then(show).catch(function(e){show(e.message);});};
document.getElementById('mic').onclick=function(){callNative('startRecording').then(show).catch(function(e){show(e.message);});};
document.getElementById('stop').onclick=function(){callNative('stopRecording').then(show).catch(function(e){show(e.message);});};
callNative('info').then(show);
