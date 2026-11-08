"""Promote checksummed sources/static assets in the fenced AWS rehearsal only.

Preserves runtime/configuration/data and a source/static rollback receipt. Never
enables consumers, applies migrations, opens the public gate, or promotes data.
Production activation requires a separately reviewed single-writer procedure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request

from install_release import ensure_runtime_directories


REPOSITORIES = {'backend', 'vendistri', 'marketplace', 'home_page'}
UNITS = ['proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service']
CONSUMERS = ['vendistri-celery-beat.service', 'vendistri-bg-tasks.service',
             'vendistri-telemetry-worker.service', 'vendistri-telemetry-intake.service',
             'vendistri-documents-worker.service', 'vendistri-shipping-worker.service',
             'vendistri-health-worker.service']


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(path):
    result = {}
    for line in path.read_text().splitlines():
        checksum, name = line.split('  ', 1)
        parts = PurePosixPath(name).parts
        if (not re.fullmatch('[0-9a-f]{64}', checksum) or not parts
                or name != PurePosixPath(name).as_posix()
                or any(part in ('.', '..') for part in parts)
                or name.startswith('/') or name in result
                or (name != 'source-release.json' and parts[0] not in REPOSITORIES)
                or any(part == '.env' or part.startswith('.env.') for part in parts)):
            raise ValueError('Invalid managed source inventory')
        result[name] = checksum
    if 'source-release.json' not in result or not any(n.startswith('backend/') for n in result):
        raise ValueError('Incomplete source inventory')
    return result


def location(root, name, installed=True):
    relative = '.migration/source-release.json' if installed and name == 'source-release.json' else name
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('Managed source path escapes release or is a symlink')
    return path


def verify(root, checksums, installed=True):
    for name, expected in checksums.items():
        path = location(root, name, installed)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Managed source checksum mismatch: ' + name)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)


def replace_file(source, destination, identity):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.migration-update')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('Temporary source path already exists')
    try:
        shutil.copy2(source, temporary)
        if identity is not None:
            os.chown(temporary, *identity)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def stage_portal(archive_path, expected_digest, staging):
    if digest(archive_path) != expected_digest:
        raise ValueError('Portal archive checksum mismatch')
    if staging.exists():
        raise ValueError('Portal staging path already exists')
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if (not parts or parts[0] != 'fe' or member.name.startswith('/')
                    or '..' in parts or not (member.isfile() or member.isdir())):
                raise ValueError('Unexpected portal archive member')
        staging.mkdir(mode=0o700)
        archive.extractall(staging, filter='data')
    manifest = staging / 'fe/asset-manifest.json'
    if not manifest.is_file() or not (staging / 'fe/index.html').is_file():
        raise ValueError('Incomplete published portal')
    config = json.loads(manifest.read_text())
    for value in config['files'].values():
        path = value.split('?', 1)[0]
        for prefix in ('https://secure.vendistri.com', '/vendistri/fe'):
            if path.startswith(prefix):
                path = path[len(prefix):]
        target = staging / 'fe' / path.lstrip('/')
        if not target.resolve().is_relative_to((staging / 'fe').resolve()) or not target.is_file():
            raise ValueError('Published portal asset missing or unsafe')
    return digest(manifest)


def restore(root, backup, portal, stop, start, health):
    receipt = json.loads((backup / 'receipt.json').read_text())
    stop()
    for name, item in receipt['originals'].items():
        target = location(root, name)
        if item is None:
            target.unlink(missing_ok=True)
        else:
            replace_file(backup / 'files' / name, target, (item['uid'], item['gid']))
    previous_portal = Path(receipt['previous_portal'])
    if previous_portal.exists():
        failed = portal.with_name('.fe-failed-' + backup.name)
        if failed.exists():
            raise ValueError('Failed portal preservation path already exists')
        if portal.exists():
            portal.rename(failed)
        previous_portal.rename(portal)
    verify(root, inventory(backup / 'old.sha256'))
    start()
    health()
    receipt['state'] = 'rolled_back'
    write_json(backup / 'receipt.json', receipt)


def promote(root, source, previous_inventory, portal, archive, archive_digest,
            backup, stop, start, health, new_identity=(1001, 1001)):
    old, new = inventory(previous_inventory), inventory(source / 'source.sha256')
    verify(root, old)
    verify(source, new, installed=False)
    changed = sorted(name for name in old.keys() | new.keys() if old.get(name) != new.get(name))
    for name in changed:
        target = location(root, name)
        if name not in old and (target.exists() or target.is_symlink()):
            raise ValueError('Unmanaged file would be overwritten: ' + name)
    if not portal.is_dir() or portal.is_symlink() or backup.exists():
        raise ValueError('Portal/rollback paths are not suitable for promotion')
    previous_portal = portal.with_name('.fe-previous-' + backup.name)
    staging = portal.with_name('.fe-staging-' + backup.name)
    if previous_portal.exists():
        raise ValueError('Previous portal path already exists')
    manifest_digest = stage_portal(archive, archive_digest, staging)
    ensure_runtime_directories(root, new_identity)
    backup.mkdir(mode=0o700)
    shutil.copy2(previous_inventory, backup / 'old.sha256')
    shutil.copy2(source / 'source.sha256', backup / 'new.sha256')
    originals = {}
    for name in changed:
        path = location(root, name)
        if name in old:
            stat = path.stat()
            originals[name] = {'uid': stat.st_uid, 'gid': stat.st_gid}
            saved = backup / 'files' / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        else:
            originals[name] = None
    receipt = {'state': 'prepared', 'originals': originals,
               'previous_portal': str(previous_portal), 'portal_manifest_sha256': manifest_digest,
               'changed_files': len(changed), 'production_activation': False}
    write_json(backup / 'receipt.json', receipt)
    try:
        stop()
        for name in changed:
            target = location(root, name)
            if name not in new:
                target.unlink()
            else:
                item = originals[name]
                identity = (item['uid'], item['gid']) if item else new_identity
                replace_file(location(source, name, installed=False), target, identity)
        portal.rename(previous_portal)
        (staging / 'fe').rename(portal)
        verify(root, new)
        start()
        health()
        receipt['state'] = 'active'
        write_json(backup / 'receipt.json', receipt)
    except BaseException:
        restore(root, backup, portal, stop, start, health)
        raise
    return receipt


def rehearsal_guard():
    if os.geteuid() != 0 or Path('/etc/vendistri/migration-stage').read_text().strip() != 'rehearsal-configured':
        raise ValueError('Requires an existing root-managed rehearsal')
    config = json.loads(Path('/etc/vendistri/rehearsal.json').read_text())
    if config['database']['name'] != 'vendistri_rehearsal':
        raise ValueError('Refusing non-rehearsal database')
    for unit in CONSUMERS:
        result = subprocess.run(['systemctl', 'is-enabled', unit], capture_output=True, text=True)
        state = subprocess.check_output(['systemctl', 'show', unit, '-p', 'ActiveState', '--value'], text=True).strip()
        if result.stdout.strip() != 'masked' or state not in ('inactive', 'failed'):
            raise ValueError('Production consumer is not fenced: ' + unit)
    for unit in UNITS:
        environment = subprocess.check_output(['systemctl', 'show', unit, '-p', 'Environment', '--value'], text=True)
        denied = subprocess.check_output(['systemctl', 'show', unit, '-p', 'IPAddressDeny', '--value'], text=True)
        if 'DJANGO_SETTINGS_MODULE=vendistri_rehearsal' not in environment or not denied.strip():
            raise ValueError('Application unit is not isolated: ' + unit)
    apache = Path('/etc/apache2/sites-enabled/000-vendistri-rehearsal.conf').read_text()
    if '^/(?!vendistri/be/health/ready/?$)' not in apache or 'Require local' not in apache:
        raise ValueError('Rehearsal public gate is absent')


def health():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            for origin in ('http://127.0.0.1', 'http://127.0.0.1:8003', 'http://127.0.0.1:8005'):
                request = urllib.request.Request(origin + '/vendistri/be/health/ready',
                                                 headers={'Host': 'secure.vendistri.com'})
                with urllib.request.urlopen(request, timeout=3) as response:
                    if response.status != 200:
                        raise OSError('API readiness failed')
            if subprocess.run(['systemctl', 'is-active', '--quiet', *UNITS]).returncode == 0:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError('Rehearsal readiness did not recover')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['promote', 'rollback'])
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--previous-inventory', type=Path)
    parser.add_argument('--portal-archive', type=Path)
    parser.add_argument('--portal-sha256')
    args = parser.parse_args()
    rehearsal_guard()
    root, portal = Path('/home/akatary/pro_claws'), Path('/var/www/vendistri/fe')
    if not args.backup.resolve().is_relative_to(root / '.migration'):
        raise ValueError('Rollback receipt must stay in the migration directory')
    stop = lambda: subprocess.run(['systemctl', 'stop', *UNITS], check=True)
    start = lambda: subprocess.run(['systemctl', 'start', *UNITS], check=True)
    if args.action == 'rollback':
        receipt = json.loads((args.backup / 'receipt.json').read_text())
        if receipt['state'] != 'active' or digest(portal / 'asset-manifest.json') != receipt['portal_manifest_sha256']:
            raise ValueError('Rollback receipt does not identify the active portal')
        verify(root, inventory(args.backup / 'new.sha256'))
        restore(root, args.backup, portal, stop, start, health)
    else:
        if not all((args.source, args.previous_inventory, args.portal_archive, args.portal_sha256)):
            parser.error('Promotion requires source, previous inventory and checksummed portal archive')
        promote(root, args.source, args.previous_inventory, portal, args.portal_archive,
                args.portal_sha256, args.backup, stop, start, health)
    rehearsal_guard()
    print(json.dumps({'action': args.action, 'ready': True, 'consumers_fenced': True,
                      'backup': str(args.backup), 'production_activation': False}))


if __name__ == '__main__':
    main()
