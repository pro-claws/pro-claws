"""Wait for archive upload, verify on AWS, retain receipts; never delete source."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from archive_to_s3 import operator_session
from botocore.config import Config

RECEIPT = Path('/private/tmp/vendistri-retirement-transfer-20261028.json')
MANIFEST = Path('/private/tmp/vendistri-retirement-source-manifest.json')
RESULT = Path('/private/tmp/vendistri-retirement-verification-20261028.json')
RUNBOOK = Path('/Users/mohamedkatary/pro-claws/backend/runbooks/resilient_backend_architecture.md')
SCRIPTS = Path('/Users/mohamedkatary/pro-claws/infra/aws')


def save(path, body):
    temporary = path.with_suffix('.new')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as out:
        out.write(json.dumps(body, indent=2) + '\n')
    temporary.replace(path)


def main():
    deadline = time.monotonic() + 8 * 3600
    state = None
    while time.monotonic() < deadline:
        try:
            state = json.loads(RECEIPT.read_text())
        except (OSError, json.JSONDecodeError):
            time.sleep(5)
            continue
        if state['status'] != 'uploading':
            break
        time.sleep(10)
    if not state or state['status'] != 'uploaded-awaiting-independent-verification':
        raise RuntimeError('Upload incomplete/failed; no cleanup allowed')
    manifest = json.loads(MANIFEST.read_text())
    ssh_options = ['-i', str(Path.home() / '.ssh/vendistri_aws_migration'),
                   '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'UserKnownHostsFile=' + str(Path.home() / '.ssh/vendistri_aws_known_hosts'),
                   '-o', 'ServerAliveInterval=15']
    host = 'ubuntu@3.211.223.36'
    subprocess.run(['scp', *ssh_options, str(SCRIPTS / 'verify_retirement_archive.py'),
                    host + ':/home/ubuntu/vendistri-retirement-verify.py'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s3 = operator_session().client('s3', config=Config(signature_version='s3v4'))
    url = s3.generate_presigned_url('get_object', Params={
        'Bucket': state['bucket'], 'Key': state['key'], 'VersionId': state['version_id']}, ExpiresIn=3600)
    body = {key: state[key] for key in ('bytes', 'sha256')}
    body.update(url=url, database_dumps=manifest['database_dumps'])
    print(json.dumps({'status': 'verifying-full-archive-on-aws', 'bytes': state['bytes']}), flush=True)
    result = subprocess.run(['ssh', *ssh_options, host,
                             '/usr/bin/nice -n 19 /usr/bin/ionice -c 3 /usr/bin/python3 -I /home/ubuntu/vendistri-retirement-verify.py'],
                            input=json.dumps(body) + '\n', text=True, capture_output=True, timeout=6*3600)
    if result.returncode:
        raise RuntimeError('AWS archive verification failed; preserve source')
    checked = json.loads(result.stdout)
    if not checked.get('archive_sha256_verified') or checked.get('database_payloads_verified') != 5:
        raise RuntimeError('Incomplete archive verification; preserve source')
    checked.update(checked_at_utc=datetime.now(timezone.utc).isoformat(),
                   bucket=state['bucket'], key=state['key'], version_id=state['version_id'],
                   sha256=state['sha256'], deletion_performed=False,
                   cleanup_blocker='Privileged deletion helper not installed; retain source and bridge.')
    save(RESULT, checked)
    prefix = state['key'].rsplit('/', 1)[0] + '/'
    for name, value in [('verified-archive-receipt.json', checked),
                         ('source-archive-manifest.json', manifest)]:
        s3.put_object(Bucket=state['bucket'], Key=prefix + name,
                      Body=(json.dumps(value, indent=2) + '\n').encode(),
                      ContentType='application/json', ServerSideEncryption='AES256')
    state['status'] = 'verified-preserve-source-awaiting-privileged-cleanup'
    state['independent_verification'] = checked
    save(RECEIPT, state)
    text = ('\n### Historical Linode archive independently verified — ' + checked['checked_at_utc'] + '\n\n'
            'The full historical archive uploaded directly from Linode to private S3: '
            '`s3://' + state['bucket'] + '/' + state['key'] + '`, version `' + state['version_id'] + '`. '
            'Compressed bytes: ' + str(state['bytes']) + '; SHA-256: `' + state['sha256'] + '`. '
            'AWS B read the complete version-specific object, verified its compressed hash/size '
            'and gzip trailer, scanned ' + str(checked['tar_members_scanned']) + ' tar members, '
            'and verified all five old database dump hashes without extracting files. '
            'Archive/source manifests and verification receipts are retained beside the object.\n\n'
            'No source deletion or traffic change occurred. The installed source helper grants '
            'archive access only. Privileged deletion/ingress retirement still requires a '
            'reviewed fixed-scope helper installed with the user\'s sudo authentication, plus '
            'traffic attribution and final reference checks. Shared Linode projects/services '
            'and legacy mail remain preserved. Do not report cleanup as completed.\n')
    with RUNBOOK.open('a') as out:
        out.write(text)
    print(json.dumps(checked), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        save(RESULT, {'verification_failed': True, 'error_type': type(error).__name__,
                      'source_deleted': False})
        print(json.dumps({'verification_failed': True, 'error_type': type(error).__name__,
                          'source_deleted': False}), flush=True)
        raise SystemExit(1)
