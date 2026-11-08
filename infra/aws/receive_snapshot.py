"""Receive a fixed final snapshot using short-lived, object-scoped S3 GET URLs."""
import hashlib,json,os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT=Path('/var/lib/vendistri-cutover-final')
NAMES={'database.dump','database-inventory.json','media.tar.gz','scheduler.tar.gz','redis.json'}
BUCKET='vendistri-aws-artifacts-artifacts-9clgm8cgzbem'

def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()

def receive(payload,root=ROOT):
    manifest=payload['manifest'];urls=payload['urls']
    if set(manifest)!=NAMES or set(urls)!=NAMES|{'manifest.json'}:raise RuntimeError('Unexpected final snapshot members')
    for url in urls.values():
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname.startswith(BUCKET+'.s3') or not parsed.hostname.endswith('.amazonaws.com'):
            raise RuntimeError('Unexpected private S3 endpoint')
    root.mkdir(mode=0o700,exist_ok=True)
    if root.is_symlink() or root.stat().st_uid!=os.geteuid() or root.stat().st_mode&0o077:raise RuntimeError('Unsafe snapshot directory')
    for name in ['manifest.json',*sorted(NAMES)]:
        path=root/name
        if path.exists():
            if name=='manifest.json':
                if json.loads(path.read_text())!=manifest:raise RuntimeError('Existing manifest differs')
            elif path.stat().st_size!=manifest[name]['bytes'] or checksum(path)!=manifest[name]['sha256']:
                raise RuntimeError('Existing partial payload needs review')
            continue
        temporary=root/(name+'.part')
        with urllib.request.urlopen(urls[name],timeout=90) as response,temporary.open('xb') as output:
            while True:
                block=response.read(1048576)
                if not block:break
                output.write(block)
        if name=='manifest.json':
            if json.loads(temporary.read_text())!=manifest:raise RuntimeError('Backup manifest differs from source')
        elif temporary.stat().st_size!=manifest[name]['bytes'] or checksum(temporary)!=manifest[name]['sha256']:
            raise RuntimeError('Private backup transfer checksum mismatch')
        temporary.rename(path)
    return {'verified_payloads':len(NAMES),'bytes':sum(row['bytes'] for row in manifest.values()),'operator_credentials_installed':False}

def main():
    if os.geteuid()!=0:raise RuntimeError('Use the installed root-owned receiver')
    os.umask(0o077);print(json.dumps(receive(json.load(sys.stdin))))

if __name__=='__main__':main()
