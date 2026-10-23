// Real HTTP/WASM/Verified workflow and mount/destroy regression.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const {spawn, execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const python = path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const driver = execFileSync(python, ['-c', 'from pathlib import Path; import playwright; print(Path(playwright.__file__).parent / "driver/package")'], {encoding: 'utf8', windowsHide: true}).trim();
const {chromium} = require(driver);
const output = path.join(root, 'scripts/out/layout-browser');
fs.mkdirSync(output, {recursive: true});

(async () => {
    const port = await new Promise(resolve => {
        const probe = net.createServer();
        probe.listen(0, '127.0.0.1', () => {const port = probe.address().port; probe.close(() => resolve(port));});
    });
    const base = 'http://127.0.0.1:' + port;
    const executable = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python';
    const serverLog = fs.openSync(path.join(output, 'server.log'), 'w');
    const server = spawn(path.join(root, executable), ['-m', 'uvicorn', 'ifc_to_fds.server:app', '--host', '127.0.0.1', '--port', String(port)], {
        cwd: root, windowsHide: true, stdio: ['ignore', serverLog, serverLog],
        env: {...process.env, IFCFDS_JOB_ROOT: path.join(output, 'jobs')}
    });
    let browser;
    const errors = [];
    try {
        let healthy = false;
        for (let i = 0; i < 100; i++) {
            try {healthy = (await fetch(base + '/api/health')).ok;} catch (_) {}
            if (healthy) break;
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        assert.ok(healthy, 'Backend did not start; inspect server.log');
        browser = await chromium.launch({headless: true,
            ...(process.env.IFCFDS_BROWSER_EXECUTABLE ? {executablePath: process.env.IFCFDS_BROWSER_EXECUTABLE} : {}),
            args: ['--enable-webgl', '--use-angle=swiftshader']});
        const page = await browser.newPage({acceptDownloads: true});
        page.setDefaultTimeout(60000);
        page.on('pageerror', error => errors.push(error.stack));
        await page.goto(base, {waitUntil: 'networkidle'});
        await page.setInputFiles('#ifc-file', path.join(root, 'tests/browser/box.ifc'));
        await page.waitForFunction(() => !!IfcFds.app.instance.state.ifcModel);
        await page.waitForFunction(() => !document.getElementById('convert-ifc').disabled);
        assert.ok(await page.evaluate(() => IfcFds.app.instance.state.lastDisplayMeshes?.length > 0), 'Real web-ifc display did not complete');
        await page.locator('#mode-tab-verified').click();
        await page.locator('#convert-verified').click({force: true});
        await page.waitForFunction(() => IfcFds.app.instance.state.lastAuditReport?.mapping_status === 'MAPPING_VERIFIED');
        await page.waitForFunction(() => !document.getElementById('save-fds').disabled);
        await page.waitForFunction(() => !IfcFds.app.instance.state.exportBusy);
        if (await page.locator('#audit-modal').isVisible()) await page.locator('#close-audit').click();
        const [download] = await Promise.all([
            page.waitForEvent('download'), page.locator('#save-fds').click()
        ]);
        assert.match(fs.readFileSync(await download.path(), 'utf8'), /&(OBST|GEOM)/);
        const lifecycle = await page.evaluate(() => {
            function counts() {
                const state = IfcFds.workbench.state;
                return [state.selectionStore._listeners.length, state.visibilityStore._listeners.length];
            }
            const before = counts();
            IfcFds.app.instance.destroy();
            const destroyed = counts();
            const canvasesAfterDestroy = document.querySelectorAll('#viewer canvas').length;
            IfcFds.app.instance = IfcFds.app.createApplication();
            IfcFds.app.instance.mount();
            IfcFds.app.instance.mount();
            return {before, destroyed, after: counts(), canvasesAfterDestroy};
        });
        assert.deepEqual(lifecycle.after, lifecycle.before, 'Remount multiplied store subscribers');
        assert.ok(lifecycle.destroyed.every((count, i) => count < lifecycle.before[i]));
        assert.equal(lifecycle.canvasesAfterDestroy, 0);
        assert.deepEqual(errors, []);
        const result = {http: 'PASS', web_ifc: 'PASS', verified: 'MAPPING_VERIFIED', download: 'PASS', lifecycle};
        fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2));
        console.log(JSON.stringify(result));
    } finally {
        if (errors.length) console.error(errors);
        if (browser) await browser.close();
        server.kill();
        fs.closeSync(serverLog);
    }
})().catch(error => {console.error(error); process.exitCode = 1;});
