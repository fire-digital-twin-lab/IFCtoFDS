"""Optional Playwright/Edge check against a running loopback server on port 8765."""

from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import sys
import time

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="msedge",
        headless=True,
        args=["--enable-webgl", "--use-angle=swiftshader"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8765/", wait_until="networkidle")
    page.locator("#verified-sources").set_input_files(
        str(
            Path(
                sys.argv[1] if len(sys.argv) > 1 else "scripts/out/golden-ui/tiny.ifc"
            ).resolve()
        )
    )
    page.locator("#verified-inventory").click()
    page.wait_for_function(
        "document.getElementById('verified-storeys').options.length > 0", timeout=60000
    )
    option = page.locator("#verified-storeys option").first.get_attribute("value")
    page.locator("#verified-storeys").select_option(option)
    page.locator("#verified-use-domain").check()
    for key, value in {
        "xmin": -1,
        "xmax": 3,
        "ymin": -1,
        "ymax": 2,
        "zmin": -1,
        "zmax": 4,
    }.items():
        page.locator("#verified-domain-" + key).fill(str(value))
    page.locator("#convert-verified").click()
    expected = (
        "INCONCLUSIVE"
        if len(sys.argv) > 2 and sys.argv[2] == "reference"
        else "MAPPING_VERIFIED"
    )
    page.wait_for_function(
        "expected => document.getElementById('verified-progress').textContent === expected",
        arg=expected,
        timeout=60000,
    )
    page.wait_for_selector("#audit-body", state="visible", timeout=20000)
    if len(sys.argv) > 2 and sys.argv[2] == "reference":
        requested = []
        page.on("request", lambda request: requested.append(request.url))
        page.locator("#close-audit").click()
        started = time.monotonic()
        with page.expect_response(
            lambda r: "/geometry/" in r.url and r.status == 200
        ) as loaded:
            page.locator("#verified-show-reference").check()
        payload = loaded.value.body()
        print(
            json.dumps(
                dict(
                    reference_payload_bytes=len(payload),
                    first_payload_load_s=time.monotonic() - started,
                )
            )
        )
        page.locator("#verified-show-reference").uncheck()
    page.screenshot(path="scripts/out/golden-ui/mapping.png", full_page=True)
    result = dict(
        errors=errors,
        progress=page.locator("#verified-progress").inner_text(),
        audit=page.locator("#audit-body").inner_text()[:1500],
        downloads=page.locator("#verified-artifacts a").count(),
    )
    print(json.dumps(result))
    assert not errors
    assert result["downloads"] == 12
    browser.close()
