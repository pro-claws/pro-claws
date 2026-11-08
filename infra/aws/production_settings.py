"""AWS production overlay; activate only after the reviewed single-writer cutover.

The root-managed private JSON must come from the live release configuration,
never the development checkout. Installing this file does not activate it.
"""
import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse

_config = json.loads(Path('/etc/vendistri/production.json').read_text())
_db, _broker = _config['database'], _config['broker']
_identity = _config['application_identity']
_environment = _config['environment']
_forbidden = {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
              'AWS_PROFILE', 'AWS_DEFAULT_PROFILE', 'AWS_SHARED_CREDENTIALS_FILE',
              'AWS_CONFIG_FILE', 'DJANGO_SETTINGS_MODULE', 'PYTHONPATH', 'PYTHONHOME'}
if _forbidden.intersection(_environment):
    raise RuntimeError('Source environment must exclude credentials/profile and process-control overrides')
if not all(isinstance(key, str) and isinstance(value, str) for key, value in _environment.items()):
    raise RuntimeError('Preserved source environment must contain string values')
if (_environment.get('DEVELOPING') != 'False' or not _environment.get('DJANGO_SECRET_KEY')
        or urlparse(_environment.get('APP_WEB_URL', '')).scheme != 'https'
        or urlparse(_environment.get('APP_WEB_URL', '')).hostname not in
        {'vendistri.com', 'www.vendistri.com', 'secure.vendistri.com'}):
    raise RuntimeError('Verified production mode, signing key and public origin are required')
if (_db['name'] != 'vendistri_production' or _db['user'] in ('postgres', 'vendistri_admin')
        or not _db['user'] or not _db['password'] or not _db['host'].endswith('.rds.amazonaws.com')
        or not _broker['host'].endswith('.cache.amazonaws.com') or not _broker['password']):
    raise RuntimeError('Requires the dedicated production database and managed TLS broker')
if (not _identity['arn'].startswith('arn:aws:iam::721082559010:user/vendistri/application/')
        or not _identity['aws_access_key_id'] or not _identity['aws_secret_access_key']
        or not _environment.get('AWS_KMS_TELEMETRY_CONFIG_KEY_ID')
        or not _environment.get('TELEMETRY_INGEST_QUEUE_URL')):
    raise RuntimeError('Scoped application identity, existing encryption key and ingest queue are required')

# Match dotenv's precedence: explicit per-unit values (including the health
# worker flag) take precedence over common source configuration.
for _key, _value in _environment.items():
    os.environ.setdefault(_key, _value)
for _key in ('DEVELOPING', 'DJANGO_SECRET_KEY', 'APP_WEB_URL',
             'AWS_KMS_TELEMETRY_CONFIG_KEY_ID', 'TELEMETRY_INGEST_QUEUE_URL'):
    if os.environ.get(_key) != _environment[_key]:
        raise RuntimeError('A unit overrides verified common production configuration')
os.environ.update({
    'DATABASE_URL': f"postgresql://{quote(_db['user'], safe='')}:{quote(_db['password'], safe='')}@{_db['host']}:5432/{_db['name']}?sslmode=verify-full",
    'AWS_ACCESS_KEY_ID': _identity['aws_access_key_id'],
    'AWS_SECRET_ACCESS_KEY': _identity['aws_secret_access_key'],
    'AWS_DEFAULT_REGION': 'us-east-1', 'AWS_REGION': 'us-east-1',
    'AWS_SESSION_TOKEN': '', 'AWS_EC2_METADATA_DISABLED': 'true',
    'AWS_SHARED_CREDENTIALS_FILE': '/dev/null', 'AWS_CONFIG_FILE': '/dev/null',
    'ADMINISTRATION_MANAGED_RUNTIME_SERVICES': 'database,redis',
})
os.environ.pop('AWS_PROFILE', None)
os.environ.pop('AWS_DEFAULT_PROFILE', None)
_redis = f"rediss://:{quote(_broker['password'], safe='')}@{_broker['host']}:6379"
os.environ['CHANNEL_LAYER_URL'] = _redis + '/6?ssl_cert_reqs=required'
os.environ['CACHE_URL'] = _redis + '/7?ssl_cert_reqs=required'
if _config['separate_weather_cache']:
    os.environ['WEATHER_CACHE_URL'] = os.environ['CACHE_URL']
else:
    os.environ.pop('WEATHER_CACHE_URL', None)

from src.settings import *  # noqa: F403,E402

# The deployed URL parser omits sslrootcert, so keep verification explicit.
DATABASES['default'].setdefault('OPTIONS', {}).update(  # noqa: F405
    sslmode='verify-full', sslrootcert='/etc/vendistri/rds-ca.pem'
)
CELERY_BROKER_URL = _redis + '/5?ssl_cert_reqs=required'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
MEDIA_ROOT = '/mnt/vendistri-media/media'
PRIVATE_MEDIA_ROOT = Path('/mnt/vendistri-media/private_media')
STATIC_ROOT = '/var/www/vendistri/be/static'
# Apache's internal GET health checks do not carry forwarded HTTPS headers.
SECURE_REDIRECT_EXEMPT = [*globals().get('SECURE_REDIRECT_EXEMPT', []),
                         r'^vendistri/be/health/ready$']
# Keep all source schedules, queues, limits, email/provider settings and signing
# material. In particular, never import the rehearsal overlay here.
