"""Operator dispatcher: keep admin credentials on encrypted stdin, never logs."""
import argparse,json,os,shlex,subprocess
from pathlib import Path
ROOT=Path('/private/tmp/vendistri-aws-prepare')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('host',choices=['a','b']);parser.add_argument('action',choices=['verify','database','validate-existing','stage-files','cache','prepare-a','prepare-b','start-a','start-b','release']);args=parser.parse_args()
    module='activate_production' if args.action.startswith(('prepare-','start-')) or args.action=='release' else 'target_restore'
    payload=''
    if module=='activate_production':
        payload=subprocess.check_output(['ssh','-o','BatchMode=yes','vendistri-prod','sudo -n /usr/local/sbin/vendistri-cutover status'],text=True)
        json.loads(payload)
    elif args.action=='database':
        result=subprocess.run(['aws','lightsail','get-relational-database-master-user-password','--relational-database-name','vendistri-aws-postgres','--profile','vendistri-setup','--region','us-east-1','--output','json'],capture_output=True,text=True,check=True)
        payload=json.dumps({'admin_password':json.loads(result.stdout)['masterUserPassword']})
    ip={'a':'100.58.5.127','b':'3.211.223.36'}[args.host]
    code="import sys;sys.path.insert(0,'/usr/local/lib/vendistri-cutover');from "+module+" import main;main()"
    ssh=['ssh','-i',str(Path.home()/'.ssh/vendistri_aws_migration'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ServerAliveInterval=15','-o','UserKnownHostsFile='+str(ROOT/'known_hosts'),'ubuntu@'+ip]
    result=subprocess.run(ssh+['sudo /usr/bin/python3 -I -c '+shlex.quote(code)+' '+args.action],input=payload,text=True,capture_output=True)
    target=ROOT/('execution-'+args.host+'-'+args.action+('.json' if result.returncode==0 else '-private-error.txt'))
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as out:out.write(result.stdout if result.returncode==0 else result.stdout+'\n'+result.stderr)
    if result.returncode:raise SystemExit('Action failed on '+args.host+': '+args.action+'; private diagnostics retained')
    print(json.dumps(json.loads(result.stdout)))


if __name__=='__main__':main()
