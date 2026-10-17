"""Automated browser tests verifying Workbench Navigation features (Phase 3)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workbench_navigation_modules_and_visual_qa():
    """Verify SemanticModelTree, ColorOverlayEngine, and SectionBoxController under file://."""
    from playwright.sync_api import sync_playwright

    index_uri = (ROOT / "index.html").as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(index_uri, wait_until="load")

        # Test 1: Verify navigation module registrations
        nav_loaded = page.evaluate("""() => {
            const nav = window.IfcFds && window.IfcFds.workbench && window.IfcFds.workbench.navigation;
            if (!nav) return { ok: false, reason: 'window.IfcFds.workbench.navigation missing' };
            return {
                ok: !!(nav.colorOverlay && nav.modelTree && nav.sectionBox),
                hasColorOverlay: !!nav.colorOverlay,
                hasModelTree: !!nav.modelTree,
                hasSectionBox: !!nav.sectionBox
            };
        }""")
        assert nav_loaded["ok"], f"Navigation modules failed to load: {nav_loaded}"

        # Test 2: ColorOverlayEngine scheme mapping & legend updates
        color_test = page.evaluate("""() => {
            const overlay = window.IfcFds.workbench.navigation.colorOverlay;

            overlay.applyColorMode('mapping');
            const legendMapping = document.getElementById('legend-swatches').innerText;

            overlay.applyColorMode('verification');
            const legendVerif = document.getElementById('legend-swatches').innerText;

            overlay.applyColorMode('ifc-type');
            const legendIfc = document.getElementById('legend-swatches').innerText;

            overlay.applyColorMode('mep');
            const legendMep = document.getElementById('legend-swatches').innerText;

            return {
                hasObst: legendMapping.includes('OBST'),
                hasPass: legendVerif.includes('PASS'),
                hasStructure: legendIfc.includes('Structure'),
                hasSuppression: legendMep.includes('Fire Suppression')
            };
        }""")
        assert color_test["hasObst"]
        assert color_test["hasPass"]
        assert color_test["hasStructure"]
        assert color_test["hasSuppression"]

        # Test 3: SemanticModelTree rendering, grouping, and search
        tree_test = page.evaluate("""() => {
            const store = window.IfcFds.workbench.state.selectionStore;
            const tree = window.IfcFds.workbench.navigation.modelTree;

            const mockItems = [
                { id: 1, globalId: 'W1', ifcType: 'IFCWALL', raw: { storey: 'Level 1', simulation_role: 'OBST' } },
                { id: 2, globalId: 'W2', ifcType: 'IFCWALL', raw: { storey: 'Level 1', simulation_role: 'OBST' } },
                { id: 3, globalId: 'D1', ifcType: 'IFCDOOR', raw: { storey: 'Level 1', simulation_role: 'HOLE' } },
                { id: 4, globalId: 'F1', ifcType: 'IFCFAN', raw: { storey: 'Basement B1', mep_category: 'HVAC_EXHAUST', system_names: ['SMOKE_EXTRACT'] } }
            ];
            store.indexElements(mockItems, 'arch.ifc');

            // Render by Storey
            tree.setGroupBy('storey');
            const htmlStorey = document.getElementById('semantic-model-tree').innerText;

            // Render by Type
            tree.setGroupBy('ifc-type');
            const htmlType = document.getElementById('semantic-model-tree').innerText;

            // Render by System
            tree.setGroupBy('system');
            const htmlSystem = document.getElementById('semantic-model-tree').innerText;

            // Search filter
            tree.setSearchQuery('FAN');
            const htmlSearch = document.getElementById('semantic-model-tree').innerText;

            return {
                hasLevel1: htmlStorey.includes('Level 1') && htmlStorey.includes('Basement B1'),
                hasIfcWall: htmlType.includes('IFCWALL') && htmlType.includes('IFCFAN'),
                hasMepSystem: htmlSystem.includes('SMOKE_EXTRACT'),
                searchFiltered: htmlSearch.includes('IFCFAN') && !htmlSearch.includes('IFCDOOR')
            };
        }""")
        assert tree_test["hasLevel1"]
        assert tree_test["hasIfcWall"]
        assert tree_test["hasMepSystem"]
        assert tree_test["searchFiltered"]

        # Test 4: SectionBoxController storey bounds cut
        section_test = page.evaluate("""() => {
            const box = window.IfcFds.workbench.navigation.sectionBox;
            const store = window.IfcFds.workbench.state.selectionStore;

            const storeyItems = [
                { id: 10, globalId: 'B1_W1', raw: { storey: 'Basement B1', bounding_box: { zmin: -3.5, zmax: -0.2 } } },
                { id: 11, globalId: 'B1_S1', raw: { storey: 'Basement B1', bounding_box: { zmin: -3.6, zmax: -3.3 } } }
            ];
            store.indexElements(storeyItems, 'arch.ifc');

            const cutSuccess = box.cutToStorey('Basement B1');
            const activeBounds = box.activeBounds;

            return {
                cutSuccess: cutSuccess,
                zmin: activeBounds && activeBounds.zmin,
                zmax: activeBounds && activeBounds.zmax
            };
        }""")
        assert section_test["cutSuccess"] is True
        # zmin should be -3.6 - 0.20 = -3.8
        assert abs(section_test["zmin"] - (-3.8)) < 1e-3
        # zmax should be -0.2 + 0.20 = 0.0
        assert abs(section_test["zmax"] - 0.0) < 1e-3

        # Test 5: Sidebar Tab Switching
        tab_test = page.evaluate("""() => {
            const tabTree = document.getElementById('sidebar-tab-tree');
            const tabWorkflow = document.getElementById('sidebar-tab-workflow');
            const panelWorkflow = document.getElementById('sidebar-panel-workflow');
            const panelTree = document.getElementById('sidebar-panel-tree');

            tabTree.click();
            const treeVisible = panelTree.style.display === 'flex' && panelWorkflow.style.display === 'none';

            tabWorkflow.click();
            const workflowVisible = panelWorkflow.style.display === 'block' && panelTree.style.display === 'none';

            return {
                treeVisible: treeVisible,
                workflowVisible: workflowVisible
            };
        }""")
        assert tab_test["treeVisible"]
        assert tab_test["workflowVisible"]

        browser.close()
