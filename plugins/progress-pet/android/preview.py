#!/usr/bin/env python3
"""Loopback-only Android UI preview with illustrative projects and no Mac credentials."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time

ASSETS = Path(__file__).parent / 'app/src/main/assets'

def project(identity, name, titles, complete, status):
    tasks = [{'id':identity+'-'+str(n), 'title':title, 'done':n<complete} for n,title in enumerate(titles)]
    return {'id':identity, 'name':name, 'folderLabel':'Sample projects/'+name, 'aliases':[name],
            'selection':'chat-'+identity, 'active':status=='active', 'needsInput':status=='input',
            'updatedAt':time.time(), 'progress':{'tasks':tasks,'total':len(tasks),'completed':complete,
            'percent':round(100*complete/len(tasks)) if tasks else None,'revision':1},
            'chats':[{'id':'chat-'+identity,'title':'Project discussion','status':'active' if status=='active' else 'idle','canSend':False}],
            'comments':[], 'questions':[], 'attention':[],
            'checklist':{'mode':'automatic','coverage':{'reviewed':24,'total':24,'chats':2,'lastReviewedAt':time.time()},'matches':[], 'changes':[], 'revision':1}}

PROJECTS = [project('motchi','Motchi',['Project dashboard','Automatic task matching','Check off completed work','Review on the calendar'],2,'active'),
            project('website','Portfolio',['Choose page layout','Build responsive pages','Review typography','Publish the site'],2,'input'),
            project('reading','Reading room',[],0,'idle'),
            project('notes','Notes app',['Build the editor','Save notes locally','Verify recovery'],3,'done')]
TRANSPORT = r'''
(function(){
 var projects=__PROJECTS__,jobs={};
 function update(p){p.progress.total=p.progress.tasks.length;p.progress.completed=p.progress.tasks.filter(function(t){return t.done;}).length;p.progress.percent=p.progress.total?Math.round(p.progress.completed/p.progress.total*100):null;p.progress.revision++;p.checklist.revision=p.progress.revision;p.updatedAt=Date.now()/1000;}
 window.previewCompletion=function(){var p=projects[0],t=p.progress.tasks[2];if(t.done||t.manualOverride)return;p.checklist.syncing=true;setTimeout(function(){t.done=true;t.evidence={kind:'Sample chat update',quote:'Automatic check-off is implemented and its checks passed.',at:Date.now()/1000,chat:p.selection};p.checklist.syncing=false;p.checklist.lastLiveReviewedAt=Date.now()/1000;p.checklist.changes.unshift({id:'sample-complete',kind:'complete',title:t.title,taskId:t.id,reason:'The sample assistant update confirms completion.',evidence:t.evidence,canUndo:true});p.checklist.matches=[{title:'Recognize finished tasks',decision:'same',reason:'Same completion outcome as the existing task.',evidence:t.evidence}];update(p);},1800);};
 document.getElementById('preview-completion').addEventListener('click',window.previewCompletion);
 window.callNative=function(action,extra){extra=extra||{};
  if(action==='info')return Promise.resolve({paired:true});
  if(action==='snapshot')return Promise.resolve(JSON.parse(JSON.stringify({projects:projects,updatedAt:Date.now()/1000,speechAvailable:false})));
  if(action==='job')return Promise.resolve(jobs[extra.id]||{status:'failed',result:{error:'No sample receipt.'}});
  if(action==='quickAccessInfo')return Promise.resolve({enabled:false,visible:false,canPinShortcut:false});
  if(action==='submit'){var r=extra.request,p=projects.find(function(x){return x.id===r.projectId;});if(!p)return Promise.reject(new Error('Choose a sample project.'));
   var text='Sample answer: '+p.progress.completed+' of '+p.progress.total+' checklist tasks are complete. ';
   if(r.action==='comment'){p.comments.unshift({text:r.text,at:Date.now()/1000});text='Sample comment saved in this preview.';}
   else if(r.action==='toggle'){var t=p.progress.tasks.find(function(x){return x.id===r.taskId;});if(t){t.done=r.done;t.manualOverride=true;update(p);}text='Sample checkmark updated.';}
   else if(r.action==='undo'){var t=p.progress.tasks[2];t.done=false;t.manualOverride=true;p.checklist.changes[0].canUndo=false;p.checklist.changes[0].undone=true;update(p);text='Sample completion undone; manual correction is protected.';}
   else if(r.action!=='ask')return Promise.reject(new Error('Work submissions are disabled in the preview. Use the paired Android app.'));
   return Promise.resolve(jobs[r.operationId]={status:'done',result:{text:text}});
  }
  return Promise.reject(new Error('Use the installed Android app for this device feature.'));
 };
})();
'''.replace('__PROJECTS__',json.dumps(PROJECTS))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=0)
    p.add_argument('--apk',type=Path)
    args=p.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route=self.path.split('?')[0]
            if route=='/Motchi.apk' and args.apk and args.apk.is_file():
                content=args.apk.read_bytes();mime='application/vnd.android.package-archive'
            else:
                name='index.html' if route=='/' else route.lstrip('/')
                if name not in {'index.html','app.js','app.css','appearance.css','appearance.js','native.js','core.js','dog.svg'}:
                    self.send_error(404);return
                content=TRANSPORT.encode() if name=='native.js' else (ASSETS/name).read_bytes()
                if name=='index.html':
                    banner='<div class="preview-banner">Android 0.14 preview · Sample data &nbsp; <button id="preview-completion">Try automatic completion</button>'
                    if args.apk:banner+=' &nbsp; <a href="/Motchi.apk" download="Motchi-0.14.0.apk">Download Android APK</a>'
                    content=content.replace(b'<body>',('<body>'+banner+'</div>').encode())
                if name=='app.css':content+=b'\n.preview-banner{padding:12px 24px;background:#203b39;color:white;font:14px system-ui;display:flex;gap:12px;align-items:center;flex-wrap:wrap}.preview-banner a{color:white}.preview-banner button{padding:8px 12px}\n'
                mime='text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'image/svg+xml' if name.endswith('.svg') else 'application/javascript'
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print('http://127.0.0.1:'+str(server.server_port)+'/',flush=True)
    server.serve_forever()
if __name__=='__main__':main()
