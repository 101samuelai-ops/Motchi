"""The local approval endpoint rejects cross-origin and form submissions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

script=Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts/dog_bridge.py'
checks=[]
def check(value,label):
 assert value,label
 checks.append(label)
with tempfile.TemporaryDirectory() as project:
 proc=subprocess.Popen([sys.executable,str(script),'--project',project,'--preview-server'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                       env={**os.environ,'MOTCHI_HISTORY_DIR':str(Path(project)/'private-history')})
 try:
  base=proc.stdout.readline().strip().split()[-1].rstrip('/')
  def request(path='/control',headers=None,value=None,method='POST'):
   body=json.dumps(value or {'action':'decideApproval','selection':'unowned','approvalId':'stale','decision':'allow'}).encode() if method=='POST' else None
   req=urllib.request.Request(base+path,data=body,headers=headers or {},method=method)
   try:
    with urllib.request.urlopen(req,timeout=3) as response:return response.status,response.read()
   except urllib.error.HTTPError as e:return e.code,e.read()
  check(request(headers={'Content-Type':'application/json','Origin':'https://other.example'})[0]==403,'Another website cannot send a Motchi approval')
  check(request(headers={'Content-Type':'application/x-www-form-urlencoded'})[0]==403,'A browser form cannot submit approval decisions')
  check(request(headers={'Content-Type':'application/json','Host':'other.example'})[0]==403,'An unexpected host cannot reach approval controls')
  check(request(path='/snapshot',headers={'Host':'other.example'},method='GET')[0]==403,'An unexpected host cannot read the project snapshot')
  status,body=request(headers={'Content-Type':'application/json','Origin':base})
  check(status==400 and b'no longer pending' in body,'A same-origin decision still requires a live owned request')
  check(request(headers={'Content-Type':'application/json'},value={'action':'inventApproval'})[0]==400,'The endpoint cannot invent a new approval action')
 finally:
  proc.terminate();proc.wait(timeout=5)
print(f'{len(checks)} approval HTTP checks passed')
for label in checks:print('PASS',label)
