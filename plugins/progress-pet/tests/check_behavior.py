import json, pathlib, subprocess, sys, tempfile, time, urllib.request, urllib.error
SCRIPT=pathlib.Path(__file__).resolve().parents[1] / 'skills/progress-pet/scripts/progress_pet.py'
checks=[]
def check(condition, label):
    assert condition,label
    checks.append(label)
def cli(folder,*args):
    result=subprocess.run([sys.executable,str(SCRIPT),'--project',folder,*args],capture_output=True,text=True,check=True)
    return json.loads(result.stdout)
with tempfile.TemporaryDirectory(prefix='progress-pet-test-') as project:
    check(cli(project,'status')['percent']==0,'Empty project is zero, with no fabricated tasks')
    for title in ['Build the pet','Calculate progress','Verify the project']:
        state=cli(project,'add',title)
    ids=[t['id'] for t in state['tasks']]
    check(cli(project,'done',ids[0])['percent']==33,'One of three is rounded to 33 percent')
    check(cli(project,'done',ids[1])['percent']==67,'Two of three is rounded to 67 percent')
    check(cli(project,'done',ids[2])['percent']==100,'Three of three reaches 100 percent')
    check(cli(project,'reopen',ids[0])['percent']==67,'Reopening a task reduces progress')
    proc=subprocess.Popen([sys.executable,str(SCRIPT),'--project',project,'serve','--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        url=proc.stdout.readline().strip().split()[-1]
        def request(path='/api/project', payload=None, headers=None):
            req=urllib.request.Request(url+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers or ({'Content-Type':'application/json'} if payload is not None else {}))
            try:
                with urllib.request.urlopen(req,timeout=5) as res:
                    return res.status,res.read(),dict(res.headers)
            except urllib.error.HTTPError as e:
                return e.code,e.read(),dict(e.headers)
        status,body,headers=request()
        state=json.loads(body)
        check(status==200 and state['percent']==67,'Server reads persisted CLI changes')
        code,body,_=request(payload={'action':'set_done','id':ids[0],'done':True,'revision':state['revision']})
        updated=json.loads(body)
        check(code==200 and updated['percent']==100,'Panel API completes tasks')
        code,_,_=request(payload={'action':'rename','name':'Lost update','revision':state['revision']})
        check(code==409,'Stale updates cannot overwrite newer changes')
        code,_,_=request(payload={'action':'add','title':'  ','revision':updated['revision']})
        check(code==400,'Blank tasks are rejected')
        code,_,_=request(payload={'action':'rename','name':'Bad origin','revision':updated['revision']},headers={'Content-Type':'application/json','Origin':'https://example.com'})
        check(code==403,'Other websites cannot modify local progress')
        code,_,_=request(headers={'Host':'example.com'})
        check(code==403,'Unexpected hosts are rejected')
        code,_,_=request('/../progress_pet.py')
        check(code==404,'Non-asset files cannot be served')
        code,html,headers=request('/')
        check(code==200 and b'Click Motchi' in html and "script-src 'self'" in headers['Content-Security-Policy'],'Pet page loads with a local-only asset policy')
        for asset in ['/app.js','/style.css']:
            check(request(asset)[0]==200,f'{asset} is available')
        check(cli(project,'status')['percent']==100,'Panel changes persist for later CLI sessions')
        path=pathlib.Path(project)/'.progress-pet.json'
        path.write_text('{invalid')
        code,_,_=request()
        check(code==500,'Invalid stored data is surfaced instead of silently reset')
        result=subprocess.run([sys.executable,str(SCRIPT),'--project',project,'add','Do not overwrite'],capture_output=True,text=True)
        check(result.returncode!=0 and path.read_text()=='{invalid','Invalid data is preserved on write failure')
    finally:
        proc.terminate()
        proc.wait(timeout=5)
print(f'{len(checks)} behavioral checks passed')
for item in checks: print('PASS',item)
