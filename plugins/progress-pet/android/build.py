#!/usr/bin/env python3
"""Build a locally signed APK. Keep the signing configuration outside the repo."""
import argparse,json,os,secrets,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--gradle',default=str(Path(__file__).resolve().parent/'gradlew'))
p.add_argument('--signing-config',type=Path,default=Path.home()/'Library/Application Support/Mochi/android/signing/release.json')
p.add_argument('--create-key',action='store_true')
p.add_argument('--debug',action='store_true')
p.add_argument('--compatibility',action='store_true')
p.add_argument('--output',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parent
if a.create_key and not a.signing_config.exists():
 a.signing_config.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 password=secrets.token_urlsafe(32);key=a.signing_config.parent/'motchi.jks'
 keytool=str(Path(os.environ['JAVA_HOME'])/'bin/keytool')
 subprocess.run([keytool,'-genkeypair','-keystore',str(key),'-storepass:env','MOTCHI_KEYPASS','-keypass:env','MOTCHI_KEYPASS','-alias','motchi','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Motchi local Android'],check=True,env={**os.environ,'MOTCHI_KEYPASS':password})
 key.chmod(0o600);a.signing_config.write_text(json.dumps({'file':str(key),'password':password}));a.signing_config.chmod(0o600)
if not a.signing_config.exists():p.error('Signing configuration missing. Use --create-key for your first local build; back up the private key securely.')
c=json.loads(a.signing_config.read_text());env={**os.environ,'MOTCHI_SIGNING_FILE':c['file'],'MOTCHI_SIGNING_PASSWORD':c['password']}
kind='Debug' if a.debug else 'Release';cmd=[a.gradle,'-p',str(root),'assemble'+kind,'lint'+kind,'test'+kind+'UnitTest','--console=plain']
if a.compatibility:cmd.append('-PmotchiCompatibility=true')
subprocess.run(cmd,check=True,env=env)
apk=root/'app/build/outputs/apk'/kind.lower()/('app-'+kind.lower()+'.apk')
if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(apk,a.output);apk=a.output
print('Signed APK:',apk)
