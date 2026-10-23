# 13 — Review và kế hoạch tổ chức thư mục, mã nguồn

Ngày: 22/10/2026. Branch: `chore/research-acceptance-hardening`. HEAD: `f0c6d9c02342312266f2cfb8f9102833640061c3`.

**Trạng thái lúc lập tài liệu: kế hoạch. Hiện đã triển khai trong working tree; xem [báo cáo 14](14-ket-qua-to-chuc-ma.md).** Mô tả “hiện tại”, PLANNED và tiêu chí bên dưới giữ bối cảnh trước triển khai; manifest và tài liệu 01–10 phản ánh kết quả mới. Phạm vi review là working tree sau đợt refactor trong tài liệu 12, gồm cả các file chưa được Git theo dõi. Không dùng riêng HEAD để mô tả cấu trúc hiện tại. Các thay đổi có sẵn được giữ nguyên; chưa commit/push.

## 1. Kết luận

Giữ Modular Monolith, tổ chức theo module trước và theo trách nhiệm bên trong module. Áp dụng public API, hợp đồng, ports, adapter và composition root có kiểm tra tự động. Bổ sung ownership, thay vì chỉ đổi tên thư mục.

Đợt trước đã hoàn thành phần gom implementation vào 8 module và tách frontend. Đợt này cần làm rõ phần bên trong: mã nghiệp vụ, điều phối, kernel hình học, đọc IFC, SQLite, filesystem và solver. Không cần thay framework hoặc chuyển sang microservices.

Domain model dùng chung là ngoại lệ có chủ đích trong phạm vi này. `CanonicalModel` hiện chứa cả trường nguồn, mapping và verification; không thể biến các context thành mô hình độc lập chỉ bằng việc chuyển file. Giữ một định nghĩa Pydantic và schema hiện tại, ghi owner cho từng model/nhóm trường. Việc thay mô hình hoặc chuyển nơi định nghĩa lớp là một thay đổi riêng, cần kiểm tra schema và worker Windows.

## 2. Phạm vi đã kiểm tra

- Kiểm kê bằng AST các file Python trong backend và các file JavaScript ứng dụng: `modules/` có 75 file Python, `domain/` có 22 file, `frontend/src/` có 67 file JavaScript. Đây là số file, bao gồm các file `__init__.py`, không phải số module nghiệp vụ.
- Đọc API/contracts của module, container, use cases, model preparer, đại diện source ingestion, geometry, jobs, reference, artifacts, HTTP và frontend wiring.
- Đọc kiểm tra kiến trúc và CI; đối chiếu báo cáo kiểm tra lần trước. Không chạy lại toàn bộ audit chức năng hay benchmark IFC lớn trong lượt review này.
- Đọc tài liệu kiến trúc/README của 5 repo tham khảo, cùng `.importlinter` của repo FastAPI. Không chạy hoặc chứng nhận chất lượng toàn bộ các repo đó.
- Chạy mới: **33 test Python kiến trúc/contract đạt**, 1 cảnh báo trimesh; `test-modular-frontend.js` và `test-worker-bundle-parity.js` đạt. Bằng chứng cục bộ: `.cache/layout-review-tests.xml`.

## 3. Tham khảo có chọn lọc

| Repo | Phần đã đối chiếu | Áp dụng cho IFCtoFDS | Giới hạn áp dụng |
| --- | --- | --- | --- |
| [kgrzybek/modular-monolith-with-ddd](https://github.com/kgrzybek/modular-monolith-with-ddd) | README, module-level architecture | Module có domain/application/infrastructure theo nhu cầu; public contract; composition root; tài liệu quyết định | Không bắt mọi giao tiếp qua event bus, không tạo IoC container riêng cho từng module |
| [deadislove/fastapi-modular-monolith-template](https://github.com/deadislove/fastapi-modular-monolith-template) | `docs/architecture.md`, `.importlinter` | Public/private surface, rule import có kiểm tra CI, README từng module và checklist tạo module | Không sao chép SQLAlchemy models qua boundary hoặc đổi toàn bộ API sang Result pattern |
| [xsreality/spring-modulith-with-ddd](https://github.com/xsreality/spring-modulith-with-ddd) | README và mô tả các nhánh cải tiến | Di chuyển từng module; giữ contract để caller không cần sửa theo nội bộ | Không đưa Spring hoặc cơ chế eventual consistency vào pipeline chỉ để giống repo |
| [bxcodec/golang-ddd-modular-monolith-with-hexagonal](https://github.com/bxcodec/golang-ddd-modular-monolith-with-hexagonal) | README, ports/adapters và module factory | Port nhỏ theo consumer; bootstrap chọn implementation; giao tiếp đồng bộ qua interface | Không sao chép cú pháp/visibility `internal` của Go sang Python rồi coi là đã được cưỡng chế |
| [Sebastian-Iwanczyszyn/modular-monolith-with-ddd-nestjs](https://github.com/Sebastian-Iwanczyszyn/modular-monolith-with-ddd-nestjs) | README, domain/application/infrastructure và giới hạn demo | Phân biệt business rule, use case, adapter; tổ chức quanh capability | Không thêm RabbitMQ, CQRS bus hoặc Outbox khi chưa có yêu cầu |

Nguồn được đọc ngày 22/10/2026. Blob SHA để đối chiếu nội dung: kgrzybek README `c358cbb4ac6e4a3131cd06dd00f93dc4cf9feba9`; FastAPI architecture `784c8fb4b069baed52dc7c43dbd3b0eef32db38d`, `.importlinter` `b71a65c465e06cce220263961861ce40c87e856d`; Spring README `314d2b900ab066a57a0af8ef72a7fa0e85ec37f3`; Go README `838925c3c38bfa22d2aa3631de71f6dd7d0a7aab`; NestJS README `761c4a75026f2f88effdf660740f42011548a257`. Đây là SHA của file, không phải commit toàn repo.

Các repo trên chủ yếu cung cấp ví dụ backend. Thiết kế frontend bên dưới là đề xuất dựa trên mã IFCtoFDS, không phải cấu trúc frontend được chứng minh từ cả 5 repo.

## 4. Findings trên mã hiện tại

P1/P2 dưới đây là độ ưu tiên cải thiện kiến trúc; không phải kết luận về lỗ hổng hoặc mức nguy hiểm của mô hình cháy.

| ID | Ưu tiên | Bằng chứng | Tác động và hướng xử lý |
| --- | --- | --- | --- |
| F01 | P1 | `tests/test_module_boundaries.py` chỉ lập đồ thị từ imports tới `ifc_to_fds.modules.*`; bỏ qua các package cũ; không kiểm tra riêng các role trong module | Không bắt caller mới đi vòng qua facade cũ hoặc application mới import infrastructure cùng module. Bổ sung policy khai báo và registry ngoại lệ cụ thể |
| F02 | P1 | `modules/jobs/service.py` 403 dòng; constructor tạo `JobRepository`, thư mục, lock, thread primitives; cùng file quản lý subprocess và retention | Điều phối, persistence, process và filesystem gắn chặt. Tách ports/store/worker process/retention, giữ façade `JobService` và hành vi đồng bộ |
| F03 | P1 | `application/use_cases/audit_conversion.py` 280 dòng, trực tiếp tính nhiều gates, coverage MEP/scope, parity và finalization | Quy tắc acceptance nằm ngoài owner Verification/Reference. Tách bước đánh giá có thứ tự, giữ root use case điều phối và giữ engine đang chạy |
| F04 | P2 | `modules/bim/inventory.py` import IfcOpenShell và mở file; `modules/geometry/engine.py` import native kernel; `storage.py` đọc/ghi payload | Cấu trúc phẳng chưa chỉ ra phần I/O. Đưa vào infrastructure; thuật toán hình học thuần vào `algorithms/` |
| F05 | P2 | `modules/artifacts/workspace.py` import `application.dto.inventory.portable_inventory` | Storage phụ thuộc helper của workflow phía ngoài. Workflow chuẩn bị checkpoint payload; workspace chỉ lưu dữ liệu theo contract |
| F06 | P2 | `domain/bim/model.py` import scope, mapping enums, MEP; CanonicalElement có cả mapping và audit state; contracts chỉ re-export | Các context còn chia sẻ model mutable; không phải các domain model hoàn toàn độc lập. Ghi ownership và quyền mutate, giữ schema; không nhân bản mesh/model để tạo vẻ độc lập |
| F07 | P2 | `modules/verification/api.py` re-export cả metric của Geometry; Jobs API công bố repository cụ thể; Geometry API gom kernel, package và storage | API dùng được nhưng trách nhiệm/public surface chưa rõ. Phân loại supported API và compatibility export; caller mới dùng đúng owner |
| F08 | P2 | `frontend/src/app/app-controller.js` 1.121 dòng; `featureContext` chung cho quick/verified/source/scope/audit, nhiều callback quay lại controller | File đã nhỏ hơn trước nhưng wiring vẫn tập trung và phụ thuộc chéo bằng callback. Tách bootstrap, shell, workbench binding và inject dependency tối thiểu theo feature |
| F09 | P2 | Các viewer installer cùng sửa prototype và dùng state của SceneViewer | Việc chia file chưa làm mỗi phần độc lập. Ghi rõ runtime contract/lifecycle, kiểm tra dispose, không vội đổi toàn bộ sang class/component mới |
| F10 | P2 | Không có `modules/*/README.md`; test backend chủ yếu phẳng; helper AST được import từ một test khác | Khó xác định owner và thêm module đúng quy tắc. Thêm README, helper test riêng, nhóm tests theo phạm vi |
| F11 | P1 — gate nghiệm thu | Tài liệu 12 còn HTTP transport bị chặn, 3 assertion legacy lỗi sẵn, thiếu đối chứng hiệu năng IFC lớn | Không được lấy PASS kiến trúc làm PASS chức năng. Chốt baseline và bằng chứng tương ứng trước khi nghiệm thu đợt chuyển cấu trúc tiếp theo |

Các facade cũ và bundles sinh tự động không được tính là bản sao implementation để xóa tùy ý. Số dòng là dấu hiệu để review trách nhiệm, không phải ngưỡng pass/fail SOLID.

## 5. Cấu trúc mục tiêu của đợt này

### 5.1 Backend

| Đường dẫn | Vai trò và quy tắc |
| --- | --- |
| `ifc_to_fds/modules/<module>/api.py` | Cửa vào runtime công khai; tên hiện tại giữ ổn định, không đổi thành public_api chỉ để giống repo khác |
| `ifc_to_fds/modules/<module>/contracts.py` | Types, DTO và ports công khai cần qua boundary; không chạy I/O khi import |
| `ifc_to_fds/modules/<module>/domain/` | Quy tắc thuần do module sở hữu; chỉ tạo khi có nội dung thật |
| `ifc_to_fds/modules/<module>/application/` | Use cases và điều phối nội bộ; tiêu thụ ports và API module khác được phép |
| `ifc_to_fds/modules/<module>/application/ports.py` | Ports nội bộ theo consumer; chỉ tách thành package khi số contract cần tổ chức |
| `ifc_to_fds/modules/<module>/infrastructure/` | IfcOpenShell, SQLite, filesystem, subprocess và native adapters |
| `ifc_to_fds/modules/geometry/algorithms/` | Mesh/boolean/solid metrics; cho phép thư viện tính toán đã có, không tự mở file/process/network |
| `ifc_to_fds/modules/fds/parsing/` | Parser namelist độc lập từ text; không phụ thuộc serializer hoặc mapping decisions |
| `ifc_to_fds/modules/<module>/README.md` | Owner, supported API, dependency, dữ liệu mutable, tài nguyên, tests và cách thêm chức năng |
| `ifc_to_fds/application/workflows/` | Điều phối qua nhiều context: prepare, convert, audit, save; không tính lại policy của từng module |
| `ifc_to_fds/application/ports/` | Ports chỉ phục vụ workflow xuyên context; thống nhất cách đặt tên, không lồng thêm `output/` không cần thiết |
| `ifc_to_fds/interfaces/http/` | App, security, configuration, uploads và nhóm routes |
| `ifc_to_fds/interfaces/cli/`, `interfaces/worker/` | Delivery CLI/worker; entry cũ tiếp tục gọi vào đây |
| `ifc_to_fds/bootstrap/` | Composition root toàn ứng dụng, cấu hình và resource ownership; không được domain/application import ngược |
| `ifc_to_fds/runtime/` | Diagnostics/provenance dùng chung thực sự; không chứa mapping hoặc acceptance |
| `ifc_to_fds/domain/` | Nơi định nghĩa duy nhất của model/schema dùng chung trong đợt này; ownership được ghi cụ thể, chưa đổi import path của lớp |

Không tạo đủ bốn thư mục trong mọi module. Geometry là capability kỹ thuật, Jobs là runtime service; không ép chúng có aggregate giả. Module có thể chứa thuật toán thuần cùng library hiện có mà không cần port cho từng phép toán.

### 5.2 Quyết định với shared model

| Model/khái niệm | Owner nghĩa và vòng đời | Trạng thái trong đợt này |
| --- | --- | --- |
| SourceIdentity, SourceMetadata, CanonicalModel, MEPGraph | BIM | Giữ định nghĩa; công bố qua BIM contracts; ghi rõ các workflow cập nhật trường theo stage |
| SpatialScope, MappingPlan, MappingDecision, mapping enums | Simulation | Giữ định nghĩa; không chuyển qua lại sang BIM để né dependency cycle |
| MappingManifest | FDS quản lý format đầu ra, workflow/artifacts quản lý sealing/lưu | Giữ schema; document rõ các producer/mutator theo stage |
| AcceptanceReport, GateResult, Finding | Verification | Giữ tên gates, findings, thứ tự finalization và fail-safe NOT_RUN |
| GoldenReference, ReferenceParityResult | Reference | Giữ mô hình approval/integrity |
| BoundingBox, TriangleMesh, schema version | Contract hình học/schema dùng chung | Một định nghĩa; không tạo thêm một bản tại Geometry |

Phase P01 phải ghi bảng field ownership cho CanonicalElement: trường nguồn chỉ thay ở ingest; scope/mapping thay ở prepare; primitive IDs thuộc serialization; audit state thuộc model được đọc lại độc lập. Đối tượng vẫn mutable như hiện tại. Không tuyên bố enforced immutability khi chưa có cơ chế thực thi.

Chuyển model vào `modules/*/domain` chỉ được lập thành đợt sau khi có phương án cho dependency chéo, JSON Schema, serialization, import identity và multiprocessing/pickle trên Windows. Đây là công việc ngoài đợt di chuyển 51 implementation file, không phải tiêu chí bị bỏ quên.

### 5.3 Frontend

| Đường dẫn | Nội dung mục tiêu |
| --- | --- |
| `src/app/bootstrap.js` | Tạo dependencies, state và viewer; mount theo thứ tự; giữ teardown handle |
| `src/app/shell-controller.js` | Theme, mode, help/credits và bố cục; không export IFC hoặc polling job |
| `src/app/workbench-bindings.js` | Nối selection/visibility/events với viewer; unsubscribe khi destroy |
| `src/app/app-controller.js` | Entry tương thích tạm thời, gọi bootstrap; gỡ sau khi mọi harness đã đổi |
| `src/features/<feature>/index.js` | API khởi tạo của feature, nhận dependency nhỏ có JSDoc; chỉ thêm cho feature có caller bên ngoài |
| `src/features/sources/` | Nạp/đổi/reset nguồn và generation tokens |
| `src/features/conversion/` | Giữ quick và verified tách biệt; giữ worker, cancel, progress, failed checkpoint semantics |
| `src/features/artifacts/` | Quyết định tải gì của job hiện tại; bind/unbind nút download |
| `src/features/{preview,scope,model-tree,inspector,audit}/` | Giữ ownership hiện tại, bổ sung contract và cleanup |
| `src/components/` | UI dùng lại; chỉ nhận props/callback, không biết job endpoint |
| `src/api/{http-client,jobs-api,geometry-api,artifacts-api}.js` | Transport/auth; giữ URL và response contract, không quyết định acceptance |
| `src/viewer/` | Giữ API SceneViewer/installers; loader nhận geometry client đã inject, không tự biết job ID/URL |
| `src/state/` | Cùng session object và các workbench stores hiện tại; không tạo state phản chiếu |
| `styles/components/`, `styles/features/` | Đi cùng ownership UI; giữ cascade và kiểm tra manifest |
| `src/engines/legacy/`, `src/workers/`, `generated/`, `vendor/` | Giữ layout đã tách; cập nhật load order khi thêm app/feature scripts, không tách tiếp thuật toán trong đợt này |

Giữ IIFE, namespace và HTTP/file://. `index.js` là tên file API của feature, không hàm ý đã chuyển sang ES modules. Trước khi bỏ context chung, liệt kê dependency thật của từng factory; tests phải dựng được feature bằng bộ dependency tối thiểu, không dùng Proxy trả hàm giả cho mọi tên để che thiếu dependency.

### 5.4 Tests, scripts, docs

| Đường dẫn | Nội dung |
| --- | --- |
| `tests/architecture/` | Imports, allowed DAG, layer roles, compatibility registry, frontend boundaries |
| `tests/modules/<module>/` | Unit/integration của module, chỉ thêm cấp con khi có đủ tests cần phân nhóm |
| `tests/workflows/` | Convert/audit/artifact pipeline xuyên context |
| `tests/interfaces/http/` | Auth, upload, admission, polling, cancel và download qua ASGI/HTTP |
| `tests/compatibility/` | Import/module identity, entry CLI/server/worker, schema và snapshot contract |
| `tests/support/` | AST helpers và builders; test không import helper từ một test khác |
| `tests/baseline/`, `tests/browser/` | Giữ đường dẫn fixture/snapshot hiện có và browser assets; không di chuyển chỉ cho đồng đều |
| `scripts/` | Giữ các lệnh entry đang được CI/README gọi; không chuyển hàng loạt generator/harness trong cùng đợt backend |
| `scripts/test-support/` | Dùng loader chung cho viewer/engine; ghi rõ root resolution |
| `docs/architecture/decisions/` | Quyết định về boundaries/shared model/compatibility/load order; không viết lại lịch sử tài liệu 11–12 |

Các test đọc source bằng đường dẫn literal phải cập nhật có chủ đích. Test contract chỉ được thay nơi đọc file, không được giảm assertion hoặc đổi output chuẩn vì source đã chuyển.

## 6. Bản đồ di chuyển và tách trách nhiệm

[module-layout-migration.json](module-layout-migration.json) liệt kê **51 file implementation** thuộc 8 module, đường dẫn đích, phase và SHA-256 nội dung đã review. Trạng thái của tất cả entry là PLANNED. Đây không phải script rename hàng loạt. Nếu hash nguồn thay đổi, phải review lại entry trước khi di chuyển. Map không bao gồm mọi file mới cần tách ở bảng dưới.

| Nguồn hiện tại | Đích / thay đổi |
| --- | --- |
| `modules/bim/{inventory,placement,units}.py`, `mep/{classifier,mep_graph}.py` | `bim/infrastructure/ifc/`; `federation.py` thành `source_loader.py`; giữ native handles nội bộ |
| `modules/bim/preview.py` | `bim/infrastructure/ifc/preview.py`; tách service/port chỉ khi cần thay I/O; giữ bytes và chunk semantics |
| `modules/geometry/{mesh,boolean,metrics}.py` | `geometry/algorithms/`; giữ số học, tolerances và dependencies tính toán |
| `modules/geometry/{engine,cache,storage,preview_cache}.py` | Native extraction và cache/payload store trong infrastructure |
| `modules/geometry/package.py` | `application/package_service.py`; tách seal/checksum thuần và adapter đọc payload khi cần, tránh import qua lại với store |
| `modules/simulation/{policy,scope,boundary,plan_validation}.py` | Application policies; các rule thuần trích riêng vào domain sau khi có characterization; không dán nhãn domain cho file còn đọc filesystem |
| `modules/simulation/boundary.py::adapter_digest` | Binding implementation digest chuyển sang composition/infrastructure manifest; Simulation policy không phải biết đường dẫn solver/verification |
| `modules/fds/{serializer,manifest,parser}.py` | Application serializer/manifest và parser độc lập; giữ parser không import exporter |
| `modules/verification/{engine,runner,checkers}` | `application/`; checker có I/O không gọi là domain thuần; giữ engine active |
| `modules/verification/{solver,boundary_policy,boundary_fixtures}.py` | Adapter chạy FDS; application boundary acceptance/certification; tách đọc certificate khỏi đánh giá nội dung |
| `modules/reference/{gate,normalizer,integrity}.py` | Application parity/projections/integrity vì hiện có gọi API FDS/Geometry; trích rule thuần riêng, không ép cả file vào domain |
| `modules/reference/{bundle_io,repository}.py` | Infrastructure bundle/filesystem repository |
| `modules/artifacts/{repository,workspace}.py` | Infrastructure; thêm checkpoint payload contract để bỏ phụ thuộc helper workflow |
| `modules/jobs/{service,repository}.py` | Application service, SQLite adapter; thêm process port, process adapter và retention service |
| `application/use_cases/{convert_verified,audit_conversion,save_artifacts}.py` | `application/workflows/`, old paths làm alias; audit giữ điều phối, các rules được chuyển cho đúng owner theo thứ tự kiểm tra cũ |
| `application/services/model_preparer.py` | `application/workflows/prepare_model.py` vì phối hợp BIM + Simulation; vẫn inject reader |
| `application/use_cases/inspect_ifc.py` | Inject preparation/query dependency; không lấy `prepare_model` thông qua module audit |
| `application/use_cases/preview_model.py` | Giữ alias tương thích; delivery mới gọi BIM API hoặc query facade đã inject, không thêm một use case rỗng |
| `interfaces/http/routes.py` | `routes/{health,jobs,previews,artifacts,reference}.py`, `uploads.py`; giữ router factory và store_uploads compatibility |
| `cli.py` | Chuyển implementation vào `interfaces/cli/`; giữ `ifc_to_fds.cli:main` đã công bố trong pyproject |
| `results.py` | Tách reference registry về Reference, artifact metadata về Artifacts, presenter về HTTP; module cũ re-export đúng symbols |
| `core/canonical.py`, `core/compare.py`, `diagnostics.py` | Kiểm kê canonical/provenance/normalization; chỉ chuyển phần dùng chung thuần vào runtime/contract helper; không xóa cả core vì còn code thật và caller cũ |
| `adapters/{ifc,fds,validation}` | Sau khi bootstrap gọi module factory/ports: chuyển implementation adapter về module sở hữu hoặc giữ seam cross-context có lý do; old import không đổi identity |

Registry compatibility phải gồm cả các đường dẫn cũ trước đợt refactor và đường dẫn module phẳng vừa tạo. Alias đi thẳng tới implementation cuối, tránh chain nhiều tầng. Hash và certificate phải bind implementation thật, không bind file alias.

## 7. Quy tắc dependency và SOLID cần thực thi

1. External caller chỉ import `api.py` hoặc `contracts.py`. Bootstrap được phép import module factory; mọi ngoại lệ là đường dẫn/symbol cụ thể có owner và phase xóa.
2. Domain không import application, infrastructure, interfaces, bootstrap, IfcOpenShell, HTTP hay subprocess. Dùng model Pydantic hiện có và helper thuần được công bố; domain không gọi runtime API module khác để lén I/O.
3. Application nội bộ dùng ports và public API được phép; không tự tạo SQLite repository, native reader hoặc process runner.
4. Infrastructure được dùng contract/port mà nó implement; composition root nối implementation. Không để application import ngược bootstrap hoặc module API của chính nó để tạo vòng.
5. Giữ allowed module DAG hiện tại làm baseline: BIM→Geometry; Simulation→Geometry; FDS→Simulation/Geometry; Verification→FDS/Simulation/Geometry; Reference→FDS/Geometry; Artifacts→Geometry; Jobs độc lập. Thêm dependency cần quyết định và test, không chỉ kiểm tra không có cycle.
6. Tách đồ thị runtime và model-contract. Shared model đang cross-reference không được mô tả sai thành các context đã độc lập; việc một contract dùng BoundingBox không cho phép import filesystem store.
7. Giữ AST tests hiện có, mở rộng bằng policy manifest và các case chứng minh bắt được import sai. Nếu thêm import-linter: kiểm chứng với lazy exports, imports tương đối và aliases trước; cập nhật dependency + lockfile, không đưa checker thứ hai có rule khác vào CI.
8. Đổi adapter qua port phải giữ exception, cancellation, return type, side effect và resource ownership. Protocol có cùng tên phương thức chưa đủ chứng minh LSP.
9. OCP không bắt có plugin registry cho mọi hàm. Không thêm interface cho phép tính mesh thuần. Chỉ tách abstraction ở reader, store, worker process, solver và transport khi có consumer/test cần thay.
10. Frontend feature không fetch trực tiếp hoặc import nội bộ feature khác. UI components không gọi engine; viewer không điều phối workflow; app bootstrap không chứa mapping/acceptance.

Policy manifest dự kiến `docs/architecture/dependency-policy.json`; registry `docs/architecture/compatibility-imports.json`. Hai file này sẽ được tạo ở P01, chứa dữ liệu mà tests đọc; không tạo các file mẫu rỗng trong lượt lên kế hoạch.

| Nguyên tắc SOLID | Thay đổi cụ thể | Bằng chứng cần có |
| --- | --- | --- |
| SRP — một nhóm trách nhiệm | Tách Jobs điều phối/SQLite/process/retention; audit workflow và policy; frontend shell và conversion | Test phần điều phối không phải tạo DB/process thật; owner mỗi file rõ ràng |
| OCP — mở rộng tại điểm cần thay | Reader/store/solver/geometry client thay implementation qua port; engine toán học giữ hàm hiện có | Chạy cùng use case bằng adapter thật và fake có chủ đích, không sửa nội dung use case để đổi adapter |
| LSP — thay thế giữ hợp đồng | Giữ signature, trạng thái lỗi/hủy, return type và quyền sở hữu tài nguyên | Contract tests cho exporter, reader, job store, process runner; geometry/download behavior không đổi |
| ISP — interface theo consumer | Workflow port khác query inventory; frontend mỗi factory chỉ nhận phần nó dùng | Factory test dùng dependency object tối thiểu; không cần implement khả năng không liên quan |
| DIP — policy không khởi tạo hạ tầng | Bootstrap/factory nối adapter; application không tạo repository/process/native reader | Import rules cộng kiểm tra thay adapter; import app vẫn không mở DB/worker |

## 8. Kế hoạch triển khai theo nhóm thay đổi có thể review

Các nhóm dưới đây là thứ tự triển khai và review, không phải yêu cầu phải tạo commit trong phiên hiện tại. P00–P01 thực hiện trước; mỗi module chỉ chuyển sau khi gate liên quan đạt. Backend và frontend có thể làm ở các lượt riêng, không gom mọi rename vào một diff không thể kiểm tra.

| Phase | Công việc và đầu ra | Kiểm tra chốt | Phụ thuộc / rủi ro |
| --- | --- | --- | --- |
| P00 | Chụp trạng thái working tree, fixture hashes, API/CLI/schema, asset manifest; lập evidence baseline trên mã hiện tại; phân loại 3 lỗi tam giác; làm chạy HTTP transport ở môi trường phù hợp | Chạy đủ HTTP auth/upload/admission/poll/cancel/download; Verified browser từ upload đến artifacts; giữ kết quả legacy trước/sau | Ưu tiên cao nhất. Không sửa event loop sản phẩm chỉ để vượt sandbox. Nếu bị chặn, ghi BLOCKED và chưa nghiệm thu phần đó |
| P01 | Chốt ADR, ownership, API inventory, allowed DAG, compatibility registry; chuyển AST helper sang tests/support; rules kiểm tra role trong module và ngăn caller mới dùng facade | Rule bắt import sai ở domain/application, private module, facade bypass và edge không được phép; tất cả API resolve; không side effect khi import | Thấp; chưa di chuyển thuật toán. Không miễn cả package vĩnh viễn |
| P02 | Artifacts làm pilot: 2 file theo migration map; thêm CheckpointPayload contract; workflow chuẩn bị inventory/MEP/config; cập nhật bootstrap/API/alias | Artifact hashes, sealed/draft state, failed checkpoint, original filenames/source hashes; temp owner sống đủ lâu; old module identity | Vừa. Port signature nếu thay phải giữ adapter tương thích và so checkpoint trước/sau |
| P03 | Di chuyển BIM ingestion/preview/MEP theo map; reader port tại đúng consumer; loại native imports khỏi domain; inspect dùng dependency inject | Inventory/storeys/units/placement/federation/MEP/openings; preview chunk/batch/cache; auditor reopens source; không copy native handle ra contract | Cao. Không đổi extraction settings hoặc use converter cache cho independent audit |
| P04 | Geometry algorithms/native extraction/cache/store/package tách trách nhiệm; tách pure seal khỏi storage dependency nếu cần; giữ public names | Geometry/boolean/opening/alias/metrics/package tests; payload dtype, byte order, checksum, lazy reads; RAM/cancel smoke trên mẫu đại diện | Cao. Không materialize toàn bộ meshes để tạo DTO cho đẹp |
| P05 | Simulation/FDS theo map; tách digest binding khỏi rule; cập nhật đường dẫn implementation trong chứng nhận; giữ parser độc lập | MappingPlan không bị serializer ghi primitive IDs; OBST/GEOM/HOLE/order/IDs đúng; FDS parse lại; certificate cũ không được chấp nhận nhầm | Cao; phải chạy solver fixture lại khi digest implementation đổi |
| P06 | Verification/Reference theo map; từng nhóm rules audit chuyển khỏi root use case; đọc certificate và chạy solver qua ports; giữ active engine | So đầy đủ report/gates/findings/evidence/coverage, manifest sealing và parity. Kiểm tra mutation: thiếu nguồn, đổi mesh, bít opening, đổi output, corrupt reference | Rất cao. Giữ thứ tự finalization và ID findings; không chuyển sang runner mới trong phase này |
| P07 | Jobs có store/process/clock/retention seam cần thiết; SQLite và subprocess adapter; factory nối resources; giữ public constructor qua façade | Queue full, startup reconcile, timeout, cancel queued/running, process tree cleanup, concurrent download vs retention, durable artifacts | Cao. Giữ RLock/transaction semantics, giới hạn RAM và max_waiting; không thay threading bằng async architecture mới |
| P08 | Nhóm HTTP routes/uploads; CLI vào interfaces; application dùng workflows; results/diagnostics phân owner; dọn alias chain | OpenAPI exact equality gồm operation IDs; CLI help/exit; `python -m ...jobs`; auth, 413, filename/path, failed artifacts và headers | Vừa/cao. Thứ tự include_router có thể đổi operation IDs/route matching, phải so toàn schema |
| P09 | Frontend tách bootstrap/shell/workbench bindings, artifacts feature/API; thay context chung bằng object nhỏ; viewer nhận geometry client | Mount/destroy không nhân listener; cancel A/chạy B không bị A ghi đè; source reset; auth download; selection/focus/back/hide/isolate/undo/walk; HTTP và file:// | Cao. Giữ ID/class CSS, load order và callback semantics; không đổi framework |
| P10 | Nhóm tests theo owner và level, cập nhật paths/support/harness/CI/docs/AGENTS; build wheel/sdist cuối; benchmark đối chứng | Số test thu thập không mất do di chuyển; 13 JS regression; worker parity; browser/solver; installed wheel ngoài checkout; baseline parity 3 IFC và mẫu lớn | Vừa. Giữ fixture paths, entry scripts và notices; không bỏ test bị lỗi để làm pipeline xanh |

### Chi tiết P09 để tránh lặp lại một controller lớn

1. Lập bảng function→owner và dependency thật; khóa state/generation semantics bằng tests hiện có.
2. Tách shell/theme/help/credits và keyboard/view controls; không đổi hành vi navigation mode.
3. Tách workbench subscriptions, lưu unsubscribe handles; app destroy gọi theo thứ tự feature → subscription → worker/URL → viewer.
4. Tách download binding về artifacts feature; API chỉ gửi request và kiểm tra response, feature chọn đúng job hiện hành.
5. Tạo dependency object riêng cho quick, verified, sources, scope và audit; xóa callbacks không dùng, không sao chép state/mesh.
6. Viewer geometry loader nhận geometry client; engine/render methods không biết backend URL. Giữ request generation, abort signal và batch policy lớn/nhỏ.
7. Cập nhật HTML, manifest, workers/generators và test loaders cùng thay đổi; tái sinh bundles bằng generator, chạy parity LF/CRLF.
8. Ghi README feature/runtime contract. Chốt bằng hành vi và khả năng test độc lập; không áp một số dòng tùy ý cho mọi file.

### Nhịp thực hiện đề xuất

Lượt đầu: P00–P01 và pilot P02. Lượt hai: BIM/Geometry. Lượt ba: Simulation/FDS và Verification/Reference. Lượt bốn: Jobs/HTTP/workflows. Lượt năm: frontend, tổ chức tests và kiểm tra phân phối cuối. Mỗi lượt có thể tách nhỏ hơn theo kết quả baseline; chưa cam kết thời gian hoàn tất khi gate HTTP và dữ liệu IFC lớn chưa được xử lý.

## 9. Tiêu chí hoàn tất

- Cả 8 module có README, public API rõ, folder phản ánh trách nhiệm thật; không tạo thư mục/lớp rỗng để đạt hình thức.
- Không có imports mới qua facade cũ, private module hoặc direction bị cấm. Các export tương thích vẫn resolve và giữ module/cache identity.
- Model/schema/gates/source identity/FDS/artifacts giữ contract. Thời gian và paths chỉ normalize theo danh sách đã chốt.
- Root workflows điều phối, không giữ các rules đã xác định owner; infrastructure không gọi helper nghiệp vụ ở root application.
- Frontend bootstrap dựng từng feature bằng dependencies được khai báo; teardown có bằng chứng không giữ listener/worker/ObjectURL cũ.
- HTTP và file:// đều có kiểm tra thật; OpenAPI không đổi; Verified E2E upload→audit→download đạt.
- So inventory và FDS trên ba IFC công khai; fixture opening/MEP/federation, acceptance mutations và FDS solver đạt theo phạm vi.
- Đối chứng IFC nhỏ và IFC lớn cùng máy/config/cache; ghi preview/export time, peak RAM, cancel latency, tài nguyên còn lại. Chốt ngưỡng sai lệch từ baseline trước khi đánh giá, không tự đặt tỷ lệ rồi coi là nghiệm thu.
- Wheel/sdist chứa đủ assets và package con; chạy ngoài checkout. Baseline fixtures và vendor không thay; notices còn đủ.
- Báo riêng PASS, FAIL, BLOCKED, NOT_RUN. Ba lỗi tam giác không được đánh dấu pass hoặc thay số thiếu giải thích.

## 10. Rollback, dữ liệu và giới hạn

Trước mỗi phase lưu danh sách paths/hashes và patch của phase vào vùng tạm không bị ghi đè. Nếu gate fail, hoàn nguyên riêng thay đổi phase dựa trên patch và source hashes; giữ các thay đổi người dùng có trước. Không dùng reset/clean hoặc xóa cả thư mục đang có công việc khác. Không tạo thêm bản sao IFC/mesh lớn chỉ để checkpoint mã.

Tài liệu 12 là bằng chứng của đợt trước, không sửa thành đã PASS đợt này. Mỗi phase bổ sung evidence riêng. CI hiện khai báo matrix Python/Windows/Linux nhưng việc đọc workflow không chứng minh tất cả jobs đã chạy thành công.

Lúc lập tài liệu này chỉ tạo kế hoạch, migration manifest và cập nhật index; chưa áp dụng 51 file move. Kết quả triển khai sau đó nằm trong [báo cáo 14](14-ket-qua-to-chuc-ma.md) và trạng thái mới của manifest. Không thêm dependency import-linter, không chuyển nơi định nghĩa model Pydantic, chưa commit/push.
