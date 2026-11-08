"""Root-owned AWS activation after verified final restore and source fencing."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT=Path('/var/lib/vendistri-production-activation')
FINAL=Path('/var/lib/vendistri-cutover-final')
CONFIG=Path('/etc/vendistri')
UNITS=Path('/etc/systemd/system')
API=['proclaws.service','proclaws-api-2.service','vendistri-realtime.service']
WORKERS=['vendistri-bg-tasks.service','vendistri-telemetry-worker.service','vendistri-documents-worker.service','vendistri-shipping-worker.service','vendistri-health-worker.service']
CONSUMERS=WORKERS+['vendistri-telemetry-intake.service','vendistri-celery-beat.service']


def run(args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE)
def save(state):
    path=ROOT/'state.new';path.write_text(json.dumps(state,indent=2)+'\n');path.replace(ROOT/'state.json')
def load():return json.loads((ROOT/'state.json').read_text())
def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):result.update(block)
    return result.hexdigest()
def require_source(proof,authority):
    if proof.get('phase')!='snapshot-complete' or proof.get('authority')!=authority:
        raise RuntimeError('Verified source snapshot/authority proof required')
def consumers_masked():
    for name in CONSUMERS:
        values=dict(line.split('=',1) for line in run(['systemctl','show',name,'-p','ActiveState','-p','UnitFileState']).splitlines())
        if values!={'ActiveState':'inactive','UnitFileState':'masked'}:
            raise RuntimeError('Expected fenced AWS consumer: '+name)


def install_unit(name,state):
    source=CONFIG/'production-prepared/units'/name;body=source.read_text()
    if 'Environment=DJANGO_SETTINGS_MODULE=vendistri_production' not in body or 'Environment=PYTHONPATH=/etc/vendistri:/home/akatary/pro_claws/backend' not in body:
        raise RuntimeError('Incomplete production unit settings')
    if list((UNITS/(name+'.d')).glob('*.conf')):
        raise RuntimeError('Unexpected AWS unit drop-in; review before activation')
    path=UNITS/name;backup=ROOT/'units'/name
    if path.is_symlink():
        if path.resolve()!=Path('/dev/null'):raise RuntimeError('Unknown unit symlink')
        backup.with_suffix('.mask').write_text('/dev/null');path.unlink()
    elif path.exists():shutil.copy2(path,backup)
    path.write_text(body);path.chmod(0o644)
    state.setdefault('installed_units',[]).append(name);save(state)


def promote_files(state):
    db=json.loads((FINAL/'database-receipt.json').read_text())
    if db.get('database')!='vendistri_production' or db.get('row_counts_sequences_migrations_constraints_indexes')!='matched':
        raise RuntimeError('Final production database acceptance receipt required')
    json.loads((FINAL/'cache-receipt.json').read_text())
    files=json.loads((FINAL/'files-receipt.json').read_text())
    efs=Path('/mnt/vendistri-media');stage=efs/('.cutover-new-'+state['stamp']);prior=efs/('.cutover-prior-'+state['stamp'])
    stage.mkdir(mode=0o700);prior.mkdir(mode=0o700)
    count=0
    for name in ('media','private_media'):
        source=FINAL/'files/media'/name;target=stage/name
        if source.is_symlink() or not source.is_dir():raise RuntimeError('Unexpected media root')
        shutil.copytree(source,target,copy_function=shutil.copy2)
        for path in [target,*target.rglob('*')]:
            if path.is_symlink():raise RuntimeError('Unexpected staged media symlink')
            if (path.stat().st_uid,path.stat().st_gid)!=(1001,1001):os.chown(path,1001,1001)
            if path.is_file():
                if digest(path)!=digest(source/path.relative_to(target)):raise RuntimeError('EFS final media hash mismatch')
                count+=1
    if count!=files['staged_files']['media.tar.gz']:raise RuntimeError('Media count mismatch')
    moved=[]
    try:
        for name in ('media','private_media'):
            if (efs/name).is_symlink():raise RuntimeError('Unexpected live media symlink')
            (efs/name).rename(prior/name);moved.append(name);(stage/name).rename(efs/name)
    except Exception:
        for name in reversed(moved):
            if (efs/name).exists():(efs/name).rename(stage/name)
            (prior/name).rename(efs/name)
        raise
    scheduler=Path('/home/akatary/pro_claws/backend/run');scheduler.mkdir(mode=0o750,exist_ok=True)
    if scheduler.is_symlink() or scheduler.stat().st_dev==efs.stat().st_dev:
        raise RuntimeError('Beat must use local storage')
    if list(scheduler.glob('celerybeat-schedule*')):raise RuntimeError('Existing scheduler requires reconciliation')
    os.chown(scheduler,1001,1001)
    for path in (FINAL/'files/scheduler').iterdir():
        target=scheduler/path.name;shutil.copy2(path,target);os.chown(target,1001,1001)
        if digest(path)!=digest(target):raise RuntimeError('Scheduler transfer mismatch')
    state['media_files_verified']=count;state['prior_media']=str(prior);state['database_receipt']=db;save(state)


def prepare(role,proof):
    require_source(proof,'source')
    consumers_masked()
    if (CONFIG/'production.json').exists() or ROOT.exists():raise RuntimeError('Existing activation state needs review')
    # Validate all settings/templates before pausing isolated AWS API processes.
    for name in API+(CONSUMERS if role=='a' else []):
        body=(CONFIG/'production-prepared/units'/name).read_text()
        if 'Environment=PYTHONPATH=/etc/vendistri:/home/akatary/pro_claws/backend' not in body:raise RuntimeError('Missing settings import path')
    ROOT.mkdir(mode=0o700);(ROOT/'units').mkdir(mode=0o700)
    state={'role':role,'phase':'preparing','stamp':datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')};save(state)
    for name in API:run(['systemctl','stop',name])
    if role=='a':promote_files(state)
    runtime=Path('/home/akatary/pro_claws/backend/run');runtime.mkdir(mode=0o750,exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_dev==Path('/mnt/vendistri-media').stat().st_dev:raise RuntimeError('Runtime files require local storage')
    os.chown(runtime,1001,1001)
    (CONFIG/'production.json').symlink_to(CONFIG/'production-prepared/config.json')
    for name in API:install_unit(name,state)
    run(['systemctl','daemon-reload']);state['phase']='prepared';save(state)
    return state


def start(role,proof):
    require_source(proof,'aws');state=load()
    if state['role']!=role or state['phase']!='prepared':raise RuntimeError('Prepared host role required')
    if role=='b':consumers_masked()
    if role=='a':
        for name in CONSUMERS:install_unit(name,state)
        run(['systemctl','daemon-reload'])
    for name in API+(CONSUMERS if role=='a' else []):run(['systemctl','enable','--now',name])
    state['phase']='started';save(state);return state


def release_config(body):
    count=0
    def replace(found):
        nonlocal count
        block=found.group(0)
        if block.startswith('<LocationMatch "^/(?!vendistri/be/health/ready/?$)">') or block.startswith('<Location />'):
            if 'Require local' not in block:raise RuntimeError('Expected temporary route gate absent')
            count+=1;return block.replace('Require local','Require all granted',1)
        return block
    updated=re.sub(r'<Location(?:Match)?\b[^>]*>.*?</Location(?:Match)?>',replace,body,flags=re.S)
    if count!=3:raise RuntimeError('Expected exactly three known temporary traffic gates')
    return updated


def release(proof):
    require_source(proof,'aws');state=load()
    if state['phase']!='started':raise RuntimeError('Running production services required')
    request=urllib.request.Request('http://127.0.0.1/vendistri/be/health/ready',headers={'Host':'secure.vendistri.com'})
    with urllib.request.urlopen(request,timeout=10) as response:
        if response.status!=200:raise RuntimeError('Production readiness failed')
    path=Path('/etc/apache2/sites-available/000-vendistri-rehearsal.conf');original=path.read_text()
    updated=release_config(original);(ROOT/'apache-before-release.conf').write_text(original)
    try:
        path.write_text(updated);run(['apache2ctl','configtest']);run(['systemctl','reload','apache2'])
    except Exception:
        path.write_text(original);run(['apache2ctl','configtest']);run(['systemctl','reload','apache2']);raise
    state['traffic_gate']='released';save(state);return state


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare-a','prepare-b','start-a','start-b','release']);args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Run the installed root-owned activation tool')
    os.umask(0o077);proof=json.load(sys.stdin)
    if args.action.startswith('prepare-'):state=prepare(args.action[-1],proof)
    elif args.action.startswith('start-'):state=start(args.action[-1],proof)
    else:state=release(proof)
    print(json.dumps(state))


if __name__=='__main__':main()
