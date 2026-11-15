"""Drive a real server process through a long job, a full queue and a restart (plan M5.2).

    python scripts/long-job-drill.py --ifc <big.ifc> [--storey ID ...] --tiny tests/baseline/fixtures/tiny.ifc \
        --root <empty dir outside the repo> --evidence <out.json>

Phases: (1) the long job runs to the end while its progress, state and peak RSS are sampled and extra
submissions test the queue limit; (2) a second long job is interrupted by killing the server, which is then
restarted on the same job root: the interrupted job must end FAILED, the finished one must still serve the same
result, and new work must run. The evidence holds only counts, states and timings.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def multipart(path: Path, configuration: dict | None):
    boundary = "drill" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"configuration\"\r\n\r\n"
        f"{json.dumps(configuration or {})}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{path.name}\"\r\n"
        "Content-Type: application/octet-stream\r\n\r\n".encode() + path.read_bytes() + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return boundary, b"".join(parts)


class Server:
    def __init__(self, root: Path, cache: Path, env: dict):
        self.key = env.get("IFCFDS_API_KEY")
        self.port = free_port()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "ifc_to_fds", "serve", "--host", "127.0.0.1", "--port", str(self.port)],
            env={**os.environ, "IFCFDS_JOB_ROOT": str(root), "IFCFDS_GEOMETRY_CACHE": str(cache),
                 "IFCFDS_SOLVER_AUTODISCOVERY": "0", **env},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(120):
            if self.call("GET", "/api/health")[0] == 200:
                return
            time.sleep(0.5)
        raise RuntimeError("server did not become healthy")

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        try:
            conn.request(method, path, body=body, headers={**({"X-API-Key": self.key} if self.key else {}), **(headers or {})})
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, raw
        except OSError:
            return 0, None
        finally:
            conn.close()

    def submit(self, path: Path, configuration=None):
        boundary, body = multipart(path, configuration)
        return self.call("POST", "/api/jobs", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})

    def kill(self):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True)
        else:
            self.process.kill()
        self.process.wait()


def wait_state(server, jid, states, timeout, samples=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, job = server.call("GET", f"/api/jobs/{jid}")
        if status == 200:
            if samples is not None:
                samples.append((round(time.monotonic() - samples_start[0], 1), job["state"], (job.get("progress") or {}).get("stage")))
            if job["state"] in states:
                return job
        time.sleep(3)
    raise TimeoutError(f"job {jid} did not reach {states} in {timeout} s")


samples_start = [time.monotonic()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", required=True, type=Path)
    parser.add_argument("--storey", action="append", default=[])
    parser.add_argument("--tiny", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--max-memory-mb", default="4096")
    parser.add_argument("--timeout-s", default="1800")
    parser.add_argument("--production", action="store_true",
                        help="IFCFDS_ENV=production: API key, host allow-list, job-root lock, full-sync SQLite")
    parser.add_argument("--max-waiting", type=int, default=2)
    args = parser.parse_args(argv)
    if args.root.exists() and any(args.root.iterdir()):
        sys.stderr.write("--root must be empty\n")
        return 2
    config = {"scope": {"storeys": args.storey}} if args.storey else None
    env = {"IFCFDS_WORKER_MAX_MEMORY_MB": args.max_memory_mb, "IFCFDS_TIMEOUT_S": args.timeout_s,
           "IFCFDS_MAX_WAITING": str(args.max_waiting)}
    if args.production:
        env.update(IFCFDS_ENV="production", IFCFDS_API_KEY=uuid.uuid4().hex + uuid.uuid4().hex[:16],
                   IFCFDS_ALLOWED_HOSTS="127.0.0.1,localhost")
    cache = args.root.parent / (args.root.name + "-cache")
    evidence: dict = {"mode": "production" if args.production else "local", "limits": {"max_memory_mb": int(args.max_memory_mb), "timeout_s": int(args.timeout_s),
                                  "max_waiting": args.max_waiting}}
    server = Server(args.root, cache, env)
    try:
        # Phase 1: long job, queue limit, final state.
        started = time.monotonic()
        samples_start[0] = started
        status, job = server.submit(args.ifc, config)
        assert status == 202, (status, job)
        long_id = job["id"]
        wait_state(server, long_id, {"RUNNING"}, 120)
        replies = [server.submit(args.tiny) for _ in range(args.max_waiting + 2)]
        extra = [status for status, _ in replies]
        queued_ids = [job["id"] for status, job in replies if status == 202]
        evidence["queue_limit"] = {"statuses_while_running": extra,
                                   "accepted": extra.count(202), "rejected_429": extra.count(429)}
        samples: list = []
        final = wait_state(server, long_id, {"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"}, int(args.timeout_s) + 120, samples)
        result_status, result = server.call("GET", f"/api/jobs/{long_id}/result")
        stages = []
        for _, _, stage in samples:
            if stage and (not stages or stages[-1] != stage):
                stages.append(stage)
        evidence["long_job"] = {
            "state": final["state"], "wall_s": round(time.monotonic() - started, 1),
            "peak_rss_mib": round((final.get("peak_rss_bytes") or 0) / 1048576),
            "error": final.get("error"), "progress_stages_seen": stages,
            "result_http": result_status,
            "verdict": (result or {}).get("status") if isinstance(result, dict) else None,
            "mapping_status": (result or {}).get("mapping_status") if isinstance(result, dict) else None,
        }
        before = json.dumps(result, sort_keys=True) if isinstance(result, dict) else None
        # The queued tiny jobs must finish first: while they are pending the queue is full and the
        # next submission would be refused with 429.
        for queued in queued_ids:
            wait_state(server, queued, {"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"}, 600)
        # Phase 2: interrupt a running job by killing the server, then restart on the same root.
        status, job = server.submit(args.ifc, config)
        assert status == 202, (status, job)
        interrupted_id = job["id"]
        wait_state(server, interrupted_id, {"RUNNING"}, 600)
        time.sleep(20)
        server.kill()
        server = Server(args.root, cache, env)
        status, after = server.call("GET", f"/api/jobs/{interrupted_id}")
        done_status, done = server.call("GET", f"/api/jobs/{long_id}/result")
        status_new, new_job = server.submit(args.tiny)
        new_final = wait_state(server, new_job["id"], {"COMPLETED", "FAILED"}, 300) if status_new == 202 else {}
        evidence["restart"] = {
            "interrupted_state_after_restart": after.get("state") if isinstance(after, dict) else None,
            "interrupted_error": after.get("error") if isinstance(after, dict) else None,
            "finished_job_result_identical": before is not None and json.dumps(done, sort_keys=True) == before,
            "new_job_http": status_new, "new_job_state": new_final.get("state"),
        }
    finally:
        server.kill()
    args.evidence.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    ok = (evidence["long_job"]["state"] == "COMPLETED"
          and evidence["restart"]["interrupted_state_after_restart"] in ("FAILED", "CANCELLED")
          and evidence["restart"]["finished_job_result_identical"]
          and evidence["restart"]["new_job_state"] == "COMPLETED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
