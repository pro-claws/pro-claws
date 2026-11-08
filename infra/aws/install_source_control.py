#!/usr/bin/python3 -I
"""Install fixed-scope migration controls. Preparation does not stop production."""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
EXPECTED={'source_control.py': '27e44be5e0bae4362a12f574640f9b6f3a0b24050491819f69ae260d3f05fa9f', 'source_root_audit.py': 'feab550306836c9016c34ada786d5425eeb1af4b6e6958b0b2b1e1300a5545b8', 'database_inventory.py': '8ee3f61beb04a18abee2ecc75fe3274d2fadc0087ca7a668f9461570cfb610d9', 'cutover_redis.py': 'd59a19c6694c23761e2ab7b4b126603bcc34c61c3eb28deb496c117aa334bd00', 'ingress_bridge.py': '01007751ff8ec7abffea0b941b8313cd797c0f97b90aca08986456be91ec6c8e'}
SOURCE=Path('/home/akatary/pro_claws/.migration/aws-20261024')
DEST=Path('/usr/local/lib/vendistri-cutover')
if os.geteuid()!=0:raise SystemExit('Run the installed checksum-verified installer with sudo')
os.chdir('/');os.umask(0o077)
# Read every payload once and verify all bytes before installing executable code.
payload={name:(SOURCE/name).read_bytes() for name in EXPECTED}
for name,value in payload.items():
 if hashlib.sha256(value).hexdigest()!=EXPECTED[name]:raise RuntimeError('Migration module checksum mismatch: '+name)
if DEST.is_symlink():raise RuntimeError('Unsafe installation directory')
DEST.mkdir(mode=0o755,exist_ok=True)
if DEST.stat().st_uid!=0:raise RuntimeError('Installation directory must be root-owned')
DEST.chmod(0o755)
for name,value in payload.items():
 path=DEST/name
 if path.is_symlink():raise RuntimeError('Unexpected installed module symlink')
 path.write_bytes(value);path.chmod(0o644);os.chown(path,0,0)
wrapper=Path('/usr/local/sbin/vendistri-cutover')
if wrapper.is_symlink():raise RuntimeError('Unexpected control wrapper symlink')
wrapper.write_text("#!/usr/bin/python3 -I\nimport sys\nsys.path.insert(0,'/usr/local/lib/vendistri-cutover')\nfrom source_control import main\nmain()\n")
wrapper.chmod(0o755);os.chown(wrapper,0,0)
unit=Path('/etc/systemd/system/vendistri-aws-ingress.service')
unit.write_text("""[Unit]
Description=Vendistri verified TLS ingress to AWS
After=network-online.target
Wants=network-online.target
ConditionPathExists=/var/lib/vendistri-cutover/aws-authority
[Service]
User=nobody
Group=nogroup
ExecStart=/usr/bin/python3 -I /usr/local/lib/vendistri-cutover/ingress_bridge.py --upstream c28c0af9e31f7ebfa3ce5f877cf9e2a9-3730386.us-east-1.elb.amazonaws.com --server-name secure.vendistri.com
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
MemoryMax=256M
CPUQuota=100%
LimitNOFILE=1024
[Install]
WantedBy=multi-user.target
""")
unit.chmod(0o644);os.chown(unit,0,0)
subprocess.run(['systemd-analyze','verify',str(unit)],check=True,capture_output=True)
actions=['prepare','status','fence','snapshot','recover-prewrite','mark-aws','route-aws','maintenance','stream-db','stream-media','stream-scheduler','stream-redis','stream-manifest','stream-inventory']
policy='akatary ALL=(root) NOPASSWD: '+', '.join('/usr/local/sbin/vendistri-cutover '+action for action in actions)+'\n'
with tempfile.NamedTemporaryFile(mode='w',dir='/etc/sudoers.d',prefix='.vendistri-cutover-',delete=False) as stream:
 temporary=Path(stream.name);stream.write(policy)
try:
 temporary.chmod(0o440)
 subprocess.run(['visudo','-cf',str(temporary)],check=True,capture_output=True)
 temporary.replace('/etc/sudoers.d/vendistri-cutover')
finally:temporary.unlink(missing_ok=True)
subprocess.run(['systemctl','daemon-reload'],check=True)
# No service is enabled, stopped or started during installation/preparation.
subprocess.run(['/usr/bin/python3','-I','-c',"import sys;sys.path.insert(0,'/usr/local/lib/vendistri-cutover');from source_root_audit import audit;audit()"],check=True)
subprocess.run([str(wrapper),'prepare'],check=True)
print('Installed and prepared fixed-scope controls; production traffic and writers unchanged')
