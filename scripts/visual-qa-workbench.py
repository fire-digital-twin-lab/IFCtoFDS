"""Visual QA and automated UI verification for IFCtoFDS Research Workbench."""

from pathlib import Path
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "scripts/out/visual-qa"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ifc_to_fds.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    time.sleep(1.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Viewport 1: 1440 x 900 (Primary desktop)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.goto(url, wait_until="networkidle")

            # 1. Screenshot: Empty State
            page.screenshot(path=str(OUTPUT_DIR / "01_empty_workbench_1440.png"))
            print("Captured: 01_empty_workbench_1440.png")

            # Load IFC Model
            page.set_input_files("#ifc-file", ROOT / "tests/browser/box.ifc")
            page.wait_for_function("!document.getElementById('convert-ifc').disabled")

            # 2. Screenshot: IFC Loaded State
            page.screenshot(path=str(OUTPUT_DIR / "02_ifc_loaded_1440.png"))
            print("Captured: 02_ifc_loaded_1440.png")

            # Test Mode Switcher: Click Quick Preview Mode
            page.locator("#mode-tab-quick").click()
            assert page.locator("#container-quick").is_visible()
            page.screenshot(path=str(OUTPUT_DIR / "03_mode_quick_1440.png"))
            print("Captured: 03_mode_quick_1440.png")

            # Switch back to Verified Mode
            page.locator("#mode-tab-verified").click()
            assert page.locator("#container-verified").is_visible()

            # Test Domain Preflight Warning: Select storeys without domain
            page.evaluate("""() => {
                const sel = document.getElementById('verified-storeys');
                const opt = document.createElement('option');
                opt.value = 'Level 1'; opt.selected = true;
                sel.appendChild(opt);
                document.getElementById('verified-use-domain').checked = false;
                document.getElementById('verified-storeys').dispatchEvent(new Event('change'));
                document.getElementById('verified-use-domain').dispatchEvent(new Event('change'));
            }""")
            assert page.locator("#verified-domain-warning").is_visible(), "Preflight warning should be visible"

            # Clear dummy storey and keep domain unchecked for full model
            page.evaluate("""() => {
                document.getElementById('verified-storeys').replaceChildren();
                document.getElementById('verified-use-domain').checked = false;
                document.getElementById('verified-use-domain').dispatchEvent(new Event('change'));
            }""")
            assert not page.locator("#verified-domain-warning").is_visible(), "Preflight warning should hide"

            # 3. Run Verified Conversion
            page.locator("#convert-verified").click(force=True)
            page.wait_for_function("Number(document.getElementById('count-obsts').textContent) > 0")
            page.locator("#close-audit").click()

            # 4. Screenshot: Verified Completed & Mapping Verified
            page.screenshot(path=str(OUTPUT_DIR / "04_verified_completed_1440.png"))
            print("Captured: 04_verified_completed_1440.png")

            # Test Bottom Drawer: Open Artifacts Tab
            page.locator("#drawer-tab-artifacts").click()
            page.screenshot(path=str(OUTPUT_DIR / "05_artifacts_tab_1440.png"))
            print("Captured: 05_artifacts_tab_1440.png")

            # Test Bottom Drawer: Open Gates Tab
            page.locator("#drawer-tab-gates").click()
            page.screenshot(path=str(OUTPUT_DIR / "06_gates_tab_1440.png"))
            print("Captured: 06_gates_tab_1440.png")

            context.close()

            # Viewport 2: 1920 x 1080 (High-res display)
            context_1080 = browser.new_context(viewport={"width": 1920, "height": 1080})
            page_1080 = context_1080.new_page()
            page_1080.goto(url, wait_until="networkidle")
            page_1080.set_input_files("#ifc-file", ROOT / "tests/browser/box.ifc")
            page_1080.wait_for_function("!document.getElementById('convert-ifc').disabled")
            page_1080.screenshot(path=str(OUTPUT_DIR / "07_workbench_1920x1080.png"))
            print("Captured: 07_workbench_1920x1080.png")
            context_1080.close()

            # Viewport 3: 1280 x 720 (Laptop screen)
            context_720 = browser.new_context(viewport={"width": 1280, "height": 720})
            page_720 = context_720.new_page()
            page_720.goto(url, wait_until="networkidle")
            page_720.set_input_files("#ifc-file", ROOT / "tests/browser/box.ifc")
            page_720.wait_for_function("!document.getElementById('convert-ifc').disabled")
            page_720.screenshot(path=str(OUTPUT_DIR / "08_workbench_1280x720.png"))
            print("Captured: 08_workbench_1280x720.png")
            context_720.close()

            browser.close()
            print("All Visual QA screenshots successfully generated!")
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
