"""Fail closed on rehearsal/admin identities while preserving live behavior."""
import copy
import json
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch


class ProductionSettingsTest(unittest.TestCase):
    def setUp(self):
        self.config = {
            'database': {'name': 'vendistri_production', 'user': 'proclaws_app',
                         'password': 'db@password', 'host': 'db.us-east-1.rds.amazonaws.com'},
            'broker': {'host': 'broker.cache.amazonaws.com', 'password': 'redis/password'},
            'application_identity': {'arn': 'arn:aws:iam::721082559010:user/vendistri/application/test',
                                     'aws_access_key_id': 'test-access', 'aws_secret_access_key': 'test-secret'},
            'environment': {'DEVELOPING': 'False', 'DJANGO_SECRET_KEY': 'preserved-signing-key',
                            'APP_WEB_URL': 'https://secure.vendistri.com',
                            'AWS_KMS_TELEMETRY_CONFIG_KEY_ID': 'existing-key',
                            'TELEMETRY_INGEST_QUEUE_URL': 'existing-ingest-queue',
                            'STRIPE_SECRET_KEY': 'preserved-provider-key',
                            'WEATHERKIT_PRIVATE_KEY_PATH': '/etc/vendistri/weather.p8'},
            'separate_weather_cache': True,
        }
        self.source = types.ModuleType('src.settings')
        self.source.DATABASES = {'default': {'OPTIONS': {'application_name': 'preserved'}}}
        self.source.CELERY_BEAT_SCHEDULE = {'billing': {'task': 'existing.billing', 'schedule': 60}}
        self.source.CELERY_TASK_ROUTES = {'existing.billing': {'queue': 'automation'}}
        self.source.EMAIL_BACKEND = 'existing.production.EmailBackend'
        self.source.SECRET_KEY = 'preserved-signing-key'
        self.source.CELERY_WORKER_PREFETCH_MULTIPLIER = 1

    def load(self, inherited=None):
        with patch.dict(os.environ, inherited or {}, clear=True), \
                patch.object(Path, 'read_text', return_value=json.dumps(self.config)), \
                patch.dict(sys.modules, {'src.settings': self.source}):
            namespace = runpy.run_path(str(Path(__file__).with_name('production_settings.py')))
            return namespace, dict(os.environ)

    def test_live_schedules_routes_email_and_signing_material_are_preserved(self):
        schedule = copy.deepcopy(self.source.CELERY_BEAT_SCHEDULE)
        result, environment = self.load({'ADMINISTRATION_RUNTIME_HEALTH_ENABLED': 'True'})
        self.assertEqual(result['CELERY_BEAT_SCHEDULE'], schedule)
        self.assertEqual(result['CELERY_TASK_ROUTES'], self.source.CELERY_TASK_ROUTES)
        self.assertEqual(result['EMAIL_BACKEND'], self.source.EMAIL_BACKEND)
        self.assertEqual(result['SECRET_KEY'], self.source.SECRET_KEY)
        self.assertEqual(environment['STRIPE_SECRET_KEY'], 'preserved-provider-key')
        self.assertEqual(environment['ADMINISTRATION_RUNTIME_HEALTH_ENABLED'], 'True')

    def test_fresh_tls_namespaces_and_database_certificate_verification(self):
        result, environment = self.load()
        self.assertIn('db%40password', environment['DATABASE_URL'])
        self.assertIn('/5?ssl_cert_reqs=required', result['CELERY_BROKER_URL'])
        self.assertIn('/6?ssl_cert_reqs=required', environment['CHANNEL_LAYER_URL'])
        self.assertIn('/7?ssl_cert_reqs=required', environment['CACHE_URL'])
        self.assertEqual(environment['WEATHER_CACHE_URL'], environment['CACHE_URL'])
        self.assertEqual(result['DATABASES']['default']['OPTIONS'],
                         {'application_name': 'preserved', 'sslmode': 'verify-full',
                          'sslrootcert': '/etc/vendistri/rds-ca.pem'})

    def test_root_and_rehearsal_configurations_are_rejected(self):
        self.config['application_identity']['arn'] = 'arn:aws:iam::721082559010:root'
        with self.assertRaises(RuntimeError):
            self.load()
        self.setUp()
        self.config['database']['name'] = 'vendistri_rehearsal'
        with self.assertRaises(RuntimeError):
            self.load()

    def test_missing_crypto_or_queue_settings_are_rejected(self):
        for key in ['AWS_KMS_TELEMETRY_CONFIG_KEY_ID', 'TELEMETRY_INGEST_QUEUE_URL']:
            with self.subTest(key=key):
                config = copy.deepcopy(self.config)
                self.config['environment'].pop(key)
                with self.assertRaises(RuntimeError):
                    self.load()
                self.config = config

    def test_source_aws_login_credentials_cannot_be_carried_over(self):
        self.config['environment']['AWS_SECRET_ACCESS_KEY'] = 'old-source-credential'
        with self.assertRaises(RuntimeError):
            self.load()

    def test_unit_cannot_silently_change_signing_key_or_production_mode(self):
        for inherited in [{'DJANGO_SECRET_KEY': 'different-key'}, {'DEVELOPING': 'True'}]:
            with self.subTest(inherited=inherited), self.assertRaises(RuntimeError):
                self.load(inherited)

    def test_weather_uses_shared_default_cache_when_source_does(self):
        self.config['separate_weather_cache'] = False
        _, environment = self.load({'WEATHER_CACHE_URL': 'old-source-url'})
        self.assertNotIn('WEATHER_CACHE_URL', environment)


if __name__ == '__main__':
    unittest.main()
