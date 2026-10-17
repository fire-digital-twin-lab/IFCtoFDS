# KẾ HOẠCH NÂNG CẤP IFCtoFDS v0.1.0 → v0.2.0

**Ngày:** 15/10/2026  
**Cơ sở:** Review mã nguồn trong `IFCtoFDS-v0.1.0.zip` và tiêu chí nghiên cứu: IFC là nguồn chuẩn, phải truy vết và kiểm chứng kết cấu, HVAC, PCCC trước khi đưa vào mô phỏng cháy.  
**Phạm vi:** Nâng cấp công cụ mapping và kiểm toán; chưa triển khai mô hình cháy, vận hành quạt, sprinkler hay suy đoán đặc tính vật lý không có trong IFC.

## A. Những điều không được làm

1. Không sửa mọi thứ cùng một PR, không viết lại viewer nếu không cần.
2. Không sửa lỗi mất lỗ mở GEOM bằng cách gán thẳng `element.mesh = element.displayMesh`: displayMesh có thể không kín hoặc bị sai Boolean. Chỉ xuất GEOM nếu hình học đã được kiểm chứng; còn lại báo `BLOCKED`.
3. Không coi `includeReviewSolids = true` là đã ánh xạ đầy đủ HVAC/PCCC. Hình học của ống khác với đồ thị mạng ống và hành vi thông gió/phun nước.
4. Không xóa phần tử ngoài phạm vi bằng thao tác ẩn trên viewer. Phải có `scopePolicy` trong dữ liệu xuất.
5. Không dùng GlobalId làm FDS ID trực tiếp và không đổi tên nguồn làm mất truy vết. FDS ID duy nhất, manifest giữ GUID/STEP ID/Name/Tag và file nguồn.
6. Không cho phép lỗi cấp P0/P1 đang mở nhưng báo kết quả `PASS`.

## B. Chiến lược kiến trúc

**Giữ:** giao diện `index.html`, Three.js viewer, JS worker, FDS parser, các exporter đã kiểm chứng, test samples.

**Thêm:** lõi `ifc-core` kiểm chứng độc lập, có thể chạy bằng Python IfcOpenShell dưới dạng CLI/local service. Sau đó tạo một dạng dữ liệu chuẩn chung cho viewer và exporter. Web-IFC là đường hiển thị/phụ trợ, không phải nguồn phán quyết chất lượng mapping.

Đề xuất cây thư mục:

```text
ifc-core/
  inventory.py           # IfcProduct inventory, cả khi geometry lỗi/thiếu
  geometry.py            # tạo BRep/tri mesh chuẩn, đơn vị, transform
  relations.py           # containment, group/system, type, port connectivity
  classification.py      # phân loại structural/HVAC/FP/other theo IFC & quan hệ
  schema.py              # JSON contracts / schema version
js/
  ifc/ifc-adapter.js     # giữ parser cũ làm fallback, diagnostics thành trạng thái rõ ràng
  mapping/scope-policy.js
  mapping/conversion-policy.js
  mapping/provenance.js
  fds/fds-exporter.js
  compare/geometry-validation.js
  compare/coverage-validation.js
  compare/topology-validation.js
  compare/acceptance-gate.js
scripts/
  audit-ifc-to-fds.py    # kiểm toán độc lập từ source IFC + exported FDS + manifest
  test-fixtures/...      # fixture IFC nhỏ, kỳ vọng hình học rõ ràng
```

Nếu chưa muốn dùng Python ở phiên bản nhỏ, có thể xây inventory/quan hệ trước bằng JS nhưng phải chứng minh tương đương với baseline IFC độc lập. Không bắt buộc ép kiến trúc client-server nếu chỉ cần CLI offline.

## C. PR 0 — Baseline & regression

- Lưu checksum SHA-256 của ZIP, IFC mẫu, FDS mẫu và config convert.
- Tách smoke/unit/integration/regression; test nặng không nằm chung smoke.
- Bắt buộc `node --check` cho mọi JS, `node scripts/test-background-export-worker.js` và regression theo tệp mẫu; pin phiên bản các runtime/phụ thuộc.
- **Quan trọng:** sau mỗi lần sửa `js/ifc/ifc-adapter.js` hay `js/fds/fds-exporter.js`, chạy:
  - `node scripts/generate-inline-parse-worker.js`
  - `node scripts/generate-inline-export-worker.js`
  để tránh worker `file://` vẫn chạy logic cũ.
- Snapshot dữ liệu phải bao gồm inventory nguồn, không lấy số lượng phần tử được nhập làm mẫu số đầy đủ.

**Gate:** mã cũ giữ chức năng, test baseline tái lập, mọi thay đổi sau có regression.

## D. PR 1 — Full source inventory

**Sửa:** `js/ifc/ifc-adapter.js` ở bước `beginParse/processEntity`; bổ sung `ifc-core/inventory.py`.

- Inventory tất cả `IfcProduct` theo schema thật, kể cả không có hình học hoặc không trong `PRODUCT_TYPES`.
- Mỗi phần tử có `sourceFileSha256`, `schema`, `stepId`, `globalId`, `ifcType`, `name`, `tag`, `predefinedType`, `storey`, `systemIds`, `representationStatus`, `mappingStatus`, `exclusionReason`.
- Không chỉ sửa danh sách whitelist. Mọi đối tượng bị loại phải có trạng thái: `NO_GEOMETRY`, `UNSUPPORTED_GEOMETRY`, `OUT_OF_SCOPE`, `SEMANTIC_ONLY`, `EXPORTABLE`.
- Ghi nhận `IFCCOVERING`, `IFCFOOTING`, `IFCPLATE`, `IFCRAMP`, `IFCFLOWCONTROLLER` và các subtype thuộc IFC schema hiện hành, nhưng không mặc định xuất như OBST.

**Gate:** toàn bộ IfcProduct đều nằm trong inventory, mọi thiếu hụt có lý do; sample Duplex có 13 IFCCOVERING và 7 IFCFOOTING được inventory nhận biết.

## E. PR 2 — Hình học chính xác & openings

**Sửa:** `js/ifc/ifc-adapter.js` (`carveItemOpenings`, `meshForMappedItem`, `meshForBooleanClippingResult`, `detectLengthScale`), `js/fds/fds-exporter.js` (`formatGeom`, `strategyForElement`).

1. Chuyển đơn vị qua `IfcProject.UnitsInContext` / `IfcUnitAssignment`; hỗ trợ cả conversion-based units. Normalized output dùng m; lưu phép đổi.
2. Biến đổi `IfcMappedItem`: dùng `M_product × M_mappingTarget × inverse(M_mappingOrigin)` với quy ước ma trận thống nhất và test tọa độ thật; kiểm tra scale không đều và gương.
3. Hình học lỗ mở: lấy Boolean/BRep đã trừ void từ kernel đáng tin cậy. Cấu trúc trả về gồm `solidMesh`, `carvedMesh`, `openingVolumes`, `geometryStatus`, không có khái niệm preview đúng thì export tự động đúng.
4. `GEOM`: chỉ xuất `carvedMesh` nếu đạt manifold, orientation, no degeneracy và opening checks. Không đạt thì dừng phần tử/tệp theo mức độ bắt buộc; không fallback âm thầm thành khối đặc.
5. `OBST + HOLE`: chỉ khi hình hộp và lỗ mở hình chữ nhật song song hệ trục đáp ứng ràng buộc. Cấu kiện cong/nghiêng phải có chứng minh gần đúng hoặc chuyển sang nhánh hình học thích hợp.
6. `Voxel`: kiểm tra kích thước lỗ/không gian thông khí sau rasterization; hiện rõ sai số cực đại và khả năng mất đường khí tại grid hiện hành.
7. `IFCPOLYGONALBOUNDEDHALFSPACE`: thực hiện phép cắt trong miền polygon, không thay bằng cắt theo cả mặt phẳng; trường hợp chưa hỗ trợ đánh dấu `UNSUPPORTED`.
8. Không tự bơm độ dày sàn phẳng bằng thông số mặc định nếu được yêu cầu fidelity; nếu cần, xem như assumption có phê duyệt và không đánh dấu MATCHED EXACT.

**Fixtures tối thiểu:** wall + 3 windows/doors, slab with shaft, rotated/mirrored mapped item, polygonal bounded cut, IFC mm/foot, inclined duct, L slab.

**Gate:** lỗ của tường FZK `Wand-Ext-ERDG-1` xuất đúng cả ở GEOM; kích thước/tọa độ trong tolerance; không còn lỗi kín/normal chưa được xử lý.

## F. PR 3 — Semantic systems & MEP/PCCC

**Thêm:** `ifc-core/relations.py`, `classification.py`, `js/mapping/conversion-policy.js`.

- Đọc `IfcRelContainedInSpatialStructure`, `IfcRelAssignsToGroup`, `IfcRelAggregates`, `IfcRelDefinesByType`, `IfcRelDefinesByProperties`, `IfcRelVoidsElement`/`IfcRelFillsElement`.
- Đọc `IfcRelConnectsPorts` và quan hệ gắn port với thiết bị tương ứng theo phiên bản IFC (IFC4 có nesting; IFC2x3 có thể dùng `IfcRelConnectsPortToElement`).
- Xây graph: `systems[]`, `equipment[]`, `segments[]`, `fittings[]`, `terminals[]`, `ports[]`, `connections[]`.
- Phân loại ống gió/ống nước và hệ PCCC theo entity class + PredefinedType + system assignment + attributes/psets, không dựa vào tên chứa `FP`, `SPR`, `Duct` đơn thuần.
- Port/source connection thiếu trong IFC phải ghi `UNKNOWN`, không tự suy ra liên thông chỉ vì ống nằm sát nhau.
- Định nghĩa các vai trò chuyển đổi: `SOLID_BARRIER`, `OPENING`, `FLOW_BOUNDARY_CANDIDATE`, `MEP_GEOMETRY`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`, `UNSUPPORTED`.
- Trích đầy đủ thiết bị và topology; không tự tạo `HVAC`, `VENT`, sprinkler/DEVC, quạt hoạt động nếu dữ liệu IFC chưa định nghĩa thông số và chưa có conversion policy được phê duyệt.

**Gate:** completeness report theo system/storey/type, có path kiểm tra kết nối trên graph, mỗi thiết bị có trạng thái riêng và nguồn truy vết.

## G. PR 4 — Scope & controlled FDS export

**Sửa:** `js/app-controller.js` `currentExportOptions`, `js/fds/fds-exporter.js` `exportableElements`/`strategyForElement`.

- Tách `viewerClip` khỏi `exportScope`; thêm `scopePolicy={storeys[], systems[], types[], regionBox?, includeIntersectingElements, regionHandling}`.
- Với cấu kiện cắt qua boundary, không được lặng lẽ cắt bằng AABB. `regionHandling` rõ ràng: `KEEP_WHOLE` / `GEOMETRIC_CLIP_VERIFIED` / `BLOCK_UNSUPPORTED`.
- Áp dụng policy nhất quán với `&MESH`, `OBST`, `GEOM`, `HOLE`, closures và manifest; phát hiện đường thông khí bịt ngoài ý muốn tại mép scope.
- Giữ `Name` và `GlobalId` nguồn trong sidecar, cấp `FDS_ID` riêng; mọi emitted OBST/GEOM/HOLE có `sourceElementId` và `mappingDecisionId`.
- Sửa `summarizeStrategy`: thống kê từ danh sách các primitive thực tế đã phát sinh, không ước lượng trước fallback.
- Khi voxel budget vượt hạn mức không tự chuyển sang GEOM chưa đạt; ghi `BLOCKED` hoặc fallback đã chứng minh.

**Gate:** chọn B1/B2 thì đúng phạm vi được phê duyệt, không mất cấu kiện giao biên; số liệu summary trùng với FDS parser.

## H. PR 5 — Independent audit & acceptance

**Thêm:** `coverage-validation`, `geometry-validation`, `topology-validation`, `acceptance-gate`, CLI audit.

- Đọc **lại** IFC gốc độc lập và parse FDS đã xuất, không dựa vào cùng `element.mesh` trong exporter.
- Kiểm tra integrity: mã nguồn, schema, unit, bbox, centroid, thể tích/diện tích (khi có), openings, quan hệ system/ports, coverage source→target, mesh cell resolution, lỗi parser/solver.
- Phân biệt sai số `ERROR_FROM_CONVERSION`, `ERROR_FROM_SIMPLIFICATION_APPROVED`, `UNSUPPORTED`, `OUT_OF_SCOPE_APPROVED`.
- Kết quả từng nguồn: `MATCHED`, `DEVIATED`, `MISSING`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`, `INCONCLUSIVE`.
- Tolerance đặt theo requirement dự án và resolution FDS, lưu cùng config; không dùng một ngưỡng 5% mặc định cho mọi cấu kiện.
- Chỉ `ACCEPTED` khi mọi đối tượng bắt buộc được giải trình; không P0/P1 đang mở; hình học, lỗ mở, kết nối đủ bằng chứng; solver không báo lỗi fatal trên bộ ca kiểm thử. Một file FDS chạy được không thay thế kiểm toán hình học.

**Output:**

```text
output/<run-id>/
  converted.fds
  source-inventory.json
  source-systems.json
  mapping-manifest.json
  geometry-comparison.csv
  findings.csv
  acceptance.json
  run-metadata.json
```

### Mẫu manifest

```json
{
  "schemaVersion": "1.0",
  "sourceFile": "model.ifc",
  "sourceSha256": "<computed-sha256>",
  "sourceElement": {"globalId": "<source-guid>", "stepId": 123, "ifcType": "IfcWall", "name": "Wall-1"},
  "scopeDecision": "IN_SCOPE",
  "conversionRole": "SOLID_BARRIER",
  "strategy": "OBST_HOLE",
  "fdsPrimitiveIds": ["Wall-1", "Wall-1_h1"],
  "geometryStatus": "VALIDATED",
  "validation": {"status": "MATCHED", "tolerances": {"positionM": 0.001}}
}
```

Trường dung sai 0.001 m ở đây **chỉ minh họa cấu trúc**, không phải ngưỡng mặc định cần áp dụng.

## I. Những ca kiểm thử chặn phát hành

| ID | Mục tiêu | Kết quả cần có |
|---|---|---|
| T-01 | Source inventory: Duplex | IFCCOVERING=13, IFCFOOTING=7 có trong inventory; nếu không ánh xạ có reason |
| T-02 | FZK wall openings | GEOM và OBST/HOLE giữ đủ lỗ; không có đặc tường bất ngờ |
| T-03 | MappedItem rotated/origin | Transform khớp baseline thế giới trong tolerance |
| T-04 | Unit converted | mm, feet → meters đúng; metadata ghi rõ |
| T-05 | IFC system/ports | Port graph và system membership khớp quan hệ IFC |
| T-06 | MEP missing port | Báo thiếu/không xác định, không dựng kết nối giả |
| T-07 | Scope B1/B2 | Viewer hide không thay export; exportScope thực có hiệu lực |
| T-08 | Large voxel budget | Không fallback sang GEOM mất opening |
| T-09 | Worker parity | inline vs standalone worker cho kết quả đồng nhất |
| T-10 | Independent validator | Cố tình xóa 1 OBST/GEOM → validator phát hiện MISSING |
| T-11 | Geometry/opening resolution | Báo lỗ mở nhỏ hơn độ phân giải lưới hoặc bị bít |
| T-12 | FDS solver | Nạp/kiểm tra mô hình nhỏ không fatal; visual review riêng |

## J. Quy tắc quản lý triển khai

- 1 PR cho một lớp vấn đề; giữ diff tập trung, có regression mới chứng minh lỗi cũ được sửa.
- Không ghi `PASS` chỉ vì compile/export thành công; mỗi finding cần evidence và kết quả kiểm thử.
- Ban đầu có thể làm 2 nhánh `fix/geometry-fidelity` và `feat/source-inventory`, merge theo thứ tự kiểm soát; tránh agent sửa đồng thời `ifc-adapter.js` mà không phân vùng.
- Chốt Gate 1 trước khi ưu tiên HVAC/PCCC; hoàn tất Gate 3 trước khi dùng tệp xuất cho mô phỏng nghiên cứu.

**Thứ tự giá trị cao nhất:** Inventory → openings/transform/units → MEP relations → scope/provenance → independent audit → FDS validation.
