"""Compare full pipeline revisions; failures and timeouts are measured outcomes."""

import argparse
import hashlib
import platform
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil


def child(root, source, configuration, output):
    sys.path.insert(0, str(root))
    os.chdir(root)
    from ifc_to_fds.pipeline import convert, save_artifacts

    result = convert([source], json.loads(configuration.read_text(encoding="utf-8")))
    save_artifacts(result, output / "model.fds")
    try:
        from ifc_to_fds.results import public_result

        public = public_result(result)
    except ImportError:
        public = result
    encoded = json.dumps(public, ensure_ascii=False).encode()
    (output / "measurement.json").write_text(
        json.dumps(
            dict(
                status=result["status"],
                timings=result["timings"],
                result_bytes=len(encoded),
                artifact_bytes=sum(
                    p.stat().st_size for p in output.rglob("*") if p.is_file()
                ),
            )
        ),
        encoding="utf-8",
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--roots", nargs="+", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--timeout", type=float, default=1800)
    p.add_argument("--child", action="store_true")
    args = p.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = Path(args.source).resolve()
    config = Path(args.config).resolve()
    if args.child:
        return child(Path(args.roots[0]).resolve(), source, config, root)
    rows = []
    for revision in args.roots:
        checkout = Path(revision).resolve()
        code = hashlib.sha256()
        for file in sorted((checkout / "ifc_to_fds").rglob("*.py")):
            code.update(file.relative_to(checkout).as_posix().encode())
            code.update(file.read_bytes())
        provenance = dict(
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            configuration_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
            code_sha256=code.hexdigest(),
            python=sys.version,
            platform=platform.platform(),
            job_limits=dict(active=1, queued=2, timeout_s=args.timeout),
        )
        for run in range(4):
            directory = root / (checkout.name + "-" + str(run))
            directory.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                "--roots",
                str(checkout),
                "--source",
                str(source),
                "--config",
                str(config),
                "--output",
                str(directory),
            ]
            started = time.monotonic()
            peak = 0
            timeout = False
            with (directory / "run.log").open("wb") as log:
                process = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=log,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                while process.poll() is None:
                    try:
                        parent = psutil.Process(process.pid)
                        peak = max(
                            peak,
                            sum(
                                p.memory_info().rss
                                for p in [parent, *parent.children(recursive=True)]
                            ),
                        )
                        if time.monotonic() - started > args.timeout:
                            for sub in parent.children(recursive=True):
                                sub.kill()
                            parent.kill()
                            timeout = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    time.sleep(0.2)
                process.wait()
            row = dict(
                revision=str(checkout),
                provenance=provenance,
                warmup=run == 0,
                run=run,
                elapsed_s=time.monotonic() - started,
                peak_rss_bytes=peak,
                timeout=timeout,
                exit_code=process.returncode,
            )
            if (directory / "measurement.json").exists():
                row.update(json.loads((directory / "measurement.json").read_text()))
            else:
                row["failure"] = (directory / "run.log").read_text(
                    encoding="utf-8", errors="replace"
                )[-3000:]
            rows.append(row)
            (root / "results.json").write_text(
                json.dumps(
                    dict(
                        timeout_s=args.timeout,
                        configuration=json.loads(config.read_text()),
                        rows=rows,
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                checkout.name,
                run,
                row["exit_code"],
                round(row["elapsed_s"], 1),
                flush=True,
            )


if __name__ == "__main__":
    main()
