"""Load actual production settings under staged systemd policies in a private mount."""
import base64,json,shlex,subprocess
from pathlib import Path
ROOT=Path('/private/tmp/vendistri-aws-prepare')
diagnostic=r'''import os,json,django
from pathlib import Path
from urllib.parse import urlparse
django.setup()
from django.conf import settings
from src.celery import app
c=json.loads(Path('/etc/vendistri/production.json').read_text())
assert settings.DATABASES['default']['NAME']=='vendistri_production'
assert settings.DATABASES['default']['OPTIONS']['sslmode']=='verify-full'
assert urlparse(app.conf.broker_url).path=='/5'
assert urlparse(settings.CACHES['default']['LOCATION']).path=='/7'
assert urlparse(os.environ['CHANNEL_LAYER_URL']).path=='/6'
assert settings.SECRET_KEY==c['environment']['DJANGO_SECRET_KEY']
assert os.environ['AWS_ACCESS_KEY_ID']==c['application_identity']['aws_access_key_id']
for filename in ['weatherkit-private-key.p8','gmail-service-account.json']:
 assert (Path('/etc/vendistri/production-prepared')/filename).read_bytes()
assert len(settings.CELERY_BEAT_SCHEDULE)==30
print(json.dumps({'production_settings_loaded':True,'database':'vendistri_production','redis_namespaces':[5,6,7],'schedules':30,'scoped_credentials_and_signing_match':True,'provider_files_readable':True,'database_connection_opened':False}))
'''
remote=r'''import json,sys,base64,grp,os,shutil,subprocess,uuid
from pathlib import Path
payload=json.load(sys.stdin);name='vendistri-production-preflight-'+uuid.uuid4().hex[:8]
root=Path('/run')/name;root.mkdir(mode=0o750);gid=grp.getgrnam('vendistri-config').gr_gid;os.chown(root,0,gid)
shadow=root/'etc';shadow.mkdir(mode=0o750);os.chown(shadow,0,gid)
prepared=shadow/'production-prepared';prepared.mkdir(mode=0o750);os.chown(prepared,0,gid)
copies=[('/etc/vendistri/vendistri_production.py',shadow/'vendistri_production.py'),('/etc/vendistri/rds-ca.pem',shadow/'rds-ca.pem'),('/etc/vendistri/production-prepared/config.json',shadow/'production.json')]
copies.extend(('/etc/vendistri/production-prepared/'+filename,prepared/filename) for filename in ['weatherkit-private-key.p8','gmail-service-account.json'])
for original,destination in copies:
 shutil.copyfile(original,destination);os.chown(destination,0,gid);destination.chmod(0o640)
script=root/'diagnostic.py';script.write_bytes(base64.b64decode(payload['diagnostic']));script.chmod(0o640);os.chown(script,0,gid)
units=[];results={}
try:
 assert not Path('/etc/vendistri/production.json').exists()
 for index,original in enumerate(['proclaws.service','vendistri-health-worker.service','vendistri-celery-beat.service']):
  unit=name+'-'+str(index)+'.service';path=Path('/run/systemd/system')/unit;units.append((unit,path))
  body=(Path('/etc/vendistri/production-prepared/units')/original).read_text()
  assert 'Environment=PYTHONPATH=/etc/vendistri:/home/akatary/pro_claws/backend' in body
  path.write_text(body+'\n[Service]\nType=oneshot\nRestart=no\nRemainAfterExit=yes\nStandardOutput=journal\nStandardError=journal\nRuntimeMaxSec=60\nTimeoutStartSec=60\nExecStart=\nExecStart=/home/akatary/pro_claws/backend/pro_claws_be_env/bin/python '+str(script)+'\nBindReadOnlyPaths='+str(shadow)+':/etc/vendistri\nIPAddressDeny=any\n')
  subprocess.run(['systemctl','daemon-reload'],check=True,capture_output=True)
  started=subprocess.run(['systemctl','start',unit],capture_output=True,text=True)
  invocation=subprocess.check_output(['systemctl','show',unit,'-p','InvocationID','--value'],text=True).strip()
  journal=subprocess.check_output(['journalctl','--no-pager','-o','cat','_SYSTEMD_INVOCATION_ID='+invocation],text=True)
  if started.returncode:
   Path('/var/tmp/'+name+'-private-error.txt').write_text(journal+'\n'+started.stderr)
   raise RuntimeError('Production unit preflight failed; private diagnostics retained')
  rows=[line for line in journal.splitlines() if line.startswith('{') and 'production_settings_loaded' in line]
  if len(rows)!=1:
   Path('/var/tmp/'+name+'-private-error.txt').write_text(journal+'\n'+invocation)
   raise RuntimeError('Missing diagnostic acceptance receipt')
  results[original]=json.loads(rows[0])
 assert not Path('/etc/vendistri/production.json').exists()
 print(json.dumps({'staged_unit_startup':results,'active_configuration_changed':False,'production_services_started':False}))
finally:
 for unit,path in units:
  subprocess.run(['systemctl','stop',unit],capture_output=True);subprocess.run(['systemctl','reset-failed',unit],capture_output=True);path.unlink(missing_ok=True)
 subprocess.run(['systemctl','daemon-reload'],check=True,capture_output=True);shutil.rmtree(root)
'''
base=['ssh','-i',str(Path.home()/'.ssh/vendistri_aws_migration'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(ROOT/'known_hosts')]
def main():
    for label,ip in [('a','100.58.5.127'),('b','3.211.223.36')]:
     r=subprocess.run(base+['ubuntu@'+ip,'sudo /usr/bin/python3 -I -c '+shlex.quote(remote)],input=json.dumps({'diagnostic':base64.b64encode(diagnostic.encode()).decode()}),capture_output=True,text=True)
     if r.returncode:(ROOT/('production-unit-preflight-private-error-'+label+'.txt')).write_text(r.stderr);raise SystemExit('Production unit preflight failed on '+label)
     value=json.loads(r.stdout);(ROOT/('production-unit-preflight-'+label+'.json')).write_text(json.dumps(value,indent=2)+'\n');print(label+': actual production module loaded under three staged unit policies; no activation',flush=True)


if __name__ == '__main__':
    main()
