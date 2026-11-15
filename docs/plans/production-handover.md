# IFCtoFDS — bàn giao tiến độ (2026-11-15, sau PR #114)

Văn bản này tóm tắt trạng thái tại `main` `d32dd7b` (đã gồm PR #109–#114). Nguồn sự thật chi tiết vẫn là [kế hoạch production](production-roadmap.md); cách kiểm thử trên dữ liệu thật nằm ở [kế hoạch kiểm thử thực tế](real-world-test-plan.md). Quy tắc làm việc của agent nằm ở `AGENTS.md` và `CLAUDE.md`.

## 1. Mục tiêu và mức đạt
Mục tiêu: IFC tầng hầm thật → deck FDS 6.11.1 kiểm định được (mapping + HVAC vận hành + cháy xe điện), qua CLI và Web/API, có kỹ sư PCCC review.

| Hạng mục | Mức đạt | Bằng chứng |
|---|---|---|
| CLI `convert` / `audit` chạy từ tiến trình mới | Đạt | test cold start, CI |
| Mapping và kiểm định độc lập trên IFC mẫu | Đạt (FZK, Duplex, Institute, fixture) | suite mặc định 1323 đạt (nhánh bàn giao, gồm PR #114); verdict snapshot trùng `main` |
| IFC thật A/B/C | **B đạt `MAPPING_VERIFIED`** (218 phần tử MATCHED, ngưỡng hình học mới 1e-9); A, C chưa | A: 22 cửa lỗi nguồn; C: lỗi nguồn và cần `--storey`; deck CLI và web trùng từng byte trên A và B |
| Hiệu năng | **C đạt, A chưa** | C tầng hầm cold 293 s (đích 300); A cold 170 s (đích 120) |
| Hình học hiệu dụng cấp solver | Một phần | OBST/VENT/OBST điều khiển đọc từ SMV; A toàn GEOM nên INCONCLUSIVE |
| HVAC vận hành | Một phần | ống thẳng, phụ kiện hai cổng, tê/Y/gót giày (nút có `LOSS(i,j)` đã duyệt), quạt lưu lượng cố định; FDS khớp tính tay (tổn áp 0,5%, tách dòng 5%, khối lượng 1%) |
| Cháy xe điện | Một phần | phát lại đường HRR đo; năng lượng khớp 0,02% |
| Web/API vận hành | Một phần | `TMPDIR` trên volume, backup/restore trên job thật, image có FDS, hàng đợi và khởi động lại đã diễn tập trên C |
| Đối chiếu PyroSim | **Chưa so được** | máy không có PyroSim và không có deck PyroSim; đã có script `compare-fds-decks.py` (PR #114, đã merge) |
| Nghiệm thu kỹ sư | Chưa | cần người |

## 2. Đã giao từ lần bàn giao trước
- **PR #110 (M1.7, M5.2):** oracle winding number nhanh hơn 3,5 lần; drill job dài trên C ở chế độ local và production.
- **PR #111 (M5.5, M3.3/M3.4/M3.6):** deck CLI và web trùng từng byte trên A, B; tê/Y/gót giày thành một nút FDS với `LOSS(i,j)`, kiểm bằng FDS thật.
- **PR #112 (audit lần 1):** năm sửa chữa — chèn lệnh FDS qua tên IFC có xuống dòng (đường Quick), thư mục upload mồ côi khi đĩa đầy, job `MAPPING_VERIFIED` không bao giờ hết hạn, upload song song vượt hàng đợi, băm lại bằng chứng ở mỗi request.
- **PR #113 (audit lần 2):**
  - `CHID` từ tên file thay `.` bằng `_`. Trước đây `Ham2Tang.v2.ifc` ra `MAPPING_VERIFIED` nhưng FDS dừng với `ERROR(108): No periods allowed in CHID`; cổng syntax cũng cho phép dấu chấm.
  - `audit` không lấy `accepted_source_defects` từ manifest nữa; mỗi lỗi nguồn đã miễn là một finding P2 trong báo cáo.
  - Ngưỡng hình học mặc định đổi sang 1e-9 (hợp đồng đổi, ghi trong `CHANGELOG.md`); kiểm tra lỗ mở giữ nhiễu Boolean cũ qua `PASSAGE_NOISE_M`.
  - Tách `_dispatch`, hạn chót job dùng `time.monotonic`, `permissions` cho `verified.yml`, test baseline ghi ra `tmp_path`, bỏ mã chết.
- **PR #114:** `scripts/compare-fds-decks.py` và Tầng 5 của kế hoạch kiểm thử thực tế.

## 3. Chưa hoàn thiện
**A. Làm được ngay, không cần đầu vào từ người dùng:**
| Mục | Việc | Ghi chú |
|---|---|---|
| Sửa ngưỡng thể tích mới | 9 phần tử của C (8 `IfcCovering`, 1 `IfcColumn`) thành DEVIATED oan vì sai số thể tích tương đối 1,6e-8…5,2e-7 > 1e-9 dù bề mặt khớp tới 1e-15 m | đã đo (`tolerance-A-C.json`); đề xuất: thêm điều kiện tuyệt đối ≤ 1e-9 m³ cho sai số thể tích khi `surface_proven`; đổi hợp đồng nên cần duyệt |
| M1.7 (phần A) | Giảm thời gian A từ 170 s xuống 120 s | validation 73 s (quét tự giao cắt ~35 s, `compare_solids` 11, `passage_metrics` 9, `mesh_quality` 12); tái dùng bằng chứng theo `geometry.id` |
| Duplex chập chờn | tìm nguyên nhân finding `representation` "Manifest openings differs" (có ở một số lần chạy, không ở lần khác) | đọc lại IFC thì khớp từng trường; có thể liên quan thứ tự hoặc cache |
| M3.1 | Cơ chế bảng họ → loại phụ kiện cấu hình được, không khớp → `REVIEW_REQUIRED` | bảng cụ thể do kỹ sư duyệt |
| M0.3 | Bộ fixture phân loại tiếp xúc | hoãn từ M0 |
| A4 | 2 test `xfail`, khóa chẩn đoán cũ của client JS, ghim action CI theo SHA | nợ nhỏ |

**B. Bị chặn bởi đầu vào hoặc quyết định của người/kỹ sư:**
| Mục | Cần gì |
|---|---|
| T19–T21 đối chiếu PyroSim | deck `.fds` do PyroSim nhập A/B/C (kèm phiên bản và cài đặt nhập), và deck B / `tee.fds` mở rồi lưu lại bằng PyroSim; hoặc một máy có PyroSim. Công cụ so đã sẵn (`scripts/compare-fds-decks.py`) |
| M2.4 `effective_geometry` PASS trên A | chọn cách xử lý GEOM: đọc cut-cell từ SMV, quay mô hình theo từng cánh, hoặc xấp xỉ bậc thang (A có 0% OBST vì mọi tường/sàn không thẳng trục) |
| M3.1 (nội dung bảng), M3.2, M3.5 | nghĩa PAD/CEAD/OAD-FAD/RAD/TEAD; hệ nào hút khói; hệ số K, lưu lượng thiết kế từng miệng hút, đường cong quạt (B-ext 2, 3) |
| Hệ số K của tê/Y/gót giày | kỹ sư đưa đủ mọi cặp cổng có thứ tự cho 84 phụ kiện của C (cơ chế đã có; K quy chiếu theo vận tốc ống đích) |
| Ma sát ống chữ nhật | có hiệu chỉnh hay không: FDS thấp hơn khoảng 18% với ống 0,5×0,3 m; `ROUGHNESS=0` là không ma sát |
| Ngưỡng hình học khác 0 | nếu kỹ sư muốn dung sai (ví dụ 1 mm) thì khai trong `audit`; không còn là mặc định |
| T6: 22 cửa lỗi nguồn của A | kỹ sư duyệt từng cửa để điền `accepted_source_defects` |
| M4.1, M4.3, M4.4 | số đo cháy nguyên xe được phép dùng, yield, tính chất vật liệu có nguồn (B-ext 4) |
| M5.6 | QoI nghiệm thu (nhiệt độ/tầm nhìn tại lối thoát, độ cao lớp khói) (B-ext 5) |
| M5.7 | kỹ sư PCCC độc lập review |
| A và C có chung không gian hầm không | transform chung (B-ext 1) |

## 4. Rủi ro và điều cần biết
- **Đối chiếu PyroSim:** chưa có số liệu nào. Chạy `audit` trên deck PyroSim thường cho REJECTED với mọi phần tử MISSING vì deck không có `! IFC_SOURCE` (đã thử bằng cách xóa các dòng này khỏi deck FZK của dự án). Chưa biết PyroSim có giữ dòng chú thích `!` và mảng `LOSS(i,j)` khi mở rồi lưu hay không; nếu không giữ, deck sửa trong PyroSim sẽ mất truy vết.
- **Ngưỡng mới đã đo trên A và C (2026-11-15):** A không đổi; C có 9 phần tử MATCHED → DEVIATED oan (nhiễu Boolean, xem mục 3A). Verdict hai tòa vẫn REJECTED như trước. Thời gian các lượt đo không so được.
- **Job `MAPPING_VERIFIED` hết hạn sau 30 ngày** (`IFCFDS_DURABLE_RETENTION_S`, `0` = giữ vô hạn). Ai cần giữ lâu hơn phải đặt biến này.
- **Cache xác minh bằng bằng chứng** không thấy việc sửa file cùng kích thước mà còn khôi phục đúng mtime; kiểm đầy đủ vẫn chạy sau khi khởi động lại.
- Thời gian đo chỉ so sánh được trong cùng phiên kèm lượt đối chứng (máy từng chậm 5,6 lần). Không chạy hai phép đo cùng lúc.
- Windows: đường dẫn artifact vượt 260 ký tự nếu gốc thư mục dài; script dùng `ProcessPoolExecutor` cần `if __name__ == "__main__"`.
- Công cụ shell của agent biến `\n` và `\u…` trong chuỗi thành ký tự thật khi ghi file bằng heredoc Python; dùng Edit hoặc Write cho chuỗi chứa chúng.
- Hook của môi trường có thể cắt đầu ra lệnh dài; đọc lại bằng Read hoặc ghi ra file khi cần.
- `air_path` vẫn dùng Boolean của Manifold khi có phần tử vỏ bao lệch nguồn; khi đó có thể INCONCLUSIVE. Phép giao trực tiếp của Manifold mất khoảng 0,3% thể tích trên mặt trùng (đo trên deck B); script so deck vì vậy tính từ hai phép hiệu.
- 21 commit đầu của nhánh #109 viết tiếng Anh kèm trailer Claude (trước khi có `AGENTS.md`); giữ nguyên theo quyết định của người dùng.

## 5. Cách tiếp tục
1. Đọc `AGENTS.md`, rồi Phần A và mốc liên quan ở `production-roadmap.md`.
2. `uv sync --locked --extra test`; `python scripts/install-fds.py` nếu cần solver.
3. Suite: `python -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=90` (~3 phút); solver: `IFCFDS_SOLVER=<fds_openmp> python -m pytest -q -m solver` (17 test, ~5 phút; trên Windows thêm thư mục `bin/mpi` của FDS vào `PATH` nếu chạy `fds_openmp.exe` trực tiếp).
4. Trước khi đẩy PR: cổng nợ `PYTHONUTF8=1 python scripts/quality/source_quality_budget.py --git-base <merge-base>`.
5. Thứ tự đề xuất cho nhóm A: đo ngưỡng mới trên A và C → M1.7 (phần A) → nguyên nhân Duplex chập chờn → M3.1 → M0.3; mỗi mục một PR nhỏ, commit tiếng Việt, không trailer Claude.
6. Khi có deck PyroSim: `python scripts/compare-fds-decks.py <deck IFCtoFDS> <deck PyroSim> --json <ra.json>`, ghi kết quả vào T19–T21 và `docs/evidence/production-roadmap/` (chỉ số tổng hợp).
