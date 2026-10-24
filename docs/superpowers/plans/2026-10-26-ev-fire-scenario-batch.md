# EV Fire Scenario Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sinh hàng loạt kịch bản cháy xe điện (xe máy + ô tô) từ IFC verified và chạy FDS đầy đủ, tổng hợp verdict qua UI.

**Architecture:** Giữ nguyên tắc A3 (scenario tham chiếu `bundle_sha256`, không mutate bundle). Thêm package `ifc_to_fds/fire/` (library + emitter), mở rộng validation bằng mesh gate, UI panel mới gọi JobService hiện có. Mỗi task ra deliverable test được độc lập.

**Tech Stack:** Python (pydantic models, pytest TDD), FDS 6.11.1 (`scripts/install-fds.py`), vanilla JS workbench hiện có.

**Spec:** `docs/superpowers/specs/2026-10-26-ev-fire-scenario-batch-design.md`

## Global Constraints

- Scenario không mutate MappingBundle, chỉ tham chiếu `bundle_sha256` (A3).
- Fail-closed: yêu cầu `MAPPING_VERIFIED` + review tay trước seal; fail mesh → INCONCLUSIVE, không chạy solver.
- Mọi preset có `citations[]` + `confidence`; `unknown-origin` bắt buộc low + cảnh báo.
- Báo cáo ghi rõ giả định + yêu cầu thẩm định PCCC độc lập.
- Python >= 3.10 (pyproject); TDD mọi task; commit sau mỗi task.

## Review Focus

- Preset không citation lọt vào batch mà không cảnh báo → test: preset thiếu citations phải bị reject hoặc auto low+warn.
- Scenario gắn nhầm `bundle_sha256` (stale mapping) → test: emitter từ chối bundle chưa VERIFIED.
- $D^*/\Delta x$ ngoài [4,16] vẫn chạy solver → test: gate chặn, job INCONCLUSIVE.
- Batch N jobs làm đầy queue (max_waiting) → test: queue đầy trả 429, scenario còn lại chờ.
- UI sinh scenario từ mapping STALE → test: ScenarioStore status STALE chặn seal.

---

### Task 1: EV physics library + schema

**Files:**
- Create: `ifc_to_fds/fire/__init__.py`, `ifc_to_fds/fire/ev_library.py`
- Create: `reference-cases/ev-library/e-bike-lfp.json`, `reference-cases/ev-library/auto-nmc.json`
- Test: `tests/test_ev_library.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_ev_preset(vehicle_class, chemistry) -> EVPreset` (pydantic: ranges, yields, citations, confidence); `list_ev_presets() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
def test_load_ebike_lfp_preset_has_ranges_and_citation():
    p = load_ev_preset("e-bike", "LFP")
    assert p.pack_kwh_range == (0.5, 3.0)
    assert p.confidence in ("low", "medium", "high")
    assert isinstance(p.citations, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ev_library.py::test_load_ebike_lfp_preset_has_ranges_and_citation -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Implement `load_ev_preset` + `EVPreset` + 2 JSON presets in `ifc_to_fds/fire/ev_library.py`**

Preset e-bike LFP `pack_kwh_range=(0.5,3.0)`, confidence low + notes giả định; auto NMC peak 2-7 MW, confidence medium.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ev_library.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ifc_to_fds/fire tests/test_ev_library.py reference-cases/ev-library
git commit -m "feat: add versioned EV fire physics library"
```

### Task 2: Geometry remediation gate (Duplex)

**Files:**
- Modify: `ifc_to_fds/geometry/engine.py` (theo lỗi self-intersect audit)
- Test: `tests/test_geometry_export_investigation.py` (thêm case Duplex)

**Interfaces:**
- Consumes: `CanonicalModel` hiện có.
- Produces: Duplex.ifc đạt VERIFIED (hoặc document mẫu sai + chọn golden khác).

- [ ] **Step 1: Write the failing test**

```python
def test_duplex_geometry_verified():
    result = convert(["examples/IfcOpenShell-Duplex.ifc"])
    assert result["mapping_status"] == "MAPPING_VERIFIED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_geometry_export_investigation.py::test_duplex_geometry_verified -v`
Expected: FAIL (REJECTED: self-intersecting solid)

- [ ] **Step 3: Fix self-intersect/unsupported paths in `ifc_to_fds/geometry/engine.py`**

Chỉ sửa pipeline, không sửa file IFC mẫu. Nếu mẫu sai thật: document + đổi golden trong test.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_geometry_export_investigation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ifc_to_fds/geometry tests/test_geometry_export_investigation.py
git commit -m "fix: remediate Duplex self-intersecting geometry"
```

### Task 3: Scenario emitter (REAC/RAMP/DEVC/CTRL)

**Files:**
- Create: `ifc_to_fds/fire/scenario_emitter.py`
- Test: `tests/test_fire_scenario_emitter.py`

**Interfaces:**
- Consumes: `load_ev_preset` (Task 1), `MappingPlan`, verified `bundle_sha256`.
- Produces: `emit_fire_scenario(mapping_plan, bundle_sha256, ev_selections, opening_states) -> ScenarioBundle` (fds_fragment: `&REAC/&RAMP/&BURN/&DEVC/&CTRL`; gắn `ev_library_version`).

- [ ] **Step 1: Write the failing test**

```python
def test_emitter_rejects_unverified_bundle():
    with pytest.raises(ValueError, match="MAPPING_VERIFIED"):
        emit_fire_scenario(plan, bundle_sha256="stale", ev_selections=[...], opening_states={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fire_scenario_emitter.py -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Implement `emit_fire_scenario` in `ifc_to_fds/fire/scenario_emitter.py`**

Từ chối bundle chưa VERIFIED (ValueError). Sinh REAC/RAMP theo preset + vị trí đỗ; DEVC/CTRL theo devices; opening_states CLOSED/OPEN + eventTime.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fire_scenario_emitter.py -v`
Expected: PASS (kèm test REAC/RAMP chứa peak theo preset)

- [ ] **Step 5: Commit**

```bash
git add ifc_to_fds/fire/scenario_emitter.py tests/test_fire_scenario_emitter.py
git commit -m "feat: add EV fire scenario emitter"
```

### Task 4: Mesh gate + solver wiring

**Files:**
- Create: `ifc_to_fds/validation/checkers/mesh_resolution.py` (`MeshResolutionChecker` theo pattern checker hiện có: `check(self, context, parsed=None)`)
- Modify: `ifc_to_fds/validation/runner.py` (đăng ký vào `_default_checkers`)
- Test: `tests/test_fire_mesh_gate.py`

**Interfaces:**
- Consumes: `ScenarioBundle` (Task 3).
- Produces: `check_mesh_resolution(scenario) -> GateResult` (PASS khi $4 \le D^*/\Delta x \le 16$ cho mọi nguồn, else FAIL/INCONCLUSIVE → chặn solver).

- [ ] **Step 1: Write the failing test**

```python
def test_mesh_gate_blocks_coarse_cell():
    res = check_mesh_resolution(scenario_7mw, cell_size=0.5)
    assert res.status != GateStatus.PASS  # D*/dx < 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fire_mesh_gate.py -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Implement `check_mesh_resolution` + $D^*$ từ HRR**

$D^* = (Q/(ρ·cp·T·√g))^{2/5}$; cài FDS qua `scripts/install-fds.py`; bật solver/effective gates.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fire_mesh_gate.py tests/test_solver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ifc_to_fds/fire/mesh_gate.py ifc_to_fds/validation tests/test_fire_mesh_gate.py
git commit -m "feat: add mesh resolution gate for fire scenarios"
```

### Task 5: UI matrix + batch queue + báo cáo gộp

**Files:**
- Create: `js/workbench/panels/ev-scenario-panel.js` (theo pattern panel hiện có)
- Modify: `js/verified-workflow.js` (gọi cancel/queue hiện có), `index.html` (mount panel)
- Test: `scripts/test-ev-scenario-panel.js` (node harness theo pattern `test-artifact-viewer.js`)

**Interfaces:**
- Consumes: `ScenarioStore` (A3 status), JobService `POST /api/jobs`, checkpoint API.
- Produces: panel sinh N scenario JSON → queue N jobs → bảng verdict + báo cáo gộp (ghi giả định + thẩm định).

- [ ] **Step 1: Write the failing harness assertion**

```js
// panel sinh 3 scenario từ matrix 2x2 clamp còn 3 hợp lệ, mỗi cái có ev_library_version + confidence
assert(scenarios.length === 3 && scenarios.every(s => s.ev_library_version));
```

- [ ] **Step 2: Run harness to verify it fails**

Run: `node scripts/test-ev-scenario-panel.js`
Expected: FAIL (file/panel chưa tồn tại)

- [ ] **Step 3: Implement panel + wiring tối thiểu**

Ma trận (số xe, khoảng cách, SoC, % chemistry, cửa/thông gió) → scenario JSON → queue; STALE mapping chặn seal (dùng `isSimulationPermitted()`).

- [ ] **Step 4: Run harness to verify it passes**

Run: `node scripts/test-ev-scenario-panel.js && node scripts/test-ui-recovery.js`
Expected: PASS cả hai

- [ ] **Step 5: Commit**

```bash
git add js/workbench/panels/ev-scenario-panel.js js/verified-workflow.js index.html scripts/test-ev-scenario-panel.js
git commit -m "feat: add EV scenario matrix panel and batch queue"
```
