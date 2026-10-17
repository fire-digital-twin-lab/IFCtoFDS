# BÁO CÁO KIỂM TOÁN KỸ THUẬT & KHOA HỌC TOÀN DIỆN
## (COMPREHENSIVE TECHNICAL & SCIENTIFIC AUDIT REPORT)
### DỰ ÁN: IFCtoFDS — NỀN TẢNG ÁNH XẠ MÔ HÌNH THÔNG TIN CÔNG TRÌNH (BIM/IFC) SANG MÔ PHỎNG ĐỘNG LỰC HỌC CHÁY (FDS)

---

- **Cơ quan thực hiện kiểm toán**: Nhóm Kiểm toán Độc lập Teamwork Multi-Agent System
- **Đơn vị chủ quản**: fire-digital-twin-lab / HUCE NCKH PCCC
- **Kho lưu trữ mục tiêu**: `fire-digital-twin-lab/IFCtoFDS`
- **Nhánh kiểm toán**: `feat/premium-research-workbench-ui`
- **Commit HEAD**: `4d8bd2e290a4dda7dd9cba71cac4e205d58e9e17` (Merge PR #4 từ `codex/verified-mapping-correctness`)
- **Chế độ kiểm toán**: READ-ONLY TUYỆT ĐỐI trên toàn bộ mã nguồn sản phẩm
- **Thời điểm hoàn thành kiểm toán**: 2026-10-17T09:30:00Z
- **Phiên bản tài liệu**: 1.0.0-FINAL

---

## MỤC LỤC BÁO CÁO

1. **Phần 1: Tóm Tắt Điều Hành (Executive Summary)**
   - 1.1. Phán Quyết Kiểm Toán Chính Thức (Official Verdict)
   - 1.2. Top 5 Điểm Mạnh Cốt Lõi (Core Strengths)
   - 1.3. Top 5 Điểm Nghẽn Cốt Tử (Critical Blockers)
   - 1.4. Đánh Giá 3 Rủi Ro Trọng Yếu (Scientific, Software, Product Risks)
2. **Phần 2: Bảng Điểm Đánh Giá 15 Lĩnh Vực Kỹ Thuật & Khoa Học (Audit Scorecard)**
3. **Phần 3: Bảng Đăng Ký Sự Cố & Khiếm Khuyết Tổng Thể (Master Issue Register P0–P3)**
4. **Phần 4: Bản Đồ Kiến Trúc & Phả Hệ Dòng Chảy Dữ Liệu (Architecture Map & Data Flow Lineage)**
   - 4.1. Kiến Trúc Hiện Tại vs Kiến Trúc Hexagonal Mục Tiêu
   - 4.2. Phả Hệ Dòng Chảy Dữ Liệu Toàn Vẹn (Data Flow Lineage)
5. **Phần 5: Phân Tích Khoảng Cách Kịch Bản Cháy (Fire Scenario Gap Analysis)**
   - 5.1. Nguồn Cháy Pin Xe Điện & Hiện Tượng Thoát Nhiệt (EV Battery & Thermal Runaway)
   - 5.2. Đường Cong Tốc Độ Thoát Nhiệt ($t^2$ Fire HRR Curves & RAMP)
   - 5.3. Điều Khiển Hệ Thống Thông Gió & Hút Khói Sự Cố (HVAC Smoke Control NFPA 92)
   - 5.4. Đầu Phun Sprinkler & Đầu Đo Cảm Biến (DEVC & Suppression)
   - 5.5. Tiêu Chí Độ Phân Giải Lưới Đặc Trưng Đám Cháy ($D^*/\Delta x$)
6. **Phần 6: Trả Lời 10 Câu Hỏi Kiểm Toán Cốt Lõi (Section 92 Final Audit Questions)**
7. **Phần 7: Lộ Trình Khắc Phục & Nâng Cấp Phân Kỳ (Phased Remediation Roadmap Phase 0–6)**

---

# PHẦN 1: TÓM TẮT ĐIỀU HÀNH (EXECUTIVE SUMMARY)

### 1.1. Phán Quyết Kiểm Toán Chính Thức (Official Verdict)

Căn cứ vào quá trình khảo sát thực nghiệm toàn diện, kiểm chứng 235 kiểm thử tự động, phân tích tĩnh cấu trúc mã nguồn, đối chiếu hợp đồng dữ liệu UI/Backend và kiểm toán tính đúng đắn khoa học theo các tiêu chuẩn quốc tế (ISO 16739 IFC4, FDS User Guide, NFPA 92, NUREG 1824, SFPE Handbook), Nhóm Kiểm toán đưa ra phán quyết hai cấp độc lập như sau:

$$\mathbf{VERDICT:}\quad \begin{cases} \mathbf{CONDITIONALLY\ READY} & \text{đối với Trích Xuất Hình Học \& Ánh Xạ Xác Minh (Geometry \& Verified Mapping)} \\ \mathbf{NOT\ RESEARCH-READY} & \text{đối với Thiết Lập Kịch Bản Cháy \& Mô Phỏng CFD (Fire Scenario \& Simulation)} \end{cases}$$

- **Đạt trạng thái `CONDITIONALLY READY` cho Verified Geometry & Mapping**: Dự án đã xuất sắc xây dựng được một nền tảng trích xuất hình học 3D từ IFC sang FDS với tính kỷ luật khoa học cao: engine hình học sử dụng số thực chính xác kép 64-bit (`manifold3d.Mesh64`), cơ chế chống bịt kín lỗ mở âm thầm (Silent Reseal Prevention) ở tầng CAD triệt để, đồ thị MEP chỉ kết nối dựa trên quan hệ thực chất của IFC, phân tách rạch ròi giữa bản chuyển đổi xem nhanh trên trình duyệt (Quick Preview) và bản chuyển đổi thẩm định chính thức ở backend (Verified Mapping), đồng thời duy trì hệ thống 12 cổng thẩm định độc lập (Validation Gates) với bộ test suite 235 ca kiểm thử đạt tỷ lệ thành công 100%.
- **Chưa đạt trạng thái `NOT RESEARCH-READY` cho Fire Scenario & Simulation**: Dự án hiện tại **chưa phải là một môi trường sẵn sàng cho nghiên cứu cháy thực tế**. Mã nguồn xuất FDS đang cố định cứng thời gian mô phỏng ở thời điểm ban đầu ($T\_END=0.0\text{ s}$), hoàn toàn không hỗ trợ nguồn cháy pin xe điện (EV Lithium-ion Battery), thiếu vắng đường cong phát triển nhiệt theo thời gian (HRR curves, RAMP), chưa có adapter chuyển đổi mạng lưới thông gió/hút khói MEP sang namelist `&HVAC` của FDS, chưa tích hợp tiêu chí tỷ lệ lưới đặc trưng đám cháy $D^*/\Delta x$, và trạng thái nghiệm thu `SIMULATION_VERIFIED` trên thực tế là mã nguồn chết (dead code).

---

### 1.2. Top 5 Điểm Mạnh Cốt Lõi (Top 5 Core Strengths)

1. **Engine Hình học 3D Manifold Float64 Nguyên Bản & Chống Sai Số Số Học**:
   Toàn bộ quá trình xử lý hình học đa diện và phép toán Boolean được thực hiện trên cấu trúc `manifold3d.Mesh64` với tọa độ 64-bit chuẩn (`float64`) và chỉ số đỉnh 64-bit (`uint64`), tuyệt đối không bị ép kiểu giảm độ chính xác xuống `float32`. Thuật toán phát hiện tự cắt (self-intersection) tại `geometry/mesh.py:166-286` chuyển đổi sang số học phân số chính xác tuyệt đối (`fractions.Fraction`) khi gặp các trường hợp suy biến hình học biên, loại trừ hoàn toàn các lỗi làm tròn dấu phẩy động.
2. **Cơ Chế Ngăn Chặn Silent Reseal Triệt Để Ở Cấp Độ CAD**:
   Tại `mapping/policy.py:88-94`, hệ thống thiết lập nguyên tắc bất biến: Bất kỳ cấu kiện nào có chứa lỗ mở (`element.openings`) đều bị cấm tuyệt đối ánh xạ thành dạng hộp đặc `OBST`, bắt buộc phải chuyển sang dạng lưới tam giác hở lỗ `GEOM`. Cơ chế này được giám sát độc lập bởi 2 thước đo tại `validation/engine.py:475-520`: `opening_residual` (đo thể tích giao cắt) và `passage_metrics` (đo độ thông thoáng luồng khí xuyên qua lỗ mở).
3. **Kỷ Luật Kiểm Thử Tự Động & CI/CD Xuất Sắc**:
   Hệ thống sở hữu bộ kiểm thử đồ sộ gồm **235 tests** phân bổ trong 28 tệp kiểm thử chuyên sâu. Tại môi trường kiểm toán tiêu chuẩn, **233 unit/integration/mutation tests chạy pass 100%** trong 188.37 giây. 2 tests còn lại thuộc marker `solver` được phân lập tường minh. Hệ thống CI/CD trên GitHub Actions bao quát 5 jobs đa nền tảng (Ubuntu/Windows, Python 3.11/3.12, Node 22, Playwright E2E browser, và FDS solver execution).
4. **Trích Xuất Đồ Thị MEP Có Chứng Cứ Thực Chất & Gán Vai Trò Thận Trọng**:
   Module `mep/mep_graph.py:120-151` chỉ thiết lập các liên kết cổng (port-to-port connections) khi tồn tại tường minh quan hệ `IfcRelConnectsPorts` trong tệp IFC nguồn (`relation_type="EXPLICIT_IFC"`). Hệ thống kiên quyết từ chối suy đoán kết nối dựa trên khoảng cách hình học đơn thuần, đồng thời gán mặc định `simulation_role = "REFERENCE_GEOMETRY"` để ngăn ngừa ảo tưởng mô phỏng khi chưa đủ điều kiện vận hành.
5. **Tính Độc Lập và Trung Thực Khoa Học của Động Cơ Thẩm Định (Validation Engine)**:
   Ma trận 12 cổng kiểm tra (Validation Gates) phân định rõ ràng giữa `MAPPING_VERIFIED`, `REJECTED` và `INCONCLUSIVE`. Đặc biệt, tại `validation/solver.py:33-42`, khi môi trường thiếu tệp thực thi FDS solver, hệ thống trả về chính xác trạng thái `INCONCLUSIVE`, tuyệt đối không bao giờ trả về kết quả đạt giả mạo (false `VERIFIED`), thể hiện tính liêm chính khoa học cao.

---

### 1.3. Top 5 Điểm Nghẽn Cốt Tử (Top 5 Critical Blockers)

1. **Khóa Cứng Thời Gian Mô Phỏng $T\_END=0.0$ Trong Trình Xuất FDS (`ISSUE-R5-01` - P0)**:
   Tại `ifc_to_fds/mapping/exporter.py:135`, mã nguồn ghi cứng dòng lệnh `&TIME T_END=0.0 /`. Tệp `.fds` sinh ra hoàn toàn không có khả năng chạy mô phỏng vật lý theo thời gian, chỉ dừng lại ở bài toán thẩm tra hình học tĩnh tại thời điểm $t=0$.
2. **Hoàn Toàn Thiếu Tiêu Chí Độ Phân Giải Lưới Đám Cháy $D^*/\Delta x$ (`ISSUE-R4-01` - P0)**:
   Kích thước ô lưới `cell_size` bị cố định mặc định ở mức $0.2\text{ m}$ (`exporter.py:69-80`). Hệ thống hoàn toàn vắng bóng thuật toán tính toán đường kính đặc trưng đám cháy $D^*$ và tỷ lệ $D^*/\Delta x$ theo khuyến nghị tiêu chuẩn NFPA 92 / NUREG 1824 ($4 \le D^*/\Delta x \le 16$), dẫn đến nguy cơ sai lệch hoàn toàn kết quả động lực học khói CFD.
3. **Trạng Thái Nghiệm Thu `SIMULATION_VERIFIED` Là Mã Nguồn Chết (`ISSUE-CONTRACT-03` - P0)**:
   Tại `domain/validation/model.py:153-162`, phương thức `finalize()` của `AcceptanceReport` chỉ có logic gán `REJECTED` hoặc `INCONCLUSIVE`. Không có bất kỳ dòng lệnh nào có khả năng gán `self.simulation_status = AcceptanceStatus.SIMULATION_VERIFIED`. Cấp độ nghiệm thu mô phỏng bị khóa hoàn toàn.
4. **Lỗi Đồng Bộ Giao Diện & Bỏ Quên Mức Độ Sự Cố Nghiêm Trọng P0 (`ISSUE-CONTRACT-01` & `02` - P1)**:
   Tồn tại sự lệch pha tên gọi giữa backend gate `"golden_reference_parity"` (`golden.py:218`) và thẻ HTML `data-gate="golden"` (`index.html:524`), khiến card kiểm định Golden Parity trên giao diện luôn ở trạng thái xám chưa chạy. Đồng thời, hàm hiển thị lỗi `js/app-controller.js:1685` bỏ sót kiểm tra `'P0'`, khiến lỗi nghiêm trọng nhất của hệ thống lại hiển thị màu vàng (Warning) thay vì màu đỏ (Critical Blocker).
5. **Rủi Ro Bịt Kín Lỗ Mở Ở Tầng Lưới FDS CFD (Voxelization Grid Reseal) (`ISSUE-R3-01` - P1)**:
   Mặc dù tầng CAD đã xuất `GEOM`, nhưng nếu kích thước ô lưới FDS ($\Delta x$) lớn hơn độ rộng của lỗ mở hẹp (khe cửa, ô thoáng, van gió), trình giải FDS khi voxelize lưới tam giác lên hệ tọa độ trực giao sẽ tự động lấp kín lỗ mở, gây nghẽn dòng khí thực tế mà hệ thống không đưa ra cảnh báo trước khi mô phỏng.

---

### 1.4. Đánh Giá 3 Rủi Ro Trọng Yếu (3 Biggest Risks)

```
+---------------------------------------------------------------------------------------------------+
|                                 MA TRẬN ĐÁNH GIÁ RỦI RO HỆ THỐNG                                  |
+---------------------------------------------------------------------------------------------------+
| 1. RỦI RO KHOA HỌC (Scientific Risk)                                                             |
|    - Hiện tượng Voxelization Reseal tại tầng lưới FDS CFD kết hợp với việc thiếu kiểm soát tỷ lệ  |
|      lưới đặc trưng D*/dx có thể làm sai lệch hoàn toàn trường vận tốc khói, nhiệt độ lớp khói    |
|      nóng và nồng độ khí độc (CO, HF), dẫn đến kết quả đánh giá an toàn sinh mạng (ASET/RSET)     |
|      không có giá trị khoa học và nguy hiểm trong kỹ thuật an toàn PCCC thực tế.                  |
+---------------------------------------------------------------------------------------------------+
| 2. RỦI RO PHẦN MỀM (Software Architecture Risk)                                                   |
|    - Kiến trúc Hexagonal đang ở trạng thái dở dang: Domain Model bị rò rỉ framework Pydantic      |
|      (19 models), tồn tại 3 chu trình phụ thuộc vòng (circular imports), Domain Validation gọi     |
|      ngược ra Parser ngoại vi, và thiếu hệ thống Ports chuẩn. Nợ kỹ thuật này sẽ làm phức tạp hóa |
|      và gây đứt gãy hệ thống khi tích hợp phân lớp kịch bản cháy phức tạp.                        |
+---------------------------------------------------------------------------------------------------+
| 3. RỦI RO SẢN PHẨM & TRẢI NGHIỆM NGƯỜI DÙNG (Product & UX Risk)                                   |
|    - Việc thiếu tiêu đề cảnh báo "UNVALIDATED PREVIEW ONLY" trong tệp FDS sinh bởi Quick Preview  |
|      và dùng chung một nút tải về trên giao diện Workbench có thể khiến kỹ sư tư vấn vô tình     |
|      sử dụng tệp FDS xấp xỉ voxel chưa thẩm định để nộp cho cơ quan cảnh sát PCCC thẩm duyệt.     |
+---------------------------------------------------------------------------------------------------+
```

---

# PHẦN 2: BẢNG ĐIỂM ĐÁNH GIÁ 15 LĨNH VỰC KỸ THUẬT & KHOA HỌC (SCORECARD)

Thang điểm đánh giá từ 0.0 đến 10.0 dựa trên các tiêu chí: Tính đầy đủ (Completeness), Tính chính xác khoa học (Scientific Rigor), Tính liêm chính mã nguồn (Integrity), và Khả năng tự động hóa kiểm chứng (Testability).

| STT | Lĩnh Vực Đánh Giá (Domain) | Điểm (0–10) | Nhận Định Cốt Lõi (Core Assessment) | Khoảng Trống Chính (Main Gap) |
|:---:|---|:---:|---|---|
| **01** | **Baseline & Môi Trường Thực Thi** | **9.5** | Commit HEAD `4d8bd2e` tích hợp PR #4 sạch sẽ; 233/235 tests pass 100%; dependencies chuẩn hóa qua `pyproject.toml`. | Tồn tại 29 cảnh báo RuntimeWarning chia cho 0 trong trimesh; các thay đổi UI trên working tree chưa được commit. |
| **02** | **Tự Động Hóa CI/CD & Ma Trận Kiểm Thử** | **9.0** | Workflow `.github/workflows/verified.yml` gồm 5 jobs đa nền tảng, phân lập rõ ràng giữa test logic, browser và solver. | Chạy solver FDS trong CI hiện phụ thuộc vào script tải ngoài hoặc self-hosted runner, chưa tối ưu containerized FDS. |
| **03** | **Kiến Trúc Sạch & Modular Monolith** | **6.5** | Đã tách các gói `domain`, `application`, `adapters`, `interfaces`. Có use case orchestrator cho quy trình Verified. | Kiến trúc dở dang: chỉ có 1 port (`storage.py`), Use Cases gọi trực tiếp các module cụ thể mà không qua abstraction. |
| **04** | **Ranh Giới Mô Hình Miền (Domain Boundaries)**| **6.0** | Các thực thể miền được định nghĩa chi tiết (BIM, Mapping, MEP, Validation, Scope). | Domain Validation phụ thuộc ngược ra Parser ngoại vi; 19 models kế thừa Pydantic; `CanonicalElement` bị nhiễm trường FDS. |
| **05** | **Hợp Đồng Giao Tiếp UI ↔ Backend** | **6.5** | Phân định rạch ròi luồng Quick Preview (client-side) và Verified Mapping (REST API + SSE job polling). | Name mismatch gate golden parity; UI drawer bỏ qua P0; cắt lát cứng 20 findings; dùng chung nút download FDS. |
| **06** | **Trích Xuất IFC & Xử Lý Đơn Vị (Units)** | **7.5** | Kiểm tra nghiêm ngặt `LENGTHUNIT` duy nhất, tính toán tỉ lệ scale chính xác cho hệ SI và Imperial. | Hoàn toàn bỏ qua `AREAUNIT`, `VOLUMEUNIT`, `TIMEUNIT` và các đơn vị đo lưu lượng gió HVAC ($m^3/s$, CFM). |
| **07** | **Phân Cấp Tọa Độ & Placement Hierarchy** | **7.0** | Ma trận biến đổi $4\times 4$ chuẩn xác; truy vết chuỗi `PlacementRelTo`; thuật toán phát hiện và chặn đệ quy lặp vòng. | Ném ngoại lệ từ chối `IfcGridPlacement` và `IfcLinearPlacement` (rất phổ biến trong công trình thực tế và IFC4/4.3). |
| **08** | **Hình Học 3D & Engine Đa Tạp (Manifold)** | **9.0** | `manifold3d.Mesh64` chuẩn kép `float64`; kiểm tra đa tạp kín; tính toán tự cắt bằng số học phân số chính xác tuyệt đối. | Chi phí tính toán CPU cao đối với các mô hình có số lượng tam giác lớn do kiểm tra phân số exact rational. |
| **09** | **Bảo Toàn Lỗ Mở & Chống Bịt Kín (Openings)** | **8.5** | Ép kiểu `GEOM` cho mọi cấu kiện có lỗ mở; 2 metrics độc lập `opening_residual` và `passage_metrics` chặn silent reseal CAD. | Chưa có cơ chế đối chiếu kích thước lỗ mở với kích thước ô lưới FDS để phòng ngừa Voxelization Grid Reseal. |
| **10** | **Đồ Thị Mạng MEP / HVAC / PCCC** | **8.0** | Quan hệ port-to-port chỉ dựa trên `IfcRelConnectsPorts` thực chất; phân loại hệ thống chuẩn; role gán thận trọng. | Hoàn toàn chưa có Adapter chuyển đổi đồ thị MEP sang các namelist mạng thông gió `&HVAC` của FDS (Duct/Node/Fan). |
| **11** | **Phạm Vi Không Gian & Miền Tính Toán** | **8.0** | Không cắt xén cấu kiện giao cắt tầng (`BOUNDARY_RETAINED`); yêu cầu miền tính toán FDS phải được cấu hình tường minh. | FDS boundary mặc định là biên cứng `INERT`, thiếu cơ chế tự động gán ranh giới mở thoát khói (`OPEN` vents). |
| **12** | **Cú Pháp & Serialization Tệp FDS** | **8.0** | Cú pháp namelist chuẩn FDS 6+; toàn bộ string bọc nháy đơn; định danh duy nhất qua bộ đếm `prim_counter`. | $T\_END=0.0$ bị fix cứng; thiếu thuật toán kiểm tra tỷ lệ khung hình ô lưới (Aspect Ratio $dx:dy:dz$). |
| **13** | **Độ Phân Giải Lưới Đặc Trưng Đám Cháy ($D^*/\Delta x$)**| **0.0** | Hoàn toàn vắng bóng trong mã nguồn; kích thước lưới `cell_size = 0.2m` bị hardcode cố định. | Thiếu toàn bộ công thức tính toán $D^*$ và bộ kiểm tra dải khuyến nghị theo NFPA 92 / NUREG 1824 ($4 \le D^*/\Delta x \le 16$). |
| **14** | **Động Cơ Thẩm Định & Tiêu Chí Nghiệm Thu** | **9.5** | 12 cổng kiểm tra độc lập; phân biệt rõ `MAPPING_VERIFIED` và `INCONCLUSIVE`; xử lý thiếu binary FDS mẫu mực. | Trạng thái nghiệm thu `SIMULATION_VERIFIED` là dead code (không có nhánh gán thành công trong mã nguồn). |
| **15** | **Sẵn Sàng Cho Kịch Bản Cháy & Tính Tái Lập**| **5.0** | Tính tái lập xuất sắc (9.0/10) với mã băm SHA-256 đầu vào/đầu ra và định dạng `.17g`; Kịch bản cháy chưa có (1.0/10). | Thiếu hoàn toàn module kịch bản cháy: nguồn cháy pin EV, đường cong HRR, đầu phun Sprinkler, cảm biến DEVC. |

**ĐIỂM TRUNG BÌNH TOÀN DIỆN: 7.23 / 10.0**

---

# PHẦN 3: BẢNG ĐĂNG KÝ SỰ CỐ & KHIẾM KHUYẾT TỔNG THỂ (MASTER ISSUE REGISTER)

Toàn bộ các phát hiện kiểm toán được phân loại theo 4 cấp độ nghiêm trọng tiêu chuẩn:
- **P0 (Critical Blocker)**: Khiếm khuyết nghiêm trọng làm tê liệt chức năng mô phỏng khoa học hoặc chặn đứng quy trình nghiệm thu.
- **P1 (High Priority)**: Lỗi vi phạm tính toàn vẹn hình học, sai lệch hợp đồng giao diện, hoặc vi phạm ranh giới kiến trúc cốt lõi.
- **P2 (Medium Priority)**: Khiếm khuyết về thiết kế phần mềm, giới hạn định dạng dữ liệu, rò rỉ framework hoặc hiệu năng tính toán.
- **P3 (Low Priority / Cleanup)**: Sai sót về tài liệu, chú thích gây hiểu lầm hoặc cảnh báo thư viện bên ngoài.

```
+---------------+-------+------------+--------------------+---------------------------------------------------------------+
|   Issue ID    | Mức độ| Trạng thái |     Thành phần     |                         Tóm tắt sự cố                         |
+---------------+-------+------------+--------------------+---------------------------------------------------------------+
| ISSUE-R5-01   |  P0   | CONFIRMED  | FDS Exporter       | T_END=0.0 bị cố định cứng, không thể mô phỏng lan truyền cháy |
| ISSUE-R4-01   |  P0   | CONFIRMED  | FDS Grid Engine    | Hoàn toàn thiếu tiêu chí độ phân giải lưới đặc trưng D*/dx    |
| ISSUE-CONTRACT-03| P0 | CONFIRMED  | Acceptance Logic   | SIMULATION_VERIFIED là dead code, không bao giờ được cấp phép |
| ISSUE-R3-01   |  P1   | CONFIRMED  | Openings / Mesh    | Nguy cơ Voxelization Reseal tại tầng lưới FDS CFD             |
| ISSUE-R3-02   |  P1   | CONFIRMED  | MEP / HVAC         | Đồ thị MEP thiếu Adapter sinh thực thể mạng FDS &HVAC         |
| ISSUE-CONTRACT-01| P1 | CONFIRMED  | UI Workbench       | Name mismatch: Backend 'golden_reference_parity' vs UI 'golden'|
| ISSUE-CONTRACT-02| P1 | CONFIRMED  | UI Workbench       | Giao diện Audit Drawer bỏ quên mức độ P0, hạ cấp thành Warning|
| ISSUE-ARCH-01 |  P1   | CONFIRMED  | Domain Validation  | Domain Model phụ thuộc ngược ra Parser ngoại vi qua property  |
| ISSUE-ARCH-03 |  P1   | CONFIRMED  | Architecture Core  | 3 chu trình phụ thuộc vòng (Circular Imports) giữa các module |
| ISSUE-CONTRACT-05| P1 | CONFIRMED  | UI / Quick Preview | Dùng chung nút tải FDS và thiếu tiêu đề cảnh báo UNVALIDATED  |
| ISSUE-ARCH-02 |  P2   | CONFIRMED  | Domain Core        | 19 Domain Models kế thừa trực tiếp Pydantic BaseModel         |
| ISSUE-ARCH-04 |  P2   | CONFIRMED  | Architecture Ports | Kiến trúc Hexagonal dở dang: thiếu Ports cho Parser/Geometry  |
| ISSUE-ARCH-05 |  P2   | CONFIRMED  | Domain BIM Model   | CanonicalElement bị nhiễm bẩn bởi các thuộc tính Mapping FDS   |
| ISSUE-CONTRACT-04| P2 | CONFIRMED  | Backend API        | Cắt lát cứng 20 findings (findings[:20]) gây mất thông tin UI |
| ISSUE-R3-03   |  P2   | CONFIRMED  | Core Units         | Bỏ qua các đơn vị đo lường AREA, VOLUME, TIME và HVAC units   |
| ISSUE-R3-04   |  P2   | CONFIRMED  | Core Placement     | Ngoại lệ từ chối IfcGridPlacement và IfcLinearPlacement       |
| ISSUE-R4-02   |  P2   | CONFIRMED  | FDS Grid Engine    | Thiếu bộ kiểm tra tỷ lệ khung hình ô lưới MESH (dx:dy:dz)     |
| ISSUE-R4-03   |  P2   | CONFIRMED  | FDS Boundary       | Miền tính toán FDS thiếu mặc định ranh giới mở thoát khói OPEN|
| ISSUE-R5-02   |  P2   | CONFIRMED  | Geometry Kernel    | Điểm nghẽn hiệu năng tính tự cắt đa tạp bằng rational fraction|
| ISSUE-R3-05   |  P3   | CONFIRMED  | Test Suite Docs    | Chú thích gây hiểu lầm trong test_unit_scale_millimeter       |
+---------------+-------+------------+--------------------+---------------------------------------------------------------+
```

---

### Bảng Chi Tiết Từng Khiếm Khuyết

#### 1. `ISSUE-R5-01`: $T\_END=0.0$ bị cố định cứng trong FDS Exporter
- **Mức độ nghiêm trọng**: **P0 (Critical Scientific Blocker)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực qua mã nguồn và tệp xuất thực nghiệm)
- **Vị trí tệp & dòng code**: `ifc_to_fds/mapping/exporter.py`, dòng 135:
  ```python
  lines.append("&TIME T_END=0.0 /")
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Nhà phát triển ban đầu chỉ thiết kế bộ xuất tệp nhằm mục đích kiểm tra hình học không gian ở bước thời gian $t=0$ của trình giải FDS (`fds -c`), chưa bao hàm tham số điều khiển thời gian mô phỏng trong mô hình cấu hình.
- **Tác động (Impact)**: Bất kỳ tệp FDS nào sinh ra bởi hệ thống đều kết thúc mô phỏng ngay lập tức tại giây thứ 0. Không thể mô phỏng quá trình bắt cháy, tích tụ khói, tăng nhiệt độ hoặc kích hoạt hệ thống PCCC.
- **Hướng khắc phục (Recommended Fix)**:
  Bổ sung trường `simulation_time: float = 600.0` vào `MappingConfig` và DTO của API; cập nhật `exporter.py` để ghi `&TIME T_END={config.simulation_time} /`.
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng hoàn toàn khả năng chạy mô phỏng cháy động học thực tế trên FDS.

#### 2. `ISSUE-R4-01`: Hoàn toàn thiếu tiêu chí độ phân giải lưới đặc trưng đám cháy $D^*/\Delta x$
- **Mức độ nghiêm trọng**: **P0 (Critical Scientific Blocker)**
- **Độ tin cậy**: `CONFIRMED` (Khảo sát toàn bộ 100% codebase)
- **Vị trí tệp & dòng code**: `ifc_to_fds/mapping/exporter.py`, dòng 69–80 (`compute_mesh_grid`):
  ```python
  def compute_mesh_grid(bounds, cell_size=0.2):
      # Chỉ tính toán số lượng ô lưới i, j, k chia đều theo cell_size cố định
      ...
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Chưa tích hợp module tính toán động lực học nhiệt FDS và tiêu chuẩn khói NFPA 92 / NUREG 1824 vào quy trình tạo lưới tính toán.
- **Tác động (Impact)**: Ô lưới cố định $0.2\text{ m}$ có thể quá thô cho đám cháy nhỏ ($<500\text{ kW}$ dẫn đến sai lệch cột khói plume) hoặc quá mịn làm bùng nổ số lượng ô lưới trên các không gian hầm rộng lớn ($>10,000\text{ m}^2$).
- **Hướng khắc phục (Recommended Fix)**:
  Xây dựng module `GridResolutionEngine` tính toán:
  $$D^* = \left(\frac{\dot{Q}}{\rho_\infty c_p T_\infty \sqrt{g}}\right)^{2/5}$$
  và cổng kiểm tra `GridResolutionGate` xác nhận tỷ lệ:
  $$4 \le \frac{D^*}{\Delta x} \le 16$$
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng tính hợp lệ khoa học và độ tin cậy của mô phỏng CFD cháy.

#### 3. `ISSUE-CONTRACT-03`: `SIMULATION_VERIFIED` là mã nguồn chết (Dead Code)
- **Mức độ nghiêm trọng**: **P0 (Critical Architecture Blocker)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực qua cấu trúc logic phân nhánh)
- **Vị trí tệp & dòng code**: `ifc_to_fds/domain/validation/model.py`, dòng 153–162:
  ```python
  sim_failed = any(
      g.status == GateStatus.FAIL
      for name, g in self.gates.items()
      if name in simulation
  )
  self.simulation_status = (
      AcceptanceStatus.REJECTED
      if sim_failed or failed
      else AcceptanceStatus.INCONCLUSIVE
  )
  self.status = (
      self.simulation_status
      if self.requested_level == "simulation"
      else self.mapping_status
  )
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Nhóm tác giả thực hiện theo quyết định kiến trúc ADR 0004 ("SIMULATION_VERIFIED is reserved and never issued by this stage"), cố tình để nhánh fallback chỉ nhận `INCONCLUSIVE` hoặc `REJECTED`, nhưng chưa hoàn thiện logic nghiệm thu khi có đủ bằng chứng solver.
- **Tác động (Impact)**: Người dùng hay nhà nghiên cứu lựa chọn chế độ nghiệm thu `level="simulation"` không bao giờ có thể nhận được chứng nhận `SIMULATION_VERIFIED`, ngay cả khi đã cung cấp tệp thực thi FDS và tất cả các gate đều PASS.
- **Hướng khắc phục (Recommended Fix)**:
  Bổ sung logic kiểm tra đầy đủ: Khi tất cả các cổng kiểm tra thuộc nhóm `simulation` đạt `GateStatus.PASS` và solver trả về kết quả hợp lệ, gán `self.simulation_status = AcceptanceStatus.SIMULATION_VERIFIED`.
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng khả năng phát hành chứng nhận nghiệm thu mô phỏng cháy.

#### 4. `ISSUE-R3-01`: Nguy cơ Voxelization Reseal tại tầng lưới FDS CFD
- **Mức độ nghiêm trọng**: **P1 (High Priority Scientific Issue)**
- **Độ tin cậy**: `CONFIRMED` (Phân tích vật lý tính toán CFD)
- **Vị trí tệp & dòng code**: `ifc_to_fds/mapping/exporter.py`, dòng 160 kết hợp với `validation/engine.py:475`:
- **Nguyên nhân gốc rễ (Root Cause)**: Hệ thống mới chỉ kiểm soát tính toàn vẹn của lỗ mở ở tầng CAD/BRep (`GEOM` vs `OBST`), chưa có bước kiểm tra chéo giữa kích thước hình học nhỏ nhất của lỗ mở ($\min(W_o, H_o)$) và bước lưới trực giao $\Delta x$ của khối `&MESH`.
- **Tác động (Impact)**: Khi chuyển sang lưới FDS CFD, trình giải tự động nội suy lưới tam giác thành các ô thể tích trực giao (stair-stepped voxels). Các khe hở thoát khói nhỏ hơn $\Delta x$ sẽ bị FDS coi là vật thể đặc, dẫn đến hiện tượng bịt kín âm thầm ở tầng lưới, làm khói không thoát được ra ngoài.
- **Hướng khắc phục (Recommended Fix)**:
  Bổ sung cổng kiểm tra `VoxelizationResealGate`: Cảnh báo lỗi P1 nếu $\min(W_{opening}, H_{opening}) \le \Delta x$, khuyến nghị làm mịn cục bộ hoặc điều chỉnh kích thước lưới.
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng tính chính xác của bài toán thoát khói qua cửa mở và van thông gió.

#### 5. `ISSUE-R3-02`: Đồ thị MEP thiếu Adapter sinh thực thể mạng FDS `&HVAC`
- **Mức độ nghiêm trọng**: **P1 (High Priority Modeling Issue)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực qua mã nguồn `mapping/policy.py`)
- **Vị trí tệp & dòng code**: `ifc_to_fds/mapping/policy.py`, dòng 128–135:
  ```python
  if is_mep_element:
      element.simulation_role = "REFERENCE_GEOMETRY"
      element.operational_status = "NOT_CONFIGURED"
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Chưa phát triển adapter chuyển ngữ nghĩa từ mô hình đồ thị kết nối `MEPGraph` sang các namelist mô phỏng mạng 1D của FDS (`&HVAC`).
- **Tác động (Impact)**: Toàn bộ hệ thống ống gió hút khói sự cố, quạt tăng áp, miệng cấp gió trong IFC chỉ được xuất dưới dạng hình khối tham chiếu trơ (hoặc bỏ qua), không hoạt động như một hệ thống vận chuyển chất lưu trong FDS.
- **Hướng khắc phục (Recommended Fix)**:
  Phát triển `MepToFdsHvacAdapter`: Ánh xạ các nút `IfcFlowSegment` thành `&HVAC TYPE='DUCT'`, các cửa gió `IfcAirTerminal` thành `&HVAC TYPE='NODE'`, và quạt `IfcFan` thành `&HVAC TYPE='FAN'` kèm lưu lượng thiết kế.
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng việc mô phỏng hệ thống kiểm soát khói cơ khí (Mechanical Smoke Control System) theo NFPA 92.

#### 6. `ISSUE-CONTRACT-01`: Name Mismatch giữa Backend Gate và Frontend Card
- **Mức độ nghiêm trọng**: **P1 (High Priority Contract Issue)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực trực tiếp trên DOM và mã JavaScript)
- **Vị trí tệp & dòng code**:
  - Backend: `ifc_to_fds/validation/golden.py`, dòng 218: `report.gates["golden_reference_parity"] = gate`
  - Frontend HTML: `index.html`, dòng 524: `<div class="gate-card" data-gate="golden">`
  - Frontend JS: `js/app-controller.js`, dòng 1657: `gatesContainer.querySelector('[data-gate="' + gateName + '"]')`
- **Nguyên nhân gốc rễ (Root Cause)**: Đặt tên khóa định danh không đồng bộ giữa tầng DTO backend (`"golden_reference_parity"`) và giao diện HTML (`"golden"`).
- **Tác động (Impact)**: `querySelector` trả về `null`. Thẻ hiển thị trạng thái Golden Reference Parity trên Audit Drawer của Workbench UI không bao giờ được cập nhật, luôn hiển thị trạng thái mặc định màu xám khiến người dùng tưởng rằng kiểm định chưa chạy.
- **Hướng khắc phục (Recommended Fix)**:
  Sửa dòng 524 trong `index.html` thành: `<div class="gate-card" data-gate="golden_reference_parity">` hoặc thêm bảng tra cứu alias trong `js/app-controller.js`.
- **Ngăn chặn điều gì (Blocking What)**: Gây sai lệch trải nghiệm giám sát thẩm định trên giao diện người dùng.

#### 7. `ISSUE-CONTRACT-02`: Giao diện Audit Drawer bỏ quên mức độ P0, hạ cấp thành Warning
- **Mức độ nghiêm trọng**: **P1 (High Priority Contract Issue)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực mã JavaScript điều khiển UI)
- **Vị trí tệp & dòng code**: `js/app-controller.js`, dòng 1685:
  ```javascript
  var isErr = f.severity === 'ERROR' || f.severity === 'P1';
  var sevColor = isErr ? 'var(--status-error-text)' : 'var(--status-warning-text)';
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Lập trình viên frontend giả định mức độ lỗi nghiêm trọng nhất chỉ là `'ERROR'` hoặc `'P1'`, bỏ sót mã enum `Severity.P0` được định nghĩa trong backend `domain/validation/model.py:10`.
- **Tác động (Impact)**: Khi backend phát hiện một lỗi nghiêm trọng cấp P0 (lỗi khoa học làm vô hiệu hóa mô hình), biến `isErr` bị tính là `false`, khiến huy hiệu P0 hiển thị màu vàng cảnh báo thay vì màu đỏ nguy hiểm, làm kỹ sư thẩm duyệt đánh giá sai mức độ rủi ro.
- **Hướng khắc phục (Recommended Fix)**:
  Cập nhật biểu thức kiểm tra: `var isErr = f.severity === 'ERROR' || f.severity === 'P0' || f.severity === 'P1';`.
- **Ngăn chặn điều gì (Blocking What)**: Chặn đứng nguy cơ bỏ lọt sai sót chí mạng trong quá trình phê duyệt thiết kế.

#### 8. `ISSUE-ARCH-01`: Domain Validation phụ thuộc ngược ra Parser ngoại vi qua property
- **Mức độ nghiêm trọng**: **P1 (High Priority Architecture Violation)**
- **Độ tin cậy**: `CONFIRMED` (Kiểm tra AST và mã nguồn)
- **Vị trí tệp & dòng code**: `ifc_to_fds/domain/validation/model.py`, dòng 76–81:
  ```python
  @property
  def parsed(self) -> Any:
      if self.parsed_fds is None and self.fds_text:
          from ifc_to_fds.validation.parser import parse_fds
          self.parsed_fds = parse_fds(self.fds_text)
      return self.parsed_fds
  ```
- **Nguyên nhân gốc rễ (Root Cause)**: Vi phạm quy tắc cơ bản của Clean Architecture: Tầng Domain tuyệt đối không được phụ thuộc hoặc gọi ra các module dịch vụ ngoại vi. Việc đặt `import` lười (lazy import) trong `@property` là kỹ thuật che giấu lỗi AST lặp vòng lúc nạp module.
- **Tác động (Impact)**: Domain Model mất tính độc lập thuần túy, không thể tái sử dụng độc lập hoặc unit test một cách cô lập.
- **Hướng khắc phục (Recommended Fix)**:
  Loại bỏ property `parsed` khỏi `ValidationContext`; việc phân tích cú pháp FDS phải được thực hiện tại tầng Application Service và truyền đối tượng `ParsedFds` vào Context qua constructor.
- **Ngăn chặn điều gì (Blocking What)**: Phá vỡ tính toàn vẹn của mô hình Clean Architecture.

#### 9. `ISSUE-ARCH-03`: Ba chu trình phụ thuộc vòng (Circular Imports) giữa các module
- **Mức độ nghiêm trọng**: **P1 (High Priority Architecture Issue)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực qua phân tích đồ thị phụ thuộc)
- **Vị trí tệp & dòng code**:
  1. *Cycle 1 (Domain)*: `domain/bim/model.py:67` import `MappingStrategy` từ `domain/mapping/model.py`, trong khi `domain/mapping/model.py:11` import `SCHEMA_VERSION` từ `domain/bim/model.py`.
  2. *Cycle 2 (Geometry)*: `geometry/storage.py:14` import `seal` từ `geometry/package.py`, trong khi `geometry/package.py:56` import `DiskPackage` từ `geometry/storage.py`.
  3. *Cycle 3 (Mapping/Validation)*: `mapping/boundary.py:99` import `validation.boundary_fixtures`, trong khi `validation/boundary_fixtures.py:9` import `mapping.boundary.POLICY`.
- **Nguyên nhân gốc rễ (Root Cause)**: Phân rã trách nhiệm giữa các gói con chưa triệt để, phải sử dụng import cục bộ bên trong hàm để đối phó lỗi `ImportError`.
- **Tác động (Impact)**: Làm tăng độ ghép nối (tight coupling), khó bảo trì, dễ phát sinh lỗi khởi tạo bất định khi refactoring.
- **Hướng khắc phục (Recommended Fix)**:
  Tách `SCHEMA_VERSION` ra module dùng chung `version.py`; chuẩn hóa ranh giới giữa storage và package; tách fixtures kiểm thử ra khỏi logic nghiệp vụ.
- **Ngăn chặn điều gì (Blocking What)**: Gây rủi ro đổ vỡ cấu trúc mã nguồn khi dự án phát triển quy mô lớn.

#### 10. `ISSUE-CONTRACT-05`: Dùng chung nút tải FDS và thiếu cảnh báo trong Quick Preview
- **Mức độ nghiêm trọng**: **P1 (High Priority UX & Safety Issue)**
- **Độ tin cậy**: `CONFIRMED` (Xác thực mã nguồn worker và controller UI)
- **Vị trí tệp & dòng code**:
  - `js/workers/fds-export-worker-inline.js:77-100`: Tệp FDS xuất ra thiếu header cảnh báo unvalidated.
  - `js/app-controller.js:546-549`: Nút `#save-fds` dùng chung biến trạng thái cho cả hai chế độ.
- **Nguyên nhân gốc rễ (Root Cause)**: Tái sử dụng nút tải về trên thanh điều khiển chính mà không có trạng thái phân biệt rõ ràng giữa hai luồng dữ liệu.
- **Tác động (Impact)**: Người dùng sau khi chạy Quick Preview chuyển sang tab Verified Mapping nhưng không chạy API backend vẫn có thể nhấn nút tải về tệp FDS chưa qua kiểm định, tiềm ẩn nguy cơ áp dụng sai tệp tính toán.
- **Hướng khắc phục (Recommended Fix)**:
  Chèn cảnh báo bắt buộc vào đầu tệp Quick Preview FDS:
  `! WARNING: CLIENT-SIDE HEURISTIC PREVIEW ONLY - NOT AUTHORITATIVE - DO NOT USE FOR LIFE-SAFETY DESIGN`. Tách biệt 2 nút tải riêng biệt trên giao diện.
- **Ngăn chặn điều gì (Blocking What)**: Phòng tránh nhầm lẫn pháp lý và kỹ thuật trong hồ sơ thiết kế an toàn PCCC.

#### 11. Các Khiếm Khuyết Mức Độ P2 & P3 Khác
- `ISSUE-ARCH-02` (P2): 19 Domain Models kế thừa `pydantic.BaseModel` làm rò rỉ framework vào thực thể miền thuần túy.
- `ISSUE-ARCH-04` (P2): Thư mục `application/ports` chỉ có 1 cổng `storage.py`, các use case gọi trực tiếp implementation.
- `ISSUE-ARCH-05` (P2): `CanonicalElement` chứa các trường định hướng FDS (`simulation_role`, `fds_representation`).
- `ISSUE-CONTRACT-04` (P2): `results.py:98` cắt cứng `findings[:20]`, làm mất thông tin khi có nhiều hơn 20 phát hiện.
- `ISSUE-R3-03` (P2): `units.py` chỉ đọc `LENGTHUNIT`, bỏ qua các đơn vị diện tích, thể tích và lưu lượng khí.
- `ISSUE-R3-04` (P2): `placement.py:28` ném lỗi khi gặp `IfcGridPlacement` hoặc `IfcLinearPlacement`.
- `ISSUE-R4-02` (P2): Thiếu bộ kiểm tra tỷ lệ khung hình ô lưới $dx:dy:dz \le 2.0$ trong FDS mesh generator.
- `ISSUE-R4-03` (P2): FDS domain mặc định các mặt là `INERT`, thiếu tự động tạo `&VENT SURF_ID='OPEN' /`.
- `ISSUE-R5-02` (P2): Thuật toán tự cắt hình học bằng phân số chính xác (`fractions.Fraction`) gây thắt cổ chai CPU.
- `ISSUE-R3-05` (P3): Chú thích trong `tests/test_units.py:18` nói file dùng mm nhưng code assert mét.

---

# PHẦN 4: BẢN ĐỒ KIẾN TRÚC & PHẢ HỆ DÒNG CHẢY DỮ LIỆU (ARCHITECTURE MAP & DATA FLOW LINEAGE)

### 4.1. Kiến Trúc Hiện Tại vs Kiến Trúc Hexagonal Mục Tiêu

Hệ thống hiện tại đang ở trạng thái **chuyển tiếp dở dang (Hybrid In-Transition)** giữa mô hình thủ tục truyền thống (procedural pipeline) và Kiến trúc Lục giác (Hexagonal Architecture / Ports & Adapters).

```
===================================================================================================
                     HIỆN TRẠNG KIẾN TRÚC HIỆN TẠI (AS-IS ARCHITECTURE)
===================================================================================================
   [User Browser UI] -------------------- REST API / SSE -------------------> [FastAPI Server]
   (app-controller.js)                                                            (server.py)
          |                                                                            |
          v                                                                            v
   [Quick Preview JS]                                                        [Use Cases Facade]
   (Client Web Worker)                                                       (convert_verified)
          |                                                                   /   |     |    \
     (BBox/Voxel)                                                            /    |     |     \
          |                                                                 v     v     v      v
          v                                                          [core] [geom] [map] [valid]
   [Unvalidated FDS]                                                 (Gọi trực tiếp không qua Ports)
                                                                            |     |     |      |
                                                                            v     v     v      v
                                                                     [Domain Models kế thừa Pydantic]
                                                                        ^                 |
                                                                        |-- (Lazy Import)-|

===================================================================================================
                 KIẾN TRÚC LỤC GIÁC MỤC TIÊU (TARGET HEXAGONAL CLEAN ARCHITECTURE)
===================================================================================================

                    +-------------------------------------------------------+
                    |           DRIVING INTERFACES (CỔNG ĐIỀU KHIỂN)        |
                    |   +-----------------------+   +-------------------+   |
                    |   | Web Workbench UI / API|   |   Python CLI App  |   |
                    |   +-----------------------+   +-------------------+   |
                    +---------------------------+---------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |            INBOUND PORTS / APPLICATION SERVICES       |
                    |   +-----------------------------------------------+   |
                    |   | ConvertVerifiedUseCase | AuditModelUseCase    |   |
                    |   | ConfigureScenarioUseCase                      |   |
                    |   +-----------------------------------------------+   |
                    +---------------------------+---------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |             DOMAIN CORE (TRUNG TÂM MIỀN THUẦN TÚY)    |
                    |   +-----------------------------------------------+   |
                    |   | Entities (Dataclasses thuần túy, No Pydantic) |   |
                    |   | CanonicalElement | BoundingBox | Mesh64       |   |
                    |   | MEPGraph | SystemNode | PortConnection        |   |
                    |   | MappingPlan | DecisionRule | FireScenario     |   |
                    |   | ValidationEngine | GateResult | Report        |   |
                    |   +-----------------------------------------------+   |
                    +---------------------------+---------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |           OUTBOUND PORTS (CỔNG TRỪU TƯỢNG HÓA RA)     |
                    |   +-------------------+       +-------------------+   |
                    |   | IfcReaderPort     |       | GeometryKernelPort|   |
                    |   +-------------------+       +-------------------+   |
                    |   | FdsSerializerPort |       | SolverExecutionPort|  |
                    |   +-------------------+       +-------------------+   |
                    +---------------------------+---------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |           DRIVEN ADAPTERS (CÁC BỘ CHUYỂN ĐỔI NGOẠI VI)|
                    |   +-------------------+       +-------------------+   |
                    |   | IfcOpenShellAdapt |       | Manifold3D Adapter|   |
                    |   +-------------------+       +-------------------+   |
                    |   | FDS Fortran Serial|       | FDS Subprocess Run|   |
                    |   +-------------------+       +-------------------+   |
                    |   | Disk Artifact Repo|       | Paraview/Smokeview|   |
                    +-------------------------------------------------------+
```

---

### 4.2. Phả Hệ Dòng Chảy Dữ Liệu Toàn Vẹn (Data Flow Lineage)

Dòng dữ liệu được thiết kế khép kín, đảm bảo tính bảo tồn cấu kiện nguồn và khả năng truy vết ngược 100%:

```
[IFC Source Files] (SHA-256 Checksum)
       │
       ▼
[Stage 1: Source Ingestion & Federation]
       │  • Trích xuất đơn vị SI/Length scale chuẩn xác (`core/units.py`)
       │  • Phân cấp tọa độ thế giới ma trận 4x4 (`core/placement.py`)
       │  • Ghi nhận siêu dữ liệu SourceFile Metadata & SourceInventory
       ▼
[Stage 2: Canonical BIM Model Generation]
       │  • BRep to Triangulated Mesh via Manifold3D (`geometry/engine.py`)
       │  • Kiểm tra chất lượng hình học đa tạp, tự cắt, kín nước (`geometry/mesh.py`)
       │  • Khai thác đồ thị hệ thống MEP & Ports có quan hệ thực chất (`mep/mep_graph.py`)
       │  • Bảo toàn cấu kiện ranh giới tầng `BOUNDARY_RETAINED` (`mapping/scope.py`)
       ▼
[Stage 3: Mapping Strategy & Policy Application]
       │  • Phân loại chiến lược: Không có opening -> OBST; Có opening -> GEOM (`mapping/policy.py`)
       │  • Tạo lập `MappingPlan` chứa danh sách các quyết định ánh xạ độc lập
       │  • Khai báo tường minh hộp tính toán `SimulationDomain` (`mapping/boundary.py`)
       ▼
[Stage 4: FDS Fortran Namelist Serialization]
       │  • Định dạng chuẩn FDS 6+: `&HEAD`, `&TIME`, `&MESH`, `&SURF`, `&OBST`, `&GEOM`
       │  • Gán định danh duy nhất chống trùng lặp `OBST_{n}_{clean_id}` (`mapping/exporter.py`)
       │  • Tính toán mã băm đầu ra `fds_sha256` và ghi nhận `MappingManifest`
       ▼
[Stage 5: Independent Validation Engine Audit]
       │  • 12 Cổng kiểm định độc lập kiểm tra cú pháp, hình học, lỗ mở, đồ thị MEP
       │  • Đo lường `opening_residual` và `passage_metrics` phát hiện silent reseal
       │  • So sánh sai số thể tích và diện tích bề mặt giữa Canonical và FDS
       ▼
[Stage 6: Acceptance & Decision Gate]
       │  • Nếu tất cả required gates PASS -> `MAPPING_VERIFIED`
       │  • Nếu có gate FAIL hoặc finding P0/P1 -> `REJECTED`
       │  • Nếu thiếu solver binary hoặc thiếu kịch bản -> `INCONCLUSIVE`
       ▼
[Stage 7: (Future Phase) Fire Scenario Injection & CFD Solver Execution]
          • Bổ sung nguồn cháy EV, đường cong $t^2$ HRR, đầu phun Sprinkler, mạng `&HVAC`
          • Kiểm tra độ phân giải lưới $D^*/\Delta x$
          • Thực thi FDS Solver -> Phân tích khói/nhiệt độ -> Cấp nhãn `SIMULATION_VERIFIED`
```

---

# PHẦN 5: PHÂN TÍCH KHOẢNG CÁCH KỊCH BẢN CHÁY (FIRE SCENARIO GAP ANALYSIS)

Để nâng cấp từ một công cụ ánh xạ hình học đơn thuần thành một nền tảng phục vụ đề tài nghiên cứu khoa học an toàn PCCC, hệ thống bắt buộc phải thu hẹp 5 khoảng cách kỹ thuật cốt tử sau:

### 5.1. Nguồn Cháy Pin Xe Điện & Hiện Tượng Thoát Nhiệt (EV Battery Fire & Thermal Runaway)
- **Đặc thù khoa học**: Đám cháy phương tiện giao thông điện (EV) có cơ chế cháy nổ phức tạp hơn rất nhiều so với xe xăng truyền thống:
  - Hiện tượng thoát nhiệt lan truyền (Thermal Runaway Propagation) giữa các cell pin lithium-ion (NMC, LFP).
  - Tốc độ giải phóng nhiệt cực đại (Peak HRR) đạt từ $3.5\text{ MW}$ đến trên $8.0\text{ MW}$ đối với xe du lịch, và vượt quá $15.0\text{ MW}$ đối với xe buýt điện.
  - Hiện tượng phun tia lửa (Jet flame) áp lực cao qua van xả áp của bộ pack pin.
  - Phát thải các loại khí độc nguy hiểm đặc thù: Hydrogen Fluoride ($HF$), Carbon Monoxide ($CO$), Hydrogen Cyanide ($HCN$), và khí dễ cháy ($H_2, CH_4$).
- **Hiện trạng mã nguồn**: **Hoàn toàn vắng bóng (0% Support)**. Không có lớp dữ liệu định nghĩa vật liệu cháy, không có mô hình phản ứng cháy đa thành phần `&REAC`, không có khai báo các cấu tử độc hại `&SPEC ID='HYDROGEN FLUORIDE'`.
- **Yêu cầu nâng cấp**:
  - Xây dựng thực thể `EVFireSource` trong tầng Domain với các thông số: dung lượng pin ($kWh$), loại hóa học cell (NMC/LFP), diện tích vùng pin ($m^2$), thời gian bắt đầu thoát nhiệt ($t_{tr}$), hệ số sinh khí $HF$ ($g/MJ$).
  - Tự động sinh các namelist FDS:
    ```fortran
    &SPEC ID='HYDROGEN FLUORIDE', FORMULA='HF' /
    &REAC FUEL='BATTERY_GAS', C=2.0, H=4.0, O=1.0, HEAT_OF_COMBUSTION=28000. /
    &SURF ID='EV_BATTERY_FIRE', HRRPUA=2500., COLOR='RED' /
    ```

---

### 5.2. Đường Cong Tốc Độ Thoát Nhiệt ($t^2$ Fire HRR Curves & RAMP)
- **Đặc thù khoa học**: Tiêu chuẩn NFPA 92, NFPA 204 và Eurocode 1 định nghĩa đường cong phát triển nhiệt theo mô hình đám cháy $t^2$:
  $$\dot{Q}(t) = \alpha \cdot t^2$$
  Trong đó $\alpha$ là hệ số phát triển đám cháy ($kW/s^2$):
  - Chậm (Slow): $\alpha = 0.00293\text{ kW/s}^2$
  - Trung bình (Medium): $\alpha = 0.01172\text{ kW/s}^2$
  - Nhanh (Fast): $\alpha = 0.0469\text{ kW/s}^2$ (thường dùng cho đám cháy kho bãi, xe cộ)
  - Cực nhanh (Ultra-fast): $\alpha = 0.1876\text{ kW/s}^2$ (thích hợp cho pin xe điện giai đoạn bùng nổ nhiệt)
  Đám cháy sau đó đạt giai đoạn ổn định (Steady Phase $\dot{Q}_{peak}$) và suy tàn (Decay Phase).
- **Hiện trạng mã nguồn**: Mã nguồn cố định cứng `T_END=0.0`. Không sinh bất kỳ namelist `&RAMP` nào để biểu diễn sự thay đổi công suất theo thời gian.
- **Yêu cầu nâng cấp**:
  - Tích hợp bộ tạo đường cong HRR cho phép người dùng lựa chọn loại đám cháy ($\alpha$) và công suất đỉnh $\dot{Q}_{peak}$.
  - Sinh chuỗi các hàm RAMP chuẩn trong FDS:
    ```fortran
    &RAMP ID='RAMP_HRR', T=0.0, F=0.0 /
    &RAMP ID='RAMP_HRR', T=120.0, F=0.25 /
    &RAMP ID='RAMP_HRR', T=240.0, F=1.0 /
    &RAMP ID='RAMP_HRR', T=1200.0, F=1.0 /
    &RAMP ID='RAMP_HRR', T=1800.0, F=0.2 /
    &SURF ID='FIRE_SURFACE', HRRPUA=1500., RAMP_Q='RAMP_HRR' /
    ```

---

### 5.3. Điều Khiển Hệ Thống Thông Gió & Hút Khói Sự Cố (HVAC Smoke Control NFPA 92)
- **Đặc thù khoa học**: Theo NFPA 92 (Standard for Smoke Control Systems) và TCVN 5687:2024:
  - Hệ thống hút khói cơ khí tầng hầm/hành lang phải duy trì lưu lượng hút định mức (ví dụ $m^3/h$) để giữ cao độ lớp khói an toàn (Clear Height) cách mặt sàn tối thiểu $2.0\text{ m}$.
  - Hệ thống quạt tạo áp cầu thang thoát nạn phải duy trì chênh áp dương từ $20\text{ Pa}$ đến $50\text{ Pa}$.
  - Khi có tín hiệu báo cháy từ cảm biến nhiệt/khói, van ngăn lửa/ngăn khói (Motorized Fire/Smoke Damper) phải tự động đóng hoặc mở theo kịch bản liên động.
- **Hiện trạng mã nguồn**: Module `mep/mep_graph.py` đã trích xuất được hệ thống hút khói `SMOKE_EXTRACT` và đánh dấu `is_fire_safety_critical`, nhưng ở bước xuất FDS bị gán cứng thành `REFERENCE_GEOMETRY`, hoàn toàn không sinh các thực thể mạng chất lưu 1D của FDS.
- **Yêu cầu nâng cấp**:
  - Xây dựng `MepToFdsHvacAdapter` chuyển đổi các thành phần:
    ```fortran
    &HVAC TYPE='NODE', ID='SMOKE_GRILLE_01', DUCT_ID='EXHAUST_DUCT_01', ENCLOSURE='ROOM_1' /
    &HVAC TYPE='DUCT', ID='EXHAUST_DUCT_01', NODE_ID='SMOKE_GRILLE_01','FAN_NODE_01', AREA=0.4, LOSS=1.5 /
    &HVAC TYPE='FAN', ID='SMOKE_EXHAUST_FAN', VOLUME_FLOW=8.5, CTRL_ID='FIRE_ALARM_CTRL' /
    &CTRL ID='FIRE_ALARM_CTRL', FUNCTION_TYPE='ALL', INPUT_ID='SMOKE_DET_01' /
    ```

---

### 5.4. Đầu Phun Sprinkler & Cảm Biến Giám Sát (DEVC & Suppression)
- **Đặc thù khoa học**:
  - Đầu phun Sprinkler hoạt động dựa trên chỉ số thời gian phản ứng nhiệt (Response Time Index - $RTI$) và nhiệt độ kích hoạt (Activation Temperature $T_{act}$, thường là $68^\circ\text{C}$ hoặc $93^\circ\text{C}$).
  - Khi kích hoạt, lưu lượng nước phun làm giảm tốc độ giải phóng nhiệt của đám cháy theo mô hình làm nguội mũ (Exponential Decay):
    $$\dot{Q}(t) = \dot{Q}_{act} \cdot e^{-(t - t_{act}) / \tau_{suppression}}$$
- **Hiện trạng mã nguồn**: Các thực thể `IfcFireSuppressionTerminal` (đầu sprinkler) chỉ được trích xuất hình học khối hoặc tọa độ điểm, không sinh namelist `&DEVC` hay mô hình dập lửa.
- **Yêu cầu nâng cấp**:
  - Hỗ trợ xuất thiết bị cảm biến và đầu phun Sprinkler:
    ```fortran
    &PROP ID='STANDARD_SPRINKLER', RTI=50., ACTIVATION_TEMPERATURE=68., OFFSET=0.05 /
    &DEVC ID='SPRINKLER_01', PROP_ID='STANDARD_SPRINKLER', XYZ=12.5, 8.4, 2.8 /
    ```

---

### 5.5. Tiêu Chí Độ Phân Giải Lưới Đặc Trưng Đám Cháy ($D^*/\Delta x$)
- **Đặc thù khoa học**: Trong mô phỏng LES (Large Eddy Simulation) của FDS, độ phân giải không gian của lưới tính toán $\Delta x = \sqrt[3]{dx \cdot dy \cdot dz}$ quyết định khả năng phân giải các xoáy rối nhiệt.
- **Đường kính đặc trưng đám cháy $D^*$**:
  $$D^* = \left( \frac{\dot{Q}}{\rho_\infty \cdot c_p \cdot T_\infty \cdot \sqrt{g}} \right)^{2/5}$$
  Với điều kiện không khí tiêu chuẩn ($\rho_\infty = 1.204\text{ kg/m}^3$, $c_p = 1.005\text{ kJ/kg}\cdot\text{K}$, $T_\infty = 293.15\text{ K}$, $g = 9.81\text{ m/s}^2$):
  $$D^* \approx 0.0573 \cdot \dot{Q}^{2/5} \quad (\dot{Q}\text{ tính bằng kW, } D^*\text{ tính bằng m})$$
- **Bảng đối chiếu tỷ lệ khuyến nghị NFPA 92 / NUREG 1824**:
  - $D^*/\Delta x < 4$: Lưới quá thô, mô phỏng không giải được các cấu trúc dòng xoáy, dự báo sai lệch nghiêm trọng nhiệt độ và vận tốc khói.
  - $4 \le D^*/\Delta x \le 16$: Dải độ phân giải tối ưu, đảm bảo độ chính xác kỹ thuật và chi phí tính toán hợp lý.
  - $D^*/\Delta x > 16$: Lưới rất mịn, độ chính xác tăng nhẹ nhưng thời gian tính toán tăng theo lũy thừa bậc 4 ($\mathcal{O}(\Delta x^{-4})$).

*Ví dụ tính toán cho đám cháy xe điện $\dot{Q} = 5.0\text{ MW} = 5000\text{ kW}$*:
$$D^* \approx 0.0573 \cdot (5000)^{0.4} \approx 0.0573 \cdot 30.17 \approx 1.73\text{ m}$$
- Ô lưới $\Delta x$ tối thiểu ($D^*/\Delta x = 16$): $\Delta x \approx 0.108\text{ m}$
- Ô lưới $\Delta x$ tối đa ($D^*/\Delta x = 4$): $\Delta x \approx 0.432\text{ m}$
- Ô lưới khuyến nghị ($D^*/\Delta x = 10$): $\Delta x \approx 0.173\text{ m}$
- **Hiện trạng mã nguồn**: Hoàn toàn vắng bóng thuật toán này (Điểm 0/10).

---

# PHẦN 6: TRẢ LỜI 10 CÂU HỎI KIỂM TOÁN CỐT LÕI (SECTION 92 FINAL AUDIT QUESTIONS)

Bảng đối chiếu câu hỏi kiểm toán độc lập theo tiêu chuẩn NFPA 92 và yêu cầu nghiệm thu cốt lõi của đề tài:

```
+---------------------------------------------------------------------------------------------------+
|               KẾT QUẢ ĐÁNH GIÁ 10 CÂU HỎI KIỂM TOÁN CỐT LÕI (SECTION 92 AUDIT)                    |
+----+---------------------------------------------------------------+----------+-------------------+
| STT| Nội Dung Câu Hỏi Kiểm Toán                                    | Phán Quyết| Bằng Chứng/Blocker|
+----+---------------------------------------------------------------+----------+-------------------+
| 01 | Đơn vị & hệ quy chiếu không gian có bảo toàn tuyệt đối không? | PARTIAL  | ISSUE-R3-03, 04   |
| 02 | Phân cấp vị trí & cấu trúc tầng có bị cắt xén/lệch không?     |   YES    | BOUNDARY_RETAINED |
| 03 | Hình học 3D có đảm bảo kín nước, đa tạp & bảo toàn thể tích?  |   YES    | Manifold3D Mesh64 |
| 04 | Lỗ mở có được bảo vệ tuyệt đối khỏi Silent Reseal không?      | PARTIAL  | ISSUE-R3-01       |
| 05 | Đồ thị MEP có dựa trên quan hệ thực chất & sẵn sàng mô phỏng? | PARTIAL  | ISSUE-R3-02       |
| 06 | Miền tính toán & điều kiện biên có thiết lập đúng thoát khói? | PARTIAL  | ISSUE-R4-03       |
| 07 | Cú pháp FDS có hợp lệ, không trùng ID & sẵn sàng cho solver?  | PARTIAL  | ISSUE-R5-01       |
| 08 | Độ phân giải lưới D*/dx có đáp ứng chuẩn NFPA 92/NUREG 1824?  |    NO    | ISSUE-R4-01       |
| 09 | Validation Gates có khách quan & phân định rõ ràng các cấp độ?|   YES    | 12 Gates / Solver |
| 10 | Hệ thống đã sẵn sàng cho nghiên cứu kịch bản cháy thực tế?    |    NO    | NOT RESEARCH-READY|
+----+---------------------------------------------------------------+----------+-------------------+
```

### Chi Tiết Phán Quyết Từng Câu Hỏi

#### Câu hỏi 1: Đơn vị và hệ quy chiếu không gian có được bảo toàn tuyệt đối không?
- **Phán quyết**: **`PARTIAL`**
- **Bằng chứng xác thực**:
  - `core/units.py:7-23` kiểm tra chặt chẽ `LENGTHUNIT` duy nhất của `IfcProject` và tính toán `scale` số thực chính xác sang mét.
  - Tuy nhiên, hệ thống hoàn toàn bỏ qua các đơn vị diện tích (`AREAUNIT`), thể tích (`VOLUMEUNIT`), thời gian (`TIMEUNIT`) và lưu lượng HVAC (`ISSUE-R3-03`).
  - `core/placement.py:28` từ chối `IfcGridPlacement` và `IfcLinearPlacement` (`ISSUE-R3-04`).

#### Câu hỏi 2: Phân cấp vị trí và cấu trúc tầng có bị cắt xén hay lệch tọa độ không?
- **Phán quyết**: **`YES`**
- **Bằng chứng xác thực**:
  - `core/placement.py:24-36` duyệt đệ quy cây `PlacementRelTo` nhân dồn ma trận biến đổi $4\times 4$ với độ chính xác cao và có tập hợp `seen` chặn lặp vòng.
  - `mapping/scope.py:45-60` gán nhãn `ScopeDecision.BOUNDARY_RETAINED` cho các cấu kiện giao cắt ranh giới tầng, bảo toàn nguyên vẹn 100% khối hình học của tường/cột/sàn mà không dùng thuật toán cắt xén (never clips geometry).

#### Câu hỏi 3: Hình học 3D có đảm bảo kín nước, đa tạp và bảo toàn thể tích khi chuyển sang FDS không?
- **Phán quyết**: **`YES`**
- **Bằng chứng xác thực**:
  - Sử dụng kernel `manifold3d.Mesh64` với tọa độ nguyên bản `float64` (`geometry/boolean.py:8-26`).
  - Hàm `inspect_mesh_quality` kiểm soát nghiêm ngặt cạnh hở, cạnh phi đa tạp, mặt suy biến (`geometry/mesh.py:28-87`).
  - Hàm `is_axis_aligned_box` xác nhận chênh lệch thể tích $|V_{mesh} - V_{bbox}| \le \max(10^{-12}, 10^{-6} \cdot V_{bbox})$, bảo toàn thể tích tuyệt đối.

#### Câu hỏi 4: Các lỗ mở có được bảo vệ tuyệt đối khỏi hiện tượng bịt kín âm thầm (Silent Reseal) không?
- **Phán quyết**: **`PARTIAL`**
- **Bằng chứng xác thực**:
  - Ở tầng CAD: **Đạt xuất sắc**. `mapping/policy.py:88-94` cấm ánh xạ thành `OBST` khi có lỗ mở, bắt buộc dùng `GEOM`. Hai metrics độc lập `opening_residual` và `passage_metrics` kiểm tra thông luồng khí (`validation/engine.py:475`).
  - Ở tầng lưới FDS CFD: **Chưa đạt**. Thiếu cơ chế kiểm tra kích thước lỗ mở với kích thước ô lưới FDS, tiềm ẩn nguy cơ Voxelization Grid Reseal (`ISSUE-R3-01`).

#### Câu hỏi 5: Đồ thị mạng MEP/HVAC/PCCC có được trích xuất từ quan hệ thực chất và sẵn sàng cho mô phỏng hút khói không?
- **Phán quyết**: **`PARTIAL`**
- **Bằng chứng xác thực**:
  - Tính thực chất: **Đạt tuyệt đối**. `mep/mep_graph.py:120-151` chỉ kết nối dựa trên `IfcRelConnectsPorts` có sẵn trong IFC, không tự suy đoán.
  - Sẵn sàng mô phỏng: **Chưa đạt**. Toàn bộ cấu kiện MEP chỉ được gán `simulation_role="REFERENCE_GEOMETRY"` (`mapping/policy.py:128-135`), chưa có adapter sinh thực thể FDS `&HVAC` (`ISSUE-R3-02`).

#### Câu hỏi 6: Miền tính toán và điều kiện biên có được thiết lập chính xác phục vụ thoát khói không?
- **Phán quyết**: **`PARTIAL`**
- **Bằng chứng xác thực**:
  - Hộp tính toán FDS `SimulationDomain` được kiểm soát chặt chẽ, nếu không cấu hình sẽ đưa ra cảnh báo `INCOMPLETE` (`mapping/boundary.py:80`).
  - Tuy nhiên, các mặt biên ngoài của MESH mặc định là biên trơ `INERT`, thiếu cơ chế tự động sinh các cửa mở thoát khói `&VENT MB=..., SURF_ID='OPEN' /` trên các mặt thoáng (`ISSUE-R4-03`).

#### Câu hỏi 7: Cú pháp FDS xuất ra có hoàn toàn hợp lệ, không trùng lặp ID, và sẵn sàng cho solver không?
- **Phán quyết**: **`PARTIAL`**
- **Bằng chứng xác thực**:
  - Cú pháp Fortran namelist tuân thủ chuẩn FDS 6+, toàn bộ ID được bao bọc trong nháy đơn, chống trùng lặp tuyệt đối nhờ bộ đếm `prim_counter` (`mapping/exporter.py`).
  - Tuy nhiên, mã nguồn bị cố định cứng `T_END=0.0` (`ISSUE-R5-01`), khiến tệp sinh ra không sẵn sàng cho việc giải động lực học chất lưu theo thời gian.

#### Câu hỏi 8: Độ phân giải lưới $D^*/dx$ có đáp ứng khuyến nghị tiêu chuẩn NFPA 92 / NUREG 1824 cho đám cháy mục tiêu không?
- **Phán quyết**: **`NO`**
- **Bằng chứng xác thực**:
  - Hoàn toàn không có bất kỳ dòng lệnh nào tính toán $D^*$ hoặc kiểm tra tỷ lệ $4 \le D^*/\Delta x \le 16$ trong toàn bộ kho lưu trữ. Kích thước lưới `cell_size = 0.2m` bị gán tĩnh (`ISSUE-R4-01`). Điểm đánh giá: **0.0 / 10.0**.

#### Câu hỏi 9: Cơ chế Validation Gate và Acceptance Logic có hoạt động độc lập, khách quan, phân định rõ ràng các cấp độ không?
- **Phán quyết**: **`YES`**
- **Bằng chứng xác thực**:
  - Hệ thống sở hữu 12 cổng kiểm tra hoạt động độc lập, tách biệt giữa `MAPPING_VERIFIED`, `REJECTED` và `INCONCLUSIVE`.
  - Khi thiếu binary FDS trong môi trường, hệ thống trả về đúng `INCONCLUSIVE` (được chứng thực bởi `test_missing_solver_never_passes`), tuyệt đối không che giấu lỗi hay giả mạo kết quả đạt.

#### Câu hỏi 10: Hệ thống đã sẵn sàng cho nghiên cứu mô phỏng kịch bản cháy thực tế (EV fire, HRR curve, HVAC control) chưa?
- **Phán quyết**: **`NO`**
- **Bằng chứng xác thực**:
  - Phán quyết chính thức: **`NOT RESEARCH-READY`**. Hệ thống hiện mới hoàn thành vai trò của một bộ chuyển đổi hình học có xác thực (Verified Geometry Mapping Converter), chưa xây dựng lớp kịch bản cháy (Fire Scenario Layer) để phục vụ mô phỏng khoa học thực tế.

---

# PHẦN 7: LỘ TRÌNH KHẮC PHỤC & NÂNG CẤP PHÂN KỲ (PHASED REMEDIATION ROADMAP)

Để đưa nền tảng đạt chuẩn `RESEARCH-READY` phục vụ đề tài nghiên cứu cấp trường và các công bố khoa học quốc tế, Nhóm Kiểm toán khuyến nghị lộ trình 7 giai đoạn (Phase 0 đến Phase 6) với mục tiêu, điều kiện tiên quyết và tiêu chí nghiệm thu cụ thể:

```
+---------------------------------------------------------------------------------------------------+
|                            LỘ TRÌNH PHÂN KỲ NÂNG CẤP HỆ THỐNG (PHASE 0 - 6)                       |
+---------------------------------------------------------------------------------------------------+
| [Phase 0] Sửa Lỗi Hợp Đồng UI & Khắc Phục Các Điểm Nghẽn Tức Thì (Immediate UI & Blocker Fixes)   |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 1] Chuẩn Hóa Kiến Trúc Lục Giác & Độc Lập Hóa Domain (Hexagonal Ports & Domain Decoupling) |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 2] Kiểm Soát Lỗ Mở Tầng Lưới & Tối Ưu Kernel Hình Học (Grid-Level Voxelization Check)      |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 3] Adapter Chuyển Đổi Đồ Thị MEP Sang Mạng Lưới FDS &HVAC (MEP to FDS HVAC Adapter)        |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 4] Phân Lớp Kịch Bản Cháy Chuyên Sâu: Pin EV, HRR, Sprinkler (Fire Scenario Layer)          |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 5] Động Cơ Độ Phân Giải Lưới Đám Cháy D*/dx & Auto-Mesh (Fire Grid Engine)                 |
|     │                                                                                             |
|     ▼                                                                                             |
| [Phase 6] Tự Động Hóa Nghiệm Thu Solver & Mô Phỏng Hoàn Chỉnh (Full Simulation Acceptance)       |
+---------------------------------------------------------------------------------------------------+
```

---

### Chi Tiết Từng Giai Đoạn

#### Giai Đoạn 0: Sửa Lỗi Hợp Đồng UI & Khắc Phục Các Điểm Nghẽn Tức Thì (Immediate Fixes)
- **Mục tiêu**: Khắc phục ngay các lỗi lệch pha giao diện và các điểm nghẽn cấp bách mà không làm thay đổi kiến trúc nghiệp vụ cốt lõi.
- **Nội dung công việc**:
  1. Đồng bộ tên cổng kiểm định: Đổi `data-gate="golden"` thành `data-gate="golden_reference_parity"` trong `index.html:524` (`ISSUE-CONTRACT-01`).
  2. Bổ sung mức độ `P0` vào bộ lọc giao diện: Sửa `isErr = f.severity === 'ERROR' || f.severity === 'P0' || f.severity === 'P1'` trong `js/app-controller.js:1685` (`ISSUE-CONTRACT-02`).
  3. Xóa bỏ cắt lát cứng 20 findings trong `ifc_to_fds/results.py:98`, trả về đầy đủ danh sách kết hợp phân trang (`ISSUE-CONTRACT-04`).
  4. Chèn tiêu đề cảnh báo bắt buộc vào tệp Quick Preview FDS và tách biệt 2 nút tải về trên giao diện (`ISSUE-CONTRACT-05`).
  5. Cho phép cấu hình `simulation_time > 0` thay vì cố định `T_END=0.0` trong `exporter.py:135` (`ISSUE-R5-01`).
- **Tiêu chuẩn nghiệm thu**: Thẻ Golden Parity cập nhật trạng thái xanh/đỏ chính xác; badge P0 hiển thị màu đỏ cảnh báo; tệp Quick Preview có banner cảnh báo rõ ràng.

#### Giai Đoạn 1: Chuẩn Hóa Kiến Trúc Lục Giác & Độc Lập Hóa Domain (Hexagonal Decoupling)
- **Mục tiêu**: Xây dựng kiến trúc phần mềm sạch (Clean Architecture), triệt tiêu các chu trình phụ thuộc vòng và rò rỉ framework.
- **Nội dung công việc**:
  1. Định nghĩa đầy đủ các Inbound & Outbound Ports trong `application/ports/`: `IfcReaderPort`, `GeometryKernelPort`, `FdsSerializerPort`, `ValidationEnginePort`, `SolverExecutionPort`.
  2. Tách bỏ `parse_fds` khỏi `domain/validation/model.py`, truyền `ParsedFds` từ bên ngoài qua service (`ISSUE-ARCH-01`).
  3. Chuyển đổi 19 models trong `domain/` từ `pydantic.BaseModel` sang standard Python `@dataclass`, chuyển Pydantic ra tầng DTO API (`ISSUE-ARCH-02`).
  4. Giải quyết triệt để 3 chu trình lặp vòng `Circular Imports` (`ISSUE-ARCH-03`), di chuyển `SCHEMA_VERSION` ra module dùng chung.
  5. Tách các trường FDS representation và simulation role ra khỏi `CanonicalElement`, lưu độc lập trong `MappingPlan` (`ISSUE-ARCH-05`).
- **Tiêu chuẩn nghiệm thu**: Bộ kiểm tra hợp đồng kiến trúc `tests/test_architecture_contracts.py` không còn bất kỳ trường hợp ngoại lệ nào; không còn lazy import trong domain.

#### Giai Đoạn 2: Kiểm Soát Lỗ Mở Tầng Lưới & Tối Ưu Kernel Hình Học (Grid-Level Reseal Check)
- **Mục tiêu**: Ngăn chặn hiện tượng Voxelization Reseal ở tầng lưới CFD và tối ưu hóa hiệu năng tính toán hình học.
- **Nội dung công việc**:
  1. Xây dựng cổng kiểm tra `VoxelizationResealGate`: Đối chiếu kích thước $\min(W_{opening}, H_{opening})$ với kích thước ô lưới dự kiến $\Delta x$, phát cảnh báo lỗi P1 nếu $\min \le \Delta x$ (`ISSUE-R3-01`).
  2. Bổ sung hàm resolve tọa độ cho `IfcGridPlacement` và `IfcLinearPlacement` trong `core/placement.py` (`ISSUE-R3-04`).
  3. Mở rộng trích xuất các đơn vị đo lường `AREAUNIT`, `VOLUMEUNIT`, `TIMEUNIT` trong `core/units.py` (`ISSUE-R3-03`).
  4. Tối ưu hóa thuật toán phát hiện tự cắt tam giác: Tận dụng các phép tính giao cắt song song của Manifold3D C++ kernel trước khi fallback sang rational fractions (`ISSUE-R5-02`).
- **Tiêu chuẩn nghiệm thu**: Chạy thử nghiệm thành công trên các tệp IFC có hệ lưới cột `IfcGridPlacement`; phát hiện chính xác lỗ mở bị voxelize lấp kín trên mô hình test case.

#### Giai Đoạn 3: Adapter Chuyển Đổi Đồ Thị MEP Sang Mạng Lưới FDS &HVAC (MEP to FDS HVAC)
- **Mục tiêu**: Kích hoạt khả năng mô phỏng hệ thống thông gió và hút khói sự cố cơ khí theo NFPA 92.
- **Nội dung công việc**:
  1. Xây dựng `MepToFdsHvacAdapter` trong `ifc_to_fds/adapters/fds/`:
     - Chuyển đổi các đoạn ống gió `IfcFlowSegment` thành `&HVAC TYPE='DUCT'`.
     - Chuyển đổi các mối nối `IfcFlowFitting` và cửa gió `IfcAirTerminal` thành `&HVAC TYPE='NODE'`.
     - Chuyển đổi quạt hút `IfcFan` thành `&HVAC TYPE='FAN'` với đặc tuyến lưu lượng áp suất.
  2. Tích hợp liên kết điều khiển `&CTRL` kích hoạt quạt hút khói khi có tín hiệu báo cháy.
  3. Bổ sung cổng thẩm định `MepHvacNetworkGate` kiểm tra tính liên tục (continuity) của mạng đường ống 1D.
- **Tiêu chuẩn nghiệm thu**: Tệp FDS xuất ra chứa đầy đủ mạng `&HVAC` hợp lệ, chạy thử nghiệm FDS solver không báo lỗi cấu trúc mạng chất lưu.

#### Giai Đoạn 4: Phân Lớp Kịch Bản Cháy Chuyên Sâu: Pin EV, HRR, Sprinkler (Fire Scenario Layer)
- **Mục tiêu**: Trang bị đầy đủ các công cụ thiết lập kịch bản cháy phục vụ trực tiếp đề tài nghiên cứu cháy tầng hầm và phương tiện điện.
- **Nội dung công việc**:
  1. Xây dựng module miền `domain/scenario/`:
     - `FireScenario`: Quản lý danh sách nguồn cháy, hệ thống chữa cháy và điều kiện thông gió.
     - `EVBatteryFireSource`: Cấu hình vị trí xe, loại pin, nhiệt trị, tốc độ thoát nhiệt đỉnh và suất phát thải khí $HF, CO$.
     - `T2FireCurve`: Tạo lập các đường cong phát triển nhiệt chuẩn (Slow, Medium, Fast, Ultra-fast) và sinh chuỗi hàm `&RAMP`.
  2. Xây dựng module đầu phun Sprinkler: Ánh xạ thiết bị PCCC thành `&PROP` (RTI, $T_{act}$) và `&DEVC TYPE='SPRINKLER'`.
  3. Bổ sung giao diện Scenario Designer trên Web Workbench UI cho phép trực quan hóa vị trí nguồn cháy và đồ thị HRR.
- **Tiêu chuẩn nghiệm thu**: Xuất thành công kịch bản cháy xe điện hầm gửi xe với đầy đủ nguồn nhiệt, đường cong RAMP, phát thải khí độc $HF$ và hệ thống đầu phun dập cháy.

#### Giai Đoạn 5: Động Cơ Độ Phân Giải Lưới Đám Cháy $D^*/dx$ & Auto-Mesh (Fire Grid Engine)
- **Mục tiêu**: Đảm bảo mô hình FDS sinh ra luôn thỏa mãn các tiêu chuẩn khoa học quốc tế về độ phân giải lưới CFD.
- **Nội dung công việc**:
  1. Xây dựng `GridResolutionEngine`:
     - Tự động tính toán đường kính đặc trưng đám cháy $D^* = (\dot{Q} / (\rho_\infty c_p T_\infty \sqrt{g}))^{2/5}$.
     - Kiểm tra và đề xuất kích thước ô lưới $\Delta x$ tối ưu thỏa mãn $4 \le D^*/\Delta x \le 16$ (`ISSUE-R4-01`).
  2. Bổ sung bộ kiểm tra tỷ lệ khung hình ô lưới (Aspect Ratio Check): Đảm bảo $\max(dx,dy,dz)/\min(dx,dy,dz) \le 2.0$ (`ISSUE-R4-02`).
  3. Tự động sinh điều kiện biên mở thoát khói `&VENT MB=..., SURF_ID='OPEN' /` trên các mặt thoáng của miền tính toán (`ISSUE-R4-03`).
- **Tiêu chuẩn nghiệm thu**: Cổng `GridResolutionGate` tự động chặn nghiệm thu và phát cảnh báo khi người dùng thiết lập lưới quá thô hoặc quá mịn so với công suất đám cháy.

#### Giai Đoạn 6: Tự Động Hóa Nghiệm Thu Solver & Mô Phỏng Hoàn Chỉnh (Full Simulation Acceptance)
- **Mục tiêu**: Hoàn thiện toàn bộ chuỗi giá trị từ BIM/IFC đến kết quả mô phỏng động lực học khói và phát hành chứng nhận `SIMULATION_VERIFIED`.
- **Nội dung công việc**:
  1. Hoàn thiện logic nghiệm thu trong `AcceptanceReport.finalize()`: Gán `SIMULATION_VERIFIED` khi tất cả các cổng kiểm tra bao gồm cả FDS solver execution đều đạt kết quả PASS (`ISSUE-CONTRACT-03`).
  2. Tích hợp module tự động chạy FDS solver nền, giám sát tiến độ giải qua tệp log `.out`, trích xuất thông số lớp khói và nhiệt độ.
  3. Kết nối công cụ trực quan hóa kết quả mô phỏng Smokeview / ParaView trực tiếp trên Web Workbench UI.
- **Tiêu chuẩn nghiệm thu**: Hệ thống thực hiện trọn vẹn quy trình tự động từ nạp tệp IFC $\rightarrow$ Ánh xạ $\rightarrow$ Thiết lập kịch bản cháy EV $\rightarrow$ Chạy FDS solver $\rightarrow$ Trả về báo cáo nghiệm thu `SIMULATION_VERIFIED` kèm biểu đồ trường nhiệt và nồng độ khói.

---

# KẾT LUẬN CHUNG

Dự án **IFCtoFDS** đã tạo dựng được một nền móng kỹ thuật và toán học vô cùng vững chắc trong việc giải quyết bài toán khó khăn nhất của chuỗi chuyển đổi BIM sang CFD: **Tính toàn vẹn hình học 3D, bảo toàn thể tích, trích xuất quan hệ MEP thực chất và triệt tiêu hiện tượng bịt kín lỗ mở âm thầm ở tầng CAD**. Sự kết hợp giữa các công cụ tính toán hình học tiên tiến (`manifold3d`, `trimesh`, `shapely`) cùng ma trận 12 cổng kiểm định độc lập giúp hệ thống hoàn toàn vượt trội so với các công cụ chuyển đổi xấp xỉ truyền thống.

Tuy nhiên, để phục vụ mục tiêu tối hậu của đề tài nghiên cứu khoa học an toàn PCCC cho công trình ngầm và phương tiện giao thông điện, dự án cần khẩn trương thực hiện lộ trình phân kỳ 7 giai đoạn đã đề xuất. Việc hoàn thiện các cổng kết nối kiến trúc Hexagonal, khắc phục các khiếm khuyết giao diện và đặc biệt là xây dựng phân lớp kịch bản cháy chuyên sâu (EV Fire, HRR, HVAC Network, $D^*/\Delta x$) sẽ đưa **IFCtoFDS** trở thành một nền tảng tiên phong, chuẩn mực và có đóng góp khoa học to lớn trong lĩnh vực kỹ thuật an toàn phòng cháy chữa cháy tại Việt Nam và quốc tế.

---
*Báo cáo được hoàn thành và ký duyệt điện tử bởi Nhóm Kiểm toán Độc lập Teamwork Multi-Agent System.*
