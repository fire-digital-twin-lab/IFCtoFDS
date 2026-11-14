# Bàn giao tiến độ — IFCtoFDS production roadmap

Cập nhật: 2026-11-14 (cuối phiên). Đọc cùng [production-roadmap.md](production-roadmap.md) (kế hoạch + checklist) và
[../evidence/production-roadmap/phase5-topology.md](../evidence/production-roadmap/phase5-topology.md).

## 1. Trạng thái git

- Nhánh làm việc: **`feat/phase5-4-component-union`**, HEAD `ad46452`. Chưa push nhánh nào. `main` vẫn ở `ff91299`.
- Chuỗi commit (cũ → mới), mỗi commit đều đã qua toàn suite (chỉ còn 3 lỗi cache có từ trước, xem §5):

| Commit | Nội dung |
|---|---|
| `e3d8592` | Giai đoạn 0–1: sửa vòng import CLI, lối mở A△A, khóa bbox/frame; `scripts/verdict-snapshot.py`, mốc verdict |
| `73e214d`, `6bb3328` | Giai đoạn 3: một đường validation, một JobRepository, test import cold |
| `392d8e0`, `ec24aba` | Giai đoạn 2: tăng tốc `has_self_intersection`, memo chất lượng mesh, bỏ monkey patch trimesh |
| `b24650b` | Giai đoạn 4: placement cứng, kiểu đơn vị, rebase cao độ tầng, provenance CRS |
| `ff4be54` | Giai đoạn 5.1–5.3: phân loại tiếp xúc, `accepted_source_defects` |
| `f0e06cf` | 5.4: hợp nhất thành phần chồng lấn (`geometry/component_union.py`) |
| `ad46452` | Kế hoạch bổ sung từ 3 IFC thật (cuối `production-roadmap.md`) |

- Nhánh phụ đã merge, có thể xóa: `fix/p0-cli-cold-start-and-baseline`, `perf/phase2-self-intersection`, `refactor/phase3-dedupe`, `feat/phase4-coordinates`, `feat/phase5-topology`.
- Worktree còn sót (chưa xóa): `../IFCtoFDS-wt-phase2`, `../IFCtoFDS-wt-phase3`, và hai worktree khóa trong `.claude/worktrees/agent-*` (lần thử isolation thất bại). Gỡ bằng `git worktree remove -f -f <path>`.

## 2. Việc đang dở: bước 5.8 (hiệu năng) — **CHƯA COMMIT**

Thay đổi trong cây làm việc (`git status`): `geometry/{cache,component_union,engine,mesh}.py`, `validation/preflight.py`,
`scripts/stage-profile.py` (bước 0.2), 5 file test mới, sửa `tests/test_component_union.py`,
`tests/test_self_intersection_contacts.py`, `tests/test_geometry_export_investigation.py`, snapshot `case_c_fzk_erdgeschoss.json`.

Đã làm và đã kiểm (test riêng đạt):

| Thay đổi | Ở đâu | Bằng chứng |
|---|---|---|
| Prefilter tách trục cho cặp đồng phẳng (chỉ khi phân loại tiếp xúc) | `mesh.py` `_coplanar_separated`, `COPLANAR_PREFILTER` | Trên 25 mesh nặng của A: 1,95 triệu cặp đồng phẳng, chỉ 0,18% thực sự chồng lấn. Test so có/không prefilter cho kết quả bằng nhau |
| `inspect_mesh_quality` dùng khóa cạnh int64 + đường nhanh cho mảng mặt | `mesh.py` | `test_mesh_quality_keys.py` so với định nghĩa `np.unique(axis=0)` |
| **Tessellation instanced** (tọa độ cục bộ, dùng lại theo `geometry.id`, áp ma trận numpy, đảo chiều mặt khi ma trận phản chiếu). Mặc định BẬT theo quyết định của người dùng; `IFCFDS_GEOMETRY_INSTANCING=0` = chế độ cũ | `engine.py` `world_mesh_from_shape`, `transformed_mesh_arrays`, `instancing_enabled` | Native A: 76 s → 18,6 s. 145/169 s tessellation của A là các `IfcDoor` cùng một mapped representation. `test_instance_geometry.py` |
| **Sửa lỗi của chính Giai đoạn 5**: độ sâu xuyên lấy `min` của hai chiều (trước là `max`, khiến tam giác chạm mép bị coi là xuyên sâu và verdict lật theo nhiễu ULP) | `mesh.py` `_penetration_depths` (vector hóa) | Hai chế độ tessellation giờ cho verdict trùng 100% trên FZK/Duplex; `DEVIATED` của FZK và Duplex về 0 |
| **Chữ ký cache có dấu vân tay mã nguồn** (`code_fingerprint` của các module định hình mesh) | `cache.py` | Cache cũ đã gây lệch converter/auditor (nghi là nguyên nhân finding `representation` chập chờn ở Duplex). `test_geometry_cache_fingerprint.py` |
| Hợp nhất quyết định bằng thể tích (`Σ V_i − V(union)`), không quét tự giao cắt toàn mesh; không tự quét kết quả hợp nhất (preflight của audit quét) | `component_union.py` (`UNION_METHOD` …`-v3`) | `test_component_union.py` |
| Snapshot đóng băng FZK: chỉ đổi 2 hash (gói hình học, CSV); test Duplex air_path đổi 2,54 → 2,32 m³ và hốc 9/8 → 8/9 (nhạy với nhiễu ~1e-15, ghi trong chú thích test) | tests | Đã so từng trường; gates/findings/records không đổi |

**Chưa xác minh — làm đầu tiên ở phiên sau:**
1. `prefetch_self_intersection` (song song theo tiến trình, gọi từ `preflight.source_topology_preflight`).
   - Đo riêng trên 11 mesh ≥ 2.000 mặt của A (tổng 105.530 mặt, lớn nhất 30.652): **tuần tự 88,5 s; 4 worker 39,1 s; 8 worker 40,1 s; kết quả giống hệt**. Thời gian bị giới hạn bởi mesh lớn nhất, nên 4 worker là đủ.
   - Nhưng lần chạy `convert` A đầy đủ có prefetch thì **bất thường**: 8 worker mỗi cái > 180 s CPU, ~800 MB RSS, phải dừng. Chưa rõ vì sao khác phép đo riêng. Có thể do trong `convert` nhiều tiến trình nặng chạy cùng lúc (cache cold, đọc lại nguồn) hoặc tập mesh khác. Phải chạy lại `convert` A đầy đủ với prefetch và theo dõi; nếu vẫn bất thường thì giới hạn `workers=4` hoặc gỡ khỏi preflight trước khi commit.
2. Chạy lại **toàn suite** (lần cuối chạy toàn bộ là trước khi thêm fingerprint/prefetch).
3. Đo lại A (cold) không có prefetch: lần đo cuối **244 s** (hình học 50 s, đọc lại 49,5 s, validation 123 s). Mục tiêu 5.8 là A ≤ 120 s, **chưa đạt**.
4. Đo lại C (lần cuối 670 s trước khi vector hóa độ sâu; mục tiêu ≤ 300 s) và B.
5. Tạo lại mốc `docs/evidence/production-roadmap/baseline-{fzk,duplex,institute}.json` bằng `scripts/verdict-snapshot.py ... -o ...` sau khi chốt mã, rồi commit 5.8.

Đòn bẩy hiệu năng còn lại (theo profile): chứng minh "sạch" cho mesh cong rất nặng (cửa 45.000 mặt, 15,7 triệu cặp ứng viên, hàng triệu lời gọi số học chính xác `side`/`crosses`). Hướng: lọc chiếu tách rời trước khi giải chính xác, giảm cặp ứng viên, hoặc song song hóa đúng cách.

## 3. Sai sót trong tài liệu đã commit — phải sửa

Các số liệu sau đo khi còn lỗi `max` độ sâu và/hoặc cache cũ, nên **kết luận sai**:
- `phase5-topology.md`: "FZK 16/18 xuyên sâu ≥ 1 mm, chồng lấn thật"; bảng độ sâu witness (script phân tích cũng dùng `max`).
- Cuối `production-roadmap.md` (phần "Bổ sung theo dữ liệu thật"): phát hiện 2 ("union vẫn tự giao cắt" B 11, A ~10, C ~60), mục 5.5 dựa trên con số đó, và thời gian A 377 s / C 1.008 s (nay A 244 s).
- Kết luận đúng hiện tại: sau sửa `min`, FZK và Duplex không còn `DEVIATED`; B còn 8, A còn 1–2, C còn 0 (+ 4 `UNSUPPORTED`). Cần đo lại trước khi viết lại.

## 4. Số liệu hiện tại (cold, máy dự án, 12 lõi)

| Mô hình | Trước (đầu phiên) | Lần đo cuối | Ghi chú |
|---|---|---|---|
| FZK-Haus | 33,8 s | ~14–20 s | `DEVIATED` 16 → 0 |
| Duplex | 34,5 s | ~13–15 s | `DEVIATED` 31 → 0 |
| Institute | 147,9 s | 57–69 s (trước 5.8) | chưa đo lại sau 5.8 |
| A (hầm 2 tầng) | 377 s | 244 s | 22 `UNSUPPORTED` (cửa không-manifold), 15 `REVIEW_REQUIRED` |
| B (tầng 7) | 17 s | 14 s | 8 `DEVIATED` |
| C (tổng hợp + MEP) | 1.008 s | 670 s (trước bản vector hóa độ sâu) | 1.722 phần tử `NONE`, 89 finding bảo toàn từ hình học tham chiếu |

Cả 3 mẫu và 3 file thật vẫn **REJECTED**.

## 5. Vấn đề đã biết chưa xử lý

- 3 test hỏng **có từ trước phiên** (cache nguồn/preview): `test_normalization_evidence_survives_converter_cache`, `test_binary_ingestion_cache_preserves_identity_and_never_reuses_mapping`, `test_preview_cache_preserves_world_geometry_and_rejects_corruption`. Có thể liên quan khóa cache; kiểm lại sau thay đổi fingerprint.
- 2 test `xfail` nghiêm ngặt từ Giai đoạn 3: engine trên FDS rỗng cho geometry `PASS`; traceability báo primitive kịch bản cháy là bất ngờ.
- Giai đoạn 3 đổi hành vi khởi động lại server (job QUEUED → FAILED; khóa chẩn đoán `name`/`jobId`); chưa kiểm client nào đọc khóa cũ.
- Cổng air_path nhạy với nhiễu ~1e-15 (số hốc đổi giữa hai chế độ tessellation).
- `test_sqlite_wal_multi_process_concurrency` từng lỗi "database is locked" một lần khi tải nặng.

## 6. Dữ liệu và cách chạy

- IFC thật (ngoài repo, không commit): `D:\User\HUCE\NCKH\Resources\IFC_Tòa nhà\` — **A** = `Ham2Tang.ifc`, **B** = `Tang7.ifc`, **C** = `ALL_FDS_2027.ifc`. Trong tài liệu commit chỉ dùng bí danh A/B/C và số tổng hợp.
- Môi trường: `uv sync --locked --extra test` → `.venv/Scripts/python.exe`. Đặt `PYTHONIOENCODING=utf-8`, `IFCFDS_SOLVER_AUTODISCOVERY=0`.
- Đo cold: đặt `IFCFDS_GEOMETRY_CACHE` tới thư mục mới (ngoài repo). Cache mặc định `.cache/geometry` dùng chung, dễ gây nhiễu khi so sánh.
- Lệnh:
  - toàn suite: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=90` (~2,5 phút; khôi phục `tests/baseline/snapshots/baseline_metrics.json` bằng `git checkout` sau khi chạy vì test tự ghi file này);
  - test chậm: `-m slow`; IFC riêng tư: `IFCFDS_PRIVATE_BASEMENT_IFC=<path> ... -m private`;
  - so verdict: `scripts/verdict-snapshot.py <ifc> --compare docs/evidence/production-roadmap/baseline-<n>.json`;
  - profile theo nhóm: `scripts/stage-profile.py <ifc> -o <out.json> [--cache DIR]`;
  - chạy thật: `.venv/Scripts/python.exe -m ifc_to_fds convert <ifc> -o <ngoài-repo>/out.fds`.
- Các script phân tích tạm (đếm cặp đồng phẳng, profile hình học, so instanced/world) nằm trong thư mục scratchpad của phiên, có thể đã mất; logic chính đã chuyển vào test hoặc `scripts/stage-profile.py`.

## 7. Thứ tự làm tiếp đề xuất

1. Hoàn tất 5.8 theo §2 (xác minh hoặc gỡ prefetch → toàn suite → đo A/B/C → tạo lại mốc → commit).
2. Sửa tài liệu sai theo §3 (đo lại B/A/C với mã cuối).
3. 5.6 (cửa không-manifold của A, giả thuyết hàn đỉnh giữa representation item) → 5.5 (nếu còn ca "union" thất bại) → 5.7 (hình học tham chiếu MEP không chặn cổng bảo toàn) → 5.9.
4. Giai đoạn 6 (`OBST_SET` cho tường có lỗ; A có 546/583 phần tử là GEOM), rồi 7 (HVAC, cần kỹ sư gán nghĩa hệ thống PAD/CEAD/OAD-FAD/RAD/TEAD của C), 8, 9, 10.

Câu hỏi mở cho kỹ sư: C và A có phải cùng một không gian hầm không (hệ tọa độ khác nhau, không tự ghép được).
