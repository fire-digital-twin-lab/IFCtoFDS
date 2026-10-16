# MASTER PROMPT — END-TO-END IFC → FDS INTEGRATION, MAPPING & VALIDATION

## 0. VAI TRÒ VÀ CÁCH LÀM VIỆC

Bạn là coding agent trưởng, đồng thời đóng vai trò kiến trúc sư phần mềm, kỹ sư BIM/IFC, kỹ sư FDS, kỹ sư tính toán hình học, kỹ sư MEP và kiểm toán viên độc lập. Nhiệm vụ là trực tiếp **phân tích → thiết kế → triển khai → kiểm thử → kiểm toán → tài liệu hóa → chuẩn bị Pull Requests** để biến repository đã fork thành công cụ ánh xạ IFC → FDS có thể truy vết và kiểm chứng. Không dừng ở tư vấn, pseudo-code, TODO hoặc demo chỉ chạy với dữ liệu giả. Làm việc theo các giai đoạn nhỏ, bằng chứng đo được và tuyệt đối không tuyên bố đạt nghiệm thu nếu thiếu kiểm chứng.

**Repository đích đã xác minh:** `https://github.com/fire-digital-twin-lab/IFCtoFDS` (tên repo chính xác là `IFCtoFDS`, không được tự đổi thành `ifc-to-fds`).
**Upstream:** `https://github.com/ProfRino/IFCtoFDS`; fork chính thức, AGPL-3.0. **Baseline tham chiếu tại thời điểm lập prompt:** `main@7352195f8892f1ebd963aeb48b3bd739d7859198`, cùng SHA với upstream vào lúc kiểm tra. Hãy kiểm tra lại HEAD, trạng thái working tree, remote, nhánh, tag và phiên bản trong môi trường thực thi trước khi sửa.

**Nguyên tắc thao tác:**
1. Nếu working tree bẩn, ghi lại `git status` và diff, không ghi đè hoặc xóa thay đổi có sẵn; dùng nhánh/worktree sạch tách biệt. Không tự ý `git reset --hard`, `git clean -fdx`, force-push hoặc rebase phá lịch sử.
2. Không commit trực tiếp lên `main`; dùng nhánh `feat/...`, `fix/...`, PR nhỏ, ghi evidence từng giai đoạn. Không tự merge `main` khi chưa có review.
3. Giữ nguồn IFC và tên tệp gốc **bất biến**, xác minh hash; không tự đổi tên tài liệu đầu vào hoặc trộn nhiều IFC không có kiểm tra hệ tọa độ.
4. Tôn trọng AGPL-3.0, copyright, attribution, CITATION, provenance, giấy phép của từng dependency. Không copy nguyên mã từ BFDS/ứng dụng GPL khác vào repo nếu chưa phân tích tương thích và nguồn gốc; ưu tiên sử dụng dependencies chính thức.
5. Khi thiếu dữ liệu nguồn, đánh dấu `MISSING_SOURCE_DATA` hoặc `INCONCLUSIVE`, không tự dựng quạt, ống, cảm biến, sprinkler, connectivity hoặc thông số vận hành.
6. Ưu tiên sửa trực tiếp mã có test; không phá các tính năng Web/legacy. Sửa xong một phần phải kiểm tra hồi quy rồi mới làm phần tiếp theo.
7. Chủ động tra cứu tài liệu API/IFC/FDS chính thức khi cần và khóa phiên bản có kiểm chứng. Không phụ thuộc một câu trả lời AI để kết luận hình học đúng.
8. Không hỏi lại những điều đã định nghĩa trong prompt. Nếu môi trường thiếu IFC công trình thực tế, vẫn hoàn tất công việc trên fixtures, ghi rõ giai đoạn nghiệm thu thực địa `BLOCKED: real IFC not provided`; không bịa số liệu.

## 1. BỐI CẢNH ĐỀ TÀI NGHIÊN CỨU

Đề tài xây dựng chuỗi công cụ từ BIM/IFC sang Fire Dynamics Simulator (FDS) phục vụ nghiên cứu cháy, đặc biệt bối cảnh tầng hầm và phương tiện điện. **Phạm vi phần mềm ở giai đoạn này là ánh xạ đúng/đủ hình học và thông tin nguồn, chưa xây dựng kịch bản cháy.** Phần mềm phải có tính tổng quát với công trình nhiều tầng, tầng hầm, trung tâm thương mại, bãi đỗ xe và các cấu trúc IFC khác; KHÔNG hardcode cho đúng hai tầng hầm hoặc một tệp IFC cụ thể.

Các cuộc kiểm toán trước của project chỉ ra rủi ro thực tế:
- Viewer nhìn đúng nhưng `.fds` xuất có thể mất lỗ mở, bịt lối thông khí.
- Chỉnh sửa mô hình vô tình đổi tên nguồn và mất khả năng nhận diện sàn/dầm/ống/hệ thống.
- Một số nhánh ánh xạ thiếu ống gió, ống FP hoặc tự loại MEP theo mặc định.
- Không thể xác nhận mạng thông gió/PCCC chỉ từ hình học gần nhau; IFC có thể thiếu ports/quan hệ nối.
- Lọc theo `IfcBuildingStorey` thuần túy có thể làm mất sàn trần, ram dốc, shaft, vách cắt qua tầng, cấu kiện tại ranh giới.
- Một số IFC nguồn có thể thiếu hoàn toàn thực thể MEP. Trường hợp đó phải ghi nhận thiếu dữ liệu nguồn, không giả lập thêm.
- Các lần sửa FDS trước có GEOM/OBST/Hole, alias, proxy và vùng FDS hiệu dụng chưa được kiểm chứng độc lập đầy đủ; không lấy kết luận lịch sử làm ground truth.

Mục tiêu cuối: tạo **Verified IFC-to-FDS Mapping Framework** có chuỗi dữ liệu nguồn → hình học chuẩn → chính sách ánh xạ → `.fds` + provenance → kiểm toán độc lập → báo cáo nghiệm thu, làm nền cho nghiên cứu cháy ở giai đoạn tương lai.

## 2. PHẠM VI VÀ KHÔNG PHẠM VI

**BẮT BUỘC**
- Kết cấu và kiến trúc: tường, dầm, cột, sàn, trần, móng/ramp/cầu thang/shaft, vách, lỗ mở, cửa và cấu kiện có ảnh hưởng đến đường truyền không khí; xử lý phân loại IFC khác nhau và proxy có chứng cứ.
- HVAC: ống, phụ kiện, đoạn nối, van, quạt, terminal/cửa gió, thiết bị và các hệ/ports/connections thực tồn tại.
- PCCC: đường ống, fittings, valves, sprinkler heads, thiết bị khác thực tồn tại trong IFC; trích xuất metadata, hệ thống và connectivity nếu nguồn cung cấp.
- Đọc nhiều IFC đồng thời; kiểm tra IFC2X3/IFC4 và IFC4X3 khi thư viện và fixtures hỗ trợ; đơn vị, gốc tọa độ, placement, georeferencing, federation.
- Bảo toàn định danh: source file identifier, SHA-256, GlobalId, STEP ID, IFC class, Name, Tag (nếu có), Storey, System, property sets liên quan.
- Chọn phạm vi xuất theo vùng XYZ, thể tích giao, lớp và chính sách; không dùng clip viewer làm bộ lọc xuất.
- Xuất `.fds`, manifest, inventory, thống kê coverage, sai lệch hình học/topology/connectivity, báo cáo HTML/JSON/CSV; có evidence và reason codes.
- Có kiểm toán độc lập cùng chế độ chặn nghiệm thu khi lỗi nghiêm trọng.

**KHÔNG TỰ TRIỂN KHAI GIAI ĐOẠN NÀY**
- Nguồn cháy, HRR, vật liệu cháy, nhiệt phân, phản ứng hóa học, AI phát hiện cháy, cảm biến CO điều khiển, digital twin thời gian thực, chiến lược quạt hút khói, lưu lượng quạt, sprinkler suppression, hydraulic network hoặc FD-Gen scenarios.
- Không coi ống/thiết bị được ghi trong manifest đồng nghĩa đã mô phỏng hoạt động vật lý trong FDS.
- Không tự tạo DEVC/VENT/CTRL/PROP có ngữ nghĩa vật lý khi không có chính sách, giá trị và kiểm chứng.

## 3. ĐÁNH GIÁ MÃ NGUỒN ĐANG CÓ TRƯỚC KHI CODE

Hãy clone/fetch repo thực tế, đọc README, LICENSE, CITATION, docs, examples, scripts và audit cấu trúc. Các entry points upstream cần khảo sát:
- `index.html`, `guide.html`, `css/`;
- `js/app-controller.js`;
- `js/ifc/ifc-adapter.js`, `ifc-meta.js`, `web-ifc-display.js`, `processed-file.js`;
- `js/fds/fds-exporter.js`, `fds-geometry-adapter.js`, `namelist-parser.js`;
- `js/compare/checks.js`;
- `js/workers/` và các inline worker bundles;
- `js/viewer/`;
- `scripts/test-ifc-conversion.js`, `test-background-export-worker.js`, script tạo bundle;
- `examples/AC20-FZK-Haus.ifc`, `examples/AC20-Institute-Var-2.ifc`, `examples/IfcOpenShell-Duplex.ifc` (nếu tồn tại trên nhánh thực tế).

Các giả thuyết lỗi đã có từ review trước: giới hạn `PRODUCT_TYPES`, review solids/MEP bị loại mặc định, nhánh `displayMesh` khác `exportMesh` làm mất openings trong GEOM, `IfcMappedItem.MappingOrigin` không đủ phép biến đổi, Boolean clipping chưa tổng quát, metadata/port graph chưa đủ, clip box không phải export scope, thiếu coverage audit. PHẢI kiểm tra lại bằng code + regression + fixture; không sửa mù theo số dòng cũ và không tuyên bố lỗi vẫn tồn tại nếu upstream đã khắc phục.

Đầu ra Phase 0: `docs/audit/00-baseline.md`, `docs/architecture/as-is.md`, `docs/roadmap.md`; chốt SHA, số lượng và trạng thái tests, risk register P0–P3, dependency/license inventory, ranh giới chức năng được giữ lại và thay đổi.

## 4. QUYẾT ĐỊNH KIẾN TRÚC

**Một fork chính, không ghép tùy tiện nhiều repos:**
- `ProfRino/IFCtoFDS`: Web UX + 3D viewer + legacy quick preview + parser/exporter FDS tái sử dụng có chọn lọc.
- `IfcOpenShell` Python: IFC parsing, geometry kernel, units, placements, IFC relationships/MEP systems. Sử dụng thư viện như dependency, không fork mã lõi không cần thiết.
- Geometry/validation bổ sung bằng thuật toán của nhóm; Voxelization Toolkit chỉ là lựa chọn phụ trợ/đối chứng nếu đã xác minh license/compatibility và nhu cầu.
- Bonsai/BFDS: baseline bán tự động để benchmark, không phụ thuộc runtime.
- NIST FDS/Smokeview: công cụ kiểm chứng khi có môi trường cài đặt; không đóng gói nhầm thành một phần của IFC parser.
- FD-Gen/fdsreader để phase nghiên cứu tiếp theo khi cần; không đưa vào conversion core nếu không có lý do kỹ thuật.

**Kiến trúc đích:**
IFC source(s) → ingestion + provenance/federation → canonical BIM model (hình học + semantic + MEP graph) → mapping policy/scoping → FDS primitives + mapping manifest → independent source/output validation → reviewed model + report.

Triển khai theo hai đường:
- **Legacy Quick Conversion:** Web JS hiện tại, giữ tương thích và cảnh báo chưa nghiệm thu.
- **Verified Conversion:** Python IfcOpenShell + canonical mapping + refactored exporter + validation; chỉ đường này được cấp nhãn VERIFIED khi đạt gates.

**Tích hợp chạy được:** xây Python CLI trước và FastAPI adapter cục bộ để UI gọi. Bảo toàn chế độ chỉ cần mở `index.html` cho legacy; verified yêu cầu backend cục bộ hoặc server được triển khai rõ ràng. Không dùng browser cố gọi subprocess Python trực tiếp. Có API job status/progress và lỗi rõ ràng. Backend không lưu vĩnh viễn IFC nhạy cảm ngoài cấu hình người dùng.

## 5. HỢP ĐỒNG DỮ LIỆU CHUẨN (CANONICAL MODEL)

Xây schemas có version + validation bằng Pydantic/JSON Schema; đủ để giao tiếp Python ↔ JS. Không truyền đống JSON vertices khổng lồ nguyên một khối khi mô hình lớn; thiết kế tệp/hình học nhị phân chunked hoặc sidecar phù hợp và giữ index theo ID.

`SourceFile`: `sourceFileId`, `originalFilename`, `sha256`, `schema`, units, placements, georeference, transformToProjectMeters, importWarnings.
`SourceElement`: `elementKey = (sourceFileId, GlobalId)`; fallback STEP ID có cờ không bền vững khi thiếu GUID; `ifcType`, `name`, `tag`, `storeyIds`, `systemIds`, `psets`, `property provenance`, `representation ids`, `geometryStatus`, `inScope`, `reasonCodes`.
`CanonicalGeometry`: geometry ID, local/world transforms, meters, BRep/mesh ref, bbox, volume/area khi xác định được, faces, normals, closure/manifold status, openings, tolerances, shape hash; không làm tròn tọa độ quá sớm.
`MEPGraph`: nodes elements/ports/systems; edges được phân biệt `EXPLICIT_IFC`, `GEOMETRIC_CANDIDATE`, `HUMAN_CONFIRMED`. Không biến `GEOMETRIC_CANDIDATE` thành đã xác nhận. Có flow directions khi IFC đủ dữ liệu.
`MappingDecision`: include/exclude/reference-only, chosen FDS role, strategy, transformation, rationale, config version, reviewer/approval, expected tolerance.
`FDSPrimitive`: unique stable ID, type `OBST|HOLE|GEOM|...`, source element keys [một-nhiều và nhiều-một khi có chứng cứ], geometric payload, conversion strategy, provenance.
`MappingManifest`: every source item and every emitted primitive with bidirectional links, rejected/unsupported/semantic-only reasons, alias proofs, config hash, tool versions, source hashes, output hashes.
`Finding`: severity, source/target IDs, XYZ/location, test, expected/actual, delta, threshold, evidence, suggested remediation, reproducibility.

**Coverage rule:** 100% `in-scope` source items được kiểm kê và có quyết định giải trình, KHÔNG đồng nghĩa 100% phải trở thành FDS `OBST`/`GEOM`. Các item bắt buộc xuất hình học mà thiếu/sai sẽ BLOCK. Giữ phân biệt source accounting, geometry mapping, semantic preservation, physical simulation readiness.

## 6. IFC INGESTION, HÌNH HỌC VÀ FEDERATION

A. Lập inventory toàn bộ `IfcProduct` + IFC relationships liên quan trước khi quyết định hình học; không dùng whitelist làm điều kiện bỏ qua không ghi nhận.
B. Dùng IfcOpenShell geometry iterator cho bulk extraction, caching/multicore khi ổn định; dùng create_shape cho debug individual. Khóa phiên bản dependency sau khi chạy test, không đặt trước API khi chưa kiểm chứng.
C. Xác minh `ObjectPlacement`, nested placements, mapped representation, `MappingOrigin^-1`, rotations/scales/mirrors; xử lý opening subtractions theo cơ chế chuẩn IFC; thử nhiều loại Boolean; không tự tạo hình hộp từ bbox nếu không được ghi là xấp xỉ và kiểm chứng.
D. Chuẩn hóa nội bộ về mét, tọa độ 3D project-local, matrix 4x4; kiểm tra units IFC, các tọa độ lớn, georeference, nhiều IFC với offset khác nhau. Mô hình không đồng bộ tọa độ thì dừng hoặc yêu cầu explicit transform đã phê duyệt.
E. Bảo toàn `IfcOpeningElement` và `IfcRelVoidsElement`, quan hệ filling và host; xây test hình học sau subtraction/meshing, không dùng display mesh khác export mesh làm nguồn authoritative.
F. `IfcProxy` hoặc class không rõ: không mặc định thành kết cấu/ống. Phân loại bằng IFC class + predefinedType + psets + system + geometry và ghi confidence/evidence; khi không đủ chắc chắn yêu cầu review.
G. `IfcSpace` và những thực thể phi vật rắn là metadata/spatial context, không xuất như vật cản.
H. Hình học lỗi/không giải được: `UNSUPPORTED_GEOMETRY`/`INCONCLUSIVE` có evidence, không bỏ qua âm thầm.

## 7. SEMANTIC + HVAC/PCCC GRAPH

Dùng `ifcopenshell.util.system` và các API liên quan theo phiên bản đã pin: get_ports, get_connected_port, get_port_element, get_element_systems, get_system_elements; duyệt trực tiếp các quan hệ IFC khi cần (IFC2X3/IFC4 có cách gắn ports khác nhau). Thu thập và kiểm tra `IfcRelConnectsPorts`, group/system membership, containments/nests/aggregates, type/psets, flow direction khi có. Không suy ra quan hệ chỉ vì hai hình học chạm gần nhau.

Phân loại ít nhất: structural/architectural; duct segments/fittings/terminals/equipment/flow controllers; pipe segments/fittings/terminals/fire suppression devices; sensors và control devices chỉ lưu metadata khi chưa mô phỏng vật lý. `IfcFlowSegment` có thể là duct/pipe tùy schema/IFC exports; phân giải theo type, psets, system và hình học có bằng chứng, không chỉ dựa vào tên. Có bảng coverage riêng cho HVAC, Fire Protection, Structural.

Đảm bảo mọi hệ có số lượng nguồn, số phần tử có hình học, số nối explicit, số thiếu port, số candidate và lý do; vẽ đồ thị hiển thị điều kiện đã xác minh và thiếu dữ liệu. Không mô phỏng vận hành của hệ thống chỉ vì metadata tồn tại.

## 8. FDS MAPPING POLICY

Thiết kế một registry có thể cấu hình theo class/role/geometry, không nhét mọi điều kiện vào một hàm dài. Mỗi decision phải có preconditions và postconditions đã kiểm chứng.

- `OBST`: chỉ cho hình học phù hợp (ví dụ trục-aligned cuboids), không dùng bbox thay cho L/U/curved solids khi không tương đương.
- `OBST + HOLE`: chỉ khi opening geometry và ngữ nghĩa đúng, áp dụng đúng host/thứ tự, không carve nhầm cửa/ống/vách khác.
- `GEOM`: dùng khi cần hình học cong/nghiêng/phức tạp và được solver hỗ trợ; kiểm tra kín, normals, non-manifold, self-intersection, orientation, duplicates, watertight theo vai trò hình học, không phát sinh mặt sai.
- `VOXEL`: chính sách fallback có error budget (volume, Hausdorff/IoU, opening area, connectivity), báo rõ phụ thuộc độ phân giải; không fallback tự động che lỗi geometry.
- `REFERENCE_ONLY`/`SEMANTIC_ONLY`: cho thành phần cần bảo toàn metadata nhưng không biểu diễn như solid FDS hoặc không có ánh xạ vật lý được duyệt.
- Phân biệt pipes/duct shells và không gian luồng khí; không mặc định biến toàn bộ ống gió thành vật cản đặc rồi tuyên bố thông gió đúng.
- Không tự tạo `VENT`, `HVAC` network, `DEVC`, `PROP`, `CTRL`, sprinkler functions, quạt, tốc độ gió, mass flow, HRR hay thông số fire physics.

**Scope:** hỗ trợ ALL hoặc explicit bounding volume/spatial filters + intersection rules. Lọc theo hệ tọa độ, giữ các vật thể xuyên qua vùng B1/B2 (ramp, shafts, stairs, slabs boundary), hỗ trợ clipping hình học được chứng minh. Chỉ bật true export scope, KHÔNG dùng clip UI làm thay đổi FDS âm thầm. Các đối tượng tại biên nếu clipping không hợp lệ thì mark review/block.

**Provenance và alias:** giữ labels nhận diện Wall/Slab/Column/Duct/Pipe trong UI/manifest, gắn `sourceFileId+GlobalId+STEP` và IFC type. Chỉ dùng geometry alias/cache chung khi bằng chứng: canonical geometry equality theo tolerance, transform chính xác, vật liệu/chính sách giống nhau và không nhầm ID nguồn; report hash, transform, instance mapping. Hạn chế nối alias từ hình học gần giống.

## 9. VALIDATION ENGINE ĐỘC LẬP

Kiểm toán phải đọc **IFC gốc và `.fds` đã serialize rồi parse lại** cùng mapping manifest; không chỉ kiểm tra Python canonical model tự sinh. Cố gắng dùng những cơ chế xác thực độc lập khác nhau để tránh common-mode bug.

Ba cấp bắt buộc:
1. Source IFC → Canonical: inventory, ID, transforms, units, geometry BRep/mesh, openings, MEP ports/relationships.
2. Canonical → Serialized FDS: các primitive, coordinates, normals, adjacency, bbox, volume/area, holes, object IDs, aliases, source trace, full coverage.
3. FDS mesh-effective geometry: độ phân giải mesh, snaps, ô bị chặn, tiết diện lỗ mở/air paths, FDS parsing/solver diagnostic khi có bộ thực thi. Không coi cú pháp hợp lệ = mô phỏng chính xác.

Các phép đo: coverage (phải định nghĩa mẫu số), source/target IoU, symmetric surface distance/Hausdorff với độ đo và sai số rõ ràng, volume/area deviation, opening count + location + aperture area, room/shaft/air path connectivity, MEP node/edge precision-recall, duplicate/overlap/watertight/degenerate geometry, elements outside scope, material/surface mapping khi áp dụng. Tolerance có policy cấu hình trong SI meters, tuyệt đối không điều chỉnh riêng từng fixture chỉ để test pass.

Có ít nhất states: `MATCHED`, `DEVIATED`, `MISSING`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`, `UNSUPPORTED`, `INCONCLUSIVE`, `MISSING_SOURCE_DATA`. Phân nhóm severity P0 (mất critical geometry, bịt lối khí, sai major transform, thiếu element bắt buộc), P1 (thiếu MEP bắt buộc, error chưa được kiểm chứng, loss source trace), P2/P3 (cải thiện). Block VERIFIED khi còn P0/P1 chưa xử lý trong phạm vi nghiệm thu hoặc kết quả inconclusive ở điều kiện bắt buộc. Cho phép user review explicit nhưng tuyệt đối không thể dùng approve để đổi số liệu đo sai thành đúng.

Test false-negative: cố tình xóa OBST, dịch ống, bịt HOLE, thay transform, thay GlobalId, cắt sai tầng, xóa edge graph; hệ thống phải bắt được. Test false-positive: exclude đã phê duyệt, non-solid IfcSpace và metadata-only không bị tính sai là lỗi mất vật cản.

## 10. UI/UX TÍCH HỢP

Giữ các tính năng viewer hiện có (Overlay / IFC / FDS, lớp hiển thị, chọn phần tử, navigation, Workers). Mở rộng UI tối thiểu đủ workflow:
1. Import 1-n IFC; hiển thị hash/schema/coordinate alignment, summary của từng file.
2. Inventory tree theo file → discipline → system → storey → element; filter theo GlobalId/Tag/Name/type/issue.
3. Select scope XYZ/storey/system với preview chính xác vùng sắp xuất (khác clip chỉ xem).
4. Chọn `Quick Preview` hoặc `Verified Conversion` (Quick phải có cảnh báo unverified).
5. Progress theo từng stage, cancel, lỗi/unsupported dễ đọc.
6. IFC/FDS side-by-side hoặc overlay; màu highlight khác biệt; chọn finding → camera focus/định danh source và FDS.
7. Audit dashboard & exports `.fds`, `manifest.json`, `inventory.json`, `mep-graph.json`, `findings.csv`, `acceptance-report.html`, settings/config.
8. Không đưa badge VERIFIED nếu thiếu FDS/geometry checks; current UI luôn hiển thị trạng thái thực.

Xây CLI sử dụng được riêng cho nghiên cứu và CI (`inspect`, `convert`, `validate`); FastAPI adapter ở same-origin với Web hoặc proxy rõ ràng. Endpoint đề xuất: import/inspect, conversion jobs/start/status/cancel, artifacts download, audit reports. Áp dụng job isolation, validation filenames/paths, upload size limits, không tự public/private IFC ra cloud, không logging dữ liệu nhạy cảm. Không cần database lớn hoặc auth phức tạp để có demo local; nếu triển khai public thì bắt buộc threat model.

## 11. CẤU TRÚC THƯ MỤC ĐỀ NGHỊ

Giữ upstream JS hoạt động; bổ sung theo chiều dọc từng feature thay vì tái cấu trúc big bang:

```text
IFCtoFDS/
  index.html
  css/
  js/
    app-controller.js
    ifc/                      # legacy + canonical scene bridge
    fds/                      # refactored exporter + namelist parser
    viewer/
    workers/
    compare/
  backend/
    pyproject.toml
    src/ifc2fds_core/
      cli.py
      api/
      schemas/
      ingestion/
      federation/
      geometry/
      semantic/
      mep/
      mapping/
      fds/
      validation/
      reports/
  tests/
    fixtures/
    unit/
    integration/
    regression/
    mutation/
    benchmark/
  examples/
  scripts/
  docs/
    audit/
    architecture/
    contracts/
    mapping-rules/
    benchmarks/
    decisions/
  .github/workflows/
  README.md
  CHANGELOG.md
  CITATION.cff
  LICENSE
```

Có thể đổi module names nếu kiểm chứng có lý do mạnh hơn; ghi ADR. Không chồng chéo quyền sở hữu dữ liệu: Python là authoritative IFC+canonical+MEP, FDS exporter tiêu thụ contracts, viewer không tự quyết định geometry correctness.

## 12. CÁC GIAI ĐOẠN TRIỂN KHAI — KHÔNG BỎ QUA

**Phase 0 — Baseline & audit:** kiểm tra repo, upstream, HEAD, scripts, license, test baseline; reproducible command; bug fixtures; kiến trúc as-is + kế hoạch ADR. Không chạm main.

**Phase 1 — Python core + contract:** thêm pyproject, lock dependency theo môi trường, CLI `inspect`; inventory toàn bộ products/relationships, hash, units, schemas, sourceFileId, canonical model schema; chạy fixtures trong repo. Unit/integration tests pass.

**Phase 2 — Geometry fidelity:** tích hợp `ifcopenshell.geom.iterator`, placements/units/mapped representations/Boolean/openings và full geometry export; kiểm thử FZK holes, Duplex classes, rotation/mirror, non-SI; chứng minh shape equality/geometry stats; không cho bbox fallback lén.

**Phase 3 — MEP/HVAC/PCCC:** hệ thống/port/graph, phân loại discipline, inventory, system coverage, IFC2X3/IFC4 fixtures có cả trường hợp thiếu data; giữ candidate edges tách explicit edges; có regression thay đổi cạnh.

**Phase 4 — Mapping + FDS exporter:** registry policy & scope, canonical → FDS primitives, output FDS, sidecar manifest, provenance, aliases evidence; round-trip parser test. Không phá Quick Conversion, geometry viewer và export đồng nguồn authoritative khi Verified.

**Phase 5 — Independent validation:** nguồn/đích/manifest compare, meshing consequences, IoU/area/opening/ports/connectivity; mutation tests; fail-closed acceptance; báo cáo HTML+CSV+JSON và log có cấu trúc.

**Phase 6 — Web Verified workflow:** FastAPI local, adapter UI, jobs/progress/cancel, upload/multiple-IFC federation, scope, FDS preview, finding highlight, artifact downloads. E2E test thao tác thực, không để nút không hoạt động/placeholder.

**Phase 7 — Solver/static validation & performance:** chạy FDS dry-run/verification command khi thực thi được, lưu stderr/stdout và version; nếu không có FDS, đánh dấu `NOT_RUN` và không tuyên bố solver-validated. Benchmarks thời gian parsing/geometry/mapping/export/validation, peak RAM, geometric metrics trên FZK, Duplex, Institute nếu thành công; stress test lớn có timeout và cancellation; không tạo số đo giả.

**Phase 8 — Research deliverables & release candidate:** README chạy Windows/Linux, setup Python/Node/Web, `docs/architecture/to-be.md`, data dictionary, mapping decision table, MEP coverage, audit criteria, limitations, benchmark methodology, attribution/license, CHANGELOG và upgrade guide. Pull requests có test evidence, screenshot UI nếu được tạo thực, reviewer checklist; không tự nâng `1.0.0` trước khi nghiệm thu thực địa.

Ở mỗi phase: `inspect → implement → unit test → integration test → diff review → document → commit → PR/checkpoint`. Nếu môi trường một phiên không thể làm hết, ưu tiên hoàn thành một vertical slice chạy end-to-end (nhập IFC → canonical → FDS → parse back → audit) thay vì tạo hàng loạt skeleton rỗng; dừng với log blockers + lệnh thực thi kế tiếp, không tuyên bố toàn bộ xong.

## 13. CÁC TESTS & ACCEPTANCE GATES BẮT BUỘC

- Giữ tất cả legacy tests trong `scripts/`; không phá Web Worker inline bundling và Node scripts.
- Test inventory source coverage: các class như `IfcCovering`, `IfcFooting`, `IfcRamp`, `IfcFlowController`, ducts/pipes/fittings/terminals không bị mất khỏi inventory. Không khẳng định phải là OBST.
- FZK Haus: tường có openings, `display` và `export` giữ cùng canonical opening; kiểm tra HOLE/GEOM bằng so sánh hình học đầu ra, không chỉ so số tam giác.
- Duplex: nhiều loại cấu kiện, missing representation, units & placement, source link.
- Institute: theo dõi thời gian/peak memory/timeout; không chấp nhận treo vô thời hạn.
- Synthetic fixtures: `IfcMappedItem` nonidentity origin, rotated/mirrored placement, mm/feet conversion, Boolean clipped walls, diagonal ramp, narrow vent, shaft crossing levels, overlapping multiple IFCs, IFC2X3/IFC4 connectivity, absent MEP network, invalid geometry, alias equality & non-equality, pipe graph missing edge, solid-vs-void ambiguity.
- Round-trip `.fds`: namelist parse, numbers finite, mesh consistency, zero invalid references, IDs stable, provenance recoverable.
- Solver/static: no unintended blocked path; geometry validity independently checked; if FDS binary missing, still run static validators and mark solver check not run.
- Mutation: injecting deleted wall/pipe, blocked opening, shifted z, broken system edge causes FAIL.
- Cross-platform: Windows and Linux where CI available; Python pinned, Node baseline; no hardcoded paths.
- Verify quick mode still works offline on browser; verified mode works via local API.

Gates: all required tests green; source accounting 100% within chosen scope (including accepted exclusions); no unresolved mandatory P0/P1; validated geometry/MEP each has proof; errors traceable to IFC; supported output parses; independent audit issues explicit. Tolerances must be predefined and reported; do not hardcode 100% geometric accuracy as a marketing claim. Acceptance is **per dataset + configured scope + tolerance + solver validation level**, not an unconditional label on the entire program.

## 14. TEST DATA VÀ BẢO MẬT

Dùng fixtures có giấy phép rõ ràng trong repo. Các file IFC/FDS công trình hầm từng dùng trong project (ví dụ `Ham2Tang.ifc`, `ALL_FDS_2027.ifc`, `ALL_FDS_2027_geometry_only.fds`) chỉ dùng **nếu thực sự hiện diện và được phép sử dụng**; đừng cho vào repo public khi chưa có quyền công bố. Nếu chưa có, ghi `REAL_PROJECT_VALIDATION_PENDING` và hoàn tất các bài kiểm thử mẫu; không gán các thống kê lịch sử thành kết quả chạy hiện tại. Không sửa, rename, xoá IFC nguồn hoặc tự tạo missing HVAC/FP để cho đẹp báo cáo.

## 15. ĐỊNH LƯỢNG NGHIÊN CỨU

Benchmark ít nhất ba phương pháp nếu có môi trường hợp lệ: (A) upstream IFCtoFDS, (B) quy trình thủ công/Bonsai+BFDS với số giờ thao tác, (C) hybrid mới. Kết quả trên cùng IFC, cùng scope, cùng dung sai và phần cứng; log hardware/software/commit/seed/config; đo riêng parse, geometry, MEP graph, mapping, export, audit; đo memory. Báo source accounting vs mapping completeness, IoU, normalized surface distance, opening preservation, MEP-node and graph edge recall/precision, traceability coverage, issue detection, solver validity. Không bịa gain (%) nếu chưa có phép đo ngang hàng.

## 16. CÔNG VIỆC ĐẦU RA CỤ THỂ VÀ BÁO CÁO MỖI VÒNG

Sau mỗi phase, báo theo mẫu:
- `Phase`, `branch`, `base SHA`, `commit(s)` và files changed.
- Thay đổi kiến trúc + lý do (ADR), provenance/licensing.
- Tests đã chạy: full command, counts, PASS/FAIL/SKIP, thời gian và logs/evidence.
- Phạm vi đã hỗ trợ, chưa hỗ trợ, P0–P3, rủi ro geometry/FDS/MEP.
- Output artifacts có đường dẫn đúng, không invent links.
- Acceptance gate nào đã đạt, gate nào BLOCKED, điều kiện đóng blocker.
- Next PR/phase cụ thể và thứ tự ưu tiên.

Tài liệu bàn giao cuối: working CLI + Verified Web workflow, unit/integration/E2E/mutation tests, representative FDS + inventory + manifest + audit report, benchmark record, developer guide, user guide, upgrade/license/source attribution, PR checklist. Không đóng dấu VERIFIED khi thiếu bằng chứng thực nghiệm.

## 17. CHỈ THỊ KHỞI ĐỘNG NGAY

1. `git status --short --branch && git remote -v && git rev-parse HEAD`; kiểm tra fork/upstream SHA, tạo worktree/branch sạch nếu cần.
2. Đọc `README.md`, `docs/*`, `scripts/*`, các file IFc/FDS/controller/worker/compare được liệt kê và lập call graph / flow chart thực tế.
3. Chạy test upstream, tái hiện ít nhất một bug hình học lỗ mở và một trường hợp source inventory bỏ sót. Nếu không tái hiện, ghi bằng chứng upstream đã khắc phục.
4. Tạo `docs/audit/00-baseline.md`, `docs/architecture/to-be.md`, ADR cho canonical model + Python-CLI/FastAPI bridge, `docs/roadmap.md` với PR phân rã.
5. Bắt tay code Phase 1 ngay trên branch mới và tiến triển liên tục theo gates. Ưu tiên `source inventory + canonical model + end-to-end FDS vertical slice`; không chỉ viết kế hoạch rồi dừng.
6. Đề xuất và thực hiện chuỗi PR nhỏ; không merge main tự động. Nếu GitHub credentials không sẵn có, tạo branch/commits local và ghi chính xác lệnh push/PR để thực hiện khi được cấp quyền.
7. Báo cáo dựa trên code, logs và công cụ thật; không nói hoàn tất một việc chưa chạy được.

**MỤC TIÊU CUỐI:** không phải sản xuất nhiều GEOM/OBST nhất hoặc đạt conversion time thấp nhất, mà là có một pipeline **bảo toàn cấu kiện nguồn, có ngữ nghĩa HVAC/PCCC, không làm sai hình học và lỗ mở, xuất FDS có truy vết, đo được sai lệch và tự chặn nghiệm thu khi thiếu bằng chứng**. Công cụ phải tổng quát, không gắn cứng vào B1/B2 và chưa có kịch bản cháy ở giai đoạn này.
