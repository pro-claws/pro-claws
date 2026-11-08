"""Host-only overlay for the pinned release; paired with service egress denial.

Copy to /etc/vendistri/vendistri_rehearsal.py. The private config is installed
separately with owner-only permissions. This is never a production setting.
"""
import json
import os
from pathlib import Path
from urllib.parse import quote

_config = json.loads(Path('/etc/vendistri/rehearsal.json').read_text())
if not _config['database']['name'].startswith('vendistri_rehearsal'):
    raise RuntimeError('Rehearsal settings require the isolated database')
if not _config['broker']['host'].endswith('.cache.amazonaws.com'):
    raise RuntimeError('Rehearsal requires the isolated AWS broker')

_db = _config['database']
_broker = _config['broker']
os.environ['DEVELOPING'] = 'False'
os.environ['APP_WEB_URL'] = 'https://vendistri-rehearsal.invalid'
os.environ['DJANGO_SECRET_KEY'] = _config['django_secret_key']
os.environ['DATABASE_URL'] = f"postgresql://{quote(_db['user'], safe='')}:{quote(_db['password'], safe='')}@{_db['host']}:5432/{_db['name']}?sslmode=verify-full&sslrootcert=/etc/vendistri/rds-ca.pem"
_redis = f"rediss://:{quote(_broker['password'], safe='')}@{_broker['host']}:6379"
os.environ['CHANNEL_LAYER_URL'] = _redis + '/1?ssl_cert_reqs=required'
os.environ['CACHE_URL'] = _redis + '/2?ssl_cert_reqs=required'
os.environ['TELEMETRY_INGEST_QUEUE_URL'] = ''
os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'
os.environ['ADMINISTRATION_MANAGED_RUNTIME_SERVICES'] = 'database,redis'

from src.settings import *  # noqa: F403,E402

# The pinned release's URL parser retains sslmode but not sslrootcert.
DATABASES['default'].setdefault('OPTIONS', {}).update(  # noqa: F405
    sslmode='verify-full', sslrootcert='/etc/vendistri/rds-ca.pem'
)

CELERY_BROKER_URL = _redis + '/0?ssl_cert_reqs=required'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BEAT_SCHEDULE = {}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ADMINISTRATION_RUNTIME_HEALTH_ENABLED = False
AWS_KMS_TELEMETRY_CONFIG_KEY_ID = ''
TELEMETRY_INGEST_QUEUE_URL = ''
MEDIA_ROOT = '/mnt/vendistri-media/media'
PRIVATE_MEDIA_ROOT = Path('/mnt/vendistri-media/private_media')
STATIC_ROOT = '/var/www/vendistri/be/static'
ALLOWED_HOSTS = [*ALLOWED_HOSTS, '127.0.0.1', 'localhost']  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r'^vendistri/be/health/ready$']
