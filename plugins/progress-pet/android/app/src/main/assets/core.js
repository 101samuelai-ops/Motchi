(function(root){
 'use strict';
 function normalize(text){return String(text||'').toLowerCase().replace(/[’']s\b/g,'').replace(/[’']/g,'').replace(/[^a-z0-9\u0080-\uffff]+/g,' ').trim();}
 function projectRoute(text,projects){
  var query=' '+normalize(text)+' ';
  var matches=projects.filter(function(p){return [p.name].concat(p.aliases||[]).some(function(name){var alias=normalize(name);if(!alias)return false;if(/[\u3400-\u9fff]/.test(alias))return query.indexOf(alias)>=0;var separated=query.replace(/([a-z0-9])([\u3400-\u9fff])/g,'$1 $2').replace(/([\u3400-\u9fff])([a-z0-9])/g,'$1 $2');return separated.indexOf(' '+alias+' ')>=0;});});
  return {project:matches.length===1?matches[0]:null,choices:matches.length?matches:projects};
 }
 function progress(p){var v=p&&p.progress||{};return v.percent==null?'Progress unknown':v.completed+' of '+v.total+' tasks · '+v.percent+'%';}
 function stale(snapshot,online,now){return !online||!snapshot||!snapshot.updatedAt||(now||Date.now())/1000-snapshot.updatedAt>120;}
 function reviewStatus(checklist,online){
  var c=checklist||{},coverage=c.coverage||{};
  if(!online)return 'Offline · showing saved checkmarks';
  if(c.mode!=='automatic')return 'Update Motchi on the Mac to enable automatic task matching';
  if(c.issue)return 'Conversation review paused · retrying on the Mac';
  if(c.syncing||c.pendingMatches)return 'Reviewing conversation · matching tasks and completion evidence';
  if(coverage.pending)return 'Automatic updates on · catching up on '+coverage.pending+' history sections';
  return 'Automatic updates on · same tasks matched, completed work checked';
 }
 function identity(){var a=new Uint32Array(4);if(root.crypto&&root.crypto.getRandomValues){root.crypto.getRandomValues(a);return 'op-'+Array.prototype.map.call(a,function(n){return n.toString(16);}).join('-');}return 'op-'+Date.now()+'-'+Math.random().toString(36).slice(2);}
 var api={normalize:normalize,projectRoute:projectRoute,progress:progress,stale:stale,identity:identity,reviewStatus:reviewStatus};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MotchiCore=api;
})(typeof window!=='undefined'?window:globalThis);
