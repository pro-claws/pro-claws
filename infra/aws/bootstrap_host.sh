#!/usr/bin/env bash
# Run as root on a fresh migration host. Does not start the application.
set -Eeuo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run as root'; exit 1; }
[[ -f /etc/vendistri/migration-stage ]] || { echo 'Not a migration host'; exit 1; }
[[ $(cat /etc/vendistri/migration-stage) == rehearsal-unconfigured ]] || { echo 'Host already configured'; exit 1; }
runtime_archive=${1:-}
runtime_sha256=${2:-}
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 ]] || { echo 'Requires production-compatible Ubuntu 22.04'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq software-properties-common ca-certificates curl apache2 \
  postgresql-client-14 redis-tools nfs-common stunnel4 rsync git jq \
  libpq5 libjpeg-turbo8 libpng16-16 libheif1
if [[ -n "$runtime_archive" ]]; then
  [[ "$runtime_sha256" =~ ^[0-9a-f]{64}$ ]] || { echo 'A verified runtime checksum is required'; exit 1; }
  printf '%s  %s\n' "$runtime_sha256" "$runtime_archive" | sha256sum --check --status
  # This operator-supplied, checksummed archive contains the audited installed
  # Python package files under usr/, not application config or user data.
  python3 - "$runtime_archive" <<'PY'
import sys, tarfile, posixpath
from pathlib import PurePosixPath
def allowed(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and '..' not in path.parts and (path.parts[0] == 'usr' or str(path) == 'etc/python3.14' or str(path).startswith('etc/python3.14/'))
with tarfile.open(sys.argv[1]) as archive:
    for member in archive.getmembers():
        if not allowed(member.name) or not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise SystemExit('Runtime archive contains an unexpected path')
        if member.issym() or member.islnk():
            link = member.linkname
            target = link.lstrip('/') if link.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(member.name), link))
            if not allowed(target):
                raise SystemExit('Runtime link escapes the verified system paths')
    # Debian's sitecustomize.py intentionally links to /etc/python3.14.
    # Links were validated above; the data filter rejects this legitimate link.
    archive.extractall('/', filter='tar')
PY
else
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -qq
  apt-get install -y -qq python3.14=3.14.4-1+jammy1 \
    python3.14-venv=3.14.4-1+jammy1
fi
[[ $(python3.14 --version) == 'Python 3.14.4' ]] || { echo 'Production runtime mismatch'; exit 1; }
id akatary >/dev/null 2>&1 || useradd --create-home --shell /bin/bash akatary
install -d -m 0750 -o akatary -g akatary /home/akatary/pro_claws
install -d -m 0700 -o akatary -g akatary /home/akatary/pro_claws/.migration
install -d -m 0755 /var/www/vendistri /mnt/vendistri-media
a2enmod proxy proxy_http proxy_wstunnel proxy_balancer lbmethod_byrequests \
  slotmem_shm proxy_hcheck headers rewrite ssl
# Every application-facing vhost is installed later with the verified release.
# A fresh Apache installation must not claim readiness before the API exists.
printf '%s\n' 'Migration rehearsal is not configured.' > /var/www/html/index.html
printf '%s\n' packages-installed > /etc/vendistri/migration-stage
echo 'Host packages installed; no application services or consumers started.'
