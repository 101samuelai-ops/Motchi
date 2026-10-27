/* Native-only transport. No remote content is loaded into this WebView. */
(function(){
 var pending={},sequence=0;
 window.nativeReply=function(id,raw){var item=pending[id];if(!item)return;delete pending[id];var result=JSON.parse(raw);result.ok?item.resolve(result.data):item.reject(new Error(result.error||'Mac unavailable.'));};
 window.nativeEvent=function(name,raw){document.dispatchEvent(new CustomEvent(name,{detail:JSON.parse(raw)}));};
 window.callNative=function(action,extra){return new Promise(function(resolve,reject){var id='native-'+Date.now()+'-'+(++sequence);pending[id]={resolve:resolve,reject:reject};try{MotchiNative.request(id,JSON.stringify(Object.assign({action:action},extra||{})));}catch(e){delete pending[id];reject(new Error('Open the installed Motchi app to connect.'));}});};
})();
