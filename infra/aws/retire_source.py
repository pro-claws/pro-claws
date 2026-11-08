#!/usr/bin/python3 -I
"""Fixed-scope Vendistri retirement on Linode, preserving shared projects.

Requires a pinned, fresh essential AWS recovery proof. Historical disposal was
explicitly authorized. No application imports, AWS credentials or arbitrary paths.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path('/var/lib/vendistri-retirement-control')
OLD = Path('/var/lib/vendistri-cutover')
APP_PATHS = ('/home/akatary/pro_claws', '/var/www/vendistri',
             '/home/akatary/proclaws_mo', '/home/akatary/vendistri_2.0',
             '/home/akatary/weather-code-rollbacks', '/home/akatary/travel-code-rollbacks',
             '/home/akatary/portal-code-rollbacks')
DATABASES = ('proclaws_prod', 'test_proclaws_prod_1', 'test_proclaws_prod_2',
             'test_proclaws_prod_3', 'test_proclaws_prod_4')
UNITS = ('proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service',
         'vendistri-bg-tasks.service', 'vendistri-telemetry-worker.service',
         'vendistri-documents-worker.service', 'vendistri-shipping-worker.service',
         'vendistri-health-worker.service', 'vendistri-celery-beat.service',
         'vendistri-telemetry-intake.service', 'vendistri-celery-worker.service')
EXEMPT = ('vendistri-aws-ingress.service', 'vendistri-cutover-lock.service')
DOMAINS = ('vendistri.com', 'www.vendistri.com', 'secure.vendistri.com', 'open.vendistri.com')
CERTS = ('vendistri.com', 'secure.vendistri.com', 'open.vendistri.com')
SCOPE = re.compile(r'vendistri|proclaws|' + '|'.join(re.escape(name) for name in APP_PATHS), re.I)
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
DATE = re.compile(r'\[([^\]]+)\]')
REQUEST = re.compile(r'"(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) ([^ ]+) HTTP/[^\"]+" (\d{3})')
PRIVATE_POLICY_HASH = '5b05ae5edf006bf8865e827ae645f1c4cf17cdeebba737cd923a2c9dd9b1c6be'


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=120)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout


def sql(query):
    return run(['/usr/sbin/runuser', '-u', 'postgres', '--', '/usr/bin/env', '-i',
                'PATH=/usr/bin:/bin', '/usr/bin/psql', '-XAt', '-h',
                '/var/run/postgresql', '-p', '5432', '-U', 'postgres', '-d',
                'postgres', '-v', 'ON_ERROR_STOP=1', '-c', query])


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(body):
    path = ROOT / 'state.new'
    path.write_text(json.dumps(body, indent=2) + '\n'); path.chmod(0o600)
    path.replace(ROOT / 'state.json')


def state():
    path = ROOT / 'state.json'
    return json.loads(path.read_text()) if path.exists() else {}


def secure_path(path):
    if path.is_symlink() or path.resolve() != path:
        raise RuntimeError('Unexpected symlink at removal root: ' + str(path))
    if path.exists() and not path.is_dir():
        raise RuntimeError('Expected directory: ' + str(path))


def context():
    if os.geteuid() != 0 or ROOT.is_symlink() or ROOT.stat().st_uid != 0:
        raise RuntimeError('Requires root-owned installed retirement controls')
    proof = json.loads((ROOT / 'recovery-proof.json').read_text())
    age = datetime.now(timezone.utc) - datetime.fromisoformat(proof['verified_at_utc'])
    if not timedelta(0) <= age < timedelta(hours=24):
        raise RuntimeError('Fresh AWS recovery verification is required')
    required = {'database.dump', 'media.tar.gz', 'redis.json', 'scheduler.tar.gz', 'database-inventory.json'}
    if {row['name'] for row in proof['essential_payloads_verified']} != required:
        raise RuntimeError('Incomplete essential recovery proof')
    if not proof.get('historical_disposal_authorized') or not proof.get('aws_is_writer_authority'):
        raise RuntimeError('Missing retirement authority')
    if not (state().get('data_retired') or state().get('data_retiring')):
        if json.loads((OLD / 'state.json').read_text()).get('authority') != 'aws':
            raise RuntimeError('Source is not fenced behind AWS authority')
    return proof


def aws_health():
    for host in DOMAINS:
        addresses = {row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or addresses & {'45.79.165.178', '2600:3c03::f03c:93ff:fe5e:4818'}:
            raise RuntimeError('Source address still resolves for an application hostname')
    with urlopen('https://secure.vendistri.com/vendistri/be/health/ready', timeout=20) as response:
        if response.status != 200 or json.loads(response.read(4096)).get('status') != 'ready':
            raise RuntimeError('AWS readiness failed')


def databases():
    return json.loads(sql("""SELECT coalesce(json_agg(row_to_json(q)), '[]'::json) FROM (
      SELECT d.datname, r.rolname AS owner, d.datconnlimit,
       (SELECT count(*) FROM pg_stat_activity a WHERE a.datid=d.oid) AS connections
      FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba
      WHERE NOT d.datistemplate ORDER BY d.datname) q"""))


def validate_databases(rows):
    for row in rows:
        if row['datname'] in DATABASES:
            if row['owner'] != 'proclaws_app' or row['connections']:
                raise RuntimeError('Old database ownership/connections changed')
            if row['datname'] == 'proclaws_prod' and row['datconnlimit'] != 0:
                raise RuntimeError('Old production database is not fenced')
        elif row['owner'] == 'proclaws_app':
            raise RuntimeError('Application role owns a database outside the approved scope')


def mount_guard(paths, text):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 5:
            raise RuntimeError('Unparseable mount inventory')
        target = fields[4].replace('\\040', ' ')
        if any(target == root or target.startswith(root + '/') for root in paths):
            raise RuntimeError('Mounted data inside a removal root')


def refers_to_source(text):
    if SCOPE.search(text): return True
    for name in re.findall(r'/(?:usr/local/(?:s?bin)|home|opt)/[^\s\x27\x22;|&()]+', text):
        path = Path(name)
        if path.is_file() and path.stat().st_size < 256000:
            body = path.read_bytes()
            if b'\0' not in body and SCOPE.search(body.decode(errors='replace')):
                return True
    return False


def references():
    for unit in UNITS:
        active = run(['/usr/bin/systemctl', 'show', unit, '-p', 'ActiveState', '--value']).strip()
        if active not in ('inactive', 'failed'):
            raise RuntimeError('Source writer still active: ' + unit)
    for line in run(['/usr/bin/systemctl', 'list-unit-files', '--no-legend', '--no-pager']).splitlines():
        name = line.split()[0]
        if name in (*UNITS, *EXEMPT) or not name.endswith(('.service', '.timer', '.socket', '.path')):
            continue
        result = subprocess.run(['/usr/bin/systemctl', 'cat', name], capture_output=True, text=True, env=ENV)
        if result.returncode == 0 and refers_to_source(result.stdout):
            raise RuntimeError('Unexpected unit references Vendistri: ' + name)
    files = [Path('/etc/crontab')]
    for folder in ('/etc/cron.d', '/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly',
                   '/etc/cron.monthly', '/var/spool/cron/crontabs'):
        files += list(Path(folder).glob('*'))
    for path in files:
        if path.is_file():
            for line in path.read_text(errors='replace').splitlines():
                if line.strip() and not line.lstrip().startswith('#') and refers_to_source(line):
                    raise RuntimeError('Cron references require separate review: ' + str(path))
    for path in Path('/etc/letsencrypt/renewal-hooks').glob('*/*'):
        if path.is_file() and refers_to_source(path.read_text(errors='replace')):
            raise RuntimeError('Certificate renewal hook requires separate review: ' + str(path))
    allowed = set(vhosts() + private_policies())
    for folder in ('sites-enabled', 'conf-enabled'):
        for path in (Path('/etc/apache2') / folder).glob('*.conf'):
            if path not in allowed and refers_to_source(path.read_text(errors='replace')):
                raise RuntimeError('Shared Apache configuration references source data: ' + str(path))
    for root in APP_PATHS:
        secure_path(Path(root))
    mount_guard(APP_PATHS, Path('/proc/self/mountinfo').read_text())
    for proc in Path('/proc').glob('[0-9]*'):
        for item in ('exe', 'cwd'):
            try:
                target = os.readlink(proc / item)
            except (OSError, PermissionError):
                continue
            if any(target == root or target.startswith(root + '/') for root in APP_PATHS):
                raise RuntimeError('A running process still uses a removal root: PID ' + proc.name)


def validate_vhost(body):
    names = re.findall(r'^\s*Server(?:Name|Alias)\s+(.+)', body, re.M)
    if not names or any(word not in DOMAINS for row in names for word in row.split()):
        raise RuntimeError('Shared/unknown domain in candidate vhost')


def vhosts():
    result = []
    for folder in ('sites-enabled', 'sites-available'):
        for prefix in ('vendistri', 'secure.vendistri', 'open.vendistri'):
            for path in sorted((Path('/etc/apache2') / folder).glob(prefix + '*.conf*')):
                body = path.read_text()
                validate_vhost(body)
                result.append(path)
    return sorted(set(result), key=str)


def private_policies():
    result = []
    for folder in ('conf-available', 'conf-enabled'):
        path = Path('/etc/apache2') / folder / 'vendistri-private-media.conf'
        if path.exists() or path.is_symlink():
            if digest(path) != PRIVATE_POLICY_HASH:
                raise RuntimeError('Vendistri private-media policy changed; retain it for review')
            result.append(path)
    return result


def traffic(lines, now):
    counts = Counter()
    for line in lines:
        match = DATE.search(line)
        if not match:
            counts['unparseable'] += 1; continue
        try:
            when = datetime.strptime(match[1], '%d/%b/%Y:%H:%M:%S %z')
        except ValueError:
            counts['unparseable'] += 1; continue
        if not now - timedelta(hours=24) <= when <= now:
            continue
        request = REQUEST.search(line)
        if not request:
            if re.search(r'" [45]\d{2} ', line):
                counts['non_http_error_requests'] += 1; continue
            # Combined logs may include additional RFC methods (e.g. PROPFIND)
            # and HTTP/0.9 request lines. Parse their bounded request/status
            # fields without exposing request contents or ignoring app routes.
            parts = line.split('"')
            fields = parts[1].split() if len(parts) > 2 else []
            status_fields = parts[2].split() if len(parts) > 2 else []
            if (len(fields) >= 2 and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', fields[0])
                    and status_fields and re.fullmatch(r'\d{3}', status_fields[0])):
                path, status = fields[1], status_fields[0]
                counts['additional_http_formats'] += 1
            else:
                counts['unparseable'] += 1; continue
        else:
            path, status = request.groups()
        path = path.split('?', 1)[0]
        counts['requests_24h_shared_or_vendor'] += 1
        if int(status) < 400 and (path.startswith('/vendistri/be/') and '/health/' not in path
                                  or path.startswith(('/ws/', '/vendistri/be/ws/', '/static/js/'))
                                  or path in ('/asset-manifest.json', '/version.json')):
            counts['successful_application_like_requests'] += 1
    return dict(counts)


def traffic_summary():
    counts = Counter(); now = datetime.now(timezone.utc)
    for path in Path('/var/log/apache2').glob('*access.log*'):
        if path.is_symlink() or not path.is_file() or path.stat().st_mtime < (now-timedelta(days=2)).timestamp():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', errors='replace') as stream:
            counts.update(traffic(stream, now))
    return dict(counts)


def config_paths():
    result = vhosts() + private_policies() + [Path('/etc/proclaws'), Path('/usr/local/sbin/vendistri-deploy')]
    for unit in (*UNITS, *EXEMPT):
        result += [Path('/etc/systemd/system') / unit,
                   Path('/etc/systemd/system') / (unit + '.d')]
    for name in ('vendistri-cutover', 'vendistri-deploy', 'vendistri-retirement-archive'):
        result.append(Path('/etc/sudoers.d') / name)
    return [str(path).lstrip('/') for path in result if path.exists() or path.is_symlink()]


def audit():
    context(); aws_health(); references(); rows = databases(); validate_databases(rows)
    run(['/usr/sbin/apache2ctl', 'configtest'])
    current = state()
    if not (ROOT / 'configuration.tar.gz').exists():
        run(['/usr/bin/tar', '-czf', str(ROOT / 'configuration.tar.gz'), '-C', '/', '--', *config_paths()])
    current.update(audited_at_utc=datetime.now(timezone.utc).isoformat(),
                   akatary_vhost_sha256=digest(Path('/etc/apache2/sites-enabled/akatary.conf')),
                   configuration_sha256=digest(ROOT / 'configuration.tar.gz'),
                   source_databases=rows, traffic=traffic_summary())
    save(current)
    print(json.dumps({'audit': 'passed', 'configuration_sha256': current['configuration_sha256'],
                      'traffic': current['traffic'], 'deletion_performed': False}))


def stream_config():
    context()
    with (ROOT / 'configuration.tar.gz').open('rb') as stream:
        shutil.copyfileobj(stream, sys.stdout.buffer)


def confirm_config():
    context(); body = json.loads(sys.stdin.readline()); parsed = urlsplit(body['url'])
    hosts = {'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com',
             'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.us-east-1.amazonaws.com'}
    if parsed.scheme != 'https' or parsed.hostname not in hosts:
        raise RuntimeError('Unapproved configuration backup location')
    with urlopen(body['url'], timeout=30) as response:
        data = response.read(4*1024*1024+1)
    if len(data) > 4*1024*1024 or hashlib.sha256(data).hexdigest() != state()['configuration_sha256']:
        raise RuntimeError('Configuration backup verification failed')
    current = state(); current['configuration_verified_offsite'] = True; save(current)
    print(json.dumps({'small_configuration_backup_verified': True}))


def retire_data():
    context(); aws_health(); references(); validate_databases(databases())
    current = state()
    if not current.get('configuration_verified_offsite'):
        raise RuntimeError('Small configuration recovery copy must be verified first')
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError('Safe directory removal is unavailable')
    for path in vhosts():
        if path.parent.name == 'sites-enabled' and path.suffix == '.conf' and ':443' in path.read_text():
            if 'ProxyPass / http://127.0.0.1:18080/' not in path.read_text():
                raise RuntimeError('Old vhost still serves source data')
    current['data_retiring'] = True; save(current)
    for unit in UNITS:
        run(['/usr/bin/systemctl', 'disable', unit])
    # Disable the old deploy entry point before releasing its lifetime lock.
    for name in ('/etc/sudoers.d/vendistri-deploy', '/usr/local/sbin/vendistri-deploy'):
        Path(name).unlink(missing_ok=True)
    run(['/usr/bin/systemctl', 'disable', '--now', 'vendistri-cutover-lock.service'])
    for row in databases():
        if row['datname'] in DATABASES:
            sql('DROP DATABASE "' + row['datname'] + '"')
    for name in APP_PATHS:
        path = Path(name); secure_path(path)
        if path.exists():
            shutil.rmtree(path)
    for name in ('/etc/proclaws', '/var/lib/vendistri-retirement-20261028'):
        path = Path(name); secure_path(path)
        if path.exists(): shutil.rmtree(path)
    for name in ('vendistri-cutover', 'vendistri-retirement-archive'):
        (Path('/etc/sudoers.d') / name).unlink(missing_ok=True)
    for path in OLD.iterdir() if OLD.exists() else ():
        if path.name == 'aws-authority': continue
        if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
        else: path.unlink()
    current.update(data_retired=True, data_retired_at_utc=datetime.now(timezone.utc).isoformat(),
                   dropped_source_databases=list(DATABASES), removed_application_roots=list(APP_PATHS))
    save(current)
    print(json.dumps({'phase': 'data-retired', 'aws_untouched': True, 'bridge_retained': True,
                      'shared_services_retained': True}))


def retire_ingress():
    context(); aws_health(); current = state()
    if not current.get('data_retired'): raise RuntimeError('Retire old data first')
    counts = traffic_summary()
    if counts.get('successful_application_like_requests', 0) or counts.get('unparseable', 0):
        raise RuntimeError('Recent app-like traffic or unparseable logs require review; bridge retained')
    if run(['/usr/bin/ss', '-Htn', '( sport = :18080 )']).strip():
        raise RuntimeError('An active ingress connection remains; bridge retained')
    if digest(Path('/etc/apache2/sites-enabled/akatary.conf')) != current['akatary_vhost_sha256']:
        raise RuntimeError('Unrelated Apache site changed; requires review')
    for setting in ('smtpd_tls_cert_file', 'smtpd_tls_key_file', 'smtp_tls_cert_file'):
        if 'vendistri' in run(['/usr/sbin/postconf', '-h', setting]):
            raise RuntimeError('Shared mail references a Vendistri certificate; retain it')
    paths = vhosts() + private_policies()
    prior = [(path, path.read_bytes(), os.readlink(path) if path.is_symlink() else None) for path in paths]
    run(['/usr/sbin/apache2ctl', 'configtest'])
    try:
        for path in paths:
            path.unlink()
        run(['/usr/sbin/apache2ctl', 'configtest']); run(['/usr/bin/systemctl', 'reload', 'apache2'])
    except Exception:
        for path, content, link in prior:
            if path.exists() or path.is_symlink(): continue
            if link: path.symlink_to(link)
            else: path.write_bytes(content); path.chmod(0o644)
        run(['/usr/sbin/apache2ctl', 'configtest']); run(['/usr/bin/systemctl', 'reload', 'apache2'])
        raise
    if Path('/etc/systemd/system/vendistri-aws-ingress.service').exists():
        run(['/usr/bin/systemctl', 'disable', '--now', 'vendistri-aws-ingress.service'])
    current['ingress_retiring'] = True; save(current)
    for unit in (*UNITS, *EXEMPT):
        path = Path('/etc/systemd/system') / unit; path.unlink(missing_ok=True)
        drop = Path('/etc/systemd/system') / (unit + '.d')
        secure_path(drop)
        if drop.exists(): shutil.rmtree(drop)
    for domain in CERTS:
        for category in ('live', 'archive'):
            path = Path('/etc/letsencrypt') / category / domain; secure_path(path)
            if path.exists(): shutil.rmtree(path)
        (Path('/etc/letsencrypt/renewal') / (domain + '.conf')).unlink(missing_ok=True)
    for name in ('/usr/local/lib/vendistri-cutover', '/var/lib/vendistri-cutover'):
        path = Path(name); secure_path(path)
        if path.exists(): shutil.rmtree(path)
    for name in ('vendistri-cutover', 'vendistri-install-cutover', 'vendistri-migration-audit',
                 'vendistri-retirement-archive', 'vendistri-retirement-audit',
                 'vendistri-install-retirement-archive'):
        (Path('/usr/local/sbin') / name).unlink(missing_ok=True)
    run(['/usr/bin/systemctl', 'daemon-reload'])
    for name in ('apache2', 'postgresql', 'redis-server', 'postfix'):
        run(['/usr/bin/systemctl', 'is-active', name])
    if digest(Path('/etc/apache2/sites-enabled/akatary.conf')) != current['akatary_vhost_sha256']:
        raise RuntimeError('Unrelated Apache configuration hash changed')
    # The small recovery copy is already verified in S3; leave no duplicate
    # protected runtime configuration in the retired source control directory.
    (ROOT / 'configuration.tar.gz').unlink(missing_ok=True)
    for name in ('.vendistri-retirement-audit.py', '.vendistri-retirement-archive.py',
                 '.vendistri-install-retirement-archive.py', '.vendistri-retirement-upload.py',
                 '.vendistri-retire-source.py', '.vendistri-recovery-proof.json',
                 '.vendistri-install-retire.py'):
        (Path('/home/akatary') / name).unlink(missing_ok=True)
    current.update(ingress_retired=True, ingress_retired_at_utc=datetime.now(timezone.utc).isoformat(),
                   retained_exceptions=['legacy mail DNS', 'shared Redis data', 'unreviewed external keys',
                                        'empty PostgreSQL role if still present', 'old Linode DNS zone pending API/UI access'])
    save(current); print(json.dumps(current))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'stream-config', 'confirm-config', 'retire-data', 'retire-ingress', 'status'))
    action = parser.parse_args().action
    if action == 'status':
        context(); print(json.dumps(state()))
    else:
        {'audit': audit, 'stream-config': stream_config, 'confirm-config': confirm_config,
         'retire-data': retire_data, 'retire-ingress': retire_ingress}[action]()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'action_stopped': True, 'reason': str(error)}))
        raise SystemExit(1)
