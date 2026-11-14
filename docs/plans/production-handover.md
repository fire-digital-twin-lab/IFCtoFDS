# IFCtoFDS — bàn giao tiến độ (2026-11-15)

Văn bản này tóm tắt trạng thái tại thời điểm merge PR #109 vào `main`. Nguồn sự thật chi tiết vẫn là [kế hoạch production](production-roadmap.md); cách kiểm thử trên dữ liệu thật nằm ở [kế hoạch kiểm thử thực tế](real-world-test-plan.md). Quy tắc làm việc của agent nằm ở `AGENTS.md` và `CLAUDE.md`.

## 1. Mục tiêu và mức đạt
Mục tiêu: IFC tầng hầm thật → deck FDS 6.11.1 kiểm định được (mapping + HVAC vận hành + cháy xe điện), qua CLI và Web/API, có kỹ sư PCCC review.

| Hạng mục | Mức đạt | Bằng chứng |
|---|---|---|
| CLI `convert` / `audit` chạy từ tiến trình mới | Đạt | test cold start, CI |
| Mapping và kiểm định độc lập trên IFC mẫu | Đạt (FZK, Duplex, Institute, fixture) | suite 1280 đạt; verdict snapshot |
| IFC thật A/B/C | **Chưa MAPPING_VERIFIED** | A: 22 cửa lỗi nguồn; B: chưa tìm nguyên nhân rò; C: cần `--storey` |
| Hiệu năng | **Chưa đạt mục tiêu** | A 211–253 s (mục tiêu 120); C 477 s (mục tiêu 300) |
| Hình học hiệu dụng cấp solver | Một phần | OBST/VENT/OBST điều khiển đọc từ SMV; A toàn GEOM nên INCONCLUSIVE |
| HVAC vận hành | Một phần | ống thẳng, phụ kiện hai cổng, quạt lưu lượng cố định; tổn áp FDS khớp tính tay 0,5% |
| Cháy xe điện | Một phần | phát lại đường HRR đo; năng lượng khớp 0,02% |
| Web/API vận hành | Một phần | `TMPDIR` trên volume, backup/restore trên job thật, image có FDS |
| Nghiệm thu kỹ sư | Chưa | cần người |

## 2. Đã giao (trong PR #109)
Phần chi tiết và commit nằm ở Phần A của kế hoạch. Tóm tắt:
- **Nền và lỗi chặn:** CLI cold start, lối mở A△A, khóa frame, mốc verdict.
- **Tốc độ:** `has_self_intersection` vector hóa chính xác; tessellation instanced; prefetch 4 worker; so byte cho phần tử tham chiếu.
- **Kiến trúc:** một đường kiểm định, một `JobRepository`; tên gate gom về `domain/validation/model.py`; bỏ mã chết.
- **Tọa độ và tô-pô:** placement cứng, đơn vị SI, rebase, georeference; phân loại tiếp xúc; hợp nhất thành phần chồng lấn; `accepted_source_defects`.
- **M2:** hộp phủ OBST (mặc định bật), `air_path` chính xác, `effective_geometry` theo phần tử, gate `passage_resolution`.
- **M3 (một phần), M4 (một phần), M5.1/M5.3/M5.4.**

## 3. Chưa hoàn thiện
**A. Làm được ngay, không cần đầu vào từ người dùng** (agent tự làm theo kế hoạch):
| Mục | Việc | Ghi chú |
|---|---|---|
| M1.7 | Giảm thời gian A và C | **Đòn bẩy số 1 đã đo:** oracle `winding_numbers` trong `geometry/component_union.py` chiếm 196/252 s của đường đọc lại (1.500 phần tử C; 96 lần gọi, mỗi lần ~2 s). Bước dựng mesh chỉ ~44 s. Tiền quét phạm vi không tính khoang cửa nhanh 3,8 lần nhưng chỉ là đòn bẩy thứ hai |
| M5.5 | CLI và web cho cùng deck (so hash) trên A | cần chạy A hai đường |
| M5.2 | Job dài trên C: RSS đỉnh, timeout, khởi động lại giữa chừng | cần `--storey` của 8 tầng hầm C |
| M3.3/M3.4/M3.6(b) | Tổn thất nút `LOSS(I,J)` cho tê/Y/gót giày (84 phụ kiện của C) và kiểm bảo toàn khối lượng | dùng K làm đầu vào đã duyệt, kiểm bằng FDS với mạng tổng hợp |
| M3.1 | Cơ chế bảng họ → loại phụ kiện cấu hình được, không khớp → `REVIEW_REQUIRED` | bảng cụ thể do kỹ sư duyệt |
| M0.3 | Bộ fixture phân loại tiếp xúc | hoãn từ M0 |
| A4 | 2 test `xfail`, khóa chẩn đoán cũ của client JS | nợ nhỏ |

**B. Bị chặn bởi đầu vào hoặc quyết định của người/kỹ sư:**
| Mục | Cần gì |
|---|---|
| M2.4 `effective_geometry` PASS trên A | chọn cách xử lý GEOM: đọc cut-cell từ SMV, quay mô hình theo từng cánh, hoặc xấp xỉ bậc thang (A có 0% OBST vì mọi tường/sàn không thẳng trục) |
| M3.1 (nội dung bảng), M3.2, M3.5 | nghĩa PAD/CEAD/OAD-FAD/RAD/TEAD; hệ nào hút khói; hệ số K, lưu lượng thiết kế từng miệng hút, đường cong quạt (B-ext 2, 3) |
| Ma sát ống chữ nhật | có hiệu chỉnh hay không: FDS thấp hơn khoảng 18% với ống 0,5×0,3 m; `ROUGHNESS=0` là không ma sát |
| M4.1, M4.3, M4.4 | số đo cháy nguyên xe được phép dùng, yield, tính chất vật liệu có nguồn (B-ext 4) |
| M5.6 | QoI nghiệm thu (nhiệt độ/tầm nhìn tại lối thoát, độ cao lớp khói) (B-ext 5) |
| M5.7 | kỹ sư PCCC độc lập review |
| A và C có chung không gian hầm không | transform chung (B-ext 1) |

## 4. Rủi ro và điều cần biết
- Thời gian đo chỉ so sánh được trong cùng phiên kèm lượt đối chứng (máy từng chậm 5,6 lần). Không chạy hai phép đo cùng lúc.
- Windows: đường dẫn artifact vượt 260 ký tự nếu gốc thư mục dài; script dùng `ProcessPoolExecutor` cần `if __name__ == "__main__"`.
- Test tự ghi `tests/baseline/snapshots/baseline_metrics.json`; khôi phục bằng `git checkout` sau mỗi lần chạy suite.
- Công cụ shell của agent biến `\n` trong chuỗi thành xuống dòng thật khi ghi file bằng heredoc Python; dùng Edit cho chuỗi chứa `\n`.
- `air_path` vẫn dùng Boolean của Manifold khi có phần tử vỏ bao lệch nguồn; khi đó có thể INCONCLUSIVE.
- Các bước CI `solver-image` và upload 2×150 MiB đã được kiểm cục bộ bằng Docker; job `solver-image` đã đạt trên CI, bước upload chỉ chạy trong stack đầy đủ.
- 21 commit đầu của nhánh viết tiếng Anh kèm trailer Claude (trước khi có `AGENTS.md`); giữ nguyên theo quyết định của người dùng.

## 5. Cách tiếp tục
1. Đọc `AGENTS.md`, rồi Phần A và mốc liên quan ở `production-roadmap.md`.
2. `uv sync --locked --extra test`; `python scripts/install-fds.py` nếu cần solver.
3. Suite: `python -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=90` (~4–7 phút); solver: `IFCFDS_SOLVER=<fds_openmp> python -m pytest -q -m solver` (17 test, ~5 phút).
4. Trước khi đẩy PR: cổng nợ `PYTHONUTF8=1 python scripts/quality/source_quality_budget.py --git-base <merge-base>`.
5. Làm các mục nhóm A theo thứ tự M1.7 → M5.5 → M5.2 → M3.3/M3.4 → M3.1 → M0.3; mỗi mục một PR nhỏ, commit tiếng Việt, không trailer Claude.
