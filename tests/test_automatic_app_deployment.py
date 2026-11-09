"""Exercise release identity and failure propagation without contacting AWS."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dispatch_deploy", ROOT / "scripts/aws/dispatch_deploy.py"
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)
SHA = "a" * 40


def archive_with(name):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        entry = tarfile.TarInfo(name)
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b"test"))
    return stream.getvalue()


class AutomaticAppDeploymentTests(unittest.TestCase):
    def test_refuses_a_checkout_other_than_the_tested_commit(self):
        with patch.dict(os.environ, {"DATAFORGE_REVISION": SHA}):
            with patch.object(deploy.subprocess, "check_output", return_value="b" * 40):
                with self.assertRaisesRegex(SystemExit, "Checkout"):
                    deploy.main()

    def test_refuses_a_different_aws_account(self):
        with patch.dict(os.environ, {"DATAFORGE_REVISION": SHA}):
            with patch.object(deploy.subprocess, "check_output", return_value=SHA):
                with patch.object(deploy, "aws", return_value='{"Account":"other"}'):
                    with self.assertRaisesRegex(SystemExit, "account"):
                        deploy.main()

    def run_release(self, archive_name, remote_status):
        uploads = []
        calls = []

        def aws(*args):
            calls.append(args)
            if args[:2] == ("sts", "get-caller-identity"):
                return json.dumps({"Account": deploy.ACCOUNT})
            if args[:2] == ("ssm", "send-command"):
                return '{"Command":{"CommandId":"test-command"}}'
            return json.dumps({"Status": remote_status, "ResponseCode": 0 if remote_status == "Success" else 1})

        def upload(args, **kwargs):
            uploads.append(Path(args[3]).read_bytes())

        with tempfile.TemporaryDirectory() as folder:
            env = {"DATAFORGE_REVISION": SHA, "GITHUB_RUN_ID": "1",
                   "GITHUB_RUN_ATTEMPT": "1", "GITHUB_STEP_SUMMARY": str(Path(folder) / "summary")}
            with patch.dict(os.environ, env):
                with patch.object(deploy.subprocess, "check_output", side_effect=[SHA, archive_with(archive_name)]):
                    with patch.object(deploy.subprocess, "run", side_effect=upload):
                        with patch.object(deploy, "aws", side_effect=aws):
                            deploy.main()
            summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text()
        return uploads, calls, summary

    def test_rejects_environment_files_before_upload(self):
        with self.assertRaisesRegex(SystemExit, "Environment files"):
            self.run_release("frontend/.env.production", "Success")

    def test_remote_failure_is_not_reported_as_success(self):
        with self.assertRaisesRegex(SystemExit, "did not succeed"):
            self.run_release("frontend/src/App.jsx", "Failed")

    def test_release_contains_exact_revision_and_waits_for_success(self):
        uploads, calls, summary = self.run_release("frontend/src/App.jsx", "Success")
        with tarfile.open(fileobj=io.BytesIO(uploads[0])) as archive:
            metadata = json.load(archive.extractfile("frontend/public/release.json"))
        self.assertEqual(metadata["revision"], SHA)
        self.assertIn(SHA, summary)
        send = next(call for call in calls if call[:2] == ("ssm", "send-command"))
        parameters = json.loads(send[send.index("--parameters") + 1])
        self.assertIn(SHA, parameters["commands"][0])
        self.assertEqual(calls[-1][:2], ("ssm", "get-command-invocation"))


if __name__ == "__main__":
    unittest.main()
