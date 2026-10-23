"""Automated browser tests verifying Workbench Interaction Core contracts (Phase 2)."""

from pathlib import Path
import os
import pytest

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[2]


def test_workbench_scripts_loaded_and_interaction_core_functional():
    """Verify that all workbench modules load in index.html under file:// and execute correctly."""
    from playwright.sync_api import sync_playwright

    index_uri = (ROOT / "index.html").as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, **({"executable_path": os.environ["IFCFDS_BROWSER_EXECUTABLE"]} if os.environ.get("IFCFDS_BROWSER_EXECUTABLE") else ({"channel": "msedge"} if os.name == "nt" else {}))
        )
        page = browser.new_page()
        page.goto(index_uri, wait_until="load")

        # Test 1: Verify workbench modules registration
        modules_loaded = page.evaluate("""() => {
            const wb = window.IfcFds && window.IfcFds.workbench;
            if (!wb) return { ok: false, reason: 'window.IfcFds.workbench is missing' };
            const state = wb.state;
            const commands = wb.commands;
            const selection = wb.selection;
            const inspector = wb.inspector;
            return {
                ok: !!(wb.events && wb.createEntityKey && wb.normalizeEntityDescriptor &&
                       state.selectionStore && state.visibilityStore && state.scenarioStore && state.workbenchStore &&
                       commands.commandBus && commands.SelectCommand && commands.HideCommand && commands.IsolateCommand &&
                       selection.selectionManager && selection.SelectionQuery &&
                       inspector.inspectorController && inspector.InspectorView),
                hasEvents: !!wb.events,
                hasSelectionStore: !!state.selectionStore,
                hasVisibilityStore: !!state.visibilityStore,
                hasScenarioStore: !!state.scenarioStore,
                hasCommandBus: !!commands.commandBus,
                hasInspectorController: !!inspector.inspectorController
            };
        }""")
        assert modules_loaded["ok"], (
            f"Workbench modules failed to load: {modules_loaded}"
        )

        # Test 2: EntityKey generation and normalization
        entity_key_test = page.evaluate("""() => {
            const wb = window.IfcFds.workbench;
            const itemA = {
                type: 'IFC',
                id: 'IfcWall #100',
                globalId: '2xWallABC123',
                ifcType: 'IFCWALL',
                ifcSource: { fileName: 'building.ifc' },
                raw: { storey: 'Level 1', simulation_role: 'OBST' }
            };
            const keyA = wb.createEntityKey(itemA);
            const descA = wb.normalizeEntityDescriptor(itemA);

            const itemB = {
                raw: { entity_key: 'mep.ifc:FAN_01', global_id: '1xFanXYZ', ifc_type: 'IFCFAN' }
            };
            const keyB = wb.createEntityKey(itemB);
            const descB = wb.normalizeEntityDescriptor(itemB);

            return {
                keyA: keyA,
                keyB: keyB,
                descA_valid: descA.entityKey === 'building.ifc:2xWallABC123' && descA.ifcType === 'IFCWALL',
                descB_valid: descB.entityKey === 'mep.ifc:FAN_01' && descB.ifcType === 'IFCFAN'
            };
        }""")
        assert entity_key_test["keyA"] == "building.ifc:2xWallABC123"
        assert entity_key_test["keyB"] == "mep.ifc:FAN_01"
        assert entity_key_test["descA_valid"]
        assert entity_key_test["descB_valid"]

        # Test 3: SelectionStore, multi-select, and CommandBus execution with undo/redo
        selection_test = page.evaluate("""() => {
            const wb = window.IfcFds.workbench;
            const store = wb.state.selectionStore;
            const bus = wb.commands.commandBus;

            store.clearSelection('test');
            bus.clear();

            const item1 = { id: 101, globalId: 'G101', ifcType: 'IFCWALL', sourceId: 'arch.ifc' };
            const item2 = { id: 102, globalId: 'G102', ifcType: 'IFCDOOR', sourceId: 'arch.ifc' };
            const item3 = { id: 103, globalId: 'G103', ifcType: 'IFCSLAB', sourceId: 'arch.ifc' };

            store.indexElements([item1, item2, item3], 'arch.ifc');

            // Select item1
            bus.execute(new wb.commands.SelectCommand([item1], 'replace', store));
            const sel1 = store.getSelectedKeys();

            // Add item2
            bus.execute(new wb.commands.SelectCommand([item2], 'add', store));
            const sel2 = store.getSelectedKeys();

            // Toggle item1 off
            bus.execute(new wb.commands.SelectCommand(item1, 'toggle', store));
            const sel3 = store.getSelectedKeys();

            // Undo toggle
            bus.undo();
            const selAfterUndo = store.getSelectedKeys();

            // Redo toggle
            bus.redo();
            const selAfterRedo = store.getSelectedKeys();

            return {
                sel1: sel1,
                sel2: sel2,
                sel3: sel3,
                selAfterUndo: selAfterUndo,
                selAfterRedo: selAfterRedo
            };
        }""")
        assert selection_test["sel1"] == ["arch.ifc:G101"]
        assert set(selection_test["sel2"]) == {"arch.ifc:G101", "arch.ifc:G102"}
        assert selection_test["sel3"] == ["arch.ifc:G102"]
        assert set(selection_test["selAfterUndo"]) == {"arch.ifc:G101", "arch.ifc:G102"}
        assert selection_test["selAfterRedo"] == ["arch.ifc:G102"]

        # Test 4: VisibilityStore (Hide, Isolate, Ghost) and reversible commands
        visibility_test = page.evaluate("""() => {
            const wb = window.IfcFds.workbench;
            const store = wb.state.visibilityStore;
            const bus = wb.commands.commandBus;

            store.resetVisibility('test');
            bus.clear();

            const key1 = 'arch.ifc:G101';
            const key2 = 'arch.ifc:G102';

            // Hide key1
            bus.execute(new wb.commands.HideCommand([key1], store));
            const visibleBefore = [store.isKeyVisible(key1), store.isKeyVisible(key2)];

            // Undo Hide
            bus.undo();
            const visibleAfterUndo = [store.isKeyVisible(key1), store.isKeyVisible(key2)];

            // Isolate key2
            bus.execute(new wb.commands.IsolateCommand([key2], store));
            const isolateState = [store.isKeyVisible(key1), store.isKeyVisible(key2)];

            // Ghost key2
            store.ghostKeys([key2], 'test');
            const ghostState = store.isKeyGhosted(key2);

            return {
                visibleBefore: visibleBefore,
                visibleAfterUndo: visibleAfterUndo,
                isolateState: isolateState,
                ghostState: ghostState
            };
        }""")
        assert visibility_test["visibleBefore"] == [False, True]
        assert visibility_test["visibleAfterUndo"] == [True, True]
        assert visibility_test["isolateState"] == [False, True]
        assert visibility_test["ghostState"] is True

        # Test 5: ScenarioStore (Principle A3: immutability of mapping, state transitions)
        scenario_test = page.evaluate("""() => {
            const wb = window.IfcFds.workbench;
            const store = wb.state.scenarioStore;

            store.setBaseMapping('sha256_mapping_bundle_001');
            const status1 = store.getStatus();

            const fire = store.addFireSource({
                name: 'Car Fire 01',
                peakHrrKw: 4000,
                position: [12.5, 8.0, 0.5]
            });

            store.setOpeningState('arch.ifc:DOOR_01', 'OPEN', 90);
            store.configureHvac('mep.ifc:FAN_01', {
                operational: true,
                flowRateM3s: 15.0,
                activation: 'TIME',
                activationTime: 60
            });

            const spec = store.getScenarioSpec();

            // Simulate mapping update -> stale scenario status
            store.setBaseMapping('sha256_mapping_bundle_002');
            const statusStale = store.getStatus();

            return {
                status1: status1,
                statusStale: statusStale,
                fireCount: spec.fireSources.length,
                fireHrr: spec.fireSources[0].peakHrrKw,
                doorState: spec.openingStates['arch.ifc:DOOR_01'].state,
                doorTime: spec.openingStates['arch.ifc:DOOR_01'].eventTime,
                fanFlow: spec.hvacOperations['mep.ifc:FAN_01'].flowRateM3s
            };
        }""")
        assert scenario_test["status1"] == "BASE_MAPPING_VALID"
        assert scenario_test["statusStale"] == "STALE"
        assert scenario_test["fireCount"] == 1
        assert scenario_test["fireHrr"] == 4000
        assert scenario_test["doorState"] == "OPEN"
        assert scenario_test["doorTime"] == 90
        assert scenario_test["fanFlow"] == 15.0

        # Test 6: InspectorController DOM update on SelectionStore change
        inspector_test = page.evaluate("""() => {
            const wb = window.IfcFds.workbench;
            const selStore = wb.state.selectionStore;
            const controller = wb.inspector.inspectorController;

            // Select a fan entity
            const fanItem = {
                type: 'IFC',
                id: 'FAN-SE-01',
                globalId: '3xExhaustFan01',
                ifcType: 'IFCFAN',
                ifcSource: { fileName: 'mep_ventilation.ifc' },
                raw: {
                    storey: 'Basement B1',
                    simulation_role: 'REFERENCE_GEOMETRY',
                    mep_category: 'HVAC_EXHAUST',
                    system_names: ['SMOKE_EXHAUST_B1'],
                    ports: [{ id: 'p1' }, { id: 'p2' }]
                }
            };

            selStore.setSelection([fanItem], 'test');
            const inspectCardHidden = document.getElementById('inspect-card').hidden;
            const inspectTitle = document.getElementById('inspect-title').textContent;

            // Switch to MEP tab
            controller.setActiveTab('mep');
            const structuredHtml = document.getElementById('inspect-structured-view').innerHTML;

            return {
                inspectCardHidden: inspectCardHidden,
                inspectTitle: inspectTitle,
                hasMepCategory: structuredHtml.includes('HVAC_EXHAUST'),
                hasSystem: structuredHtml.includes('SMOKE_EXHAUST_B1'),
                hasConfigureButton: structuredHtml.includes('Configure Fan Volume Flow')
            };
        }""")
        assert inspector_test["inspectCardHidden"] is False
        assert "FAN-SE-01" in inspector_test["inspectTitle"]
        assert inspector_test["hasMepCategory"]
        assert inspector_test["hasSystem"]
        assert inspector_test["hasConfigureButton"]

        browser.close()
