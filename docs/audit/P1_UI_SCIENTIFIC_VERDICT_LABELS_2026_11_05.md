# Scientific verdict labels in the workbench — 05/11/2026

## Finding P1-SCI-UI

The summary status badge in `js/app-controller.js` previously grouped
`MAPPING_VERIFIED` and `SIMULATION_VERIFIED` into the same green label,
**VERIFIED**. Even though the current Python scientific pipeline does not
issue `SIMULATION_VERIFIED`, this display conflated BIM-to-FDS mapping
verification with the independent validation of CFD simulation physics.

## Correction

- `MAPPING_VERIFIED` displays **MAPPING VERIFIED**, identifying the
  precise level of proven evidence. The simulation field remains separate.
- The unsupported `SIMULATION_VERIFIED` label is **not** rendered as an
  approved green badge. It is presented as **CFD NOT VERIFIED** with an
  inconclusive visual state, pending a future scientific acceptance contract.
- The audit drawer does not echo a forged `SIMULATION_VERIFIED` status as
  accepted; displays a qualified INCONCLUSIVE marker instead.
- `INCONCLUSIVE`, `REJECTED`, and diagnostic failures keep their
  pre-existing classifications.
- No change to IFC geometry, FDS input, verification thresholds or stored
  scientific reports.

`scripts/test-verified-regressions.js` executes the actual status badge
function against a minimal DOM and checks mapping, unsupported simulation,
inconclusive, and rejected statuses. Existing JavaScript and browser CI
remain required. Additional E2E visual review with real mapping reports
and EV scenarios remains outstanding.

## Acceptance and limitations

This is **presentation-layer fail-closed protection**. It is not
independent physical verification or source evidence authentication.
The Python scientific contract review is tracked separately in PR #49.
G09/G10 remain INCONCLUSIVE until independent reference measurements,
solver convergence, uncertainty, validation of field quantities and
expert approval are documented. Release remains NOT_PRODUCTION_READY.


## P1-SCI-EV — Lỗi vận hành không phải từ chối khoa học

`classifyScenarioResult()` ở EV scenario panel trước đây trả `REJECTED`
cho HTTP 500, job FAILED, CANCELLED, TIMED_OUT hoặc một trường
`verdict=FAIL` được truyền vào mà không kèm evidence mesh/physics.

Chính sách mới:
- Job QUEUED/RUNNING/429: `QUEUED_WAITING` — chưa có scientific verdict.
- HTTP error, job FAILED/CANCELLED/TIMED_OUT, không lấy được result:
  `INCONCLUSIVE` — hệ thống **không biết** mô phỏng đạt hay không.
- Chỉ `mesh_status=FAIL` hoặc `physics_status=FAIL` trong trạng thái
  kết quả hoàn tất mới phân loại `REJECTED` của kịch bản.
- Chuỗi `verdict=FAIL` hay `SIMULATION_VERIFIED` đơn độc không cấp
  kết luận khoa học. `energy_budget_status=PASS` cũng không phải CFD.
- `scripts/test-ev-scenario-panel.js` bổ sung ca lỗi vận hành và
  verdict giả, đồng thời giữ test thất bại mesh/physics thật.

Giới hạn: UI không tự kiểm chứng chứng cứ CFD hoặc source IFC; API/persisted
result contract và evidence index tiếp tục là lớp tin cậy chính. Chưa có
scientific validation trên dữ liệu công trình thật. Không nâng G09/G10.
