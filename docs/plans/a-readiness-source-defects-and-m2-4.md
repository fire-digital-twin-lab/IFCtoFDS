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
| 2 | **Quyết định `EXCLUDE` có duyệt** (loại khỏi FDS, trạng thái `EXCLUDED_APPROVED`; cần phiên bản chính sách, lý do, người duyệt, bằng chứng) cùng tuyên bố trạng thái cửa | Làm được ngay, không đổi mô hình | 21 cửa vắng mặt khỏi deck (lối đi mở); báo cáo **không sinh finding** cho phần tử bị loại, chỉ có số đếm; cần kỹ sư tuyên bố đóng hay mở | Kỹ sư review |
| 3 | **Thế bằng tấm mỏng đã duyệt** dựng từ thuộc tính IFC (`OverallWidth`, `OverallHeight`, vị trí đặt, bề dày của các vỏ đóng kín đo được 12 đến 49 mm, chưa xác nhận đó là cánh cửa) | Giữ được vai trò chắn dòng | Hình học dựng từ thuộc tính, không phải từ lưới lỗi: phải đo sai số và phê duyệt dung sai (`AGENTS.md`); cần cơ chế quyết định mới trong mapping | Kỹ sư duyệt, tôi cài đặt |
| 4 | Tự động sửa lưới | | **Loại:** dữ liệu cho thấy không có solid khôi phục được | |

**Đính chính:** bản đầu của tài liệu này nêu `accepted_source_defects` như phương án miễn trừ. Cơ chế đó chỉ nhận ba loại lỗi tự giao cắt (`COPLANAR_FACE_OVERLAP`, `TRIANGLE_CROSSING`, `COMPONENT_VOLUME_OVERLAP`) trên lưới đóng kín, **không áp dụng cho cạnh hở hay cạnh non-manifold**.

**Khuyến nghị:** phương án 1 cho 21 cửa. Dùng phương án 2 chỉ như bước tạm nếu chưa sửa được nguồn, và chỉ khi kỹ sư tuyên bố rõ trạng thái cửa. Phương án 3 chỉ khi kỹ sư muốn mô phỏng cửa đóng mà không sửa được nguồn.

### Có thật sự phải sửa file Revit không? (đo 2026-11-16)
**Không bắt buộc cho cả 21 cửa.** Đo bằng cách lấy mẫu 2.000 điểm trên bề mặt từng cửa và hỏi điểm đó nằm trong vật rắn nào của deck A (tường đã cắt lỗ). Tỷ lệ điểm nằm trong vật rắn cho biết tại chỗ đó deck có lối đi trống hay tường đặc:

| Nhóm | Số cửa | Tỷ lệ điểm cửa nằm trong vật rắn | Khi loại cửa khỏi deck |
| --- | ---: | --- | --- |
| Lấp một ô mở (`IfcOpeningElement`) của tường | 6 | 0,01 đến 0,02 (lối đi trống) | **Lối đi mở thật** |
| Không có quan hệ lấp, nhưng đứng trong khoảng trống | 2 | 0,01 và 0,02 | **Lối đi mở thật** |
| Không có quan hệ lấp, nằm trong tường đặc | 8 | 0,81 đến 0,83 | **Không đổi gì**: tường đặc đã chắn, tức mặc định là đóng |
| Không có quan hệ lấp, nửa trong tường | 5 | 0,26 đến 0,27 | Chưa rõ (có thể khung cửa nằm trong bề dày tường); cần xem từng cái |

Hệ quả:
- **8 cửa nằm trong tường đặc không cần sửa Revit.** Loại chúng bằng quyết định `EXCLUDE` không làm đổi mô phỏng.
- **8 cửa đứng trong lối đi trống (6 + 2)** là nơi việc thiếu cửa tạo ra lối đi mở. Nếu cửa thép được xem là mặc định đóng như cửa thang máy, loại cửa là **không bảo thủ**; muốn đóng thì cần có hình học cửa.
- **5 cửa nửa trong tường** cần xem từng cái trước khi kết luận.

Vì sao sửa Revit là cách ưu tiên (không phải duy nhất) cho nhóm 8 cửa trống:
1. Pipeline không tự sinh hình học. Dữ liệu cửa hiện không dựng lại được một solid hợp lệ (xem trên).
2. **Phương án thay bằng tấm mỏng dựng từ thuộc tính IFC** (`OverallWidth`, `OverallHeight`, vị trí đặt) là tính năng mới: quyết định mới trong mapping, dựng tấm xoay theo cửa (GEOM, vì mô hình bị xoay), cách xác minh khi không có solid nguồn để so, và dung sai được duyệt. Ước tính nhiều ngày công và cần duyệt thiết kế.
3. Sửa hai họ cửa trong Revit là một thay đổi nhỏ giải quyết cả nhóm, và dữ liệu đúng ở nguồn cũng có lợi cho mọi công cụ khác dùng cùng IFC.

Nếu không sửa được Revit, hai lựa chọn còn lại: loại cửa và **ghi rõ lối đi được mô hình hóa là mở** (đã có finding P2 cho từng cửa), hoặc làm tính năng tấm mỏng.

### Tường (1 phần tử)
Đã đo trên IFC nguồn: lưới chỉ 51 đỉnh, 88 mặt. 26 cạnh hở gom thành **hai cụm giống hệt nhau**, mỗi cụm khoảng 0,39 × 0,30 × 0,06 m (11 đỉnh, tổng chiều dài cạnh 1,14 m), ở hai cao độ gần nhau (z ≈ −5,64 và −5,44 m). Tức là hai lỗ xuyên nhỏ thiếu mặt bên, không phải tường hỏng cả khối. Nhưng khối bao của tường là 18,4 × 15,4 × 3,3 m, nên **loại cả tường vì hai lỗ nhỏ sẽ mở cả một vùng lớn** trong mô phỏng. **Khuyến nghị: sửa ở nguồn** (đóng hai lỗ trong Revit), không loại tường.

### Thử quyết định trên A (dry-run, 2026-11-16)
Chạy A với 22 quyết định `EXCLUDE` (21 cửa và tường) và 15 quyết định `REFERENCE_GEOMETRY` (giữ hình học tham chiếu, không xuất vào FDS), người duyệt ghi là bạn kèm chú thích "chờ kỹ sư xác nhận":

| | Trước | Sau (dry-run) |
| --- | --- | --- |
| Kết luận mapping | `REJECTED` | **`MAPPING_VERIFIED`** |
| Phần tử | 546 MATCHED, 22 UNSUPPORTED, 15 REVIEW_REQUIRED, 210 SEMANTIC_ONLY | 546 MATCHED, 22 `EXCLUDED_APPROVED`, 15 `REFERENCE_PRESERVED`, 210 SEMANTIC_ONLY |
| Finding | 44 (P1) và 1 (P2) | **0** |

Hai điều cần lưu ý:
1. **Báo cáo hết finding dù 22 phần tử vắng khỏi deck** (21 cửa, 1 tường lớn): người đọc chỉ thấy số đếm `EXCLUDED_APPROVED`. Nên hiển thị mỗi phần tử bị loại thành một finding P2 để không thể bỏ sót. Chưa làm.
2. `MAPPING_VERIFIED` ở đây chỉ nói các quyết định loại trừ đã được ghi và duyệt, không nói loại trừ đó đúng về vật lý (cửa vắng nghĩa là lối đi mở; loại tường mở cả một vùng).

**Cập nhật dry-run (cửa thang máy mặc định đóng, roadmap A7):** 6 phần tử thang máy chuyển từ `REFERENCE_GEOMETRY` sang `PASSIVE_OBSTACLE`. Chạy lại A với mã đã có finding loại trừ cho kết quả: `MAPPING_VERIFIED`, **552 MATCHED** (546 cũ và 6 phần tử thang máy nay được xuất thành vật rắn mỏng và đối chiếu khớp nguồn), 9 `REFERENCE_PRESERVED`, 210 `SEMANTIC_ONLY`, 22 `EXCLUDED_APPROVED`, và **đúng 22 finding P2** loại `scope` (mỗi phần tử bị loại một finding, nêu người duyệt và lý do). Chỉ còn ba cổng mô phỏng `INCONCLUSIVE` (`passage_resolution`, `solver` chưa chạy trong lượt này, `effective_geometry`).

Tệp quyết định (có mã cấu kiện thật) và danh sách bàn giao 21 cửa để sửa trong Revit (mã, tầng, họ cửa, kích thước, chỉ số lưới) nằm **ngoài repo** trong thư mục sao lưu cục bộ.

## 3. M2.4: `effective_geometry` trên A (và B)

### Kết quả solver trên ba model (2026-11-16, FDS 6.11.1, `T_END=0`)

| Model | `solver` | `effective_geometry` | `passage_resolution` | Ghi chú |
| --- | --- | --- | --- | --- |
| B | `PASS` | `INCONCLUSIVE` (218 GEOM) | `INCONCLUSIVE` (20 lỗ chưa đo) | `MAPPING_VERIFIED`, 24 s |
| A | `PASS` | `INCONCLUSIVE` (546 GEOM) | `INCONCLUSIVE` (177 lỗ chưa đo) | `REJECTED` (22 lỗi nguồn), 248 s |
| C, 8 tầng hầm | `PASS` | **`FAIL`**: "Mesh M1: Solver obstruction inventory differs from input" | **`FAIL`**: 43 lối đi hẹp hơn 2 ô (ô 0,2 m) | `REJECTED`; miền chỉ định bằng `--domain` |

Với C, miền (x từ −12 đến 89, y từ −1 đến 18, z từ −9 đến 1 m) được lấy từ deck PyroSim của C **chỉ cho phép thử này**, vì deck của ta không có `MESH` khi chưa khai báo miền. Cấu kiện của ta cao tới khoảng 38 m, nên có thể đã bị miền cắt; **chưa kiểm** xem đó có phải nguyên nhân của `effective_geometry` `FAIL` hay đó là lệch thật giữa deck và danh mục vật cản của solver. Lỗi này cần điều tra trước khi dùng kết luận cho C. 43 lối đi hẹp hơn 2 ô là kết quả hình học thật ở cỡ ô 0,2 m (cần cỡ ô mịn hơn hoặc xử lý lối đi).

### C: `effective_geometry` `FAIL` là báo động giả của cổng (đã điều tra)
Với C, cổng báo "danh mục vật cản của solver khác đầu vào" ở mesh M1: solver liệt kê 60 vật cản, đầu vào có 87 vật cản chạm M1. Cả 27 vật cản bị thiếu là lớp bọc và lót ống gió, và **cả 27 đều nằm trọn trong các `OBST` khai báo trước chúng**. Trong 54 `OBST` nằm trọn trong vật cản khác, 27 cái chỉ bị phủ bởi vật cản khai báo **trước** thì đều bị solver bỏ, còn 27 cái bị phủ bởi vật cản khai báo **sau** thì đều được liệt kê. Đã xác nhận bằng FDS 6.11.1 trên deck nhỏ (kể cả tấm mỏng hơn nửa ô lưới): FDS bỏ khỏi danh mục các vật cản nằm trọn trong vật cản đã khai báo. Đó là cách FDS xử lý vật cản thừa, không phải sai lệch hình học. Cổng đã được sửa (PR riêng, có fixture do FDS sinh ra và ca vẫn bị chặn); với dữ liệu thật của C kết quả chuyển từ `FAIL` sang `INCONCLUSIVE` vì một dầm có tọa độ rơi đúng giữa hai nút lưới (hòa nửa ô, chính sách hiện có coi là chưa chứng minh được). Lưu ý: kết quả mới chỉ khẳng định cổng không còn báo sai, chưa khẳng định hình học của C đúng.

### Phát hiện mới (đo 2026-11-16)
`solver` `PASS` ở cả A và B (FDS 6.11.1 khởi tạo thành công). Nhưng `effective_geometry` `INCONCLUSIVE` ở **cả hai** vì mọi phần tử đều là `GEOM` (A: 546, B: 218) và "đầu ra cut-cell của GEOM chưa được đọc từ SMV". Vậy M2.4 không riêng của A: B vốn `MAPPING_VERIFIED` cũng không có kết luận hình học hiệu dụng ở cấp mô phỏng.

### Phương án

| # | Phương án | Đánh giá |
| --- | --- | --- |
| a | **Kiểm cut-cell bằng probe DEVC** (khối khí và diện tích mặt mở theo ô lưới, đối chiếu giá trị giải tích) | Có nền sẵn: commit `b836cf2` trên nhánh cũ (4 tệp, 365 dòng) đã chạy với FDS 6.11.1 nhưng chỉ cho **một GEOM đơn lẻ** trong deck chẩn đoán riêng. Mở rộng ra cả deck cần nghiên cứu dung sai |
| b | Quay mô hình theo từng cánh để tường thẳng trục | **Không khả thi:** FDS dùng một khung trục duy nhất; A có nhiều cánh theo các hướng khác nhau, hướng trội khoảng 40° chỉ chiếm khoảng 14% số mặt (M2.1) |
| c | Xấp xỉ bậc thang bằng `OBST` theo lưới | Cần dung sai được duyệt. Bằng chứng từ deck PyroSim của A (cùng cách làm): IoU trung vị của tường chỉ 0,12 và 97% `OBST` là tấm mỏng. Không khuyến nghị cho tường |

### Khuyến nghị: phương án (a), làm theo bốn bước
1. **Đã làm:** đưa lại mô-đun probe cut-cell lên nhánh `feat/cutcell-probes` (commit `b836cf2`, cherry-pick sạch lên `main`). Test với FDS 6.11.1 đạt (tứ diện chuẩn khớp, phát hiện được dịch chuyển), test lưới và cổng nợ nguồn đạt.
2. **Đã làm một phần:** thí điểm trên 24 GEOM của A (`scripts/cutcell-pilot.py`), 19 phần tử đánh giá được, xem kết quả bên dưới.
3. **Chờ người duyệt:** chốt dung sai từ phân bố sai số đo được (tôi không tự đặt ngưỡng).
4. Chạy cho cả deck (ước khoảng 1.100 DEVC trong một lượt chẩn đoán `T_END` nhỏ) và cho `effective_geometry` `PASS` hoặc `FAIL` theo từng phần tử.

### Kết quả thí điểm (A, FDS 6.11.1, ô 0,2 m)
Mỗi phần tử chạy trong deck cô lập trên cùng lưới nút 0,2 m; giá trị kỳ vọng tính bằng boolean chính xác và đã được kiểm độc lập bằng lấy mẫu điểm. Mẫu: 514 trong 546 GEOM đủ điều kiện về kích thước (≤ 60.000 ô, nên **chưa có tường và sàn lớn**); chọn 24, đánh giá được 19 (4 không phải một vỏ đơn, 1 thiếu chỗ đặt probe).

- **Chỉ 17/514 phần tử (3,3%, đều là sàn) có từ 95% diện tích mặt song song với trục lưới.** Mọi cột, tường, cửa, thanh đều bị xoay so với lưới.
- **Khối khí cục bộ (114 probe):** trung vị sai số 4e-9 m³, nhưng đuôi dài: p90 = 1,2e-2 m³, tối đa 2,7e-2 m³ (3,3 ô lưới).
- **Phần tử dày (độ dày ước lượng ≥ 0,2 m, 7 cái):** sai số tương đối của khối khí toàn miền so với thể tích phần tử có trung vị 6e-5, tối đa 1,2e-3. FDS khớp rất tốt.
- **Phần tử mỏng (độ dày ước lượng < 0,2 m, 12 cái):** 6 cái chính xác, **6 cái FDS cho tổng thể tích rắn gấp 1,9 đến 4 lần thể tích thật** (phần thừa bằng 0,85 đến 3,0 lần thể tích phần tử; khí ít hơn kỳ vọng). FDS có vẻ làm dày các lớp mỏng. Độ dày ước lượng là V/(d1·d2) của khối bao nên chỉ là chỉ báo thô.
- **Diện tích mặt mở:** 5/17 (trục x), 5/13 (y) và 7/16 (z) probe lệch trên 1e-6 m², tối đa 0,12 m². Nhiều ca FDS báo mặt hở hoàn toàn (0,36 m²) khi giải tích còn một lớp mỏng. Ca đối xứng chuẩn (tứ diện) và hộp xoay 40° cho kết quả đúng ở cả ba trục, nên đây không phải lỗi phép đo theo trục.

**Ý nghĩa:** với phần tử dày, FDS giữ hình học cut-cell chính xác. Với lớp mỏng, FDS có thể thay đổi thể tích đáng kể, nên `effective_geometry` ở cấp phần tử có khả năng phân biệt thật, không chỉ là thủ tục. **Giới hạn:** mẫu nhỏ, chưa có tường và sàn lớn (loại phần tử chiếm đa số của A), nên chưa đủ để chốt dung sai hay khái quát cho cả deck. Cần mở rộng mẫu (cắt cửa sổ đo trong phần tử lớn thay vì dựng cả phần tử) trước bước 3.

Cho đến khi xong, kết luận đúng là: mapping có thể `MAPPING_VERIFIED`, còn hình học hiệu dụng ở cấp solver của các phần tử `GEOM` là `INCONCLUSIVE`, và báo cáo phải nêu điều đó.

## 4. Trạng thái duyệt

**2026-11-16: đã duyệt toàn bộ các khuyến nghị ở mục 4 bản đầu**, kèm hai chỉ dẫn mới: cửa thang máy mặc định đóng (ghi ở roadmap A7 trước khi áp dụng) và cho phép chốt dung sai cut-cell nếu hợp lý.

| Việc | Trạng thái |
| --- | --- |
| Có phải sửa Revit không | **Đã phân tích** (mục 2): không bắt buộc cho cả 21 cửa; chỉ cần cho 8 cửa đứng trong lối đi trống nếu muốn cửa đóng; 5 cửa nửa trong tường cần xem từng cái |
| 21 cửa: sửa ở nguồn | **Còn lại, phía người giữ mô hình**, ưu tiên 8 cửa trong lối đi trống. Danh sách bàn giao đã lập, ngoài repo |
| Tường: 26 cạnh hở | **Đã làm.** Hai lỗ nhỏ khoảng 0,39 × 0,30 × 0,06 m; khuyến nghị sửa ở nguồn, không loại tường |
| Cửa thang máy mặc định đóng | **Đã ghi (A7) và áp dụng.** 6 phần tử thành `PASSIVE_OBSTACLE`, đã chạy A: 552 MATCHED, `MAPPING_VERIFIED`. Kỹ sư cần xác nhận |
| 9 phần tử `REVIEW_REQUIRED` còn lại (giá đỡ mái, lan can) | **Đã thử** với `REFERENCE_GEOMETRY` (không xuất vào FDS). Kỹ sư xác nhận |
| Người duyệt ký các quyết định | **Còn lại.** Người duyệt hiện ghi là bạn kèm chú thích chờ kỹ sư xác nhận |
| Dung sai cut-cell | **Đã chốt tạm thời (A7):** khối khí sai ≤ 1% thể tích phần tử; diện tích mặt mở chỉ báo cáo. Xem lại sau khi mở rộng mẫu. Chưa nối vào cổng nào |
| M2.4: hướng (a) | **Đã làm bước 1 và một phần bước 2** (mục 3); chờ mở rộng mẫu |
| Hiển thị phần tử bị loại thành finding P2 | **Đã làm** (PR riêng): 22 finding trong lần chạy A |
| `effective_geometry` của C báo `FAIL` | **Đã điều tra và sửa cổng** (mục 3): báo động giả do FDS bỏ vật cản thừa |
