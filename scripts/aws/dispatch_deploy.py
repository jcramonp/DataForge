"""Package a tested commit and wait for its SSM application deployment."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile
import time

BUCKET = "dataforge-academy-919774751018-input"
INSTANCE = "i-02ce56fe4c428d16a"
ACCOUNT = "919774751018"
REGION = "us-east-1"


def aws(*args):
    return subprocess.check_output(
        ["aws", *args, "--region", REGION, "--output", "json"], text=True
    )


def main():
    revision = os.environ["DATAFORGE_REVISION"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit("Invalid commit SHA")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != revision:
        raise SystemExit("Checkout does not match tested revision")
    if json.loads(aws("sts", "get-caller-identity"))["Account"] != ACCOUNT:
        raise SystemExit("Unexpected AWS account")
    key = f"deployment/cicd/{revision}/{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / "source.tar.gz"
        archive_bytes = subprocess.check_output([
            "git", "archive", revision, "Dockerfile", ".dockerignore",
            "requirements.txt", "src", "config", "database", "frontend",
        ])
        with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as source:
            with tarfile.open(archive_path, "w:gz") as target:
                for member in source.getmembers():
                    if member.name == "frontend/public/release.json":
                        continue
                    parts = Path(member.name).parts
                    if any(p.startswith(".env") and p != ".env.example" for p in parts):
                        raise SystemExit("Environment files cannot enter release")
                    target.addfile(member, source.extractfile(member) if member.isfile() else None)
                content = json.dumps({"revision": revision}).encode()
                marker = tarfile.TarInfo("frontend/public/release.json")
                marker.size = len(content)
                target.addfile(marker, io.BytesIO(content))
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        subprocess.run([
            "aws", "s3", "cp", str(archive_path), f"s3://{BUCKET}/{key}",
            "--region", REGION, "--only-show-errors",
        ], check=True)
    script = Path(__file__).with_name("deploy_app.sh").read_bytes()
    encoded = base64.b64encode(script).decode()
    remote_path = f"/opt/dataforge-cicd-{revision}.sh"
    commands = "set -eu\numask 077\n"
    commands += f"printf %s {shlex.quote(encoded)} | base64 -d > {remote_path}\n"
    commands += shlex.join(["bash", remote_path, revision, digest, BUCKET, key])
    parameters = json.dumps({"commands": [commands], "executionTimeout": ["1800"]})
    command = json.loads(aws(
        "ssm", "send-command", "--instance-ids", INSTANCE,
        "--document-name", "AWS-RunShellScript", "--parameters", parameters,
        "--comment", f"DataForge tested app {revision[:12]}",
    ))["Command"]["CommandId"]
    print(f"SSM command={command} revision={revision}", flush=True)
    deadline = time.monotonic() + 2100
    while time.monotonic() < deadline:
        try:
            invocation = json.loads(aws(
                "ssm", "get-command-invocation", "--command-id", command,
                "--instance-id", INSTANCE,
            ))
        except subprocess.CalledProcessError:
            # SSM invocation records can appear shortly after SendCommand.
            time.sleep(10)
            continue
        status = invocation["Status"]
        print(f"SSM status={status}", flush=True)
        if status not in {"Pending", "InProgress", "Delayed"}:
            print(invocation.get("StandardOutputContent", ""))
            print(invocation.get("StandardErrorContent", ""))
            if status != "Success" or invocation.get("ResponseCode") != 0:
                raise SystemExit("SSM deployment did not succeed")
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
                summary.write(f"### Application deployed\nCommit: `{revision}`\n\nSSM: `{command}`\n\nReadiness and live release SHA verified.\n")
            return
        time.sleep(10)
    raise SystemExit(f"SSM polling timed out; inspect command {command} before another deployment")


if __name__ == "__main__":
    main()
