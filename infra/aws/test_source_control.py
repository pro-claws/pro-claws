import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import source_control as control


class FencingTests(unittest.TestCase):
    def test_shared_role_does_not_require_global_login_change(self):
        probe={'owned':True,'super':False,'backup_super':True,'connection_limit':-1,'other_owned':4,'other_connections':2}
        with patch.object(control,'sql',return_value=json.dumps(probe)):
            self.assertEqual(control.scope_probe(),probe)
    def test_database_fence_never_alters_role_or_other_databases(self):
        with patch.object(control,'sql') as sql:
            control.fence_database()
            statements=' '.join(call.args[0] for call in sql.call_args_list)
            self.assertIn('ALTER DATABASE proclaws_prod CONNECTION LIMIT 0',statements)
            self.assertIn("a.datname='proclaws_prod'",statements)
            self.assertNotIn('ALTER ROLE',statements)
    def test_recovery_restores_original_limit_without_role_changes(self):
        with patch.object(control,'sql') as sql:
            control.recover_database({'original_connection_limit':42})
            self.assertIn('CONNECTION LIMIT 42',sql.call_args.args[0])
            self.assertNotIn('ALTER ROLE',sql.call_args.args[0])
    def test_unrelated_virtual_host_is_preserved(self):
        other = '<VirtualHost *:443>\nServerName another.example\nDocumentRoot /var/www/other\n</VirtualHost>'
        own = '<VirtualHost *:443>\nServerName secure.vendistri.com\nSSLEngine on\nSSLCertificateFile /old/cert\nProxyPass / http://old\n</VirtualHost>'
        rendered, count = control.render_sites(other + '\n' + own, 'aws')
        self.assertEqual(count, 1); self.assertTrue(rendered.startswith(other))
        self.assertIn('SSLCertificateFile /old/cert', rendered)
        self.assertIn('ws://127.0.0.1:18080/ws/', rendered)
        self.assertNotIn('http://old', rendered)
    def test_mixed_aliases_fail_closed(self):
        with self.assertRaises(ValueError):
            control.render_sites('<VirtualHost *:443>\nServerName vendistri.com\nServerAlias unrelated.example\n</VirtualHost>', 'aws')
    def test_maintenance_removes_existing_routes(self):
        body = '<VirtualHost *:443>\nServerName vendistri.com\nAlias /files /old\nProxyPass / http://old\n</VirtualHost>'
        result, _ = control.render_sites(body, 'maintenance')
        self.assertIn('R=503', result); self.assertNotIn('/old', result)
    def test_no_fencing_before_window(self):
        with patch.object(control, 'TARGET', control.datetime(2999, 1, 1, tzinfo=control.timezone.utc)), patch.object(control, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'locked until'): control.fence({})
            run.assert_not_called()
    def test_post_write_source_recovery_forbidden(self):
        with patch.object(control, 'sql') as sql:
            with self.assertRaisesRegex(RuntimeError, 'AWS authority'): control.recover({'authority': 'aws'})
            sql.assert_not_called()
    def test_failed_route_restores_previous_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'sites').mkdir()
            original = '<VirtualHost *:443>\nServerName vendistri.com\nDocumentRoot /old\n</VirtualHost>'
            (root/'sites/0.conf').write_text(original)
            live = root/'live.conf'; live.write_text(original)
            state = {'sites': {str(live): '0.conf'}}
            with patch.object(control, 'ROOT', root), patch.object(control, 'run', side_effect=[RuntimeError('invalid config'), '', '']) as run:
                with self.assertRaisesRegex(RuntimeError, 'invalid config'): control.route(state, 'aws')
                self.assertEqual(live.read_text(), original)
                self.assertEqual(run.call_count, 3)


if __name__ == '__main__': unittest.main()
