"""Install verified migration sources and the archived production dependencies.

Run as root on an initialized AWS rehearsal host. Does not configure credentials
or start application/worker services.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile


def ensure_runtime_directories(root, identity=(1001, 1001)):
    # Logs are deliberately absent from immutable source archives. The deployed
    # handlers create files/locks lazily but require this private parent first.
    logs = root / 'backend/logs'
    if logs.is_symlink() or (logs.exists() and not logs.is_dir()):
        raise ValueError('Application log directory must be a real directory')
    if not logs.exists():
        logs.mkdir(mode=0o750)
        os.chown(logs, *identity)
    if logs.stat().st_uid != identity[0] or not logs.stat().st_mode & 0o200:
        raise ValueError('Application user must own a writable log directory')


def install_runtime_assets(archive_path, digest, root):
    with archive_path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
            raise SystemExit('Runtime asset archive checksum mismatch')
    destination = root / 'private_data/dbip-city.mmdb'
    if destination.exists() or destination.is_symlink():
        raise SystemExit('Refusing to overwrite an installed runtime asset')
    if (root / 'private_data').is_symlink():
        raise SystemExit('Runtime asset directory must not be a link')
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        if len(members) != 1 or not members[0].isfile() or members[0].name != 'private_data/dbip-city.mmdb':
            raise SystemExit('Unexpected runtime asset archive contents')
        archive.extractall(root, filter='data')
    os.chown(destination.parent, 1001, 1001)
    os.chown(destination, 1001, 1001)


def main(source, dependencies, digest, runtime_assets, runtime_digest):
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    marker = Path('/etc/vendistri/migration-stage')
    if not marker.exists() or marker.read_text().strip() != 'packages-installed':
        raise SystemExit('Requires a bootstrapped rehearsal host')
    subprocess.run(['sha256sum', '--check', '--status', 'source.sha256'], cwd=source, check=True)
    with dependencies.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
            raise SystemExit('Dependency archive checksum mismatch')
    account = pwd.getpwnam('akatary')
    if account.pw_uid != 1001 or account.pw_gid != 1001:
        raise SystemExit('Application identity must match the EFS access point UID/GID')
    root = Path('/home/akatary/pro_claws')
    manifest = json.loads((source / 'source-release.json').read_text())
    for name in manifest['repositories']:
        destination = root / name
        if destination.exists():
            raise SystemExit(f'Refusing to overwrite existing {name}')
        shutil.copytree(source / name, destination, symlinks=True)
        subprocess.run(['chown', '-R', 'akatary:akatary', str(destination)], check=True)
    ensure_runtime_directories(root)
    runtime = root / '.migration/venv'
    subprocess.run(['/usr/bin/python3.14', '-m', 'venv', '--without-pip', str(runtime)], check=True)
    site = runtime / 'lib/python3.14/site-packages'
    with tarfile.open(dependencies) as archive:
        archive.extractall(site, filter='data')
    # Recreate console wrappers with the new venv path; archived wrappers point
    # to the old release directory and must not be reused.
    for name in ('daphne', 'celery'):
        script = runtime / 'bin' / name
        script.write_text(f'#!{runtime}/bin/python\nimport sys\nfrom importlib.metadata import entry_points\nsys.exit(next(iter(entry_points(group="console_scripts", name="{name}"))).load()())\n')
        script.chmod(0o755)
    (root / 'backend/pro_claws_be_env').symlink_to(runtime)
    install_runtime_assets(runtime_assets, runtime_digest, root / 'backend')
    shutil.copy2(source / 'source-release.json', root / '.migration/source-release.json')
    subprocess.run(['chown', '-R', 'akatary:akatary', str(root / '.migration')], check=True)
    marker.write_text('source-installed\n')
    subprocess.run([str(runtime / 'bin/python'), '-c', 'import django,celery,psycopg,redis,channels_redis,cryptography; print("Runtime imports verified")'], check=True)
    print('Pinned release installed; application services and consumers remain stopped')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--runtime-assets', type=Path, required=True)
    parser.add_argument('--runtime-sha256', required=True)
    args = parser.parse_args()
    main(args.source.resolve(), args.dependencies.resolve(), args.sha256,
         args.runtime_assets.resolve(), args.runtime_sha256)
