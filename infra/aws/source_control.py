"""Root-owned, fixed-scope Vendistri fencing/snapshot/ingress recovery control.

No application code is imported as root. No shared PostgreSQL/Redis/Apache
service is stopped. Fencing cannot begin before the agreed UTC window.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

from source_root_audit import UNITS, PATTERN, match
from database_inventory import collect

ROOT = Path('/var/lib/vendistri-cutover')
STATE = ROOT / 'state.json'
BASE = Path('/home/akatary/pro_claws')
TARGET = datetime(2026, 10, 25, 4, tzinfo=timezone.utc)
CONSUMERS = [name for name in UNITS if name not in ('proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service')]
PAUSE_FIRST = ['vendistri-celery-beat.service', 'vendistri-telemetry-intake.service',
               'proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service']
EXEMPT = {'vendistri-aws-ingress.service', 'vendistri-cutover-lock.service'}
DOMAINS = {'vendistri.com', 'www.vendistri.com', 'secure.vendistri.com', 'open.vendistri.com'}


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


def sql(query):
    return run(['runuser', '-u', 'postgres', '--', '/usr/bin/psql', '-XAt', '-v', 'ON_ERROR_STOP=1',
                '-d', 'postgres', '-c', query])


def save(state):
    temporary = ROOT / 'state.new'
    temporary.write_text(json.dumps(state, indent=2) + '\n'); temporary.chmod(0o600)
    temporary.replace(STATE)


def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def load():
    return json.loads(STATE.read_text())


def app(code, environment):
    # env is applied only AFTER runuser drops privileges (never to root's loader).
    pairs = [key + '=' + value for key, value in environment.items()
             if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', key)]
    args = ['runuser', '-u', 'akatary', '--', '/usr/bin/env', '-i', *pairs,
            str(BASE / 'backend/pro_claws_be_env/bin/python'), '-c', code]
    result = subprocess.run(args, cwd=BASE / 'backend', capture_output=True, text=True)
    if result.returncode:
        (ROOT / 'application-private-error.txt').write_text(result.stderr)
        raise RuntimeError('Application diagnostic failed; private error retained')
    return json.loads(result.stdout.strip().splitlines()[-1])


INFO_CODE = """import django,json,os;django.setup()
from django.conf import settings
from src.celery import app
d=settings.DATABASES['default']
print(json.dumps({'database':{key:d.get(key) for key in ['NAME','USER','HOST','PORT']},'broker':app.conf.broker_url,'cache':settings.CACHES['default']['LOCATION'],'weather':os.environ.get('WEATHER_CACHE_URL') or settings.CACHES['default']['LOCATION']}))
"""
DRAIN_CODE = """import django,json;django.setup()
from src.celery import app
from redis import Redis
inspect=app.control.inspect(timeout=3)
rows=[inspect.active() or {},inspect.reserved() or {},inspect.scheduled() or {}]
r=Redis.from_url(app.conf.broker_url,socket_timeout=5)
prefix=(app.conf.broker_transport_options or {}).get('global_keyprefix','')
queues=['default','automation','health','telemetry','documents','shipping']
depth=sum(r.llen(prefix+queue+suffix) for queue in queues for suffix in ['', '\\x06\\x163','\\x06\\x166','\\x06\\x169'])
print(json.dumps({'workers':len(set().union(*(row.keys() for row in rows))),'active':sum(map(len,rows[0].values())),'reserved':sum(map(len,rows[1].values())),'eta':sum(map(len,rows[2].values())),'queued':depth,'unacked':r.hlen(prefix+'unacked')}))
"""


def scope_probe():
    query = """SELECT json_build_object('owned',EXISTS(SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname='proclaws_prod' AND r.rolname='proclaws_app'),
      'database_settings',(SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname='proclaws_prod') AND setrole=0),
      'super',(SELECT rolsuper FROM pg_roles WHERE rolname='proclaws_app'),
      'backup_super',(SELECT rolsuper FROM pg_roles WHERE rolname=current_user),
      'connection_limit',(SELECT datconnlimit FROM pg_database WHERE datname='proclaws_prod'),
      'login',(SELECT rolcanlogin FROM pg_roles WHERE rolname='proclaws_app'),
      'other_owned',(SELECT count(*) FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE r.rolname='proclaws_app' AND d.datname<>'proclaws_prod'),
      'other_connections',(SELECT count(*) FROM pg_stat_activity WHERE usename='proclaws_app' AND datname<>'proclaws_prod'))"""
    result = json.loads(sql(query))
    if not result['owned'] or result['super'] or not result['backup_super']:
        raise RuntimeError('Requires the owned target database, a non-superuser app and a superuser backup connection')
    return result


def fence_database():
    # The role owns other databases. Never ALTER ROLE or terminate its sessions
    # elsewhere. Zero database slots rejects normal users, including its owner,
    # while the OS postgres superuser can still take the final read-only dump.
    sql('ALTER DATABASE proclaws_prod CONNECTION LIMIT 0; ALTER DATABASE proclaws_prod SET default_transaction_read_only=on;')
    sql("SELECT pg_terminate_backend(a.pid) FROM pg_stat_activity a JOIN pg_roles r ON r.oid=a.usesysid WHERE a.datname='proclaws_prod' AND NOT r.rolsuper AND a.pid<>pg_backend_pid()")


def recover_database(state):
    limit=state['original_connection_limit']
    if not isinstance(limit,int) or isinstance(limit,bool) or limit < -1:
        raise RuntimeError('Invalid original database connection limit')
    sql('ALTER DATABASE proclaws_prod RESET default_transaction_read_only; ALTER DATABASE proclaws_prod CONNECTION LIMIT '+str(limit)+';')


def cron_paths():
    paths=[Path('/etc/crontab')]
    for folder in ['/etc/cron.d','/etc/cron.hourly','/etc/cron.daily','/etc/cron.weekly','/etc/cron.monthly','/var/spool/cron/crontabs']:
        paths.extend(path for path in Path(folder).glob('*') if path.is_file())
    return [path for path in paths if path.is_file()]


def system_units():
    candidates=set(UNITS)
    for row in run(['systemctl','list-unit-files','--no-pager','--no-legend']).splitlines():
        name=row.split()[0]
        if name in EXEMPT or not name.endswith(('.service','.timer','.path','.socket')):continue
        definition=subprocess.run(['systemctl','cat',name],capture_output=True,text=True)
        if definition.returncode==0 and match(definition.stdout):
            if re.search(r'untask|puzzlify|sponj|/var/www/akatary',definition.stdout,re.I):
                raise RuntimeError('Shared restart unit requires manual isolation')
            candidates.add(name)
    return candidates


def names(block):
    result = set()
    for value in re.findall(r'^\s*Server(?:Name|Alias)\s+(.+)$', block, re.M):
        result.update(value.split())
    return result


def render_sites(body, mode):
    count = 0
    def replace(found):
        nonlocal count
        block = found.group(0); hosts = names(block)
        if not hosts.intersection(DOMAINS):
            return block
        if hosts - DOMAINS:
            raise ValueError('Mixed unrelated virtual-host aliases require manual review')
        count += 1
        opening = block[:block.index('>') + 1]
        preserved = []
        for line in block.splitlines()[1:]:
            text = line.strip()
            if re.match(r'^(ServerName|ServerAlias|SSLEngine|SSLCertificateFile|SSLCertificateKeyFile|SSLCertificateChainFile|SSLProtocol|SSLCipherSuite|SSLHonorCipherOrder|ErrorLog|CustomLog)\s', text):
                preserved.append(line)
            elif text == 'Include /etc/letsencrypt/options-ssl-apache.conf':
                preserved.append(line)
        if ':443' not in opening:
            rules = ['RewriteEngine On', 'RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L,NE]']
        elif mode == 'maintenance':
            rules = ['RewriteEngine On', 'Header always set Retry-After "120"',
                     'ErrorDocument 503 "Vendistri maintenance in progress"', 'RewriteRule ^ - [R=503,L]']
        elif mode == 'aws':
            rules = ['ProxyPreserveHost On', 'ProxyAddHeaders On', 'RequestHeader set X-Forwarded-Proto "https"',
                     'ProxyTimeout 120',
                     'ProxyPass /vendistri/be/ws/ ws://127.0.0.1:18080/vendistri/be/ws/',
                     'ProxyPassReverse /vendistri/be/ws/ ws://127.0.0.1:18080/vendistri/be/ws/',
                     'ProxyPass /ws/ ws://127.0.0.1:18080/ws/',
                     'ProxyPassReverse /ws/ ws://127.0.0.1:18080/ws/',
                     'ProxyPass / http://127.0.0.1:18080/', 'ProxyPassReverse / http://127.0.0.1:18080/']
        else:
            raise ValueError('Unsupported ingress mode')
        return '\n'.join([opening, *preserved, *rules, '</VirtualHost>'])
    result = re.sub(r'<VirtualHost\b[^>]*>.*?</VirtualHost\s*>', replace, body, flags=re.S | re.I)
    return result, count


def route(state, mode):
    previous = {}
    try:
        for name in state['sites']:
            path = Path(name); previous[name] = path.read_bytes()
            original = (ROOT / 'sites' / state['sites'][name]).read_text()
            updated, count = render_sites(original, mode)
            if not count:
                raise RuntimeError('Expected Vendistri vhost absent')
            path.write_text(updated)
        run(['apache2ctl', 'configtest']); run(['systemctl', 'reload', 'apache2'])
    except Exception:
        for name, value in previous.items():
            Path(name).write_bytes(value)
        run(['apache2ctl', 'configtest']); run(['systemctl', 'reload', 'apache2'])
        raise
    state['ingress'] = mode; save(state)


def prepare():
    if STATE.exists():
        return load()
    os.umask(0o077); ROOT.mkdir(mode=0o700, exist_ok=True)
    if (ROOT / 'fencing-started').exists():
        raise RuntimeError('Partial fencing state requires operator review')
    if ROOT.stat().st_uid != 0 or ROOT.is_symlink() or ROOT.stat().st_mode & 0o077:
        raise RuntimeError('Unsafe cutover state directory')
    probe = scope_probe()
    if not probe['login']:
        raise RuntimeError('Source application role is already fenced; inspect before preparing')
    if probe['connection_limit'] < -1 or probe['connection_limit']==0:
        raise RuntimeError('Source database already disallows ordinary connections; inspect before preparation')
    pid = int(run(['systemctl', 'show', 'proclaws.service', '-p', 'MainPID', '--value']).strip())
    environment = dict(item.split('=', 1) for item in (Path('/proc') / str(pid) / 'environ').read_text().split('\0') if '=' in item)
    environment['DJANGO_SETTINGS_MODULE'] = 'src.settings'
    (ROOT / 'runtime-environment.json').write_text(json.dumps(environment))
    info = app(INFO_CODE, environment)
    if info['database'] != {'NAME': 'proclaws_prod', 'USER': 'proclaws_app', 'HOST': '127.0.0.1', 'PORT': '5432'}:
        raise RuntimeError('Live database scope differs from reviewed source')
    (ROOT / 'application-private.json').write_text(json.dumps(info))
    state = {'phase': 'prepared', 'authority': 'source', 'original_login': probe['login'], 'sites': {}, 'cron': {}, 'units': {}}
    state['original_connection_limit']=probe['connection_limit']
    if (ROOT/'allow-source-start').exists() or (ROOT/'aws-authority').exists():
        raise RuntimeError('Unexpected prior authority marker; inspect before preparation')
    state['original_database_settings'] = probe['database_settings'] or []
    if any(value.startswith('default_transaction_read_only=') for value in state['original_database_settings']):
        raise RuntimeError('Existing database read-only setting needs manual preservation review')
    state['source_environment_sha256'] = hashlib.sha256((BASE / 'backend/.env').read_bytes()).hexdigest()
    (ROOT / 'sites').mkdir(exist_ok=True)
    for path in Path('/etc/apache2/sites-enabled').glob('*.conf'):
        resolved = path.resolve(); body = resolved.read_text()
        _, count = render_sites(body, 'maintenance')
        if count:
            key = str(len(state['sites'])) + '.conf'
            (ROOT / 'sites' / key).write_text(body); state['sites'][str(resolved)] = key
    if not state['sites']:
        raise RuntimeError('No reviewed Vendistri sites found')
    (ROOT / 'cron').mkdir(exist_ok=True)
    for path in cron_paths():
        body = path.read_text()
        if any(line.strip() and not line.lstrip().startswith('#') and match(line) for line in body.splitlines()):
            if re.search(r'untask|puzzlify|sponj|/var/www/akatary', body, re.I):
                raise RuntimeError('Shared cron wrapper needs manual application-only isolation')
            key = str(len(state['cron'])) + '.cron'
            shutil.copy2(path, ROOT / 'cron' / key)
            state['cron'][str(path)] = {'backup': key, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    candidates = system_units()
    for name in sorted(candidates):
        props = run(['systemctl', 'show', name, '-p', 'ActiveState', '-p', 'UnitFileState'])
        state['units'][name] = dict(line.split('=', 1) for line in props.splitlines())
        state['units'][name]['definition_sha256'] = hashlib.sha256(run(['systemctl','cat',name]).encode()).hexdigest()
        if (Path('/etc/systemd/system')/(name+'.d/99-cutover-fence.conf')).exists():
            raise RuntimeError('Existing service fence requires review')
    save(state); return state


def fence(state):
    if datetime.now(timezone.utc) < TARGET:
        raise RuntimeError('Fencing is locked until 2026-10-25 04:00 UTC')
    if state['authority'] != 'source':
        raise RuntimeError('Source cannot regain authority after AWS commitment')
    probe=scope_probe()
    if probe['connection_limit']!=state['original_connection_limit']:
        raise RuntimeError('Source database connection limit changed since preparation')
    if state['phase'] != 'prepared':
        raise RuntimeError('Fence requires the prepared phase; inspect any partial attempt')
    if hashlib.sha256((BASE / 'backend/.env').read_bytes()).hexdigest() != state['source_environment_sha256']:
        raise RuntimeError('Production environment changed since preparation')
    for repo, expected in [('backend','6138b72752ce83a9be315b2afb9c544d232ec839'),('vendistri','268ec896194f64e4b1cdef4a57372a6e557d1398'),('marketplace','9d82b67a4c812e047522cc30774fe9b7457e4cee'),('home_page','b36ac7f66070ef723ad9d70e0f96c1bc8853f8d1')]:
        actual = run(['runuser','-u','akatary','--','git','-C',str(BASE/repo),'rev-parse','HEAD']).strip()
        if actual != expected:
            raise RuntimeError('Production release changed; reconcile before cutover')
    for name,item in state['units'].items():
        if hashlib.sha256(run(['systemctl','cat',name]).encode()).hexdigest()!=item['definition_sha256']:
            raise RuntimeError('Service definition changed since preparation')
    if system_units()!=set(state['units']):
        raise RuntimeError('Source restart paths changed since preparation')
    current_cron={str(path) for path in cron_paths() if any(line.strip() and not line.lstrip().startswith('#') and match(line) for line in path.read_text().splitlines())}
    if current_cron!=set(state['cron']):
        raise RuntimeError('Source cron inventory changed since preparation')
    for name,item in state['cron'].items():
        if checksum(Path(name))!=item['sha256']:raise RuntimeError('Source cron changed since preparation')
    for name,key in state['sites'].items():
        if Path(name).read_bytes()!=(ROOT/'sites'/key).read_bytes():raise RuntimeError('Source vhost changed since preparation')
    state['phase'] = 'fencing-started'; save(state)
    # Persistent deployment lock survives SSH disconnects and this command exit.
    lock = Path('/etc/systemd/system/vendistri-cutover-lock.service')
    lock.write_text('[Unit]\nDescription=Vendistri cutover deployment lock\nConditionPathExists=/var/lib/vendistri-cutover/fencing-started\n[Service]\nType=simple\nExecStart=/usr/bin/flock --exclusive --nonblock /run/lock/vendistri-deploy.lock /usr/bin/sleep infinity\nRestart=no\n[Install]\nWantedBy=multi-user.target\n')
    (ROOT/'fencing-started').touch()
    run(['systemctl', 'daemon-reload']); run(['systemctl', 'enable', '--now', 'vendistri-cutover-lock.service'])
    time.sleep(.2)
    run(['systemctl', 'is-active', '--quiet', 'vendistri-cutover-lock.service'])
    for name, item in state['cron'].items():
        path = Path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('Cron changed since preparation')
        original = (ROOT / 'cron' / item['backup']).read_text()
        updated = '\n'.join('# vendistri-cutover-fenced ' + line if line.strip() and not line.lstrip().startswith('#') and match(line) else line for line in original.splitlines()) + '\n'
        path.write_text(updated); item['fenced_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        save(state)
    state['phase'] = 'draining'; save(state); route(state, 'maintenance')
    first = set(PAUSE_FIRST) | (set(state['units']) - set(UNITS))
    for name in first:
        folder = Path('/etc/systemd/system') / (name + '.d'); folder.mkdir(exist_ok=True)
        (folder / '99-cutover-fence.conf').write_text('[Unit]\nConditionPathExists=/var/lib/vendistri-cutover/allow-source-start\n')
    run(['systemctl', 'daemon-reload'])
    for name in first:
        run(['systemctl', 'stop', name])
    environment = json.loads((ROOT / 'runtime-environment.json').read_text())
    deadline = time.monotonic() + 180
    while True:
        counts = app(DRAIN_CODE, environment)
        state['last_drain'] = counts; save(state)
        if counts['workers'] != 5:
            raise RuntimeError('Expected five responding source workers; cannot prove a complete drain')
        if not any(counts[key] for key in ('active', 'reserved', 'eta', 'queued', 'unacked')):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Work is not drained; keep source in maintenance and reconcile or recover pre-write')
        time.sleep(3)
    for name in state['units']:
        run(['systemctl', 'stop', name])
    # Runtime masks cannot override real /etc unit files, so use drop-ins as a
    # persistent start/autoboot fence. No unrelated unit is changed.
    for name in state['units']:
        folder = Path('/etc/systemd/system') / (name + '.d'); folder.mkdir(exist_ok=True)
        (folder / '99-cutover-fence.conf').write_text('[Unit]\nConditionPathExists=/var/lib/vendistri-cutover/allow-source-start\n')
    run(['systemctl', 'daemon-reload'])
    for process in Path('/proc').glob('[0-9]*'):
        try:
            cwd=(process/'cwd').resolve()
            if cwd==BASE or str(cwd).startswith(str(BASE)+'/'):
                raise RuntimeError('Detached application process remains; inspect before database fencing')
        except (FileNotFoundError,ProcessLookupError,PermissionError):
            pass
    fence_database()
    state['phase'] = 'fenced'; save(state)


def snapshot(state):
    if state['phase'] != 'fenced' or state['authority'] != 'source':
        raise RuntimeError('Final snapshot requires a fenced source before AWS authority')
    folder = ROOT / ('final-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(mode=0o700)
    state['snapshot_directory']=str(folder);save(state)
    with (folder / 'database.dump').open('xb') as output:
        subprocess.run(['runuser', '-u', 'postgres', '--', '/usr/bin/pg_dump', '-Fc', '-d', 'proclaws_prod'], stdout=output, stderr=subprocess.PIPE, check=True)
    def query(statement):
        wrapped = "SELECT coalesce(json_agg(row_to_json(t)),'[]') FROM (" + statement + ') t'
        rows = json.loads(run(['runuser','-u','postgres','--','/usr/bin/psql','-XAt','-v','ON_ERROR_STOP=1','-d','proclaws_prod','-c',wrapped]))
        return [list(row.values()) for row in rows]
    (folder/'database-inventory.json').write_text(json.dumps(collect(query)))
    with (folder / 'media.tar.gz').open('xb') as output:
        subprocess.run(['runuser', '-u', 'akatary', '--', '/usr/bin/tar', '-czf', '-', '-C', '/var/www/vendistri/be', 'media', 'private_media'], stdout=output, stderr=subprocess.PIPE, check=True)
    # The live scheduler remains on local storage. Copy the entire closed DBM
    # basename, including any SQLite sidecars, without starting Beat.
    scheduler = sorted((BASE / 'backend/run').glob('celerybeat-schedule*'))
    if not scheduler:
        raise RuntimeError('Closed scheduler state not found at reviewed path')
    with tarfile.open(folder / 'scheduler.tar.gz', 'w:gz') as archive:
        for path in scheduler:
            if not path.is_file() or path.is_symlink():
                raise RuntimeError('Unexpected scheduler member')
            archive.add(path, arcname=path.name, recursive=False)
    environment = json.loads((ROOT / 'runtime-environment.json').read_text())
    code = "import sys;sys.path.insert(0,'/usr/local/lib/vendistri-cutover');from cutover_redis import source_export;source_export()"
    info = app(code, environment)
    (folder / 'redis.json').write_text(json.dumps(info))
    manifest = {path.name: {'bytes': path.stat().st_size, 'sha256': checksum(path)}
                for path in folder.iterdir() if path.is_file()}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    state['phase'] = 'snapshot-complete'; state['manifest'] = manifest; save(state)


def recover(state):
    if state['authority'] != 'source' or (ROOT/'aws-authority').exists():
        raise RuntimeError('AWS authority committed: DNS-only/source database rollback is forbidden')
    if state['phase'] not in ('fencing-started','draining','fenced','snapshot-complete'):
        raise RuntimeError('No pre-write maintenance phase to recover')
    recover_database(state)
    for name in state['units']:
        (Path('/etc/systemd/system') / (name + '.d/99-cutover-fence.conf')).unlink(missing_ok=True)
    for name, item in state['cron'].items():
        path = Path(name)
        if item.get('fenced_sha256') and hashlib.sha256(path.read_bytes()).hexdigest() != item['fenced_sha256']:
            raise RuntimeError('Cron edited after fencing; manual merge required')
        shutil.copy2(ROOT / 'cron' / item['backup'], path)
    for name, key in state['sites'].items():
        Path(name).write_bytes((ROOT / 'sites' / key).read_bytes())
    run(['apache2ctl', 'configtest']); run(['systemctl', 'reload', 'apache2'])
    run(['systemctl', 'daemon-reload'])
    for name, props in state['units'].items():
        if props['ActiveState'] == 'active':
            run(['systemctl', 'start', name])
    run(['systemctl', 'disable', '--now', 'vendistri-cutover-lock.service'])
    (ROOT/'fencing-started').unlink(missing_ok=True)
    state['phase'] = 'recovered-source'; state['ingress'] = 'original'; save(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'status', 'fence', 'snapshot', 'recover-prewrite', 'mark-aws', 'route-aws', 'maintenance',
                                          'stream-db', 'stream-media', 'stream-scheduler', 'stream-redis', 'stream-manifest', 'stream-inventory'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Requires the installed root-owned control with sudo')
    os.chdir('/tmp'); os.umask(0o077)
    if args.action=='status' and not STATE.exists():
        print(json.dumps({'phase':'not-prepared','authority':'source','fencing_marker_present':(ROOT/'fencing-started').exists()}))
        return
    if args.action == 'prepare':
        state = prepare()
    else:
        state = load()
    if args.action == 'fence':
        fence(state)
    elif args.action == 'snapshot':
        snapshot(state)
    elif args.action == 'recover-prewrite':
        recover(state)
    elif args.action == 'mark-aws':
        if state['phase'] != 'snapshot-complete':
            raise RuntimeError('A complete final snapshot is required before AWS commitment')
        (ROOT/'aws-authority').touch()
        state['authority'] = 'aws'; save(state)
    elif args.action == 'route-aws':
        if state['authority'] != 'aws':
            raise RuntimeError('AWS authority must be committed before routing')
        run(['systemctl','enable','--now','vendistri-aws-ingress.service'])
        run(['systemctl','is-active','--quiet','vendistri-aws-ingress.service'])
        route(state, 'aws')
    elif args.action == 'maintenance':
        route(state, 'maintenance')
    elif args.action.startswith('stream-'):
        if state['phase'] != 'snapshot-complete':
            raise RuntimeError('Final snapshot is not complete')
        name = {'stream-db': 'database.dump', 'stream-media': 'media.tar.gz', 'stream-scheduler': 'scheduler.tar.gz',
                'stream-redis': 'redis.json', 'stream-manifest': 'manifest.json', 'stream-inventory': 'database-inventory.json'}[args.action]
        with (Path(state['snapshot_directory']) / name).open('rb') as stream:
            shutil.copyfileobj(stream, sys.stdout.buffer)
        return
    print(json.dumps({'phase': state['phase'], 'authority': state['authority'], 'ingress': state.get('ingress', 'original'),
                      'controlled_units': len(state['units']), 'controlled_cron_files': len(state['cron'])}))


if __name__ == '__main__':
    main()
