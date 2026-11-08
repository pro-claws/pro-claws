import tempfile,unittest
from pathlib import Path
from migrate_dns import records_from_export,make_template

ZONE='''$TTL 86400
@ IN SOA ns1.linode.com. hostmaster.example.com. 1 1 1 1 1
@ IN NS ns1.linode.com.
@ IN MX 10 SMTP.GOOGLE.COM.
secure IN MX 10 SMTP.GOOGLE.COM.
@ IN TXT "v=spf1 include:_spf.google.com ~all"
google._domainkey IN TXT "v=DKIM1; p=AbC" "dEf"
@ IN A 45.79.165.178
@ IN AAAA 2600:3c03::1
mail IN A 45.79.165.178
_validation IN CNAME _token.acm-validations.aws.
'''

class CompleteZone(unittest.TestCase):
    def records(self,keep=True):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'zone';p.write_text(ZONE);return records_from_export(p,keep)
    def test_apex_alias_coexists_with_mail_and_dualstack(self):
        rows=self.records();apex=[r for r in rows if r['Name']=='vendistri.com.']
        self.assertEqual({r['Type'] for r in apex},{'A','AAAA','MX','TXT'})
        self.assertEqual(sum('AliasTarget' in r for r in rows),8)
        self.assertTrue(all(not r['AliasTarget']['EvaluateTargetHealth'] for r in rows if 'AliasTarget' in r))
    def test_txt_dkim_chunks_and_validation_are_preserved(self):
        rows=self.records();dkim=next(r for r in rows if r['Name']=='google._domainkey.vendistri.com.')
        self.assertEqual(dkim['ResourceRecords'],['"v=DKIM1; p=AbC" "dEf"'])
        self.assertEqual(next(r for r in rows if r['Type']=='CNAME')['ResourceRecords'],['_token.acm-validations.aws.'])
        self.assertFalse(any(r['Type'] in ('NS','SOA') for r in rows))
    def test_legacy_mail_retirement_is_explicit(self):
        self.assertTrue(any(r['Name']=='mail.vendistri.com.' for r in self.records()))
        self.assertFalse(any(r['Name']=='mail.vendistri.com.' for r in self.records(False)))
    def test_cloudformation_zone_identity_is_not_replaced(self):
        original={'Resources':{'Zone':{'Type':'AWS::Route53::HostedZone','DeletionPolicy':'RetainExceptOnCreate','Properties':{'Name':'vendistri.com','HostedZoneConfig':{}}},'CertificateValidation':{'Properties':{'HostedZoneId':{'Ref':'Zone'},'RecordSets':[]}}}}
        result=make_template(original,self.records())
        self.assertEqual(result['Resources']['Zone']['Properties']['Name'],'vendistri.com')
        self.assertEqual(result['Resources']['CertificateValidation']['Properties']['HostedZoneId'],{'Ref':'Zone'})
        self.assertEqual(original['Resources']['CertificateValidation']['Properties']['RecordSets'],[])

if __name__=='__main__':unittest.main()
