"""Prepare complete Route 53 records from the supplied authoritative zone export."""
import argparse,copy,json
from pathlib import Path
import dns.zone,dns.rdatatype
import yaml

DOMAIN='vendistri.com.'
APPS={DOMAIN,'www.'+DOMAIN,'secure.'+DOMAIN,'open.'+DOMAIN}
TARGET='dualstack.c28c0af9e31f7ebfa3ce5f877cf9e2a9-3730386.us-east-1.elb.amazonaws.com.'
TARGET_ZONE='Z35SXDOTRQ7X7K'

class CloudFormationLoader(yaml.SafeLoader):pass
CloudFormationLoader.add_constructor('!Ref',lambda loader,node:{'Ref':loader.construct_scalar(node)})

def records_from_export(path,keep_legacy_mail=True):
    zone=dns.zone.from_file(str(path),origin=DOMAIN,relativize=False)
    records=[]
    for name,node in zone.nodes.items():
        absolute=name.to_text()
        for dataset in node.rdatasets:
            kind=dns.rdatatype.to_text(dataset.rdtype)
            if kind in ('NS','SOA'):continue
            if absolute in APPS and kind in ('A','AAAA'):continue
            if absolute=='mail.'+DOMAIN and not keep_legacy_mail and kind in ('A','AAAA'):continue
            records.append({'Name':absolute,'Type':kind,'TTL':str(dataset.ttl),'ResourceRecords':[item.to_text() for item in dataset]})
    for name in sorted(APPS):
        for kind in ('A','AAAA'):
            records.append({'Name':name,'Type':kind,'AliasTarget':{'DNSName':TARGET,'HostedZoneId':TARGET_ZONE,'EvaluateTargetHealth':False}})
    return sorted(records,key=lambda item:(item['Name'],item['Type']))

def make_template(original,records):
    result=copy.deepcopy(original)
    result['Description']='Vendistri Route 53 DNS: verified email/validation records and direct dual-stack AWS application aliases.'
    result['Resources']['Zone']['Properties']['HostedZoneConfig']['Comment']='Vendistri complete AWS DNS; preserve Google mail; delegate only after authoritative validation.'
    result['Resources']['CertificateValidation']['Properties']['RecordSets']=records
    result.setdefault('Outputs',{})['NameServers']={'Value':{'Fn::Join':[',',{'Fn::GetAtt':['Zone','NameServers']}]}}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--export',type=Path,required=True);p.add_argument('--template',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--retire-legacy-mail',action='store_true');args=p.parse_args()
    records=records_from_export(args.export,not args.retire_legacy_mail)
    template=make_template(yaml.load(args.template.read_text(),Loader=CloudFormationLoader),records)
    args.output.write_text(json.dumps(template,indent=2)+'\n')
    print(json.dumps({'record_sets':len(records),'application_aliases':sum('AliasTarget' in r for r in records),'mail_mx_preserved':sum(r['Type']=='MX' for r in records),'legacy_mail_address_preserved':not args.retire_legacy_mail,'delegation_changed':False}))

if __name__=='__main__':main()
