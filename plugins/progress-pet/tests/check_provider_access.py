"""GUI provider credential handling and useful local fallback; no real keys/models."""
from pathlib import Path
import json,os,sys,tempfile,threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
import provider_access as P
import project_discussion as D
from dog_bridge import DogBridge

checks=0
def check(value,message):
 global checks
 assert value,message
 checks+=1

with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);config=root/'config.toml'
 config.write_text('model_provider="fixture"\n[model_providers.fixture]\nenv_key="MOTCHI_FIXTURE_KEY"\n')
 with patch.dict(os.environ,{'CODEX_HOME':str(root)},clear=True):
  P._cache.clear()
  with patch.object(P,'shell_value',return_value='fixture-credential') as read:
   with ThreadPoolExecutor(max_workers=4) as pool:envs=list(pool.map(lambda _:P.environment(),range(8)))
   check(all(e['MOTCHI_FIXTURE_KEY']=='fixture-credential' for e in envs),'GUI children reuse the selected provider credential')
   check(read.call_count==1,'Concurrent answer/checklist requests share one bounded credential read')
   check('MOTCHI_FIXTURE_KEY' not in os.environ,'The parent environment is not modified')
   check(all('OPENAI_API_KEY' not in e for e in envs),'Unrelated provider keys are not fetched')
  with patch.dict(os.environ,{'MOTCHI_FIXTURE_KEY':'already-configured'}),patch.object(P,'shell_value') as read:
   check(P.environment()['MOTCHI_FIXTURE_KEY']=='already-configured' and not read.called,'Existing child credentials take precedence')
  P._cache.clear()
  with patch.object(P,'shell_value',side_effect=OSError):
   check('MOTCHI_FIXTURE_KEY' not in P.environment(),'Missing shell credentials fail without leaking errors')
  config.write_text('model_provider="fixture"\n[model_providers.fixture]\nenv_key="KEY; touch /tmp/unwanted"\n')
  with patch.object(P,'shell_value') as read:
   check(P.configured_key() is None and not read.called,'Configured env names cannot become shell expressions')
  config.write_text('model_provider="fixture"\nprofile="other"\n[profiles.other]\nmodel_provider="second"\n[model_providers.fixture]\nenv_key="FIRST_KEY"\n[model_providers.second]\nenv_key="SECOND_KEY"\n')
  check(P.configured_key()=='SECOND_KEY','The selected user profile supplies its own provider key name')
  config.write_text('invalid = [')
  check(P.configured_key() is None,'Invalid configuration does not crash project discovery')

 # A fake shell emits unrelated startup noise and a marker-delimited secret.
 class Child:
  def communicate(self,timeout):return ('startup noise\nMOTCHI_ENV_test\nfixture-secret\n\nMOTCHI_ENV_test\n','')
  def poll(self):return 0
 with patch.object(P.pwd,'getpwuid',return_value=SimpleNamespace(pw_shell='/bin/zsh')),patch.object(P.secrets,'token_hex',return_value='test'),patch.object(P.subprocess,'Popen',return_value=Child()) as spawn:
  check(P.shell_value('MOTCHI_FIXTURE_KEY')=='fixture-secret','Only framed output is read from shell startup')
  check('fixture-secret' not in str(spawn.call_args),'Credential values never appear in subprocess arguments')

 rows=[{'id':'chat-a','cwd':str(root/'alpha'),'title':'Alpha','status':'active','progress':{'name':'Alpha'}},
       {'id':'chat-a2','cwd':str(root/'alpha'),'title':'Alpha followup','status':'idle','progress':{'name':'Alpha'}},
       {'id':'chat-b','cwd':str(root/'beta'),'title':'Beta','status':'idle','progress':{'name':'Beta'}}]
 bridge=object.__new__(DogBridge);bridge.snapshot=lambda:{'items':rows}
 bridge.ask=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Inventory must not need an AI provider'))
 for question in ['我们现在的项目还有哪些？','我们有哪些项目？','列出所有项目','What projects do we have?','List our projects']:
  result=bridge.discuss_result({'text':question})
  check(result['answerSource']=='localCatalog' and len(result['projects'])==2 and 'Alpha' in result['text'],'Catalog questions return grouped local facts without AI: '+question)
 result=bridge.ask_result({'action':'ask','selection':'chat-a','text':'我们现在的项目还有哪些？'})
 check(result['answerSource']=='localCatalog' and result['routedSelection']=='chat-a','The native typed composer uses the same local project inventory')
 for question in ['这个项目还有哪些任务？','Add a project','Which projects are finished?','项目进度怎么样？','Explain project management']:
  check(not D.project_inventory(question),'Status, execution and explanations are not mistaken for inventory: '+question)
 try:bridge.discuss_result({'text':'List our projects','projectId':'unknown'});rejected=False
 except ValueError:rejected=True
 check(rejected,'Exact identity validation still precedes local answers')
 for message,code in [('Missing environment variable: `SECRET_NAME`.','authentication'),('429 rate limit','rate_limit'),('network connection failed','connection'),('model_not_found','configuration'),('unknown internal data','unavailable')]:
  check(P.failure_code(message)==code,'Provider failures reduce to safe categorical diagnostics')
 result=D.presentation('',{'projects':[],'providerFailure':'authentication'},set(),'你好')
 check(result['providerIssue']=='authentication' and '凭据' in result['text'] and 'SECRET_NAME' not in str(result),'Visible failures explain the cause without exposing credentials')
 worker=root/'codex-fixture';worker.write_text('#!'+sys.executable+'\nimport sys,json\nsys.stdin.read()\nprint(json.dumps({"type":"error","message":"Missing environment variable: SECRET_NAME"}),flush=True)\nprint(json.dumps({"type":"turn.failed","error":{"message":"Missing environment variable: SECRET_NAME"}}),flush=True)\n');worker.chmod(0o700)
 bridge.root=root;bridge.project=str(root);bridge.codex=str(worker);bridge.history={};bridge.isolated_config_flags=lambda _:[]
 context={'projects':[],'scope':'general','historyKey':'general','fallback':'No projects'}
 with patch.object(P,'environment',return_value=dict(os.environ)):
  DogBridge.ask(bridge,None,'hello',discussion_context=context)
 check(context['providerFailure']=='authentication','Actual subprocess errors reach presentation as a safe code')
 print(f'{checks} provider access and local answer checks passed')
