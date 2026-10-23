# Kế hoạch refactor theo module và tách giao diện IFCtoFDS

Ngày rà soát: 22/10/2026. Mã nguồn tham chiếu: nhánh `chore/research-acceptance-hardening`, commit `f0c6d9c02342312266f2cfb8f9102833640061c3`.

Phạm vi công việc lần này là phân tích và lập kế hoạch. Chưa di chuyển hoặc sửa mã sản phẩm. Đề xuất dưới đây dựa trên mã hiện tại, không coi cấu trúc mục tiêu trong các tài liệu cũ là cấu trúc đã triển khai.

## 1. Quyết định kiến trúc

Tiếp tục **modular monolith**, tổ chức triển khai theo chức năng và áp dụng ports/adapters tại ranh giới cần thay thế hoặc kiểm thử. Giao diện có thư mục `frontend/` riêng, tổ chức theo feature và component; backend tiếp tục là package `ifc_to_fds`.

Mỗi module có chủ sở hữu trách nhiệm, API công khai, hợp đồng dữ liệu và kiểm thử riêng. Các module vẫn được phát hành cùng nhau trong một ứng dụng. “Phát triển riêng” ở giai đoạn này nghĩa là có thể thay đổi và kiểm thử một chức năng qua hợp đồng ổn định; chưa có yêu cầu phát hành từng module thành wheel riêng hoặc triển khai thành dịch vụ riêng.

Giữ nguyên mô hình dữ liệu Pydantic, thuật toán hình học, chiến lược OBST/GEOM, quy tắc openings, tọa độ, định danh, trạng thái nghiệm thu và luồng job hiện tại. Việc đổi framework giao diện, chuyển sang ES modules, thay thư viện hình học hoặc đổi mô hình dữ liệu phải được đánh giá thành công việc khác.

## 2. Hiện trạng đã kiểm chứng

Số dòng dưới đây là tổng dòng vật lý của tệp, không loại dòng trống hoặc bình luận.

| Khu vực | Bằng chứng hiện tại | Hệ quả đối với kế hoạch |
| --- | --- | --- |
| Điều khiển giao diện | `js/app-controller.js`: 1.759 dòng; chứa state, khởi tạo, khoảng 75 vị trí đăng ký event, import, export, API, UI và lịch sử thao tác | Tách theo luồng và quyền sở hữu state trước khi giảm kích thước tệp |
| Viewer | `js/viewer/scene-viewer.js`: 2.087 dòng; chứa dựng cảnh, camera, walk, clipping, picking, tải artifact và truy cập DOM | Phân rã theo trách nhiệm, giữ `SceneViewer` làm facade trong thời gian chuyển tiếp |
| IFC JavaScript | `js/ifc/ifc-adapter.js`: 2.030 dòng; có STEP parser, transform, units, openings, triangulation và worker sharding | Tách nội bộ engine legacy sau khi đóng băng đầu ra; không thay bằng pipeline Python |
| FDS JavaScript | `js/fds/fds-exporter.js`: 1.416 dòng; quyết định biểu diễn, voxelization, openings, ID và serialization | Giữ thứ tự phát sinh namelist, allocator ID và độ chính xác số khi tách |
| HTML/CSS | `index.html`: 810 dòng và 43 script tags; `css/app.css`: 1.154 dòng | Gom về frontend rồi tách layout/component/style theo từng vùng |
| State | Controller có object `state` riêng; workbench có selection/visibility/scenario stores; `ui/StateStore` có định nghĩa nhưng chưa tìm thấy nơi khởi tạo trong mã được Git theo dõi | Không tạo thêm store song song; lập bảng quyền sở hữu và di chuyển từng trường |
| Backend đã refactor | Có `domain/`, `application/`, `adapters/`, `bootstrap/`; `pipeline.py` hiện chỉ còn 79 dòng và là facade | Tiếp tục cấu trúc hiện có, không lập lại công việc đã hoàn tất |
| Ports chưa được nối | `IfcReaderPort`, `FdsExporterPort` mới được định nghĩa/re-export; use case vẫn gọi package cụ thể | Hoàn thiện chữ ký và adapter, sau đó inject qua bootstrap |
| Hợp đồng exporter lệch | Port khai báo nhiều tham số legacy nhưng thiếu `cell_size`; hàm thật nhận `model`, `cell_size`, `mapping_plan` | Đóng băng hợp đồng theo lời gọi thực tế trước khi nối port |
| Kiểm định song song | `AuditConversionUseCase` vẫn gọi `validation.engine.run_independent_validation`; có thêm `ValidationRunner` và checker riêng | Chưa được thay đường chạy chính chỉ vì runner đã tồn tại |
| Phạm vi parity | Test engine/runner hiện so trạng thái, các gate chung, element statuses và counters; chưa so toàn bộ evidence của workflow cuối | Bổ sung so sánh đầu ra đầy đủ trước khi chuyển đường kiểm định |
| HTTP | `server.py`: 445 dòng; gộp middleware, upload, cấu hình, route jobs/artifacts/preview và phục vụ static | Tách router và app factory, giữ URL, status code, giới hạn và lifecycle |
| Tương thích đường dẫn | Worker dùng `importScripts`, factory dùng `document.currentScript.src`; web-ifc có đường dẫn `./js/vendor/web-ifc/`; scripts/tests/CI đọc tệp theo đường dẫn cố định | Di chuyển frontend phải bao gồm server, worker generators, WASM, tests và CI trong cùng thay đổi |

Tài liệu `ARCHITECTURE_MODULARIZATION_BLUEPRINT.md` mô tả một commit cũ và đề xuất đổi Pydantic sang dataclass. Trong khi đó, quy tắc dependency hiện tại cho phép Pydantic và kiểm thử đang dựa trên API của nó. Không đưa việc đổi Pydantic vào lần refactor bảo toàn hành vi này. Ngưỡng 200–300 dòng cũng chỉ nên dùng làm tín hiệu xem xét, không phải điều kiện bắt buộc để chia tệp.

## 3. Cấu trúc thư mục mục tiêu

Danh sách này mô tả đích đến. Không tạo trước hàng loạt thư mục trống; chỉ tạo khi di chuyển phần triển khai tương ứng.

```text
frontend/
  index.html
  guide.html
  src/
    app/                 # Khởi tạo, ghép feature, đăng ký và hủy đăng ký
    components/          # Button, Modal, Tabs, Progress, StatusBadge...
    features/
      sources/           # Chọn IFC/FDS, inventory, federation inputs
      preview/           # Điều phối preview nguồn và geometry loading
      conversion/        # Hai workflow verified và quick hiện có
      scope/             # Storey, bounding box, simulation domain
      model-tree/        # Cây mô hình, lọc và nhóm
      inspector/         # Danh tính, mapping, hình học, MEP
      audit/             # Báo cáo, gate, findings và evidence
      artifacts/         # Tải FDS, manifest, ZIP và checkpoint
      scenario/          # Trạng thái scenario đã có; không thêm vật lý mới
    viewer/              # Dựng cảnh và tương tác Three.js
    state/               # Project/conversion state và ghép các store hiện có
    commands/            # Hành động có undo/redo
    api/                 # HTTP client, auth headers, job/artifact APIs
    engines/legacy/      # IFC parser, FDS parser/exporter của quick path
    workers/             # Worker entry, factory và message contract
    shared/              # Entity identity, diagnostics, helpers thuần
  styles/
    tokens.css
    base.css
    layout.css
    components/
    features/
    guide.css
  vendor/                # Three.js, controls, web-ifc, WASM và giấy phép
  generated/             # Inline worker bundles; chỉ sinh từ mã nguồn
ifc_to_fds/
  domain/                # Giữ các model/value object/enum hiện tại
  application/           # Convert, audit, inspect, preview và output ports
  modules/
    sources/
    geometry/
    mep/
    mapping/
    fds/
    validation/
    reference/
    artifacts/
    jobs/
  interfaces/
    http/                # App factory, router, middleware và request schemas
    cli/
    worker/
  bootstrap/             # Nối adapter vào port, quản lý lifecycle
tests/
  architecture/
  contracts/
  modules/
  integration/
  browser/
  baseline/
```

Ở bước di chuyển đầu tiên, dùng `frontend/js/` và `frontend/css/` để giữ cấu trúc tương đối cũ. Chuyển dần sang `src/`, `styles/`, `vendor/` và `generated/` ở các bước sau. Không vừa di chuyển toàn bộ thư mục vừa phân rã tất cả engine.

Các model dùng chung trong `domain/` vẫn là một định nghĩa duy nhất. Module không tạo bản sao `CanonicalModel`, `MappingPlan`, `MappingManifest`, `AcceptanceReport` hoặc entity identity. Model chỉ phục vụ một module có thể chuyển vào module đó sau khi kiểm kê hết nơi sử dụng; giữ re-export ở import path cũ.

## 4. Ranh giới module backend

| Module | Sở hữu | API công khai dự kiến | Nguồn triển khai hiện tại |
| --- | --- | --- | --- |
| `sources` | Đọc inventory, units, placement, federation và nguồn gốc tệp | `load_sources`, `inspect_inventory` | `core/inventory.py`, `federation.py`, `placement.py`, `units.py` |
| `geometry` | Native geometry, boolean, quality, cache, geometry package và preview geometry | `extract_geometry`, `extract_reference_geometry`, `write_geometry_package` | `geometry/` |
| `mep` | Phân loại HVAC/PCCC, systems, ports, connections và so sánh mạng | `extract_network`, `compare_networks` | `mep/`, các model trong `domain/mep/` |
| `mapping` | Spatial scope, simulation domain, simulation role, boundary và mapping decisions | `prepare_scope`, `plan_mapping`, `build_mapping_plan` | `mapping/policy.py`, `scope.py`, `boundary.py`, `domain/mapping/plan.py` |
| `fds` | Serializer, parser, cú pháp namelist và serialization result | `serialize_fds`, `parse_fds` | `mapping/exporter.py`, `validation/parser.py` |
| `validation` | Checkers, evaluator, evidence và điều phối kiểm định | `validate_serialized_output` | `validation/engine.py`, `runner.py`, `checkers/`, metrics/effective |
| `reference` | Reference case, approval, integrity, intentional deltas và parity | `load_reference`, `evaluate_parity`, `create_candidate` | `validation/golden/`, `adapters/reference/` |
| `artifacts` | Artifact catalog, checkpoint, lưu/đọc bundle và checksum | `save_run_artifacts`, `read_artifact`, `list_checkpoints` | `adapters/storage/`, phần artifact của `results.py` và use case convert |
| `jobs` | Queue, state, timeout, cancel, subprocess và repository | `submit`, `status`, `cancel`, `result`, `close` | `adapters/jobs/`, `jobs.py` |

Đây là tên API thiết kế, không phải cam kết đổi chữ ký hiện tại ngay. Facade cũ tiếp tục nhận đầu vào và trả kết quả cũ trong giai đoạn chuyển tiếp.

Mỗi module thường có `api.py`, `contracts.py`, phần triển khai nội bộ và adapter nếu cần. Không bắt mọi module phải có đủ bốn tầng hoặc thêm repository cho các phép biến đổi thuần.

Workflow nhiều bước ở `application/`: đọc nguồn → hình học → scope/mapping → serialize → checkpoint → đọc nguồn độc lập để audit → reference parity → lưu kết quả. Các module trao đổi qua hợp đồng công khai; `bootstrap` chọn adapter. Module jobs nhận worker entry được inject; bản thân queue không import use case convert để tránh vòng phụ thuộc.

Các import path `ifc_to_fds.pipeline`, `ifc_to_fds.jobs`, `ifc_to_fds.server`, `core.canonical`, `mapping.exporter` và `validation.acceptance` được giữ bằng facade/re-export trong quá trình chuyển đổi. Chưa xóa chúng ở bước đầu.

## 5. Tách giao diện theo component và feature

Component dùng lại được chỉ nhận dữ liệu và callback: `mount(root, props)`, `update(props)`, `destroy()`. Khi `destroy`, component tháo listener và subscription do chính nó tạo. Giữ DOM ID/class hiện tại ở bước đầu để không thay hành vi và selector của kiểm thử.

Mỗi feature sở hữu phần UI chuyên biệt, controller, selector và state riêng nếu thật sự cần. Ví dụ `features/conversion/` có `conversion-controller.js`, `conversion-options-view.js`, `verified-workflow.js`, `quick-workflow.js`. Component dùng lại như progress bar nằm ở `components/`; form domain chỉ dùng tại feature scope nằm trong `features/scope/`.

| Phần hiện tại | Nơi chuyển đến | Trách nhiệm sau khi tách |
| --- | --- | --- |
| Khởi tạo và wiring trong `app-controller.js` | `src/app/bootstrap.js` | Tạo dependency, mount feature, nối sự kiện và cleanup |
| `finishIfcLoad`, import events, inventory | `features/sources/` và `features/preview/` | Giữ chính sách chọn backend preview/web-ifc/legacy và generation tokens |
| `exportVerified`, `verified-workflow.js` | `features/conversion/verified-workflow.js` | Submit, polling, hủy, hydrate kết quả; gọi API client |
| `ensureFullModel`, export worker, quick export | `features/conversion/quick-workflow.js` | Lazy parse, worker message, tiến độ, kết quả và cleanup |
| `domain-panel.js` và clip controls | `features/scope/` | Form scope/domain; gửi clipping command sang viewer |
| `workbench/inspector/*` | `features/inspector/` | Tái sử dụng controller/view đang có |
| `workbench/navigation/model-tree.js` | `features/model-tree/` | Cây, filter, grouping và selection commands |
| `audit-drawer.js`, `renderAuditReport` | `features/audit/` | Hiển thị status, gates, findings và evidence |
| Logic tải artifact ở nhiều tệp | `features/artifacts/` và `api/artifacts-api.js` | Tải theo job hiện hành, giữ auth, loại tệp và kiểm tra lỗi |
| Theme/help/credits và DOM cache | `app/` hoặc component tương ứng | Tách UI shell khỏi conversion workflow |

Không đổi toàn bộ sang React/Vue trong đợt này. JavaScript hiện tại đã có các thành phần tách được và hỗ trợ mở tệp trực tiếp. Chuyển thẳng sang ES modules hoặc nạp HTML partial bằng `fetch` có thể làm mất đường chạy `file://`; phải xử lý chế độ phân phối trước nếu muốn thay đổi sau này.

## 6. Quyền sở hữu state và tài nguyên

| State/tài nguyên | Chủ sở hữu mục tiêu | Quy tắc bảo toàn |
| --- | --- | --- |
| IFC/FDS đang mở, tên tệp, source ID | Project/session state | Một chủ sở hữu, không clone toàn bộ mesh khi phát sự kiện |
| Job ID, request ID, generation, busy/progress | Workflow conversion hoặc preview | Kết quả cũ không được ghi đè lượt mới; giữ quy tắc cancel hiện tại |
| Selection, visibility, scenario | Các store workbench hiện tại | Giữ identity theo nguồn, giữ semantics của reset và undo |
| Delete/voxelize history và command history | Mỗi nhóm giữ chủ sở hữu hiện tại lúc tách | Bảo toàn từng loại undo; chỉ hợp nhất sau khi có test cho interleaving |
| Camera, controls, scene, renderer | Viewer runtime | Không đưa object Three.js hoặc frame state vào store UI |
| Report, manifest, artifact links | Kết quả của job hiện hành | Đổi source/job phải xóa dữ liệu cũ theo hành vi đã kiểm thử |
| Worker, Object URL, AbortController, listeners | Module/component tạo ra | Có `cancel`/`dispose`/`destroy`; giải phóng khi hủy, đổi nguồn hoặc đóng |

Không biến `StateStore` đang chưa dùng thành kho chứa mọi trạng thái chỉ để có một global store. Chuyển từng nhóm trường từ controller về đúng chủ sở hữu, giữ adapter tương thích cho phần chưa chuyển.

## 7. Phân rã viewer và engine legacy

Giữ API của `SceneViewer` trong giai đoạn đầu, ủy quyền dần cho `scene-runtime`, `camera-controller`, `walk-controller`, `clipping-controller`, `picking-controller`, `selection-renderer`, `visibility-controller`, `mesh-factory` và `resource-disposer`. Geometry/artifact loader thuộc feature preview hoặc lớp API; viewer nhận dữ liệu hình học đã giải mã. Đường render không tự đọc nút DOM hoặc biết endpoint job.

Giữ nhịp `requestAnimationFrame` trong viewer; không render lại cây mô hình/inspector trên mỗi frame. Ràng buộc viewport và tọa độ IFC ↔ Three.js phải giữ nguyên.

IFC legacy được tách thành STEP parser, metadata/units/placement, representations, openings và mesh utilities. FDS legacy được tách thành policy hiện có, OBST/voxel/GEOM emitters, ID allocator và serializer. Đây là tách mã cũ, không hợp nhất thuật toán của JavaScript với verified backend.

Workers dùng một nguồn mã duy nhất. Inline bundles vẫn được sinh bằng generator; không sửa nội dung bundle bằng tay. Giữ message type, request ID, progress, error stage/stack và kết quả như hiện tại.

## 8. Luật dependency và đóng gói

1. `interfaces` gọi `application`; không đặt quyết định mapping hoặc acceptance trong route/CLI.
2. `application` phụ thuộc domain và output ports; implementation được nối ở `bootstrap`.
3. Module khác chỉ sử dụng `api.py`/contracts công khai của module, không import helper nội bộ. Cho phép phụ thuộc trực tiếp khi có hướng rõ và không tạo cycle; không dùng event bus cho mọi lời gọi đồng bộ.
4. `domain` không import HTTP, subprocess, filesystem adapter, IfcOpenShell hoặc giao diện. Giữ Pydantic theo quy tắc hiện tại.
5. `sources` và `geometry` được ghép bằng workflow/port; tránh để federation import geometry rồi geometry import ngược sources.
6. Backend cung cấp verified mapping; quick path giữ vai trò legacy hiện tại. Nút UI và trạng thái report phải phân biệt được hai đường chạy.
7. `frontend/api/` sở hữu transport và auth; feature quyết định flow; component chỉ hiển thị; viewer chỉ dựng và tương tác cảnh.
8. Khai báo dependency/import rules bằng kiểm thử kiến trúc, kiểm tra cycle và quy tắc cấm truy cập module nội bộ. Giới hạn ngoại lệ chuyển tiếp bằng danh sách cụ thể có bước gỡ bỏ.

Backend tiếp tục một `pyproject.toml` và một wheel; module là Python subpackage. Frontend có manifest tài nguyên và cách phân phối riêng. Chỉ thêm bundler nếu một nhu cầu cụ thể được chứng minh và đã có phương án tương thích `file://`; folder riêng không bắt buộc framework hoặc build server mới.

## 9. Lộ trình theo thay đổi có thể review riêng

| Bước | Thay đổi | Điều kiện hoàn tất | Rủi ro |
| --- | --- | --- | --- |
| R0 — Chốt chuẩn so sánh | Ghi commit, cấu hình, fixture hashes, API/CLI/artifact schemas, các thao tác UI và phép đo hiệu năng đại diện | Phân biệt phần tất định với thời gian/path; có kết quả trước refactor; không tự cập nhật snapshot khi fail | Thấp |
| R1 — Gom frontend | Chuyển cơ học sang `frontend/js`, `frontend/css`, HTML; cập nhật server, worker paths, generators, WASM, scripts và CI | Mở `/`, `/index.html`, `/guide.html`, static server và double-click từ root đều được; workers/WASM tải được | Vừa |
| R2 — Tách UI | Rút shell, modal, tabs, progress, audit, inspector, scope và tree; giữ CSS/DOM/handler semantics | Giao diện và tương tác tương đương; mount/destroy không nhân listener; controller giảm đúng trách nhiệm | Vừa |
| R3 — Tách workflow/state/API | Rút sources, preview, verified/quick conversion, artifact client; chuyển từng nhóm state | Hủy A rồi chạy B không bị A ghi đè; đổi file không giữ report cũ; auth và cleanup giữ nguyên | Cao |
| R4 — Tách viewer và legacy engines | Tách lần lượt camera/walk/clipping/picking/loaders, sau đó parser/exporter; mỗi nhóm là một PR nhỏ | So cảnh, ray/opening checks, identity, undo/redo và FDS output; worker thường và inline tương đương | Cao |
| R5 — Tách HTTP và nối ports | App factory/router, cấu hình, upload; sửa hợp đồng port theo lời gọi thật; inject concrete adapters | API/CLI/job/artifact contracts giữ nguyên; không tạo subprocess khi chỉ import module; shutdown đóng manager đúng | Vừa |
| R6 — Đóng gói module backend | Di chuyển từng cụm vào `modules/`, giữ facade/re-export; storage checkpoint qua port; domain model giữ ổn định | Unit/contract/integration tests từng module đạt; import graph không cycle mới; package cài và chạy được | Vừa |
| R7 — Hợp nhất đường kiểm định | Mở rộng parity, chuyển từng gate đã chứng minh tương đương; sau cùng mới thay engine chính | Cùng findings/evidence/status và toàn bộ kết quả audit; nguồn được đọc độc lập; không mất gate mới | Cao |
| R8 — Hoàn thiện phân phối | Kiểm tra frontend/backend package, smoke tests từ thư mục phân phối sạch, cập nhật tài liệu và CI | Không phụ thuộc file chỉ có trong checkout; alias còn cần vẫn hoạt động; reference case giữ integrity | Vừa |

Thứ tự ưu tiên là R0 → R1 → R2 → R3. Có thể hoàn thành các bước giao diện trước khi làm sâu R6–R7. Không gom toàn bộ lộ trình vào một PR. Lỗi nghiệp vụ phát hiện trong lúc tách được ghi và sửa bằng thay đổi riêng để phân biệt với sai lệch do refactor.

Tại R1, các entry ở root phải tiếp tục mở được ứng dụng: server trả HTML từ frontend cho URL cũ; chế độ mở tệp có launcher tương thích đến HTML mới, kiểm tra riêng lịch sử điều hướng và đường dẫn asset. Chỉ phục vụ thư mục frontend và các asset được phép, không mount cả repository ra HTTP. Cần kiểm tra path có khoảng trắng trên Windows và giữ giấy phép vendor.

## 10. Tiêu chí giữ nguyên logic

* Cùng IFC + cấu hình → cùng quyết định scope/mapping, ID/provenance, danh sách đối tượng và biểu diễn FDS. Phần FDS tất định cần so hash hoặc nội dung chính xác; nếu phải normalize thì chỉ normalize trường không thuộc hợp đồng và có danh sách rõ ràng.
* Giữ số lượng và thứ tự OBST/HOLE/closure khi thứ tự có ý nghĩa; giữ GEOM vertices/faces, bounds, openings và sai số số học hiện tại. Không đổi seed, rounding hoặc allocator ID trong lần tách mã.
* Manifest/report/inventory/MEP/artifact schemas, checksum, bundle sealing và trạng thái `NOT_RUN`/`INCONCLUSIVE`/`REJECTED`/verified giữ semantics hiện có.
* Audit mở lại IFC nguồn và kiểm tra FDS/package đã serialize. Không dùng lại model/cache đã được converter sửa để chứng minh chính kết quả của converter.
* Selection theo nguồn, Focus/Back, Hide/Show, Isolate/Unisolate, global restore, undo/redo, clipping, đi bộ và đổi mode vẫn hoạt động tương đương.
* Upload, queue full, cancel, timeout, retry/error, generation token, auth headers, checkpoint và download giữ contract. Không coi việc tạo FDS thành công là đã mapping verified.
* Kiểm tra HTTP và `file://` riêng. Việc một đường chạy qua HTTP thành công không chứng minh worker inline hoặc WASM hoạt động ở chế độ mở tệp.
* Đo cùng fixture, máy, cấu hình, cold/warm cache và số lần chạy: thời gian preview/export, peak RAM, phản hồi UI và số tài nguyên giữ lại sau hủy. Chốt ngân sách sai lệch trước PR; không hứa cải thiện hiệu năng chỉ từ di chuyển thư mục.

Các gates cần chạy theo phần thay đổi: Python architecture/domain/contracts/baseline; JavaScript workflow, artifacts, worker parity và UI recovery; browser thực cho viewer/paths; solver và mô hình lớn khi thay đổi chạm serialization, hình học hoặc validation. Không sửa snapshot/fixture chuẩn để làm xanh một thay đổi chưa giải thích được.

## 11. Kiểm tra đã chạy trong lần lập kế hoạch

* Python: **67 passed, 1 deselected** trên 7 tệp test kiến trúc, cải tiến, post-refactor, engine parity, behavior baseline, workbench interaction và UI recovery/performance. Có 22 cảnh báo tính toán từ trimesh; đây không phải xác nhận đã giải quyết nguyên nhân các cảnh báo.
* JavaScript: **9 script đạt**: worker bundle parity, UI recovery, workbench stabilization, golden workflow, artifact viewer, verified regressions, background export worker, artifact downloads và legacy GEOM compatibility.
* Lượt Python đầu vướng quyền thư mục tạm của môi trường. Chạy lại với TEMP/TMP và pytest basetemp nằm trong workspace đã đạt; không tính lỗi quyền ban đầu là lỗi sản phẩm.
* Chưa chạy toàn bộ suite, browser thật, solver hoặc nghiệm thu mô hình tầng hầm lớn trong lần lập kế hoạch này. Các kết quả trên chỉ làm chuẩn ban đầu cho phạm vi đã chọn.

## 12. Nguồn tham chiếu kỹ thuật

* FastAPI hỗ trợ tách endpoint theo `APIRouter`, ghép trong ứng dụng chính: https://fastapi.tiangolo.com/tutorial/bigger-applications/
* MDN mô tả giới hạn chạy JavaScript modules qua `file://`: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules

Lựa chọn modular monolith, thứ tự di chuyển và ranh giới module là đề xuất kỹ thuật dựa trên repository được rà soát, không phải yêu cầu bắt buộc từ các tài liệu tham chiếu này.
