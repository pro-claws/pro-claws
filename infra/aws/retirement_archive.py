#!/usr/bin/python3 -I
"""Fixed-scope root archive reader for the retired Linode Vendistri install.

No deletion, service changes, application imports or AWS credentials. All five
local databases and the historical files are preserved before source retirement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path('/var/lib/vendistri-retirement-20261028')
STATE = Path('/var/lib/vendistri-cutover/state.json')
DATABASES = ('proclaws_prod', 'test_proclaws_prod_1', 'test_proclaws_prod_2',
             'test_proclaws_prod_3', 'test_proclaws_prod_4')
APP_PATHS = ('/home/akatary/pro_claws', '/var/www/vendistri',
             '/home/akatary/proclaws_mo', '/home/akatary/vendistri_2.0',
             '/home/akatary/weather-code-rollbacks',
             '/home/akatary/travel-code-rollbacks', '/home/akatary/portal-code-rollbacks')
UNITS = ('proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service',
         'vendistri-bg-tasks.service', 'vendistri-telemetry-worker.service',
         'vendistri-documents-worker.service', 'vendistri-shipping-worker.service',
         'vendistri-health-worker.service', 'vendistri-celery-beat.service',
         'vendistri-telemetry-intake.service', 'vendistri-celery-worker.service')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def context():
    if os.geteuid() != 0:
        raise RuntimeError('Requires the fixed-scope root helper')
    if STATE.is_symlink() or STATE.stat().st_uid != 0:
        raise RuntimeError('Invalid authority state ownership')
    if json.loads(STATE.read_text()).get('authority') != 'aws':
        raise RuntimeError('AWS writer authority is required')
    for unit in UNITS:
        result = subprocess.run(['/usr/bin/systemctl', 'show', unit, '-p', 'ActiveState',
                                 '--value'], capture_output=True, text=True, env=ENV, timeout=15)
        if result.returncode or result.stdout.strip() not in ('inactive', 'failed'):
            raise RuntimeError('Source writer is not stopped: ' + unit)
    if ROOT.is_symlink():
        raise RuntimeError('Archive metadata root must not be a link')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    info = ROOT.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError('Archive metadata root must be root-owned mode 0700')


def safe_source(path):
    """Archive only explicitly scoped roots, without following root symlinks."""
    if path.is_symlink() or path.resolve() != path:
        raise RuntimeError('Unexpected link at archive root: ' + str(path))
    return path.exists()


def roots():
    paths = [Path(name) for name in APP_PATHS]
    paths += [Path('/var/lib/vendistri-cutover'), Path('/usr/local/lib/vendistri-cutover'),
              Path('/etc/proclaws')]
    for name in ('vendistri-cutover', 'vendistri-install-cutover',
                 'vendistri-migration-audit', 'vendistri-retirement-audit',
                 'vendistri-retirement-archive'):
        paths.append(Path('/usr/local/sbin') / name)
    for unit in (*UNITS, 'vendistri-aws-ingress.service', 'vendistri-cutover-lock.service'):
        paths += [Path('/etc/systemd/system') / unit,
                  Path('/etc/systemd/system') / (unit + '.d')]
    for folder in ('/etc/apache2/sites-available', '/etc/apache2/sites-enabled'):
        # Preserve legacy Vendistri configs/backups; do not include unrelated sites.
        for prefix in ('vendistri', 'secure.vendistri', 'open.vendistri'):
            paths += sorted(Path(folder).glob(prefix + '*.conf*'))
    for domain in ('vendistri.com', 'secure.vendistri.com', 'open.vendistri.com'):
        paths += [Path('/etc/letsencrypt/live') / domain,
                  Path('/etc/letsencrypt/archive') / domain,
                  Path('/etc/letsencrypt/renewal') / (domain + '.conf')]
    selected = []
    for path in paths:
        if path.is_symlink():
            # Config symlinks are preserved as links, not dereferenced. Targets
            # in sites-available/systemd remain separate reviewed archive roots.
            if str(path).startswith(('/etc/apache2/', '/etc/systemd/system/')):
                selected.append(path)
                continue
            raise RuntimeError('Unexpected source root link: ' + str(path))
        if safe_source(path):
            selected.append(path)
    return sorted(set(selected), key=str)


def prepare():
    context()
    selected = roots()
    for folder in ('metadata', 'databases'):
        path = ROOT / folder
        if path.is_symlink():
            raise RuntimeError('Invalid metadata directory')
        path.mkdir(mode=0o700, exist_ok=True)
    receipt = ROOT / 'metadata/manifest.json'
    if receipt.exists():
        return status()
    dump_rows = []
    for database in DATABASES:
        path = ROOT / 'databases' / (database + '.dump')
        if path.exists() or path.is_symlink():
            raise RuntimeError('Existing incomplete dump requires review; never overwrite')
        with path.open('xb') as output, (ROOT / 'prepare-private-error.log').open('ab') as error:
            result = subprocess.run(['/usr/sbin/runuser', '-u', 'postgres', '--',
                                     '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
                                     '/usr/bin/pg_dump', '-Fc', '-h', '/var/run/postgresql',
                                     '-p', '5432', '-U', 'postgres', '-d', database],
                                    stdout=output, stderr=error, env=ENV)
        if result.returncode or path.stat().st_size < 100:
            raise RuntimeError('Local database archival failed; private diagnostics retained')
        dump_rows.append({'database': database, 'bytes': path.stat().st_size, 'sha256': digest(path)})
    data = {'source_authority': 'aws', 'archive_roots': [str(path) for path in selected],
            'database_dumps': dump_rows, 'deletion_performed': False,
            'note': 'Historical archive; live AWS data is separate and newer.'}
    receipt.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data))


def prepared():
    path = ROOT / 'metadata/manifest.json'
    if not path.exists():
        raise RuntimeError('Archive preparation is incomplete')
    body = json.loads(path.read_text())
    if body['archive_roots'] != [str(path) for path in roots()]:
        raise RuntimeError('Archive root inventory changed')
    for row in body['database_dumps']:
        dump = ROOT / 'databases' / (row['database'] + '.dump')
        if dump.stat().st_size != row['bytes'] or digest(dump) != row['sha256']:
            raise RuntimeError('Prepared database dump mismatch')
    return body


def status():
    context()
    print(json.dumps(prepared()))


def stream():
    context()
    body = prepared()
    selected = roots()
    if body['archive_roots'] != [str(path) for path in selected]:
        raise RuntimeError('Archive root inventory changed')
    selected += [ROOT / 'metadata', ROOT / 'databases']
    command = ['/usr/bin/nice', '-n', '19', '/usr/bin/ionice', '-c', '3',
               '/usr/bin/tar', '--create', '--numeric-owner', '--acls', '--xattrs',
               '--one-file-system', '--use-compress-program=/usr/bin/gzip -1',
               '--file=-', '--directory=/', '--',
               *[str(path).lstrip('/') for path in selected]]
    with (ROOT / 'stream-private-error.log').open('ab') as error:
        result = subprocess.run(command, stdout=sys.stdout.buffer, stderr=error, env=ENV)
    if result.returncode:
        raise RuntimeError('Archive stream was incomplete; do not complete or delete inputs')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'status', 'stream'))
    action = parser.parse_args().action
    {'prepare': prepare, 'status': status, 'stream': stream}[action]()


if __name__ == '__main__':
    main()
