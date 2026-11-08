"""Read/verify the full private archive on an AWS host; never extract its files.

Input is one JSON line with a version-specific short-lived GET URL, expected
compressed SHA-256/size, and prepared database dump hashes. Output is metadata.
"""
import gzip
import hashlib
import json
from pathlib import PurePosixPath
import sys
import tarfile
from urllib.parse import urlsplit
from urllib.request import urlopen

HOSTS = {'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com',
         'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.us-east-1.amazonaws.com'}


class HashedReader:
    def __init__(self, source):
        self.source, self.digest, self.size = source, hashlib.sha256(), 0

    def read(self, size=-1):
        data = self.source.read(size)
        self.digest.update(data)
        self.size += len(data)
        return data


def verify(source, expected):
    reader = HashedReader(source)
    wanted = {row['database'] + '.dump': row for row in expected['database_dumps']}
    verified, seen, total = {}, set(), 0
    with gzip.GzipFile(fileobj=reader, mode='rb') as compressed:
        with tarfile.open(fileobj=compressed, mode='r|') as archive:
            for member in archive:
                name = str(PurePosixPath(member.name))
                if member.name.startswith('/') or '..' in PurePosixPath(member.name).parts:
                    raise RuntimeError('Unsafe archive member name')
                total += 1
                for root in ('home/akatary/pro_claws', 'var/www/vendistri',
                             'var/lib/vendistri-retirement-20261028/databases'):
                    if name == root or name.startswith(root + '/'):
                        seen.add(root)
                if name.startswith('var/lib/vendistri-retirement-20261028/databases/') and member.isfile():
                    base = PurePosixPath(name).name
                    if base in wanted:
                        if base in verified:
                            raise RuntimeError('Duplicate archived database')
                        digest, length = hashlib.sha256(), 0
                        stream = archive.extractfile(member)
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(block)
                            length += len(block)
                        row = wanted[base]
                        if length != row['bytes'] or digest.hexdigest() != row['sha256']:
                            raise RuntimeError('Archived database payload mismatch')
                        verified[base] = True
        # Drain through gzip EOF to validate the trailer/CRC, not only tar EOF.
        while compressed.read(1024 * 1024):
            pass
    while reader.read(1024 * 1024):
        pass
    if reader.size != expected['bytes'] or reader.digest.hexdigest() != expected['sha256']:
        raise RuntimeError('Full compressed archive hash/size mismatch')
    if set(verified) != set(wanted) or len(verified) != 5 or len(seen) != 3:
        raise RuntimeError('Required application roots or five database dumps missing')
    return {'archive_sha256_verified': True, 'bytes': reader.size,
            'gzip_crc_verified': True, 'tar_members_scanned': total,
            'database_payloads_verified': len(verified), 'files_extracted': 0,
            'source_deleted': False}


def main():
    expected = json.loads(sys.stdin.readline())
    parsed = urlsplit(expected['url'])
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
        raise SystemExit('Unexpected archive location')
    try:
        with urlopen(expected['url'], timeout=180) as response:
            result = verify(response, expected)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'verification_failed': True, 'type': type(error).__name__,
                          'source_deleted': False}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
