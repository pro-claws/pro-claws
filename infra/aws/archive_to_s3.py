"""Operator: authorize each archive part, complete only after a clean source tar.

No source data or presigned URLs are logged. Source emits part hashes and
receipts; AWS validates each part checksum. A later independent full-object
read and archive scan is required before any source deletion.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import boto3
from botocore.config import Config
from botocore.credentials import RefreshableCredentials
import botocore.session

BUCKET = 'vendistri-aws-artifacts-artifacts-9clgm8cgzbem'


def operator_session():
    # AWS CLI supports this account's login provider; the retained backend SDK
    # lacks its optional CRT dependency. Export in memory, with refresh through
    # the CLI, rather than changing application environments or saving secrets.
    def refresh():
        result = subprocess.run(['aws', 'configure', 'export-credentials', '--profile',
                                 'vendistri-setup', '--format', 'process'],
                                capture_output=True, text=True, check=True)
        body = json.loads(result.stdout)
        return {'access_key': body['AccessKeyId'], 'secret_key': body['SecretAccessKey'],
                'token': body['SessionToken'], 'expiry_time': body['Expiration']}
    core = botocore.session.get_session()
    core._credentials = RefreshableCredentials.create_from_metadata(
        metadata=refresh(), refresh_using=refresh, method='operator-aws-cli-export')
    return boto3.Session(botocore_session=core, region_name='us-east-1')


def write_receipt(path, body):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        stream.write(json.dumps(body, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise SystemExit('Existing transfer receipt: review before starting another archive')
    session = operator_session()
    s3 = session.client('s3', config=Config(signature_version='s3v4'))
    key = 'source-retirement-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '/linode-vendistri-history.tar.gz'
    created = s3.create_multipart_upload(Bucket=BUCKET, Key=key,
                                        ServerSideEncryption='AES256', ChecksumAlgorithm='SHA256')
    upload_id = created['UploadId']
    state = {'bucket': BUCKET, 'key': key, 'upload_id': upload_id,
             'status': 'uploading', 'parts': [], 'deletion_performed': False}
    write_receipt(args.receipt, state)
    process = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15',
                                'vendistri-prod', '/usr/bin/python3 -I /home/akatary/.vendistri-retirement-upload.py'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    expected = 1
    pending = None
    summary = None
    try:
        for line in process.stdout:
            row = json.loads(line)
            event = row.get('event')
            if event == 'part':
                if pending is not None or row['number'] != expected or not 0 < row['bytes'] <= 64 * 1024 * 1024:
                    raise RuntimeError('Invalid source part sequence')
                pending = row
                url = s3.generate_presigned_url('upload_part', Params={
                    'Bucket': BUCKET, 'Key': key, 'UploadId': upload_id,
                    'PartNumber': expected, 'ChecksumSHA256': row['checksum']}, ExpiresIn=900)
                process.stdin.write(json.dumps({'number': expected, 'url': url}) + '\n')
                process.stdin.flush()
            elif event == 'uploaded':
                if not pending or row['number'] != expected or row['checksum'] != pending['checksum']:
                    raise RuntimeError('Invalid source part receipt')
                state['parts'].append({'PartNumber': expected, 'ETag': row['etag'],
                                       'ChecksumSHA256': row['checksum']})
                state['uploaded_bytes'] = row['total_bytes']
                write_receipt(args.receipt, state)
                if expected == 1 or expected % 16 == 0:
                    print(json.dumps({'uploaded_gib': round(row['total_bytes'] / 1024**3, 2),
                                      'parts': expected}), flush=True)
                expected += 1
                pending = None
            elif event == 'complete':
                if summary or pending or row['parts'] != len(state['parts']) or row['bytes'] != state.get('uploaded_bytes'):
                    raise RuntimeError('Invalid source completion receipt')
                summary = row
            else:
                raise RuntimeError('Source archive/upload failed; preserve source')
        if process.wait() != 0 or not summary:
            raise RuntimeError('Source did not exit cleanly; multipart not completed')
        completed = s3.complete_multipart_upload(Bucket=BUCKET, Key=key, UploadId=upload_id,
                                                  MultipartUpload={'Parts': state['parts']})
        head = s3.head_object(Bucket=BUCKET, Key=key, VersionId=completed['VersionId'])
        if head['ContentLength'] != summary['bytes'] or head.get('ServerSideEncryption') != 'AES256':
            raise RuntimeError('Completed archive metadata mismatch')
        state.update(status='uploaded-awaiting-independent-verification',
                     version_id=completed['VersionId'], sha256=summary['sha256'], bytes=summary['bytes'])
        write_receipt(args.receipt, state)
        print(json.dumps({key: state[key] for key in ('status', 'bucket', 'key', 'version_id', 'sha256', 'bytes')}))
    except Exception as error:
        process.terminate()
        process.wait()
        state.update(status='failed-preserve-source', error_type=type(error).__name__)
        write_receipt(args.receipt, state)
        print(json.dumps({'status': state['status'], 'error_type': type(error).__name__,
                          'source_deleted': False}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
