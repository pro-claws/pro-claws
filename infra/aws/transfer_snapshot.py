"""Operator-side encrypted final snapshot transfer; requires a fenced source.

Does not fence the source, restore a database, activate services or move traffic.
"""
import hashlib
import base64
import shlex
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone

SCRATCH=Path('/private/tmp/vendistri-aws-final')
BUCKET='vendistri-aws-artifacts-artifacts-9clgm8cgzbem'
ACTIONS={'database.dump':'stream-db','media.tar.gz':'stream-media','scheduler.tar.gz':'stream-scheduler',
         'redis.json':'stream-redis','database-inventory.json':'stream-inventory'}
SSH=['ssh','-i',str(Path.home()/'.ssh/vendistri_aws_migration'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
     '-o','UserKnownHostsFile=/private/tmp/vendistri-aws-prepare/known_hosts','ubuntu@100.58.5.127']


def main():
    os.umask(0o077)
    # Existing partial data requires explicit inspection; never overwrite it.
    SCRATCH.mkdir(mode=0o700)
    manifest_bytes=subprocess.check_output(['ssh','-o','BatchMode=yes','vendistri-prod',
        'sudo -n /usr/local/sbin/vendistri-cutover stream-manifest'])
    manifest=json.loads(manifest_bytes)
    if set(manifest)!=set(ACTIONS):raise RuntimeError('Unexpected final snapshot manifest')
    (SCRATCH/'manifest.json').write_bytes(manifest_bytes)
    for name,action in ACTIONS.items():
        path=SCRATCH/name
        with path.open('xb') as output:
            subprocess.run(['ssh','-o','BatchMode=yes','vendistri-prod',
                            'sudo -n /usr/local/sbin/vendistri-cutover '+action],stdout=output,check=True)
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.stat().st_size!=manifest[name]['bytes'] or digest!=manifest[name]['sha256']:
            raise RuntimeError('Final transfer checksum mismatch')
        print(name+': source checksum matched',flush=True)
    prefix='production-cutover-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for name in ['manifest.json',*ACTIONS]:
        subprocess.run(['aws','s3','cp',str(SCRATCH/name),'s3://'+BUCKET+'/'+prefix+'/'+name,
                        '--sse','AES256','--only-show-errors','--profile','vendistri-setup','--region','us-east-1'],check=True)
        head=json.loads(subprocess.check_output(['aws','s3api','head-object','--bucket',BUCKET,'--key',prefix+'/'+name,
                          '--profile','vendistri-setup','--region','us-east-1','--output','json'],text=True))
        if head['ContentLength']!=(SCRATCH/name).stat().st_size or head.get('ServerSideEncryption')!='AES256' or not head.get('VersionId'):
            raise RuntimeError('Private versioned backup receipt did not verify')
    # Let AWS fetch the private backup directly; never send operator credentials.
    names=['manifest.json',*ACTIONS]
    urls={name:subprocess.check_output(['aws','s3','presign','s3://'+BUCKET+'/'+prefix+'/'+name,
              '--expires-in','900','--profile','vendistri-setup','--region','us-east-1'],text=True).strip() for name in names}
    receiver=Path(__file__).with_name('receive_snapshot.py').read_bytes()
    install="import sys,base64;from pathlib import Path;p=Path('/usr/local/lib/vendistri-cutover/receive_snapshot.py');p.write_bytes(base64.b64decode(sys.stdin.read()));p.chmod(0o644)"
    subprocess.run(SSH+['sudo /usr/bin/python3 -I -c '+shlex.quote(install)],input=base64.b64encode(receiver).decode(),text=True,check=True,capture_output=True)
    code="import sys;sys.path.insert(0,'/usr/local/lib/vendistri-cutover');from receive_snapshot import main;main()"
    result=subprocess.run(SSH+['sudo /usr/bin/python3 -I -c '+shlex.quote(code)],input=json.dumps({'manifest':manifest,'urls':urls}),text=True,check=True,capture_output=True)
    print(json.dumps(json.loads(result.stdout)))
    (SCRATCH/'backup-receipt.json').write_text(json.dumps({'bucket':BUCKET,'prefix':prefix,'checksums':'matched','services_started':False}))
    print('Final source snapshot verified, privately archived and staged on AWS A; services remain stopped')


if __name__=='__main__':main()
