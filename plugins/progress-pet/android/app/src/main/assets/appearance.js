/* Local presentation preferences; never changes project or connection identity. */
(function(root){
 'use strict';
 var layouts=[{id:'canvas',name:'Companion canvas',description:'A large companion above your project cards.'},{id:'studio',name:'Sidekick studio',description:'Motchi beside primary and secondary projects.'},{id:'lounge',name:'Bubble lounge',description:'A speech-bubble stage with two project columns.'}];
 var palettes={canvas:{light:['#f4f2e9','#fffef9','#293a2e','#617361','#d7dfcf','#486947'],dark:['#1c2520','#29362d','#edf3e9','#b0c0ad','#42513e','#bfdbac']},studio:{light:['#f1f3f7','#ffffff','#27364b','#66748a','#d8e0ed','#425e99'],dark:['#1b2331','#293447','#edf3ff','#b0bfd4','#42506a','#b4ccff']},lounge:{light:['#f4eef6','#fffafd','#48324e','#7a6480','#e5d7e9','#875292'],dark:['#281f2f','#392d42','#f9edff','#cbb3d3','#56415f','#e2b8ec']}};
 function hex(value){return typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value)?value.toLowerCase():null;}
 function style(value){value=value&&typeof value==='object'?value:{};return {layout:layouts.some(function(x){return x.id===value.layout;})?value.layout:'canvas',mode:['system','light','dark'].indexOf(value.mode)>=0?value.mode:'dark',background:hex(value.background),text:hex(value.text)};}
 function normalize(value){value=value&&typeof value==='object'?value:{};return Object.assign(style(value),{schema:value.schema===2?2:1,previousDesign:value.previousDesign&&typeof value.previousDesign==='object'?style(value.previousDesign):null,primaryIds:Array.isArray(value.primaryIds)?value.primaryIds.filter(function(x,i,a){return typeof x==='string'&&a.indexOf(x)===i;}).slice(0,1000):null,rotateGreetings:value.rotateGreetings!==false});}
 // This release adopts the requested reference once, retaining a restorable
 // appearance. Later launches and design changes keep the user's selection.
 function reference(value){var prefs=normalize(value);if(!prefs.previousDesign&&(prefs.layout!=='canvas'||prefs.mode!=='dark'||prefs.background||prefs.text))prefs.previousDesign=style(prefs);return Object.assign(prefs,{schema:2,layout:'canvas',mode:'dark',background:null,text:null});}
 function load(value){if(!value||typeof value!=='object')return Object.assign(normalize(),{schema:2});var prefs=normalize(value);return prefs.schema===2?prefs:reference(prefs);}
 function restore(value){var prefs=normalize(value);return Object.assign(prefs,prefs.previousDesign||{},{schema:2,previousDesign:null});}
 function rgb(colour){return colour.slice(1).match(/../g).map(function(x){return parseInt(x,16);});}
 function mix(a,b,weight){var x=rgb(a),y=rgb(b);return '#'+x.map(function(n,i){return ('0'+Math.round(n*(1-weight)+y[i]*weight).toString(16)).slice(-2);}).join('');}
 function luminance(colour){return rgb(colour).map(function(x){x/=255;return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4);}).reduce(function(sum,x,i){return sum+x*[.2126,.7152,.0722][i];},0);}
 function contrast(a,b){var x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
 function colours(value,darkSystem){var prefs=normalize(value),dark=prefs.mode==='dark'||prefs.mode==='system'&&darkSystem,base=palettes[prefs.layout][dark?'dark':'light'],bg=prefs.background||base[0],ink=prefs.text||base[2],adjusted=false;
  if(contrast(bg,ink)<4.5){ink=contrast(bg,'#18201b')>=4.5?'#18201b':'#f8faf7';adjusted=true;}
  var custom=!!(prefs.background||prefs.text),surface=custom?mix(bg,ink,.04):base[1],muted=custom?mix(ink,bg,.18):base[3];
  if(contrast(surface,ink)<4.5)surface=bg;
  if(contrast(surface,muted)<4.5)muted=ink;
  var light=luminance(bg)>.35,tones=light?{input:'#8b5100',active:'#2855ad',error:'#b52d40',done:'#206a3c',recent:'#53665e'}:{input:'#ffcd76',active:'#9cbeff',error:'#ffa3af',done:'#89dda6',recent:'#c3cec7'};
  var vars={'--paper':bg,'--white':surface,'--ink':ink,'--muted':muted,'--line':custom?mix(bg,ink,.22):base[4],'--accent':custom?ink:base[5],'--on-accent':contrast(custom?ink:base[5],'#ffffff')>=4.5?'#ffffff':'#18201b','--green':mix(bg,tones.done,.14),'--track':mix(bg,ink,.14),'--soft':mix(bg,ink,.06)};
  Object.keys(tones).forEach(function(key){var colour=tones[key],target=contrast(bg,'#000000')>contrast(bg,'#ffffff')?'#000000':'#ffffff',tint;
   for(var i=0;i<=10;i++){colour=mix(tones[key],target,i/10);tint=mix(bg,colour,.1);if(contrast(tint,colour)>=4.5&&contrast(surface,colour)>=4.5)break;}
   vars['--status-'+key]=colour;vars['--tint-'+key]=tint;
  });
  return {vars:vars,background:bg,text:ink,adjusted:adjusted};
 }
 function next(layout,step){var i=layouts.findIndex(function(x){return x.id===layout;});return layouts[((i<0?0:i)+step+layouts.length)%layouts.length].id;}
 function status(project){var progress=project.progress||{},chats=project.chats||[];
  if(project.needsInput)return {key:'input',label:'Needs your input',symbol:'?'};
  if(project.error||chats.some(function(c){return ['error','failed'].indexOf(c.status)>=0;}))return {key:'error',label:'Error',symbol:'!'};
  if(project.active)return {key:'active',label:'In progress',symbol:'◷'};
  if(progress.total>0&&progress.completed>=progress.total&&progress.percent!=null)return {key:'done',label:'Checklist complete',symbol:'✓'};
  return {key:'recent',label:progress.percent==null?'Progress unknown':'Recent',symbol:'·'};
 }
 function groups(projects,value){var prefs=normalize(value),ids=prefs.primaryIds===null?projects.slice(0,2).map(function(p){return p.id;}):prefs.primaryIds;return {primary:projects.filter(function(p){return ids.indexOf(p.id)>=0;}),secondary:projects.filter(function(p){return ids.indexOf(p.id)<0;})};}
 var api={layouts:layouts,normalize:normalize,load:load,reference:reference,restore:restore,colours:colours,next:next,status:status,groups:groups,contrast:contrast};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MotchiAppearance=api;
})(typeof window!=='undefined'?window:globalThis);
