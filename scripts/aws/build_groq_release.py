"""Build the reviewed, secret-free overlay for the initial Academy Groq rollout."""
import hashlib
import io
import json
from pathlib import Path
import tarfile


def main():
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / 'scripts/aws/groq-release-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    output = root / 'dataforge-groq-runtime.tar.gz'
    with tarfile.open(output, 'w:gz') as archive:
        for name, entry in manifest.items():
            path = root / name
            normalized = path.read_text().replace('\r\n', '\n').rstrip() + '\n'
            if hashlib.sha256(normalized.encode()).hexdigest() != entry['new_hash']:
                raise SystemExit('Source changed; regenerate reviewed manifest before packaging: ' + name)
            archive.add(path, arcname='payload/' + name)
        for source, name in [
            ('scripts/aws/install_groq.py', 'install.py'),
            ('scripts/aws/install_groq.sh', 'install.sh'),
        ]:
            archive.add(root / source, arcname=name)
        data = manifest_path.read_bytes()
        entry = tarfile.TarInfo('manifest.json')
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    print(output)
    print('SHA-256:', hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
