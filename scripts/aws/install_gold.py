"""Install only the reviewed Gold consumption overlay; refuse unrelated local changes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone

release = Path(__file__).resolve().parent
root = Path('/opt/dataforge')
allowed = {'src/api/main.py', 'frontend/src/views/AssetsView.jsx', 'src/api/gold_preview.py', 'frontend/src/services/api.js'}
manifest = json.loads((release / 'manifest.json').read_text())
if os.geteuid() != 0 or set(manifest) != allowed:
    raise SystemExit('Unexpected user or release manifest.')

def digest(content):
    normalized = content.replace('\r\n', '\n').rstrip() + '\n'
    return hashlib.sha256(normalized.encode()).hexdigest()

for name, entry in manifest.items():
    source = release / 'payload' / name
    target = root / name
    if not target.resolve().is_relative_to(root.resolve()) or source.is_symlink():
        raise SystemExit('Unsafe release path.')
    if digest(source.read_text()) != entry['new_hash']:
        raise SystemExit('Release checksum mismatch: ' + name)
    if target.exists() and digest(target.read_text()) not in entry['accepted_hashes']:
        raise SystemExit('Local file differs from reviewed versions: ' + name)

backup = Path('/opt/dataforge-deploy-backups') / ('gold-consumption-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
backup.mkdir(parents=True, mode=0o700)
for name in manifest:
    target = root / name
    if target.exists():
        saved = backup / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(release / 'payload' / name, target)
    target.chmod(0o644)
print('Reviewed Gold consumption overlay installed. Source backup:', backup)
