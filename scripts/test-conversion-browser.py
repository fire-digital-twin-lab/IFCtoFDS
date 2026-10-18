"""Browser regression through file selection, workers, API and FDS display.

Requires Playwright 1.58 and an installed Chromium (or Edge on Windows).
Private IFCs are opt-in via --source; the default fixture is public and small.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "tests/browser/box.ifc")
    parser.add_argument("--url")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "scripts/out/browser-conversion"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = None
    log = None
    results = []
    try:
        if not args.url:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            args.url = f"http://127.0.0.1:{port}"
            local_python = ROOT / ".venv/Scripts/python.exe"
            executable = str(local_python) if local_python.is_file() else sys.executable
            log = (args.output / "server.log").open("w", encoding="utf-8")
            server = subprocess.Popen(
                [
                    executable,
                    "-m",
                    "uvicorn",
                    "ifc_to_fds.server:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for _ in range(100):
                try:
                    urllib.request.urlopen(args.url + "/api/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Local test server did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                **({"channel": "msedge"} if os.name == "nt" else {}),
                headless=True,
                args=["--enable-webgl", "--use-angle=swiftshader", "--allow-file-access-from-files", "--disable-web-security"],
            )
            try:
                for protocol, preview in [
                    ("http", False),
                    ("file", False),
                    ("http", True),
                    ("file", True),
                ]:
                    page = browser.new_page(accept_downloads=True)
                    page.on(
                        "pageerror",
                        lambda e: print("PAGE ERROR: " + str(e), flush=True),
                    )
                    page.set_default_timeout(60000)
                    if not preview:
                        page.route(
                            "**/js/ifc/web-ifc-display.js",
                            lambda route: route.fulfill(body=""),
                        )
                    url = (
                        args.url
                        if protocol == "http"
                        else (ROOT / "index.html").as_uri()
                    )
                    page.goto(url, wait_until="networkidle")
                    page.evaluate("""() => {
                        window.testPreviewCount = 0;
                        const api = IfcFds.ifc.WebIfcDisplay;
                        if (api) { const old = api.prototype.load; api.prototype.load = function(...args) {
                            return old.apply(this, args).then(meshes => { window.testPreviewCount = meshes.length; return meshes; });
                        }; }
                    }""")
                    print(
                        json.dumps(
                            {"case": protocol, "preview": preview, "stage": "import"}
                        ),
                        flush=True,
                    )
                    page.set_input_files("#ifc-file", args.source)
                    page.wait_for_function(
                        "!document.getElementById('convert-ifc').disabled"
                    )
                    if preview:
                        assert page.evaluate("testPreviewCount") > 0, (
                            "Web-IFC preview did not execute"
                        )
                    page.locator("#convert-ifc").click(force=True)
                    page.wait_for_function(
                        "!document.getElementById('save-fds').disabled || document.querySelector('#diagnostics button')"
                    )
                    errors = page.locator("#diagnostics li.error").all_text_contents()
                    assert not errors, errors
                    assert not page.locator("#save-fds").is_disabled()
                    with page.expect_download() as download:
                        page.locator("#save-fds").click(force=True)
                    text = Path(download.value.path()).read_text(encoding="utf-8")
                    assert "&OBST" in text or "&GEOM" in text
                    results.append(
                        dict(
                            protocol=protocol,
                            preview=preview,
                            mode="quick",
                            status="PASS",
                        )
                    )
                    # Display exceptions must retain an already-created FDS download.
                    page.evaluate(
                        "() => { window.originalFdsLoader = IfcFds.viewer.SceneViewer.prototype.loadFdsModel; IfcFds.viewer.SceneViewer.prototype.loadFdsModel = function() { throw new RangeError('injected display failure'); }; }"
                    )
                    page.locator("#convert-ifc").click(force=True)
                    page.wait_for_function(
                        "document.querySelector('#diagnostics button')"
                    )
                    assert (
                        "FDS display failed"
                        in page.locator("#diagnostics").inner_text()
                    )
                    assert not page.locator("#save-fds").is_disabled()
                    with page.expect_download() as download:
                        page.locator("#diagnostics button").click(force=True)
                    detail = json.loads(
                        Path(download.value.path()).read_text(encoding="utf-8")
                    )
                    assert (
                        detail["stage"] == "viewer"
                        and detail["stack"]
                        and detail["requestId"]
                    )
                    assert (
                        not {"mesh", "fds_text", "vertices", "inventory"}
                        & detail.keys()
                    )
                    if protocol == "http":
                        page.locator("#convert-verified").click(force=True)
                        page.wait_for_function(
                            "[...document.querySelectorAll('#diagnostics button')].length > 1"
                        )
                        page.locator("#close-audit").click()
                        with page.expect_download() as download:
                            page.locator("#diagnostics button").last.click(force=True)
                        detail = json.loads(
                            Path(download.value.path()).read_text(encoding="utf-8")
                        )
                        assert detail["stage"] == "viewer" and detail["jobId"]
                        assert not page.locator("#save-fds").is_disabled()
                        page.evaluate(
                            "() => { IfcFds.viewer.SceneViewer.prototype.loadFdsModel = window.originalFdsLoader; }"
                        )
                        # Verified default: box.ifc is an exact box, so policy emits OBST (not forced GEOM)
                        page.locator("#convert-verified").click(force=True)
                        page.wait_for_function(
                            "Number(document.getElementById('count-obsts').textContent) > 0"
                        )
                        assert (
                            page.evaluate(
                                "Number(document.getElementById('count-geoms').textContent)"
                            )
                            == 0
                        ), "Verified default must NOT force all_geom"
                        page.locator("#close-audit").click()
                        results.append(
                            dict(
                                protocol=protocol,
                                preview=preview,
                                mode="verified",
                                status="PASS",
                                display_failure_retains_fds=True,
                            )
                        )
                    else:
                        failure = page.evaluate(
                            "IfcFds.verified.run(new File([''], 'fixture.ifc'), {}).catch(e => e.message)"
                        )
                        assert "http://127.0.0.1:8000" in failure
                        results.append(
                            dict(
                                protocol=protocol,
                                mode="verified",
                                status="NOT_SUPPORTED",
                                reason=failure,
                            )
                        )
                    # An old worker may still deliver a queued message after termination.
                    page.evaluate("""() => {
                        IfcFds.viewer.SceneViewer.prototype.loadFdsModel = window.originalFdsLoader;
                        IfcFds.workers.createExportWorker = () => ({url: null, worker: {
                            addEventListener(type, handler) { if (type === 'message') window.oldMessage = handler; },
                            postMessage(request) { window.oldRequest = request; }, terminate() {}
                        }});
                    }""")
                    page.locator("#convert-ifc").click(force=True)
                    page.wait_for_function("window.oldRequest")
                    page.set_input_files(
                        "#ifc-file",
                        {
                            "name": "next-source.ifc",
                            "mimeType": "application/octet-stream",
                            "buffer": args.source.read_bytes(),
                        },
                    )
                    try:
                        page.wait_for_function(
                            "!document.getElementById('convert-ifc').disabled"
                        )
                    except Exception:
                        (args.output / "stale-worker-state.txt").write_text(
                            page.locator("body").inner_text(), encoding="utf-8"
                        )
                        page.screenshot(path=str(args.output / "stale-worker.png"))
                        raise
                    page.evaluate(
                        "oldMessage({data: {type: 'complete', requestId: oldRequest.requestId, text: 'STALE'}})"
                    )
                    assert page.locator("#save-fds").is_disabled()
                    assert (
                        page.locator("#fds-source-name").inner_text() == "No conversion"
                    )
                    results[-1]["stale_worker_ignored"] = True
                    page.close()
                    print(json.dumps(results[-2:]), flush=True)
            finally:
                browser.close()
    finally:
        (args.output / "results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        if server and server.poll() is None:
            parent = psutil.Process(server.pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            server.wait(timeout=10)
        if log:
            log.close()


if __name__ == "__main__":
    main()
