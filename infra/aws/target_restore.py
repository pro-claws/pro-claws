"""Restore a verified, fenced-source snapshot without starting application units."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from database_inventory import collect
from schema_validation import comparable

ROOT = Path('/var/lib/vendistri-cutover-final')
CONFIG = Path('/etc/vendistri/production-prepared/config.json')


def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    required = {'database.dump','database-inventory.json','media.tar.gz','scheduler.tar.gz','redis.json'}
    if set(manifest) != required:
        raise RuntimeError('Unexpected snapshot files')
    for name, expected in manifest.items():
        path = folder/name
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        digest=digest.hexdigest()
        if path.stat().st_size != expected['bytes'] or digest != expected['sha256']:
            raise RuntimeError('Snapshot checksum mismatch')
    return manifest


def database_command(config, name, user, password, statement, rows=True):
    # Root uses only root-owned OS PostgreSQL clients and stdlib, never imports
    # dependencies or application modules from an application-writable venv.
    env=os.environ.copy()
    env.update(PGPASSWORD=password,PGSSLMODE='verify-full',PGSSLROOTCERT='/etc/vendistri/rds-ca.pem',PGCONNECT_TIMEOUT='15')
    if rows:
        statement="SELECT coalesce(json_agg(row_to_json(t)),'[]') FROM ("+statement+') t'
    result=subprocess.run(['psql','-XAt','-v','ON_ERROR_STOP=1','--host',config['database']['host'],
                           '--username',user,'--dbname',name,'-c',statement],env=env,capture_output=True,text=True,check=True)
    return [list(row.values()) for row in json.loads(result.stdout)] if rows else None


def restore_database(config, folder, admin_password, rehearsal=False):
    verify(folder)
    target = 'vendistri_transfer_drill' if rehearsal else 'vendistri_production'
    user = config['database']['user']
    if config['database']['name'] != 'vendistri_production' or user != 'proclaws_app':
        raise RuntimeError('Unreviewed production database configuration')
    if database_command(config,'postgres','vendistri_admin',admin_password,"SELECT 1 FROM pg_database WHERE datname='"+target+"'"):
        raise RuntimeError('Target database already exists; refusing to replace or retry blindly')
    # Both identifiers above are fixed and validated, never operator input.
    database_command(config,'postgres','vendistri_admin',admin_password,'CREATE DATABASE '+target+' OWNER proclaws_app',rows=False)
    env = os.environ.copy()
    env.update(PGPASSWORD=config['database']['password'],PGSSLMODE='verify-full',PGSSLROOTCERT='/etc/vendistri/rds-ca.pem')
    start = time.monotonic()
    subprocess.run(['pg_restore','--exit-on-error','--no-owner','--no-acl','--host',config['database']['host'],
                    '--username',user,'--dbname',target,str(folder/'database.dump')],env=env,check=True,capture_output=True)
    def query(statement):
        return database_command(config,target,user,config['database']['password'],statement)
    actual = json.loads(json.dumps(collect(query)))
    expected = json.loads((folder/'database-inventory.json').read_text())
    if comparable(actual) != comparable(expected):
        (folder/'target-inventory-private.json').write_text(json.dumps(actual))
        raise RuntimeError('Restored inventory differs: keep application units stopped')
    receipt = {'database': target, 'row_counts_sequences_migrations_constraints_indexes': 'matched',
               'tables':len(actual['rows']), 'seconds':round(time.monotonic()-start,2),'services_started':False}
    (folder/('database-drill-receipt.json' if rehearsal else 'database-receipt.json')).write_text(json.dumps(receipt))
    return receipt


def validate_existing(config,folder):
    verify(folder)
    db=config['database']
    if db['name']!='vendistri_production' or db['user']!='proclaws_app':raise RuntimeError('Unexpected validation scope')
    def query(statement):return database_command(config,db['name'],db['user'],db['password'],statement)
    actual=json.loads(json.dumps(collect(query)))
    expected=json.loads((folder/'database-inventory.json').read_text())
    if comparable(actual)!=comparable(expected):raise RuntimeError('Production inventory still differs')
    changed={key:sum(a!=b for a,b in zip(actual[key],expected[key])) for key in ('constraints','indexes')}
    receipt={'database':db['name'],'row_counts_sequences_migrations_constraints_indexes':'matched','tables':len(actual['rows']),'sequences':len(actual['sequences']),'migrations':len(actual['migrations']),'sql_array_cast_rendering_differences':changed,'services_started':False}
    (folder/'database-receipt.json').write_text(json.dumps(receipt));return receipt


def stage_files(folder):
    verify(folder)
    stage = folder/'files'
    stage.mkdir(mode=0o700)
    counts = {}
    for filename, directories in [('media.tar.gz',{'media','private_media'}),('scheduler.tar.gz',None)]:
        destination = stage/filename.replace('.tar.gz',''); destination.mkdir(mode=0o700)
        with tarfile.open(folder/filename) as archive:
            members = archive.getmembers()
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise RuntimeError('Unsafe archive member')
                if directories is not None and (not path.parts or path.parts[0] not in directories):
                    raise RuntimeError('Unexpected media archive namespace')
                if directories is None and (len(path.parts)!=1 or not path.name.startswith('celerybeat-schedule') or not member.isfile()):
                    raise RuntimeError('Unexpected scheduler archive member')
            archive.extractall(destination, members=members, filter='data')
            counts[filename] = sum(member.isfile() for member in members)
    receipt={'staged_files':counts,'live_media_or_scheduler_changed':False}
    (folder/'files-receipt.json').write_text(json.dumps(receipt)); return receipt


def restore_cache(config, folder):
    verify(folder)
    code='''import json,sys
from redis import Redis
from urllib.parse import quote
sys.path.insert(0,'/usr/local/lib/vendistri-cutover')
from cutover_redis import restore_export
p=json.load(sys.stdin);b=p['broker']
base=f"rediss://:{quote(b['password'],safe='')}@{b['host']}:6379"
clients={number:Redis.from_url(base+f'/{number}?ssl_cert_reqs=required',socket_timeout=10) for number in (5,6,7)}
if any(client.dbsize() for client in clients.values()):raise RuntimeError('Production Redis namespaces are not empty; reconcile without purging')
print(json.dumps(restore_export(clients[7],p['export'])))
'''
    child=subprocess.run(['runuser','-u','akatary','--','/home/akatary/pro_claws/backend/pro_claws_be_env/bin/python','-c',code],
        input=json.dumps({'broker':config['broker'],'export':json.loads((folder/'redis.json').read_text())}),capture_output=True,text=True,check=True)
    result=json.loads(child.stdout)
    (folder/'cache-receipt.json').write_text(json.dumps(result));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['verify','database','database-drill','validate-existing','stage-files','cache'])
    args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Install and run as root')
    os.umask(0o077)
    if ROOT.is_symlink() or ROOT.stat().st_uid!=0 or ROOT.stat().st_mode&0o077:
        raise RuntimeError('Unsafe final snapshot directory')
    config=json.loads(CONFIG.read_text())
    if args.action in ('database','database-drill'):
        # Master credential supplied over encrypted stdin; never stored or logged.
        password=json.load(sys.stdin)['admin_password']
        result=restore_database(config,ROOT,password,args.action=='database-drill')
    elif args.action=='validate-existing':result=validate_existing(config,ROOT)
    elif args.action=='stage-files':result=stage_files(ROOT)
    elif args.action=='cache':result=restore_cache(config,ROOT)
    else:result={'checksums':'verified','files':len(verify(ROOT))}
    print(json.dumps(result))


if __name__=='__main__':main()
