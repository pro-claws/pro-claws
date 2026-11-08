"""Unprivileged Linode archive uploader using one-use S3 part URLs over stdin.

No AWS credentials are installed on Linode. The fixed root helper emits only
the scoped archive; the operator controls multipart completion after tar exits.
"""
import base64
import hashlib
import json
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PART_SIZE = 64 * 1024 * 1024
S3_HOSTS = {'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.amazonaws.com',
            'vendistri-aws-artifacts-artifacts-9clgm8cgzbem.s3.us-east-1.amazonaws.com'}


def emit(row):
    print(json.dumps(row), flush=True)


def read_part(stream, size=PART_SIZE):
    chunks, length = [], 0
    while length < size:
        chunk = stream.read(size - length)
        if not chunk:
            break
        chunks.append(chunk)
        length += len(chunk)
    return b''.join(chunks)


def valid_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in S3_HOSTS or parsed.username:
        raise ValueError('Unexpected upload destination')


def main():
    process = subprocess.Popen(['sudo', '-n', '/usr/local/sbin/vendistri-retirement-archive',
                                'stream'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total, count = 0, 0
    digest = hashlib.sha256()
    try:
        while True:
            data = read_part(process.stdout)
            if not data:
                break
            count += 1
            if count > 10000:
                raise RuntimeError('Multipart limit exceeded')
            checksum = base64.b64encode(hashlib.sha256(data).digest()).decode()
            emit({'event': 'part', 'number': count, 'bytes': len(data), 'checksum': checksum})
            message = json.loads(sys.stdin.readline())
            if message.get('number') != count:
                raise RuntimeError('Invalid part response')
            valid_url(message['url'])
            for attempt in range(3):
                try:
                    request = Request(message['url'], data=data, method='PUT',
                                      headers={'x-amz-checksum-sha256': checksum})
                    with urlopen(request, timeout=180) as response:
                        etag = response.headers['ETag']
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2)
            digest.update(data)
            total += len(data)
            emit({'event': 'uploaded', 'number': count, 'etag': etag,
                  'checksum': checksum, 'total_bytes': total})
        if process.wait() != 0 or not total:
            raise RuntimeError('Root archive stream failed; do not complete upload')
        emit({'event': 'complete', 'bytes': total, 'parts': count, 'sha256': digest.hexdigest()})
    except Exception as error:
        emit({'event': 'error', 'type': type(error).__name__, 'deletion_performed': False})
        process.terminate()
        process.wait()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
