"""Keep rehearsal isolation separate from the deployed service resource limits."""
from pathlib import Path
import tempfile
import unittest
from configure_rehearsal import configure_units, apache_configuration


class RehearsalUnitsTest(unittest.TestCase):
    def test_public_origins_keep_api_and_legacy_routing_with_rehearsal_gate(self):
        config = apache_configuration('<VirtualHost *:80>\nServerName open.vendistri.com\n</VirtualHost>')
        for value in ('Include /etc/apache2/vendistri-api-balancer.inc',
                      'Require all denied', 'Alias /vendistri/ /var/www/vendistri/',
                      'AllowOverride FileInfo Options=MultiViews'):
            self.assertEqual(config.count(value), 4 if value in ('Require all denied', 'AllowOverride FileInfo Options=MultiViews') else 2)
        self.assertEqual(config.count('^/(?!vendistri/be/health/ready/?$)'), 2)
        self.assertIn('service-forms', config)
        self.assertIn('Require local', config.split('ServerName open.vendistri.com')[1])

    def test_resource_limits_and_restart_policy_survive_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            templates = root / 'deploy/systemd'
            templates.mkdir(parents=True)
            destination = root / 'units'
            destination.mkdir()
            original = ('[Service]\nEnvironmentFile=/etc/proclaws/aws-kms.env\n'
                        'Environment=DJANGO_SETTINGS_MODULE=src.settings\n'
                        'ExecStart=python -p 8005\nMemoryMax=1G\nCPUQuota=150%\n'
                        'Restart=always\nRuntimeMaxSec=4h30m\n')
            for name in ('proclaws-api-2.service', 'vendistri-realtime.service'):
                (templates / name).write_text(original)
            configure_units('4h', root, destination)
            for name, port, runtime in [('proclaws.service', '8003', '4h'),
                                        ('proclaws-api-2.service', '8005', '4h30m'),
                                        ('vendistri-realtime.service', '8013', '4h')]:
                unit = (destination / name).read_text()
                for value in ('MemoryMax=1G', 'CPUQuota=150%', 'Restart=always',
                              f'RuntimeMaxSec={runtime}\n', 'IPAddressDeny=any',
                              'RequiresMountsFor=/mnt/vendistri-media',
                              'DJANGO_SETTINGS_MODULE=vendistri_rehearsal', '-p ' + port):
                    self.assertIn(value, unit)
                self.assertNotIn('/etc/proclaws/aws-kms.env', unit)
                self.assertNotIn('DJANGO_SETTINGS_MODULE=src.settings', unit)


if __name__ == '__main__':
    unittest.main()
