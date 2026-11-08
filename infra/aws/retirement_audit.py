"""Fixed-scope, read-only Linode retirement audit; no application imports.

Run with /usr/bin/python3 -I after checksum verification. Prints metadata only:
never log lines, URLs, environment values, keys, messages or database contents.
No services, configuration, databases or application files are changed.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


APP_PATHS = (
    '/home/akatary/pro_claws', '/var/www/vendistri',
    '/home/akatary/proclaws_mo', '/home/akatary/vendistri_2.0',
    '/home/akatary/weather-code-rollbacks',
    '/home/akatary/travel-code-rollbacks',
    '/home/akatary/portal-code-rollbacks',
)
LOG_ROOT = Path('/var/log/apache2')
DATE = re.compile(r'\[([^\]]+)\]')
SCOPE = re.compile(r'vendistri|proclaws|/home/akatary/pro_claws(?:/|\b)', re.I)


def run(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Read-only audit command failed: ' + args[0])
    return result.stdout


def traffic_counts(lines, now):
    counts = Counter()
    latest = None
    malformed = 0
    for line in lines:
        match = DATE.search(line)
        if not match:
            malformed += 1
            continue
        try:
            when = datetime.strptime(match[1], '%d/%b/%Y:%H:%M:%S %z')
        except ValueError:
            malformed += 1
            continue
        latest = max(latest, when) if latest else when
        if now - timedelta(hours=24) <= when <= now:
            counts['requests_last_24h'] += 1
        if now - timedelta(hours=1) <= when <= now:
            counts['requests_last_hour'] += 1
    return dict(counts, latest_request_utc=latest.astimezone(timezone.utc).isoformat()
                if latest else None, unparseable_lines=malformed)


def log_inventory(now):
    rows = []
    for path in sorted(LOG_ROOT.glob('*access.log*')):
        if path.is_symlink() or not path.is_file():
            continue
        # Limit the audit to the current and previous three days' rotations.
        if path.stat().st_mtime < (now - timedelta(days=4)).timestamp():
            continue
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', errors='replace') as stream:
            counts = traffic_counts(stream, now)
        rows.append({'file': path.name, 'bytes': path.stat().st_size,
                     'host_attribution': 'open.vendistri.com' if
                     path.name.startswith('open.vendistri.access.log') else
                     'shared_or_unknown; cannot attribute clients to Vendistri',
                     **counts})
    return rows


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run this read-only audit with sudo in your terminal')
    now = datetime.now(timezone.utc)
    state_path = Path('/var/lib/vendistri-cutover/state.json')
    if state_path.is_symlink() or state_path.stat().st_uid != 0:
        raise RuntimeError('Unexpected migration state ownership')
    state = json.loads(state_path.read_text())
    if state.get('authority') != 'aws':
        raise RuntimeError('AWS is not recorded as the writer authority')
    paths = []
    for name in APP_PATHS:
        path = Path(name)
        item = {'path': name, 'exists': path.exists(), 'symlink': path.is_symlink()}
        if path.exists():
            stat = path.lstat()
            item.update(uid=stat.st_uid, gid=stat.st_gid, device=stat.st_dev)
        paths.append(item)
    units = []
    for row in run(['/usr/bin/systemctl', 'list-unit-files', '--no-legend', '--no-pager']).splitlines():
        name = row.split()[0]
        if not name.endswith(('.service', '.timer', '.socket', '.path')):
            continue
        body = subprocess.run(['/usr/bin/systemctl', 'cat', name], capture_output=True,
                              text=True, timeout=15)
        if body.returncode or not SCOPE.search(body.stdout):
            continue
        properties = run(['/usr/bin/systemctl', 'show', name, '-p', 'ActiveState',
                          '-p', 'UnitFileState', '-p', 'FragmentPath'])
        units.append({'unit': name, **dict(line.split('=', 1) for line in
                                           properties.splitlines() if '=' in line)})
    sql = """SELECT json_agg(row_to_json(q)) FROM (
      SELECT d.datname, r.rolname AS owner, d.datconnlimit,
             pg_database_size(d.oid) AS bytes,
             (SELECT count(*) FROM pg_stat_activity a WHERE a.datid=d.oid) AS connections
      FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba
      WHERE NOT d.datistemplate ORDER BY d.datname) q"""
    databases = json.loads(run(['/usr/sbin/runuser', '-u', 'postgres', '--',
                               '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
                               '/usr/bin/psql', '-XAt', '-h', '/var/run/postgresql',
                               '-p', '5432', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
                               '-c', sql]))
    vhosts = []
    for path in sorted(Path('/etc/apache2/sites-enabled').glob('*.conf')):
        body = path.read_bytes()
        vhosts.append({'file': path.name, 'target': str(path.resolve()),
                       'sha256': hashlib.sha256(body).hexdigest(),
                       'server_names': re.findall(r'^\s*ServerName\s+(\S+)',
                                                 body.decode(errors='replace'), re.M)})
    report = {'read_only': True, 'production_changed': False,
              'checked_at_utc': now.isoformat(), 'authority': 'aws',
              'source_phase': state.get('phase'), 'paths': paths, 'units': units,
              'local_databases': databases, 'enabled_vhosts': vhosts,
              'apache_traffic': log_inventory(now),
              'traffic_limit': 'Combined logs omit vhost identity; counts do not prove '
              'which clients are legitimate or that bridge traffic is zero.',
              'deletion_performed': False}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
