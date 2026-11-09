"""Host-side readiness/history monitor; stdlib and the EC2 AWS CLI only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import urlopen
from datetime import datetime, timezone


def fetch_json(path):
    with urlopen("http://127.0.0.1:8081/api/" + path, timeout=15) as response:
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("Response exceeds monitor limit")
        return json.loads(data)


def observe(fetch=fetch_json):
    try:
        ready = fetch("ready")
        checks = ready["checks"]
        healthy = (ready.get("status") == "ready" and isinstance(checks, list)
                   and bool(checks) and all(c.get("ok") is True for c in checks))
    except Exception:
        healthy = False
    try:
        runs = fetch("runs?limit=200")
        if not isinstance(runs, list) or any(
            not isinstance(r, dict) or not r.get("orchestration_run_id")
            or r.get("status") not in {"pending", "queued", "running", "success", "failed", "cancelled"}
            for r in runs
        ):
            raise ValueError("Invalid history response")
        history_ok = True
    except Exception:
        runs, history_ok = [], False
    return healthy, history_ok, runs


def evaluate(previous, ready, history_ok, runs, notify, threshold=2, checkpoint=lambda state: None):
    """Commit notification bookkeeping only after the publisher acknowledges it."""
    state = json.loads(json.dumps(previous))
    sent = 0
    for channel, ok in (("application", ready), ("run_history", history_ok)):
        current = state.setdefault(channel, {"failures": 0, "alerted": False})
        current["failures"] = 0 if ok else current["failures"] + 1
        if not ok and current["failures"] >= threshold and not current["alerted"]:
            notify("DataForge: " + channel + " unavailable",
                   "ALERTA REAL: two consecutive checks failed for " + channel
                   + ". Inspect the API, PostgreSQL, S3 and monitor journal. No data was changed.")
            current["alerted"] = True
            checkpoint(state)
            sent += 1
        elif ok and current["alerted"]:
            notify("DataForge: " + channel + " recovered",
                   "RECUPERACION: " + channel + " now passes its check.")
            current["alerted"] = False
            checkpoint(state)
            sent += 1

    if history_ok:
        failures = [r for r in runs if r["status"] == "failed"]
        seen = state.setdefault("notified_failures", [])
        if state.get("history_initialized"):
            new = [r for r in failures if str(r["orchestration_run_id"]) not in seen]
            if new:
                # One bounded message per check, without source data or raw errors.
                summary = [{"orchestration_run_id": r["orchestration_run_id"],
                            "external_run_id": str(r.get("external_run_id", ""))[:160],
                            "client_code": str(r.get("client_code", ""))[:80],
                            "project_code": str(r.get("project_code", ""))[:80]} for r in new]
                payload = json.dumps(summary)
                if len(payload.encode()) > 60000:
                    payload = json.dumps({"count": len(new), "run_ids": [r["orchestration_run_id"] for r in new]})
                notify("DataForge: pipeline failed",
                       "ALERTA REAL: new failed persisted orchestrations: " + payload)
                seen.extend(str(r["orchestration_run_id"]) for r in new)
                checkpoint(state)
                sent += 1
        else:
            # Establish history baseline, avoiding alerts for old failed demo runs.
            seen.extend(str(r["orchestration_run_id"]) for r in failures)
            state["history_initialized"] = True
        # Keep identities for the current bounded history; also retain recently sent ones.
        state["notified_failures"] = list(dict.fromkeys(seen))[-2000:]
    return state, sent


def publish(config, subject, message):
    result = subprocess.run(
        ["aws", "sns", "publish", "--region", config["region"],
         "--topic-arn", config["topic_arn"], "--subject", subject,
         "--message", message, "--output", "json"],
        check=True, capture_output=True, text=True, timeout=20,
    )
    if not json.loads(result.stdout).get("MessageId"):
        raise RuntimeError("SNS acknowledgement missing")


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="/etc/dataforge-monitor.json")
    parser.add_argument("--state", default="/var/lib/dataforge-monitor/state.json")
    parser.add_argument("--test-notification", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config = json.loads(Path(args.config).read_text())
        if args.test_notification:
            publish(config, "DataForge: monitor notification test",
                    "PRUEBA CONTROLADA: installed monitor can publish to SNS. No real application or pipeline failure is implied.")
            print(json.dumps({"event": "monitor_test_notification_sent"}))
            return 0
        path = Path(args.state)
        previous = json.loads(path.read_text()) if path.exists() else {}
        ready, history_ok, runs = observe()
        state, sent = evaluate(previous, ready, history_ok, runs,
                               lambda subject, message: publish(config, subject, message),
                               checkpoint=lambda state: save_state(path, state))
        state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
        save_state(path, state)
        print(json.dumps({"event": "monitor_check", "ready": ready,
                          "history_ok": history_ok, "runs_checked": len(runs),
                          "notifications": sent, "timestamp": state["last_checked_at"]}))
        return 0
    except Exception as exc:
        # Never print raw HTTP responses, API data, credentials or AWS error details.
        print(json.dumps({"event": "monitor_error", "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
