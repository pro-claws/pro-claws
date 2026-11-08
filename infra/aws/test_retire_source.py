from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import retire_source as control


class ScopeTests(unittest.TestCase):
    def test_database_owner_and_connections_must_match(self):
        for row in ({'datname':'proclaws_prod','owner':'other','connections':0,'datconnlimit':0},
                    {'datname':'proclaws_prod','owner':'proclaws_app','connections':1,'datconnlimit':0},
                    {'datname':'proclaws_prod','owner':'proclaws_app','connections':0,'datconnlimit':-1},
                    {'datname':'unrelated','owner':'proclaws_app','connections':0,'datconnlimit':-1}):
            with self.subTest(row=row), self.assertRaises(RuntimeError):
                control.validate_databases([row])

    def test_unrelated_database_is_preserved_and_fixed_scope_has_five_names(self):
        control.validate_databases([{'datname':'other','owner':'other','connections':2}])
        self.assertEqual(len(control.DATABASES),5)
        self.assertNotIn('postgres', control.DATABASES)

    def test_symlink_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source'; path.symlink_to('/private/tmp')
            with self.assertRaises(RuntimeError): control.secure_path(path)

    def test_nested_and_exact_mounts_are_rejected(self):
        for target in ('/scope/source','/scope/source/private'):
            with self.assertRaises(RuntimeError):
                control.mount_guard(('/scope/source',),'1 2 3 / '+target+' rw - ext4 /dev/x rw')
        control.mount_guard(('/scope/source',),'1 2 3 / /scope/unrelated rw - ext4 /dev/x rw')

    def test_shared_vhost_and_wildcard_alias_cannot_be_removed(self):
        control.validate_vhost('ServerName vendistri.com\nServerAlias www.vendistri.com\n')
        for alias in ('akatary.com','*.vendistri.com'):
            with self.assertRaises(RuntimeError):
                control.validate_vhost('ServerName vendistri.com\nServerAlias '+alias+'\n')

    def test_successful_api_requests_block_ingress_retirement_without_leaking_query(self):
        now=datetime(2026,10,29,3,tzinfo=timezone.utc)
        row='client [29/Oct/2026:02:00:00 +0000] "GET /vendistri/be/user?private=secret HTTP/1.1" 200 9'
        result=control.traffic([row],now)
        self.assertEqual(result['successful_application_like_requests'],1)
        self.assertNotIn('secret',str(result))
        self.assertNotIn('client',str(result))

    def test_failed_scanner_and_public_health_do_not_count_as_app_success(self):
        now=datetime(2026,10,29,3,tzinfo=timezone.utc)
        rows=['x [29/Oct/2026:02:00:00 +0000] "GET /wp-admin HTTP/1.1" 404 9',
              'x [29/Oct/2026:02:00:00 +0000] "GET /vendistri/be/health/ready HTTP/1.1" 200 9',
              'x [29/Oct/2026:02:00:00 +0000] "-" 400 9']
        result=control.traffic(rows,now)
        self.assertEqual(result.get('successful_application_like_requests',0),0)
        self.assertEqual(result.get('unparseable',0),0)

    def test_extra_http_methods_and_http09_keep_application_traffic_guard(self):
        now=datetime(2026,10,29,3,tzinfo=timezone.utc)
        rows=['x [29/Oct/2026:02:00:00 +0000] "PROPFIND / HTTP/1.1" 200 9',
              'x [29/Oct/2026:02:00:00 +0000] "GET /vendistri/be/user" 200 9']
        result=control.traffic(rows,now)
        self.assertEqual(result['additional_http_formats'],2)
        self.assertEqual(result['successful_application_like_requests'],1)
        self.assertEqual(result.get('unparseable',0),0)

    def test_genuinely_unparseable_request_still_blocks_retirement(self):
        now=datetime(2026,10,29,3,tzinfo=timezone.utc)
        result=control.traffic(['x [29/Oct/2026:02:00:00 +0000] "unexpected" 200 9'],now)
        self.assertEqual(result['unparseable'],1)

    def test_unverified_config_blocks_all_destructive_actions(self):
        with patch.object(control,'context'),patch.object(control,'aws_health'),\
             patch.object(control,'references'),patch.object(control,'databases',return_value=[]),\
             patch.object(control,'state',return_value={}),patch.object(control,'sql') as sql,\
             patch.object(control.shutil,'rmtree') as remove,patch.object(control,'run') as run:
            with self.assertRaises(RuntimeError): control.retire_data()
            sql.assert_not_called();remove.assert_not_called();run.assert_not_called()

    def test_active_ingress_connection_blocks_vhost_changes(self):
        with patch.object(control,'context'),patch.object(control,'aws_health'),\
             patch.object(control,'state',return_value={'data_retired':True}),\
             patch.object(control,'traffic_summary',return_value={}),\
             patch.object(control,'run',return_value='ESTAB connection'),\
             patch.object(control,'vhosts') as sites:
            with self.assertRaises(RuntimeError):control.retire_ingress()
            sites.assert_not_called()

    def test_reload_failure_restores_regular_vhost_and_its_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            available=Path(folder)/'available.conf';available.write_text('ServerName vendistri.com\n')
            enabled=Path(folder)/'enabled.conf';enabled.symlink_to(available)
            tests=[0]
            def run(args):
                if args[0]=='/usr/sbin/apache2ctl':
                    tests[0]+=1
                    if tests[0]==2:raise RuntimeError('fixture config failure')
                return ''
            with patch.object(control,'context'),patch.object(control,'aws_health'),\
                 patch.object(control,'state',return_value={'data_retired':True,'akatary_vhost_sha256':'same'}),\
                 patch.object(control,'traffic_summary',return_value={}),\
                 patch.object(control,'digest',return_value='same'),\
                 patch.object(control,'run',side_effect=run),\
                 patch.object(control,'vhosts',return_value=[available,enabled]):
                with self.assertRaises(RuntimeError):control.retire_ingress()
            self.assertTrue(enabled.is_symlink())
            self.assertEqual(enabled.read_text(),'ServerName vendistri.com\n')


if __name__=='__main__':unittest.main()
