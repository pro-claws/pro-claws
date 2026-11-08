#!/usr/bin/python3 -I
"""Install pinned Vendistri-only cleanup controls; initially audit, never delete."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HELPER_SHA = '0ee827be54f5aa70625805bd05a95ad686e09296c831ac2a03fa755e8db62788'
PROOF_SHA = '3eb38e116075e84259cdaf62e2bf77168019df3d60fd127143f35ee2ea75750a'
ROOT = Path('/var/lib/vendistri-retirement-control')
TARGET = Path('/usr/local/sbin/vendistri-retire')


def atomic(path, body, mode):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.vendistri-', delete=False) as output:
        temporary = Path(output.name); output.write(body)
    temporary.chmod(mode); temporary.replace(path)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Authenticate sudo locally; never send the password')
    os.umask(0o077)
    helper = Path('/home/akatary/.vendistri-retire-source.py').read_bytes()
    proof = Path('/home/akatary/.vendistri-recovery-proof.json').read_bytes()
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA or hashlib.sha256(proof).hexdigest() != PROOF_SHA:
        raise SystemExit('Pinned cleanup code/recovery proof checksum mismatch')
    if ROOT.is_symlink():
        raise SystemExit('Invalid cleanup metadata root')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    if ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o077:
        raise SystemExit('Cleanup metadata must be root-owned and private')
    atomic(ROOT / 'recovery-proof.json', proof, 0o600)
    atomic(TARGET, helper, 0o755)
    actions = ('audit', 'stream-config', 'confirm-config', 'retire-data', 'retire-ingress', 'status')
    rule = 'akatary ALL=(root) NOPASSWD: ' + ', '.join(str(TARGET) + ' ' + action for action in actions) + '\n'
    with tempfile.NamedTemporaryFile(dir='/etc/sudoers.d', prefix='.vendistri-', delete=False) as output:
        candidate = Path(output.name); output.write(rule.encode())
    candidate.chmod(0o440)
    try:
        subprocess.run(['/usr/sbin/visudo', '-cf', str(candidate)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        candidate.replace('/etc/sudoers.d/vendistri-retire')
    finally:
        candidate.unlink(missing_ok=True)
    subprocess.run([str(TARGET), 'audit'], check=True)
    print(json.dumps({'cleanup_controls_installed': True, 'audit_only': True,
                      'source_data_deleted': False, 'traffic_changed': False}))


if __name__ == '__main__':
    main()
