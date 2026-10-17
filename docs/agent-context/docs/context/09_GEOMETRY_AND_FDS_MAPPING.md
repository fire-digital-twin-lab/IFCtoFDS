# 09 — Quy tắc ánh xạ hình học IFC → FDS

## Các lớp độ đúng

1. **Source geometry:** Solid/BRep/representation từ IFC + ObjectPlacement, units, geometry voids; hình học nguồn là ground truth *theo nội dung tệp*.
2. **Canonical geometry:** Source đã chuẩn hóa vào meters/hệ tọa độ chung; kiểm tra manifold/orientation/booleans.
3. **FDS serialized representation:** `OBST`, `GEOM`, `HOLE` cụ thể; `.fds` phải được parse lại; kiểm tra nhiều primitive cho 1 IFC.
4. **Effective FDS geometry:** do mesh, solver settings, object semantics; cần kiểm tra topology thông khí ở lưới hiệu dụng.

## Ma trận chiến lược (không tự động đồng nhất loại IFC = primitive)

| Geometry / vai trò | Chiến lược ưu tiên | Điều kiện cho phép |
|---|---|---|
| Hộp chữ nhật thẳng trục | `OBST` | Exact bbox/solid equivalence, phù hợp FDS semantics |
| Host chữ nhật có opening thẳng trục | `OBST+HOLE` | Cutouts đúng vị trí/tiết diện, đúng logic xử lý HOLE theo FDS |
| Solid cong/nghiêng/cấu kiện phức tạp | `GEOM` hoặc kiểm chứng phương án khác | Geometry validity, orientation, nondegeneracy, solver support |
| Host/void Boolean không được kernel xử lý | `BLOCK_UNSUPPORTED`/review | Không fallback thành khối kín thiếu lỗ |
| Bề mặt IFC không đủ thành solid | `SEMANTIC_ONLY`/`REVIEW_REQUIRED` hoặc surface strategy riêng | Chỉ khi vật lý/trường hợp FDS hỗ trợ, không tự đùn độ dày |
| Ống gió/ống PCCC/đầu phun | Geometry/semantic policy theo vai trò | Đừng tự đổi thành vật cản toàn đặc gây bịt dòng khí hoặc giả định function |
| Proxy/Alias | Strategy theo shape thực, không theo tên | Có chứng cứ equivalence và policy |
| Vật thể nhỏ ngoài nhu cầu miền CFD | Có thể loại theo policy được duyệt | Phải ghi exclusion, vẫn còn trong inventory |

## Units và Placement

- Đọc `IfcProject.UnitsInContext`/IfcUnitAssignment, SI prefix và conversion-based unit; chuẩn hóa sang mét, lưu factor và ma trận; test mm/ft.
- Với file đa IFC: áp dụng file-to-project transform tường minh; không trộn local/project/map CRS thiếu ground control points.
- Với `IfcMappedItem`: semantics thường là `M_world = M_product * M_mappingTarget * inverse(M_mappingOrigin)` theo quy ước matrix áp dụng đã kiểm thử; kiểm tra rotation/mirror/nonuniform scale.
- Không rút gọn số tọa độ quá sớm; phải nêu precision ở serialization.

## Openings và topology

- `IfcRelVoidsElement` xác lập host-opening, `IfcRelFillsElement` xác lập fill. Opening có thể bị fill đóng — điều kiện mở/đóng là policy/nguồn, không mặc định mở.
- Bản hình học để xem phải tham chiếu **cùng canonical geometry** với exporter; không để `displayMesh` giữ lỗ còn `exportMesh` bịt lỗ.
- Kiểm tra các lỗ xuyên sàn, trục kỹ thuật, ramp, cửa cấp/hút khói, cross-floor links, seam và vách phân khoang.
- Mỗi opening có sourceKey, hostKey, geometry/cross-section, clearances và `preservedStatus`; topology check đánh giá đường khí không bị bít.
- Các opening nhỏ hơn cell resolution có nguy cơ mất hiệu lực; phải gắn mesh-dependent finding, không chỉ kiểm tra file namelist.

## Voxel / mesh / GEOM safety

- `voxelSize` dùng xấp xỉ thành OBST, `cellSize` dùng `MESH` FDS — không được nhầm.
- `voxel budget` vượt hạn mức không được âm thầm fallback sang GEOM không hợp lệ/mất lỗ.
- IoU/thể tích chỉ là phép đo phù hợp cho closed watertight meshes. Mesh hở phải dùng surface/path/topology checks thích hợp.
- Đối với `GEOM`, kiểm tra triangle degeneracy, duplicated/nonmanifold edges, normals/orientation, self-intersections khi cần và điều kiện FDS hỗ trợ.
- Chỉ sử dụng compact/trivial `OBST` nếu không thay hình học ảnh hưởng miền tính toán; chứng minh qua reconstructed solids/occupancy.

## Clip/scope và giữ vật cản thiết yếu

- Không biến toàn bộ phần tử tầng 1 thành `EXCLUDED` nếu nó là trần biên của B1.
- Nếu crop cạnh scope, phải xử lý hình học theo clip chính xác hoặc giữ toàn bộ cấu kiện theo chính sách; không dùng AABB crop làm chứng cứ.
- Đối với phần vỉa hè phía trước của ca B1/B2, scope phải cho phép exclude, nhưng không xóa cấu kiện ảnh hưởng đường khí/lối thoát ở boundary.

## Kiểm tra lý thuyết và đo lường

Đặt profile theo loại: `epsilon_pos_m`, `epsilon_surface_m`, `epsilon_opening_m`, `epsilon_volume_fraction`, `epsilon_connectivity`, `min_effective_opening_cells`. Chốt trước chạy benchmark và ghi trong run manifest. Không hardcode 0.001m/5% cho mọi công trình.

## Exports đầu tiên

Bắt đầu với fixture wall + rectangular/round opening, rotated mapper, L-shaped slab, shaft crossing two storeys. Chỉ sau khi verified mới mở rộng các types khác. Output trả lỗi rõ, không silent omission.
