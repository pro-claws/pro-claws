#!/usr/bin/python3 -I
"""Install the checksum-pinned archive-only helper; never delete source data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

EXPECTED = 'a4594fad897b2f465aa9e89ae4def61f16b09e5dd724def149d6b9a958ebbf82'
SOURCE = Path('/home/akatary/.vendistri-retirement-archive.py')
TARGET = Path('/usr/local/sbin/vendistri-retirement-archive')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Authenticate sudo in your own terminal')
    os.umask(0o077)
    body = SOURCE.read_bytes()
    if hashlib.sha256(body).hexdigest() != EXPECTED:
        raise SystemExit('Archive helper checksum mismatch')
    with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.retirement-', delete=False) as output:
        temporary = Path(output.name)
        output.write(body)
    temporary.chmod(0o755)
    temporary.replace(TARGET)
    rule = 'akatary ALL=(root) NOPASSWD: ' + ', '.join(str(TARGET) + ' ' + action
                                                   for action in ('prepare', 'status', 'stream')) + '\n'
    with tempfile.NamedTemporaryFile(dir='/etc/sudoers.d', prefix='.retirement-',
                                     mode='w', delete=False) as output:
        candidate = Path(output.name)
        output.write(rule)
    candidate.chmod(0o440)
    try:
        subprocess.run(['/usr/sbin/visudo', '-cf', str(candidate)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        candidate.replace('/etc/sudoers.d/vendistri-retirement-archive')
    finally:
        candidate.unlink(missing_ok=True)
    subprocess.run([str(TARGET), 'prepare'], check=True)
    print(json.dumps({'archive_only_helper_installed': True, 'source_deleted': False,
                      'traffic_changed': False, 'aws_credentials_installed': False}))


if __name__ == '__main__':
    main()
