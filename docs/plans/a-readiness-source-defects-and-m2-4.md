# A: 22 lỗi bề mặt nguồn và M2.4 (`effective_geometry`)

**Mốc** · 2026-11-16, `main` `af3ec8d`. Dữ liệu thật dùng bí danh A, B, C; chỉ ghi số tổng hợp. Tài liệu này phân tích và đề xuất, **không đổi mã hay quyết định nào**. Các mục cần người duyệt ghi rõ ở cuối.

## 1. Hiện trạng A

A (`REJECTED`) bị chặn bởi hai cổng mapping `FAIL`, cả hai đều đến từ cùng 22 phần tử:

| Cổng | Trạng thái | Nguyên nhân |
| --- | --- | --- |
| `geometry`, `geometry_preservation` | `FAIL` | 22 phần tử `UNSUPPORTED` (21 cửa, 1 tường) không có solid nguồn hợp lệ |
| `representation` | `INCONCLUSIVE` | 15 phần tử `REVIEW_REQUIRED` (10 proxy, 5 lan can) chờ quyết định duyệt |
| `structural_completeness` | `INCONCLUSIVE` | 1 tường bị giữ lại chưa có kết luận duyệt |
| `solver` | `PASS` | FDS 6.11.1 khởi tạo thành công trên deck A (2026-11-16, 248 s) |
| `effective_geometry`, `passage_resolution` | `INCONCLUSIVE` | cổng mô phỏng, không thuộc kết luận mapping (xem mục 3) |

Điều kiện để A đạt `MAPPING_VERIFIED`: xử lý 22 phần tử, ghi quyết định cho 15 phần tử cần duyệt và kết luận cho tường bị giữ lại. Ba cổng mô phỏng vẫn `INCONCLUSIVE` sau đó (mục 3).

## 2. Hai mươi hai lỗi bề mặt

**Đây là lỗi hệ thống của hai họ cửa Revit, không phải 22 lỗi riêng lẻ.**

| Nhóm | Số lượng | Tầng | Dấu hiệu |
| --- | ---: | --- | --- |
| Cửa thép 2 cánh (một họ) | 16 | hầm 1 và hầm 2 | 3.814 hoặc 3.826 cạnh hở, 9 đến 21 cạnh non-manifold, 847 đến 858 cạnh ngược chiều |
| Cửa thép 1 cánh (một họ) | 5 | hầm 1 và hầm 2 | 385 hoặc 389 cạnh hở, 2 hoặc 3 cạnh non-manifold, 1.333 đến 1.581 cạnh ngược chiều |
| Tường `IfcWall` | 1 | hầm 2 | 26 cạnh hở, 1 non-manifold, 26 ngược chiều; khối bao 18,4 × 15,4 × 3,3 m |

Mỗi họ cho cùng "dấu vân tay" lưới ở mọi chiếc, nên nguyên nhân nằm ở họ cửa, không phải do lỗi ngẫu nhiên.

### Nguyên nhân (đã đo trên IFC nguồn)
Thân cửa là `IfcMappedItem` chứa `IfcFaceBasedSurfaceModel` (tập mặt, không phải solid). Trên một cửa 2 cánh: 29 tập mặt, trong đó 4 đóng kín và 25 mảnh hở. Trên một cửa 1 cánh: 17 tập mặt, 5 đóng kín và 12 hở. Các mảnh hở có tổng diện tích khoảng 55 đến 59 m² mỗi cửa (chi tiết phụ kiện rất mịn) và mảnh lớn nhất trải suốt kích thước cửa (1.200 × 100 × 2.200 mm). Các tập đóng kín chỉ bao khoảng 0,1 đến 1,4 lít.

**Kết luận kỹ thuật:** không dựng lại được một solid cánh cửa hợp lệ từ chính dữ liệu nguồn. Cách "chỉ giữ các vỏ đóng kín" cho hình học sai (mất mảnh lớn nhất), và hàn đỉnh hay lấp lỗ tự động sẽ tạo ra hình học không có trong nguồn. Điều này khớp kết luận M1.1 trước đó.

### Ảnh hưởng nếu bỏ qua các cửa
Chỉ 6 trong 21 cửa lấp một lỗ mở (`IfcRelFillsElement`) của một tường chủ. 15 cửa còn lại không có quan hệ lấp lỗ trong IFC. Cửa không có trong deck đồng nghĩa lối đi ở đó **mở** trong mô phỏng. Nếu thực tế các cửa thép này đóng, đây là sai khác **không bảo thủ** cho bài toán kiểm soát khói.

### Phương án

| # | Phương án | Ưu | Nhược | Ai làm |
| --- | --- | --- | --- | --- |
| 1 | **Sửa ở nguồn:** xuất lại hai họ cửa với chi tiết thô hoặc ẩn phụ kiện (hoặc thân dạng khối đặc) | Một thay đổi sửa cả 21 chiếc; không cần miễn trừ; pipeline xác minh bình thường | Cần truy cập Revit | Người giữ mô hình |
| 2 | **Miễn trừ có duyệt** (`accepted_source_defects`: digest lưới, loại lỗi, người duyệt) cùng quyết định rõ trạng thái cửa | Làm được ngay, không đổi mô hình | 21 cửa vắng mặt khỏi deck (lối đi mở); mỗi mục thành finding P2; cần kỹ sư tuyên bố cửa đóng hay mở | Kỹ sư review |
| 3 | **Thế bằng tấm mỏng đã duyệt** dựng từ thuộc tính IFC (`OverallWidth`, `OverallHeight`, vị trí đặt, bề dày của các vỏ đóng kín đo được 12 đến 49 mm, chưa xác nhận đó là cánh cửa) | Giữ được vai trò chắn dòng | Hình học dựng từ thuộc tính, không phải từ lưới lỗi: phải đo sai số và phê duyệt dung sai (`AGENTS.md`); cần cơ chế quyết định mới trong mapping | Kỹ sư duyệt, tôi cài đặt |
| 4 | Tự động sửa lưới | | **Loại:** dữ liệu cho thấy không có solid khôi phục được | |

**Khuyến nghị:** phương án 1 cho 21 cửa. Dùng phương án 2 chỉ như bước tạm kèm quyết định thận trọng (coi cửa là đóng) nếu chưa sửa được nguồn. Phương án 3 chỉ khi kỹ sư muốn mô phỏng cửa đóng mà không sửa được nguồn.

### Tường (1 phần tử)
Khác với cửa, lưới tường gần hợp lệ (26 cạnh hở). Nhưng khối bao 18,4 × 15,4 × 3,3 m cho thấy đây có thể là phần tử lớn: miễn trừ sẽ bỏ nó khỏi deck, ảnh hưởng lớn hơn nhiều so với một cửa. Cần **xem vị trí 26 cạnh hở** (khe hở nhỏ hay lỗ lớn) rồi chọn: sửa ở nguồn, hoặc miễn trừ có duyệt kèm ghi nhận thể tích bị bỏ. Chưa làm bước kiểm này.

## 3. M2.4: `effective_geometry` trên A (và B)

### Kết quả solver trên ba model (2026-11-16, FDS 6.11.1, `T_END=0`)

| Model | `solver` | `effective_geometry` | `passage_resolution` | Ghi chú |
| --- | --- | --- | --- | --- |
| B | `PASS` | `INCONCLUSIVE` (218 GEOM) | `INCONCLUSIVE` (20 lỗ chưa đo) | `MAPPING_VERIFIED`, 24 s |
| A | `PASS` | `INCONCLUSIVE` (546 GEOM) | `INCONCLUSIVE` (177 lỗ chưa đo) | `REJECTED` (22 lỗi nguồn), 248 s |
| C, 8 tầng hầm | `PASS` | **`FAIL`**: "Mesh M1: Solver obstruction inventory differs from input" | **`FAIL`**: 43 lối đi hẹp hơn 2 ô (ô 0,2 m) | `REJECTED`; miền chỉ định bằng `--domain` |

Với C, miền (x từ −12 đến 89, y từ −1 đến 18, z từ −9 đến 1 m) được lấy từ deck PyroSim của C **chỉ cho phép thử này**, vì deck của ta không có `MESH` khi chưa khai báo miền. Cấu kiện của ta cao tới khoảng 38 m, nên có thể đã bị miền cắt; **chưa kiểm** xem đó có phải nguyên nhân của `effective_geometry` `FAIL` hay đó là lệch thật giữa deck và danh mục vật cản của solver. Lỗi này cần điều tra trước khi dùng kết luận cho C. 43 lối đi hẹp hơn 2 ô là kết quả hình học thật ở cỡ ô 0,2 m (cần cỡ ô mịn hơn hoặc xử lý lối đi).

### Phát hiện mới (đo 2026-11-16)
`solver` `PASS` ở cả A và B (FDS 6.11.1 khởi tạo thành công). Nhưng `effective_geometry` `INCONCLUSIVE` ở **cả hai** vì mọi phần tử đều là `GEOM` (A: 546, B: 218) và "đầu ra cut-cell của GEOM chưa được đọc từ SMV". Vậy M2.4 không riêng của A: B vốn `MAPPING_VERIFIED` cũng không có kết luận hình học hiệu dụng ở cấp mô phỏng.

### Phương án

| # | Phương án | Đánh giá |
| --- | --- | --- |
| a | **Kiểm cut-cell bằng probe DEVC** (khối khí và diện tích mặt mở theo ô lưới, đối chiếu giá trị giải tích) | Có nền sẵn: commit `b836cf2` trên nhánh cũ (4 tệp, 365 dòng) đã chạy với FDS 6.11.1 nhưng chỉ cho **một GEOM đơn lẻ** trong deck chẩn đoán riêng. Mở rộng ra cả deck cần nghiên cứu dung sai |
| b | Quay mô hình theo từng cánh để tường thẳng trục | **Không khả thi:** FDS dùng một khung trục duy nhất; A có nhiều cánh theo các hướng khác nhau, hướng trội khoảng 40° chỉ chiếm khoảng 14% số mặt (M2.1) |
| c | Xấp xỉ bậc thang bằng `OBST` theo lưới | Cần dung sai được duyệt. Bằng chứng từ deck PyroSim của A (cùng cách làm): IoU trung vị của tường chỉ 0,12 và 97% `OBST` là tấm mỏng. Không khuyến nghị cho tường |

### Khuyến nghị: phương án (a), làm theo bốn bước
1. Đưa lại mô-đun probe cut-cell lên `main` (không đổi hành vi hiện tại).
2. **Thí điểm trên 20 đến 30 phần tử GEOM** phân tầng theo loại và hướng, ở cỡ ô thực tế (0,2 m): đo sai số của khối khí và diện tích mặt mở của FDS so với giá trị giải tích chính xác.
3. **Người duyệt chốt dung sai** từ phân bố sai số đo được (tôi không tự đặt ngưỡng).
4. Chạy cho cả deck (ước khoảng 1.100 DEVC trong một lượt chẩn đoán `T_END` nhỏ) và cho `effective_geometry` `PASS` hoặc `FAIL` theo từng phần tử.

Cho đến khi xong, kết luận đúng là: mapping có thể `MAPPING_VERIFIED`, còn hình học hiệu dụng ở cấp solver của các phần tử `GEOM` là `INCONCLUSIVE`, và báo cáo phải nêu điều đó.

## 4. Cần người duyệt

| Việc | Chọn |
| --- | --- |
| 21 cửa: phương án 1, 2 hay 3 | Sửa nguồn (khuyến nghị), miễn trừ, hoặc tấm mỏng |
| Nếu miễn trừ cửa: trạng thái cửa trong mô phỏng | Đóng hay mở, kèm người chịu trách nhiệm |
| 1 tường: kiểm 26 cạnh hở rồi quyết định | Cho phép tôi mở phần tử để xem vị trí lỗ |
| 15 phần tử `REVIEW_REQUIRED` (10 proxy, 5 lan can) | Quyết định từng loại (giữ thụ động, loại có lý do) |
| M2.4: duyệt hướng (a) và cho phép chạy thí điểm | Có/không; dung sai chốt sau thí điểm |
