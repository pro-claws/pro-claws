"""Prepare live unit definitions for AWS; never install/unmask/start them."""
from pathlib import Path
import json
import re
import shlex
import subprocess

SCRATCH = Path('/private/tmp/vendistri-aws-prepare')
UNITS = ['proclaws.service', 'proclaws-api-2.service', 'vendistri-realtime.service',
         'vendistri-bg-tasks.service', 'vendistri-telemetry-worker.service',
         'vendistri-documents-worker.service', 'vendistri-shipping-worker.service',
         'vendistri-health-worker.service', 'vendistri-celery-beat.service',
         'vendistri-telemetry-intake.service']
PROPERTIES = ['MemoryMax', 'CPUQuotaPerSecUSec', 'RuntimeMaxUSec', 'Restart',
              'KillMode', 'TimeoutStopUSec', 'User']
source_code = '''import subprocess,json,sys
units=json.load(sys.stdin);result={}
for unit in units:
 text=subprocess.check_output(['systemctl','cat',unit],text=True)
 properties=subprocess.check_output(['systemctl','show',unit,'-p','MemoryMax','-p','CPUQuotaPerSecUSec','-p','RuntimeMaxUSec','-p','Restart','-p','KillMode','-p','TimeoutStopUSec','-p','User'],text=True)
 result[unit]={'text':text,'properties':dict(line.split('=',1) for line in properties.splitlines())}
print(json.dumps(result))
'''
def main():
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                             'vendistri-prod', 'python3 -c ' + shlex.quote(source_code)],
                            input=json.dumps(UNITS), capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('Source unit export failed; private definitions withheld')
    units = json.loads(result.stdout)
    local_dependencies = {'postgresql.service', 'redis.service', 'redis-server.service'}
    for name, item in units.items():
        lines = []
        for line in item['text'].splitlines():
            if re.search(r'\b(?:AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|AWS_PROFILE)=', line):
                raise RuntimeError('Source unit contains inline AWS credentials/profile; review required')
            if line.startswith('IPAddressDeny=') and line.split('=', 1)[1].strip():
                raise RuntimeError('Source unit has network policy requiring explicit AWS adaptation')
            if line.startswith('EnvironmentFile='):
                value = line.split('=', 1)[1].lstrip('-').strip()
                if value not in ('', '/etc/proclaws/aws-kms.env', '/home/akatary/pro_claws/backend/.env'):
                    raise RuntimeError('Unreviewed source environment file in ' + name)
                continue
            key, separator, value = line.partition('=')
            if separator and key in ('After', 'Wants', 'Requires', 'BindsTo', 'PartOf'):
                value = ' '.join(token for token in value.split()
                                 if token not in local_dependencies and not token.startswith('postgresql@'))
                line = key + '=' + value
            lines.append(line)
        item['text'] = '\n'.join(lines) + '''
    [Unit]
    After=network-online.target remote-fs.target
    Wants=network-online.target
    RequiresMountsFor=/mnt/vendistri-media
    [Service]
    Environment=DJANGO_SETTINGS_MODULE=vendistri_production
    Environment=PYTHONPATH=/etc/vendistri:/home/akatary/pro_claws/backend
    '''

    remote = r'''import json,sys,os,grp,subprocess
    from pathlib import Path
    units=json.load(sys.stdin)
    assert Path('/etc/vendistri/migration-stage').read_text().strip()=='rehearsal-configured'
    assert not Path('/etc/vendistri/production.json').exists()
    root=Path('/etc/vendistri/production-prepared/units')
    assert not root.exists(),'Prepared units already exist; review before replacing'
    group=grp.getgrnam('vendistri-config')
    root.mkdir(mode=0o750);os.chown(root,0,group.gr_gid)
    for name,item in units.items():
     assert '/' not in name and name.endswith('.service')
     path=root/name;path.write_text(item['text']);path.chmod(0o640);os.chown(path,0,group.gr_gid)
    check=subprocess.run(['systemd-analyze','verify',*[str(root/name) for name in units]],capture_output=True,text=True)
    if check.returncode:
     diagnostics=root.parent/'units-verify-private-error.txt';diagnostics.write_text(check.stderr);diagnostics.chmod(0o600)
     raise SystemExit('Staged unit verification failed; private diagnostics withheld')
    summary={name:item['properties'] for name,item in units.items()}
    print(json.dumps({'production_unit_templates':len(units),'systemd_verify':'passed','units_installed_or_started':False,'source_effective_resource_policies':summary}))
    '''
    base = ['ssh', '-i', str(Path.home() / '.ssh/vendistri_aws_migration'), '-o', 'IdentitiesOnly=yes',
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'UserKnownHostsFile=' + str(SCRATCH / 'known_hosts')]
    for label, ip in [('a', '100.58.5.127'), ('b', '3.211.223.36')]:
        result = subprocess.run(base + ['ubuntu@' + ip, 'sudo python3.14 -c ' + shlex.quote(remote)],
                                input=json.dumps(units), capture_output=True, text=True)
        if result.returncode:
            raise SystemExit('Unit staging needs attention on ' + label + '; no live unit was changed')
        value = json.loads(result.stdout)
        (SCRATCH / ('midnight-production-units-' + label + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        print(label + ': 10 live-derived unit definitions staged and verified; no live units changed', flush=True)


if __name__ == '__main__':
    main()
