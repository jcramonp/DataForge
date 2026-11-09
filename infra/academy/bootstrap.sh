#!/bin/bash
set -euo pipefail

dnf install -y docker git
systemctl enable --now docker
systemctl enable --now amazon-ssm-agent

version=v2.32.4
url="https://github.com/docker/compose/releases/download/${version}"
tmp=$(mktemp -d)
trap 'rm -f "$tmp/docker-compose-linux-x86_64" "$tmp/checksums.txt"; rmdir "$tmp"' EXIT
cd "$tmp"
curl -fSsL --retry 3 -O "$url/docker-compose-linux-x86_64"
curl -fSsL --retry 3 -O "$url/checksums.txt"
awk '$2 == "docker-compose-linux-x86_64" || $2 == "*docker-compose-linux-x86_64" { print }' checksums.txt | sha256sum --check --strict
install -D -m 0755 docker-compose-linux-x86_64 /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
install -d -m 0750 /opt/dataforge

