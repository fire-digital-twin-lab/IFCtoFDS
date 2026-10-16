# Báo cáo review mã nguồn IFCtoFDS v0.1.0

**Ngày review:** 15/10/2026  
**Nguồn:** `IFCtoFDS-v0.1.0.zip` (SHA-256: `3ea08378a8e29a85d6431961bdaaa3c01a86844d35ffb07b10ba39c7079214bf`)  
**Trạng thái:** **NOT ACCEPTED** cho mục tiêu ánh xạ IFC → FDS đúng/đủ hình học, kết cấu, HVAC, PCCC và truy vết khoa học. Đây là **đánh giá mã nguồn**, không phải kiểm toán hình học trên các IFC công trình riêng của người dùng (chúng không có trong ZIP).

## A. Scope nghiệm thu

- IFC là nguồn chuẩn; không tự tạo/suy đoán cấu kiện, kết nối, thông số vận hành.
- Đúng kích thước, vị trí, cao độ, lỗ mở, topo, hình học; không bịt đường khí ngoài ý muốn.
- Kết cấu: đầy đủ các phần tử thuộc phạm vi chọn; HVAC/PCCC: đầy đủ ống, phụ kiện, van, quạt, miệng gió, thiết bị và quan hệ thực có.
- Truy vết từ GlobalId, STEP ID, Name, Tag, Storey, System và các quan hệ IFC đến từng FDS primitive.
- Alias phải có bằng chứng tương đương; thống kê MISSING / DEVIATED / EXCLUDED / MATCHED / INCONCLUSIVE.
- Không cần tự phát sinh kịch bản cháy hoặc chức năng hoạt hóa thiết bị không có dữ liệu nguồn.

## B. Kết quả đã kiểm chứng

1. ZIP có 62 entries, gồm JS browser/worker, HTML/CSS, tài liệu, 3 tệp IFC mẫu và 1 FDS mẫu.
2. Chạy `node --check` trên toàn bộ `.js` trong mã gốc đã giải nén: không thấy lỗi cú pháp.
3. `node scripts/test-background-export-worker.js`: **PASS**, đầu ra lần kiểm tra: `obsts=162`, `geoms=5`, inline worker `obsts=162` (mẫu FZK).
4. Smoke parse/export `AC20-FZK-Haus.ifc`: 44.249 STEP entities, 47 elements được importer nhận, 22 phần tử xuất mặc định, 22 GEOM khi chọn all-GEOM; parse ~2,5 giây. `Wand-Ext-ERDG-1` có 3 openings, 12 faces trong export mesh nhưng 1.532 faces trong display mesh (lỗ chỉ có trong bản để hiển thị); all-GEOM xuất từ bản 12 faces, do đó không giữ các lỗ mở tương ứng.
5. Smoke parse/export `IfcOpenShell-Duplex.ifc`: 27.529 STEP entities, 208 elements được importer nhận, 84 phần tử xuất mặc định, 84 GEOM khi chọn all-GEOM; parse ~3,0 giây. IFC gốc có 13 `IFCCOVERING`, 7 `IFCFOOTING` nhưng cả hai class vắng mặt khỏi `PRODUCT_TYPES` của importer và bị bỏ qua.
6. `docs/conversion-test-results.md` ghi FZK imported 45 và Duplex imported 148, FDS-ready 77; sai khác so với các kết quả parse thực tế 47, 208, 84; tài liệu chưa đồng bộ với bản ZIP.
7. Bộ regression tổng hợp `scripts/test-ifc-conversion.js` và bản giảm mẫu chưa hoàn tất trong giới hạn runtime đã thử; **không kết luận PASS hay FAIL** cho toàn bộ regression. Không có FDS solver executable được xác minh trong môi trường hiện tại, vì thế chưa có bằng chứng mô hình chạy hợp lệ trong FDS.

## C. Findings đã xác thực từ mã nguồn

| ID | Mức | Vấn đề | Bằng chứng | Tác động |
|---|---|---|---|---|
| IFC-001 | P0 | Product allowlist loại vĩnh viễn các class IFC quan trọng | `js/ifc/ifc-adapter.js:2-25,192-193,614-617` | IFC không có cơ chế inventory toàn vẹn; cấu kiện bị thiếu mà mapping count không nhận diện |
| IFC-002 | P0 | MEP (IFCFLOWSEGMENT, IFCFLOWFITTING, IFCFLOWTERMINAL, ... ) `review` → bị loại theo mặc định; một số lớp thiết bị không được nhập | `ifc-adapter.js:26-37,1696-1704`; `fds-exporter.js:451-457` | Thiếu ống/thiết bị HVAC/PCCC; bật review chỉ biến phần tử thành vật cản hình học, không tạo mạng hệ thống |
| IFC-003 | P0 | Không có graph quan hệ System/Port/Connectivity/Containment, inventory đầy đủ, xuất audit chứng minh | `ifc-adapter.js:171-189,245-275`, `fds-exporter.js:1377-1386` | Không thể truy vết hệ thống/port và chứng minh đầy đủ kết nối |
| IFC-004 | P0 | Checks chỉ kiểm tra bề ngoài, không IFC↔FDS độc lập; không có acceptance gate | `js/compare/checks.js:2-82` | Có thể xuất kết quả khi thiếu cấu kiện, mất lỗ, lệch tọa độ hoặc sai connectivity |
| IFC-005 | P1 | Các phép trừ opening dạng box có ở `displayMesh`, không có trong `mesh` gửi FDS GEOM | `ifc-adapter.js:759-785`, `fds-exporter.js:353-370` | GEOM có thể bịt cửa/sổ/đường thông khí; tái hiện ở mẫu FZK |
| IFC-006 | P1 | `IfcRepresentationMap.MappingOrigin` không được đưa vào phép biến đổi hình học mapped item | `ifc-adapter.js:926-960` | Sai vị trí/hướng các cấu kiện dùng reusable mapped geometry |
| IFC-007 | P1 | `IfcPolygonalBoundedHalfSpace` chỉ cắt theo mặt phẳng, chưa xét ranh giới polygon | `ifc-adapter.js:963-988` | Sai topology, hình học hoặc bề mặt cắt |
| IFC-008 | P1 | Chỉ phát hiện SI LENGTHUNIT; không xử lý đầy đủ IfcConversionBasedUnit và project unit assignment | `ifc-adapter.js:545-573` | Sai hệ đơn vị khi IFC dùng đơn vị phi SI hoặc context phức tạp |
| IFC-009 | P1 | Clip box chỉ là viewer; không được chuyển thành policy scope khi export | `app-controller.js:130-137,973-991` | Người dùng tưởng bỏ một tầng/khu vực nhưng FDS vẫn chứa nguyên đối tượng |
| IFC-010 | P1 | Thiếu Validate geometry vs FDS solver; GEOM manifold warnings không ngăn export | `compare/checks.js:60-80`, `fds-exporter.js:4-93` | Xuất tệp chưa nghiệm thu; không có bằng chứng solver acceptance |
| IFC-011 | P2 | Strategy summary không phản ánh GEOM fallback khi quá voxel budget, các exclusions theo primitive | `fds-exporter.js:112-124,313-335` | Metrics có thể sai khác nội dung FDS xuất |
| IFC-012 | P2 | Metadata provenance có Name/GlobalId/Type/STEP nhưng thiếu Storey/System/Tag và mapping trace nhiều-đến-một | `fds-exporter.js:1377-1386` | Khó tra ngược số lượng lớn parts MEP và phân loại alias |
| IFC-013 | P2 | Docs/test counts chưa đồng bộ | `docs/conversion-test-results.md` và kết quả smoke | Báo cáo chất lượng có thể gây hiểu nhầm |
| IFC-014 | P2 | App tải Three/Web-IFC từ CDN, còn README nói mở file trực tiếp dễ dàng | `index.html:371-374`, `js/ifc/web-ifc-display.js:7` | Phụ thuộc kết nối internet, khó tái lập offline |
| IFC-015 | P2 | File FDS đặt tên sinh từ IFC, thay vì bảo toàn mapping giữa source/run/output bằng manifest | `app-controller.js:887-891` | Chưa có lineage phiên bản nhiều mô hình |

**Lưu ý:** Mức P0 là mức *block nghiệm thu theo yêu cầu nghiên cứu*; không khẳng định mọi trường hợp sử dụng công cụ demo đều gặp lỗi P0.

## D. Kiến trúc đề xuất

```
IFC originals (immutable + SHA-256)
  |
  +--> Authoritative IFC inventory
  |      - Schema + units + placements
  |      - GlobalId/STEP/Name/Tag/System/Storey
  |      - IFC relationships, systems, ports, connections
  |      - Unsupported / malformed / excluded per object
  |
  +--> Geometry extraction & normalization
  |      - Unify coordinates (document reversible transform)
  |      - BRep/CSG/openings/tessellation validation
  |
  +--> Scope policy / conversion decision per entity
  |      - KEEP / EXCLUDE with evidence
  |      - Passive obstacles vs flow path vs system graph
  |
  +--> Mapping engine
  |      - IFC element -> FDS GEOM/OBST/HOLE and sidecar semantic graph
  |      - Alias only after explicit equivalence test
  |
  +--> FDS export + mapping-manifest.json
  |
  +--> Independent audit using original IFC + exported FDS
         - Coverage, geom, openings, connectivity, manifold
         - Mesh/namelist/solver check
         - findings.csv + acceptance.json
         - PASS only with evidence
```

**Khuyến nghị kỹ thuật:** Giữ browser viewer và exporter như UI/prototype, nhưng sử dụng backend/CLI IFC parser đủ khả năng lấy IFC geometry và relationships (ví dụ IfcOpenShell) để tạo inventory và baseline độc lập. Đừng giả định viewer Web-IFC và exporter native parser tạo hình học tương đương nếu chưa kiểm chứng.

## E. Thứ tự sửa

### Gate 0: đóng băng baseline, test không phá mẫu
- Ghi SHA-256 nguồn/test input, version FDS, schema IFC, cấu hình, số phần tử nguồn theo type.
- Regression có timeout đo được và phân tách `parse`, `geometry`, `voxel`, `export`, `solver`.

### Gate 1: khắc phục lỗi mất hình học
- Tạo `sourceInventory` bao phủ mọi `IfcProduct`, có lý do chi tiết cho unsupported.
- Sửa GEOM opening; kiểm chứng ít nhất ba opening trên FZK; đồng thời kiểm tra mặt kín và normals.
- Sửa MappingOrigin, unit conversion; thêm fixtures rotated/mapped/scaled/unit-converted.
- Đưa scope filter thành phép lọc dữ liệu thật, không chỉ clip viewer.

### Gate 2: completeness MEP / PCCC
- Lập danh sách từng thiết bị và hệ thống từ IFC; đọc liên hệ hệ thống và graph port.
- Phân biệt vật cản thụ động, luồng HVAC và thiết bị PCCC; không suy ra active physics nếu thiếu dữ liệu.
- Ánh xạ đủ mặt cắt, đường tâm, thiết bị và footprint đại diện có kiểm chứng; lưu graph bên sidecar.

### Gate 3: độc lập kiểm toán và nghiệm thu
- So sánh theo GlobalId, type, system, storey, số lượng, bbox, volume/area và kiểm tra giao cắt/lỗ mở.
- Đánh giá `MATCHED`, `DEVIATED`, `MISSING`, `EXCLUDED_APPROVED`, `ALIAS_VERIFIED`, `INCONCLUSIVE` với proof và tolerance.
- Kiểm tra solver FDS đầu ra, tạo `findings.csv`, `mapping-manifest.json`, `audit.json` và conclusion `ACCEPTED/CONDITIONAL/REJECTED`.

## F. Kết luận

Ứng dụng hiện tại có nền tảng UI/conversion hữu ích và một số test tốt cho hình học đơn giản; nhưng **không được coi là đã ánh xạ đủ IFC→FDS**, và chưa có đủ bằng chứng khoa học để nghiệm thu tổng thể kết cấu, HVAC, PCCC. Ưu tiên sửa phải là **completeness + openings + transformations + independent audit**, không phải tối ưu giao diện hay thêm physics/fire scenarios.
