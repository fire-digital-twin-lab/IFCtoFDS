"""Real IFC -> Three.js -> tree/selection/visibility regression (no mock meshes)."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.browser


@pytest.mark.parametrize("preview", [False, True], ids=["native", "web-ifc"])
def test_real_ifc_identity_visibility_and_source_lifecycle(preview):
    from playwright.sync_api import sync_playwright

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--enable-webgl", "--use-angle=swiftshader"],
                **({"executable_path": os.environ["IFCFDS_BROWSER_EXECUTABLE"]} if os.environ.get("IFCFDS_BROWSER_EXECUTABLE") else ({"channel": "msedge"} if os.name == "nt" else {})),
            )
            try:
                page = browser.new_page()
                page.set_default_timeout(60000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                if not preview:
                    page.route(
                        "**/src/features/preview/web-ifc-display.js",
                        lambda route: route.fulfill(body=""),
                    )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}", wait_until="networkidle"
                )
                page.wait_for_function("!!(IfcFds.app.instance && IfcFds.workbench.navigation.colorOverlay.viewer)")
                page.evaluate("""() => {
                    const proto = IfcFds.viewer.SceneViewer.prototype;
                    const original = proto.addWebIfcDisplayMeshes;
                    window.previewMeshes = 0;
                    proto.addWebIfcDisplayMeshes = function(model, meshes) {
                        window.previewMeshes += meshes.length;
                        return original.call(this, model, meshes);
                    };
                    IfcFds.workbench.navigation.colorOverlay.viewer.setIfcEdgesVisible(false);
                }""")
                page.set_input_files("#ifc-file", ROOT / "tests/browser/box.ifc")
                page.wait_for_function(
                    "!document.getElementById('convert-ifc').disabled"
                )
                page.wait_for_function(
                    "IfcFds.workbench.state.selectionStore.getAllDescriptors().some(d => d.globalId)"
                )
                if preview:
                    assert page.evaluate("previewMeshes") > 0
                assert page.evaluate("""() => {
                    const v = IfcFds.workbench.navigation.colorOverlay.viewer;
                    const edges = [];
                    v.ifcGroup.traverse(node => { if (node._isIfcEdge && !node._isIfcOpeningEdge) edges.push(node); });
                    return edges.length > 0 && edges.every(edge => !edge.visible);
                }""")
                page.locator("#sidebar-tab-tree").click()
                row = page.locator(".tree-item-row").first
                key = row.get_attribute("data-entity-key")
                assert key.startswith("box.ifc:")
                row.click()
                assert page.evaluate(
                    """key => {
                    const v = IfcFds.workbench.navigation.colorOverlay.viewer;
                    return v.selectedObjects.length === 1 && v.selectedObjects[0].userData.entityKey === key;
                }""",
                    key,
                )
                # Actual raycast click at the projected centre of the loaded wall.
                page.locator("#close-inspector").click()
                assert (
                    page.evaluate(
                        "IfcFds.workbench.state.selectionStore.getSelectedKeys().length"
                    )
                    == 0
                )
                coords = page.evaluate("""() => {
                    const v = IfcFds.workbench.navigation.colorOverlay.viewer;
                    v.setView('iso');
                    v.ifcGroup.updateMatrixWorld(true);
                    const point = new THREE.Box3().setFromObject(v.ifcSolidGroup).getCenter(new THREE.Vector3());
                    v.camera.updateMatrixWorld(true);
                    point.project(v.camera);
                    const r = v.renderer.domElement.getBoundingClientRect();
                    return {x: r.x + (point.x + 1) * r.width / 2, y: r.y + (1 - point.y) * r.height / 2};
                }""")
                page.mouse.click(coords["x"], coords["y"])
                assert page.evaluate(
                    "IfcFds.workbench.state.selectionStore.getSelectedKeys()"
                ) == [key]
                assert row.evaluate("el => el.style.fontWeight") == "600"
                # Generate actual FDS primitives from the same IFC to exercise discrete clipping.
                page.locator("#sidebar-tab-workflow").click()
                page.locator("#convert-ifc").click(force=True)
                page.wait_for_function("!document.getElementById('save-fds').disabled")
                result = page.evaluate("""() => {
                    const wb = IfcFds.workbench, v = wb.navigation.colorOverlay.viewer;
                    const vis = wb.state.visibilityStore;
                    const mesh = v.obstGroup.children[0] || v.geomGroup.children[0];
                    const key = mesh.userData.entityKey;
                    if (!key) throw new Error('FDS mesh has no entity key');
                    v.resetClipping();
                    vis.hideKeys([key]);
                    v.setClipPlane('x', 'min', -100);
                    const hideThenSection = !mesh.visible;
                    vis.resetVisibility();
                    v.setClipPlane('x', 'min', 100);
                    vis.hideKeys([key]);
                    vis.showKeys([key]);
                    const sectionThenHide = !mesh.visible;
                    vis.isolateKeys([key]);
                    const isolateOutside = !mesh.visible;
                    v.resetClipping();
                    const resetKeepsIsolation = mesh.visible;
                    v.setExclusions({}, {[mesh.userData.id]: true});
                    vis.resetVisibility();
                    const exclusionSurvives = !mesh.visible;
                    v.setExclusions({}, {});
                    const material = mesh.material;
                    const before = [material.opacity, material.transparent, material.depthWrite];
                    vis.ghostKeys([key]);
                    const ghosted = material.opacity === 0.15 && material.transparent && !material.depthWrite;
                    vis.unghostKeys([key]);
                    const restored = JSON.stringify(before) === JSON.stringify([material.opacity, material.transparent, material.depthWrite]);
                    vis.ghostKeys([key]);
                    v.setFdsOpacity(0.4);
                    const ghostSurvivesOpacity = material.opacity === 0.15;
                    vis.unghostKeys([key]);
                    const opacityRestored = material.opacity === 0.4;
                    const ifcMesh = v.ifcSolidGroup.children[0];
                    const ifcKey = ifcMesh.userData.entityKey;
                    const edges = ifcMesh.children.filter(child => child._isIfcEdge && !child._isIfcOpeningEdge);
                    if (!edges.length) throw new Error('Real IFC wall has no edge helpers');
                    const edgesOff = () => edges.every(edge => !edge.visible);
                    v.setIfcEdgesVisible(false);
                    const edgesInitiallyOff = edgesOff();
                    vis.hideKeys([ifcKey]);
                    vis.showKeys([ifcKey]);
                    const edgesOffAfterHideShow = edgesOff();
                    vis.resetVisibility();
                    const edgesOffAfterReset = edgesOff();
                    vis.isolateKeys([ifcKey]);
                    const edgesOffAfterIsolate = edgesOff();
                    vis.resetVisibility();
                    const edgesOffAfterIsolateReset = edgesOff();
                    vis.hideKeys([ifcKey]);
                    v.setIfcEdgesVisible(true);
                    const edgesOnRespectsHidden = edgesOff() && !ifcMesh.visible;
                    vis.resetVisibility();
                    const edgesOnAfterReset = edges.every(edge => edge.visible) && ifcMesh.visible;
                    v.setIfcCategoryVisible(ifcMesh.userData.ifcCategory, false);
                    vis.resetVisibility();
                    const categorySurvives = !ifcMesh.visible;
                    wb.state.scenarioStore.setBaseMapping('old');
                    wb.state.scenarioStore.addFireSource({name:'Old draft'});
                    wb.commands.commandBus.execute(new wb.commands.SelectCommand([key]));
                    return {hideThenSection, sectionThenHide, isolateOutside, resetKeepsIsolation,
                        exclusionSurvives, ghosted, restored, ghostSurvivesOpacity, opacityRestored, categorySurvives,
                        edgesInitiallyOff, edgesOffAfterHideShow, edgesOffAfterReset, edgesOffAfterIsolate,
                        edgesOffAfterIsolateReset, edgesOnRespectsHidden, edgesOnAfterReset};
                }""")
                assert all(result.values()), result
                # A new source clears scenario, tree selection and undo history together.
                page.set_input_files(
                    "#ifc-file",
                    {
                        "name": "replacement.ifc",
                        "mimeType": "application/octet-stream",
                        "buffer": (ROOT / "tests/browser/box.ifc").read_bytes(),
                    },
                )
                page.wait_for_function(
                    "IfcFds.workbench.state.selectionStore.getAllDescriptors().some(d => d.entityKey.startsWith('replacement.ifc:'))"
                )
                assert (
                    page.evaluate(
                        "IfcFds.workbench.state.scenarioStore.getScenarioSpec().fireSources.length"
                    )
                    == 0
                )
                assert (
                    page.evaluate(
                        "IfcFds.workbench.state.scenarioStore.getScenarioSpec().mappingBundleSha"
                    )
                    is None
                )
                assert (
                    page.evaluate(
                        "IfcFds.workbench.state.selectionStore.getSelectedKeys().length"
                    )
                    == 0
                )
                assert (
                    page.evaluate("IfcFds.workbench.commands.commandBus.canUndo()")
                    is False
                )
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
