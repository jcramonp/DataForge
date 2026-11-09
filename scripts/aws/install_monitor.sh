#!/bin/bash
set -euo pipefail
umask 077
test "$(id -u)" = 0
exec 9>/var/lock/dataforge-deploy.lock
flock -n 9
release=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$release"
sha256sum -c SHA256SUMS
command -v aws >/dev/null
python3 -m py_compile monitor.py
backup="/opt/dataforge-deploy-backups/monitor-$(date -u +%Y%m%dT%H%M%S%NZ)"
install -d -m 0700 "$backup"
for file in /usr/local/libexec/dataforge-monitor.py /etc/dataforge-monitor.json /etc/systemd/system/dataforge-monitor.service /etc/systemd/system/dataforge-monitor.timer; do
  if test -f "$file"; then cp --parents "$file" "$backup/"; fi
done
install -d -m 0755 /usr/local/libexec
install -m 0644 monitor.py /usr/local/libexec/dataforge-monitor.py
install -m 0600 monitor-config.json /etc/dataforge-monitor.json
install -m 0644 dataforge-monitor.service dataforge-monitor.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dataforge-monitor.timer
systemctl start dataforge-monitor.service
systemctl show dataforge-monitor.service -p Result -p ActiveState
systemctl list-timers dataforge-monitor.timer --no-pager
echo DATAFORGE_MONITOR_INSTALLED
