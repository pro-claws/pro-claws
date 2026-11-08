"""Configure isolated HTTP/realtime services using the pinned unit templates.

Run as root after source/data installation. Does not start workers, Beat or
attach the hosts to public traffic. Private-only egress is mandatory.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path('/home/akatary/pro_claws/backend')
MARKER = Path('/etc/vendistri/migration-stage')
EGRESS = '''
[Unit]
RequiresMountsFor=/mnt/vendistri-media
[Service]
Environment=PYTHONPATH=/etc/vendistri
Environment=AWS_EC2_METADATA_DISABLED=true
IPAddressDeny=any
IPAddressAllow=127.0.0.0/8 172.26.0.0/16 172.31.0.0/16
'''


def configure_units(api_runtime, root=ROOT, destination=Path('/etc/systemd/system')):
    secondary_runtime = '4h30m' if api_runtime == '4h' else '4h'
    for original, destination_name, port, runtime in [
        ('proclaws-api-2.service', 'proclaws.service', '8003', api_runtime),
        ('proclaws-api-2.service', 'proclaws-api-2.service', '8005', secondary_runtime),
        ('vendistri-realtime.service', 'vendistri-realtime.service', '8013', api_runtime),
    ]:
        unit = (root / 'deploy/systemd' / original).read_text()
        unit = unit.replace('EnvironmentFile=/etc/proclaws/aws-kms.env\n', '')
        unit = unit.replace('DJANGO_SETTINGS_MODULE=src.settings', 'DJANGO_SETTINGS_MODULE=vendistri_rehearsal')
        unit = unit.replace('ADMINISTRATION_RUNTIME_HEALTH_ENABLED=True', 'ADMINISTRATION_RUNTIME_HEALTH_ENABLED=False')
        unit = unit.replace('After=network.target postgresql.service redis-server.service', 'After=network-online.target remote-fs.target')
        unit = unit.replace('After=network.target redis.service', 'After=network-online.target remote-fs.target')
        unit = unit.replace('Wants=redis.service\n', '')
        unit = unit.replace('-p 8005', '-p ' + port).replace('RuntimeMaxSec=4h30m', 'RuntimeMaxSec=' + runtime)
        (destination / destination_name).write_text(unit + EGRESS)


def apache_configuration(mobile_origin):
    # Both public origins already serve API and legacy asset paths. Keep one
    # routing owner rather than allowing the marketing origin to serve SPA HTML
    # for an API request. The restored .htaccess files own frontend deep links.
    common = '''
    ProxyPreserveHost On
    RequestHeader set Host "secure.vendistri.com"
    RequestHeader set X-Forwarded-Proto "https"
    <LocationMatch "^/(?!vendistri/be/health/ready/?$)">
        Require local
    </LocationMatch>
    <LocationMatch "^/vendistri/be/private_media(?:/|$)">
        Require all denied
    </LocationMatch>
    ProxyPass /vendistri/be/static/ !
    Alias /vendistri/be/static/ /var/www/vendistri/be/static/
    ProxyPass /vendistri/be/media/ !
    Alias /vendistri/be/media/ /mnt/vendistri-media/media/
    ProxyPass /vendistri/be/ws/ ws://127.0.0.1:8013/vendistri/be/ws/
    ProxyPassReverse /vendistri/be/ws/ ws://127.0.0.1:8013/vendistri/be/ws/
    ProxyPass /ws/ ws://127.0.0.1:8013/ws/
    ProxyPassReverse /ws/ ws://127.0.0.1:8013/ws/
    Include /etc/apache2/vendistri-api-balancer.inc
    Alias /vendistri/ /var/www/vendistri/
    <Directory /var/www/vendistri>
        Options -Indexes
        AllowOverride None
        Require all granted
    </Directory>
    <Directory /var/www/vendistri/fe>
        Options -Indexes
        AllowOverride FileInfo Options=MultiViews
        Require all granted
    </Directory>
    <Directory /var/www/vendistri/home_page>
        Options -Indexes
        AllowOverride FileInfo Options=MultiViews
        Require all granted
    </Directory>
    <Directory /var/www/vendistri/be/static>
        Options -Indexes
        Require all granted
    </Directory>
    <Directory /mnt/vendistri-media/media>
        Options -Indexes
        AllowOverride None
        Require all granted
    </Directory>
    <Directory /mnt/vendistri-media/private_media>
        Require all denied
    </Directory>
    RewriteEngine On
    RewriteRule ^/?vendistri/(fe/)?service-forms/?$ https://secure.vendistri.com/service-forms [R=302,L]
'''
    config = f'''<VirtualHost *:80>
    ServerName secure.vendistri.com
    DocumentRoot /var/www/vendistri/fe
{common}
</VirtualHost>
<VirtualHost *:80>
    ServerName vendistri.com
    ServerAlias www.vendistri.com
    DocumentRoot /var/www/vendistri/home_page
{common}
    RewriteRule ^/?(dashboard|locations|machines|tasks|routes|account-settings|subscription|inventory|reports|help-center|contact)(/.*)?$ https://secure.vendistri.com%{{REQUEST_URI}} [R=301,L]
</VirtualHost>
'''
    # Reuse the dedicated mobile association-file origin, including MIME rules.
    config += mobile_origin.replace('</VirtualHost>', '<Location />\nRequire local\n</Location>\n</VirtualHost>')
    return config


def configure_apache():
    subprocess.run(['usermod', '-a', '-G', 'akatary', 'www-data'], check=True)
    mobile_origin = Path('/home/akatary/pro_claws/home_page/deploy/apache/open.vendistri.conf').read_text()
    config = apache_configuration(mobile_origin)
    balancer = (ROOT / 'deploy/apache/secure.vendistri.api-balancer.conf').read_text()
    # Preserve the live site's GET readiness checks; exempt this single path
    # from HTTPS redirect in the rehearsal overlay so it actually reaches SQL.
    balancer = balancer[balancer.index('<Proxy'):].replace(
        'hcmethod=TCP', 'hcmethod=GET hcuri=/vendistri/be/health/ready'
    )
    Path('/etc/apache2/vendistri-api-balancer.inc').write_text(balancer)
    Path('/etc/apache2/sites-available/000-vendistri-rehearsal.conf').write_text(config)
    shutil.copy2(ROOT / 'deploy/apache/vendistri-private-media.conf', '/etc/apache2/conf-available/vendistri-private-media.conf')
    subprocess.run(['a2dissite', '000-default'], check=True)
    subprocess.run(['a2ensite', '000-vendistri-rehearsal'], check=True)
    subprocess.run(['a2enconf', 'vendistri-private-media'], check=True)
    subprocess.run(['apache2ctl', 'configtest'], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-runtime', choices=['4h', '4h30m'], required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not MARKER.exists() or MARKER.read_text().strip() != 'source-installed':
        raise SystemExit('Requires a freshly installed rehearsal release')
    if not Path('/mnt/vendistri-media').is_mount() or not Path('/etc/vendistri/rehearsal.json').is_file():
        raise SystemExit('Restored private configuration and shared storage are required')
    shutil.copy2(Path(__file__).with_name('rehearsal_settings.py'), '/etc/vendistri/vendistri_rehearsal.py')
    os.chmod('/etc/vendistri/vendistri_rehearsal.py', 0o644)
    configure_units(args.api_runtime)
    configure_apache()
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    MARKER.write_text('rehearsal-configured\n')
    MARKER.chmod(0o644)
    print('Rehearsal configured; verify egress isolation before starting HTTP/realtime')
