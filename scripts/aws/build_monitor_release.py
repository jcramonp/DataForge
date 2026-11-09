"""Package only the standalone monitor and its reviewed systemd installer."""
import hashlib
import io
from pathlib import Path
import tarfile


def main():
    root = Path(__file__).resolve().parents[2]
    files = {
        "scripts/aws/monitor.py": "monitor.py",
        "scripts/aws/monitor-config.json": "monitor-config.json",
        "scripts/aws/dataforge-monitor.service": "dataforge-monitor.service",
        "scripts/aws/dataforge-monitor.timer": "dataforge-monitor.timer",
        "scripts/aws/install_monitor.sh": "install.sh",
    }
    output = root / "dataforge-monitor-runtime.tar.gz"
    checksums = ""
    with tarfile.open(output, "w:gz") as archive:
        for source, name in files.items():
            path = root / source
            checksums += hashlib.sha256(path.read_bytes()).hexdigest() + "  " + name + "\n"
            archive.add(path, arcname=name)
        entry = tarfile.TarInfo("SHA256SUMS")
        data = checksums.encode()
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    print(output)
    print("SHA-256:", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
