"""Read-only privileged source audit. Never stops or changes production services."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE = Path('/home/akatary/pro_claws')
PATTERN = re.compile(r'/home/akatary/pro_claws(?:/|\b)|/var/www/vendistri(?:/|\b)|\b(?:vendistri|proclaws)(?:[.\-/]|\b)', re.I)
UNITS = ['proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service',
         'vendistri-bg-tasks.service', 'vendistri-telemetry-worker.service',
         'vendistri-documents-worker.service', 'vendistri-shipping-worker.service',
         'vendistri-health-worker.service', 'vendistri-celery-beat.service', 'vendistri-telemetry-intake.service']


def command(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Audit command failed: ' + args[0])
    return result.stdout


def match(text):
    if PATTERN.search(text):
        return True
    # Follow referenced local wrapper scripts for one level, never execute them.
    for name in re.findall(r'/(?:usr/local/(?:s?bin)|home|opt)/[^\s\x27\x22;|&()]+', text):
        path = Path(name)
        try:
            if path.is_file() and path.stat().st_size < 256000:
                body = path.read_bytes()
                if b'\0' not in body and PATTERN.search(body.decode(errors='replace')):
                    return True
        except OSError:
            pass
    return False


def audit():
    if os.geteuid() != 0:
        raise SystemExit('Run the read-only audit with sudo in your terminal')
    cron = []
    paths = [Path('/etc/crontab')]
    for folder in ['/etc/cron.d', '/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly',
                   '/etc/cron.monthly', '/var/spool/cron/crontabs']:
        paths.extend(path for path in Path(folder).glob('*') if path.is_file())
    for path in paths:
        if not path.is_file():
            continue
        body = path.read_bytes()
        lines = [line for line in body.decode(errors='replace').splitlines()
                 if line.strip() and not line.lstrip().startswith('#') and match(line)]
        if lines:
            cron.append({'path': str(path), 'sha256': hashlib.sha256(body).hexdigest(),
                         'matching_active_lines': len(lines),
                         'line_sha256': [hashlib.sha256(line.encode()).hexdigest() for line in lines]})
    names = command(['systemctl', 'list-unit-files', '--no-legend', '--no-pager']).splitlines()
    candidates = []
    for row in names:
        name = row.split()[0]
        if not name.endswith(('.service', '.timer', '.socket', '.path')):
            continue
        result = subprocess.run(['systemctl', 'cat', name], capture_output=True, text=True)
        if result.returncode or not match(result.stdout):
            continue
        properties = command(['systemctl', 'show', name, '-p', 'ActiveState', '-p', 'UnitFileState', '-p', 'FragmentPath'])
        candidates.append({'unit': name, **dict(line.split('=', 1) for line in properties.splitlines())})
    sql = """SELECT json_build_object('source_database_exists',EXISTS(SELECT 1 FROM pg_database WHERE datname='proclaws_prod'),
      'source_database_owned_by_application',EXISTS(SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname='proclaws_prod' AND r.rolname='proclaws_app'),
      'application_role_superuser',(SELECT rolsuper FROM pg_roles WHERE rolname='proclaws_app'),
      'application_role_login',(SELECT rolcanlogin FROM pg_roles WHERE rolname='proclaws_app'),
      'other_database_ownership_count',(SELECT count(*) FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE r.rolname='proclaws_app' AND d.datname<>'proclaws_prod'),
      'other_database_active_connections',(SELECT count(*) FROM pg_stat_activity WHERE usename='proclaws_app' AND datname<>'proclaws_prod'))"""
    database = json.loads(command(['runuser', '-u', 'postgres', '--', '/usr/bin/psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres', '-c', sql]))
    result = {'read_only_audit': True, 'cron_matches': cron, 'matching_units': candidates,
              'database_fencing_scope': database, 'production_changed': False}
    target = BASE / '.migration/aws-20261024/source-root-audit.json'
    # Write the sanitized receipt as the application user, never use root to
    # follow a path inside an application-writable directory.
    writer = "import os,sys;fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600);os.fchmod(fd,0o600);out=os.fdopen(fd,'w');out.write(sys.stdin.read());out.close()"
    subprocess.run(['runuser', '-u', 'akatary', '--', '/usr/bin/python3', '-c', writer, str(target)],
                   input=json.dumps(result, indent=2) + '\n', text=True, capture_output=True, check=True)
    print(json.dumps({'read_only_audit': 'complete', 'cron_files_matching_platform': len(cron),
                      'matching_unit_count': len(candidates), 'receipt': str(target), 'production_changed': False}))


if __name__ == '__main__':
    audit()
