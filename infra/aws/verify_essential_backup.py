"""Verify version-pinned recovery payloads on AWS; emit metadata only."""
import hashlib
import json
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

HOSTS = {'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com',
         'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.us-east-1.amazonaws.com'}


def main():
    rows = json.loads(sys.stdin.readline())
    checked = []
    for row in rows:
        if urlsplit(row['url']).hostname not in HOSTS or not row['url'].startswith('https://'):
            raise RuntimeError('Unexpected recovery object location')
        digest, length = hashlib.sha256(), 0
        with urlopen(row['url'], timeout=120) as response:
            for block in iter(lambda: response.read(1024 * 1024), b''):
                digest.update(block)
                length += len(block)
        if length != row['bytes'] or digest.hexdigest() != row['sha256']:
            raise RuntimeError('Recovery payload mismatch')
        checked.append({key: row[key] for key in ('name', 'bytes', 'sha256', 'version_id')})
    print(json.dumps({'essential_payloads_verified': checked}))


if __name__ == '__main__':
    main()
