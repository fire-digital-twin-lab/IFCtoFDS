# IFCtoFDS — kế hoạch hoàn thiện production (bản 2)

Cập nhật 2026-11-15. File này **thay thế** kế hoạch bản 1 và file bàn giao cũ (cả hai còn trong lịch sử git, commit `356eb42`).
Đây là nguồn sự thật duy nhất: trạng thái ở Phần A, việc phải làm ở Phần B. Đánh dấu `[x]` khi một bước xong **và đã qua cổng kiểm tra của nó**.

Phạm vi đã chốt: mapping + HVAC vận hành + cháy xe điện; chạy qua CLI và Web/API (Docker Compose); nghiệm thu trên IFC thật của dự án.

---

# Phần A — Trạng thái

## A1. Git
- Đã merge vào `main` bằng merge commit (nhánh đã xóa sau merge): #109 `439366a` (M0–M2 và một phần M3–M5), #110 `848904b` (M1.7, M5.2), #111 `64b0fa6` (M5.5, M3.3/M3.4/M3.6), #112 `4d077a0` (audit lần 1, 5 sửa), #113 `15a37e2` (audit lần 2, 10 sửa), #114 `d32dd7b` (script so deck PyroSim), #92 `beb435f` (underflow xu hướng lưới), #116 `b286408` (số đo ngưỡng), #117 `39998f7` (dọn tài liệu, hộp audit), #118 `e448e11` (ngưỡng thể tích theo bề dày lớp vỏ). M6: #119 `6dce86f`, #120 `2e00f82`, #121 `354654f`, #122 `0bcf211`, #124 `4d1b2ad`, #125 `5c44de3`, #123 `42051e4`, #126 `493a243`, #127 `e82a2eb`, #128 `6bc8af6` (bàn giao), #129 `e0faf41`, #130 `fdbacea`, #132 `7429ab6`, #131 `16efd48`. Công việc tiếp theo làm trên nhánh mới từ `main`, mỗi mục một PR nhỏ.
- Commit từ M2 trở đi viết tiếng Việt, không ghi công Claude (xem `AGENTS.md`). 21 commit tiếng Anh cũ hơn giữ nguyên theo quyết định của người dùng.
- Bàn giao và kế hoạch kiểm thử: [production-handover.md](production-handover.md), [real-world-test-plan.md](real-world-test-plan.md).

## A2. Đã xong (suite mặc định sạch tại từng commit)
| Mốc | Commit | Kết quả chính |
|---|---|---|
| 0–1 | `e3d8592` | CLI `convert` chạy từ tiến trình mới; lối mở A△A = 0; khóa `scope.coordinate_frame`; `verdict-snapshot.py`; marker `slow`, `private` |
| 2 Tốc độ | `392d8e0` | `has_self_intersection` vector hóa + số nguyên chính xác; FZK 34→8 s, Institute 148→42 s |
| 3 Kiến trúc | `73e214d` | Một đường kiểm định, một `JobRepository`, bỏ `ifc_to_fds/server/` |
| 4 Tọa độ | `b24650b` | Placement cứng chuẩn IFC, đơn vị về mét SI, rebase cao độ tầng và trục Z, georeference |
| 5 Tô-pô | `ff4be54`, `f0e06cf` | `contact`/`numerical_contact`, `accepted_source_defects`, hợp nhất thành phần chồng lấn |
| M0 | `883433a`, `4bb570e` | Hồi quy hợp nhất sửa xong; prefetch 4 worker; mốc verdict tạo lại |
| M1 | `a498915`…`855f096` | Phần tử tham chiếu không bị chặn; ngưỡng thể tích chồng lấn số học; chặn nhiều IfcSite; sửa đường dẫn cache dài |
| M2 | `426a96f`, `61a1738` | Hộp phủ OBST (mặc định bật); `air_path` chính xác; `effective_geometry` theo phần tử, đọc VENT và OBST điều khiển từ SMV; gate `passage_resolution` |
| M3 (một phần) | `8800f92` | Phụ kiện hai cổng và quạt lưu lượng cố định từ thông số đã duyệt; tổn áp FDS khớp tính tay 0,5% |
| Dọn dẹp + M4 (một phần) | `76bd48f`, `87a7430` | Bỏ mã chết, gom tên gate về một chỗ; phát lại đường HRR đo và kiểm chứng bằng FDS |
| M5.1, M5.3, M5.4 | `92ac39b` | `TMPDIR` trên volume (upload 2×150 MiB: lỗi 400 → 202, đo bằng Docker); diễn tập backup/restore trên job thật; image `solver` có FDS 6.11.1 Linux ghim hash, probe đạt trong container với cờ production |
| M1.7 và M5.2 | `c849461`, `74d7e1d` | C cold 293 s (đạt); A cold 170 s (chưa đạt 120). Drill job dài trên C ở chế độ local và production: COMPLETED 260–266 s, RSS đỉnh 1,2 GiB, hàng đợi và khởi động lại đúng |
| M3.3/M3.4/M3.6, M5.5 | tiếp theo `5298c71` | Tê, Y, gót giày thành một nút FDS với `LOSS(i,j)` đã duyệt; tách dòng khớp tay 5%, bảo toàn khối lượng 1%. Deck CLI và web trùng từng byte trên A và B; B `MAPPING_VERIFIED` |
| Audit lần 1 (PR #112) | `4d077a0` | Tên IFC có xuống dòng không còn chèn lệnh vào deck Quick; thư mục upload không mồ côi khi `submit` lỗi (kể cả đĩa đầy); job `MAPPING_VERIFIED` hết hạn sau `IFCFDS_DURABLE_RETENTION_S` (30 ngày); upload song song bị giữ chỗ trước khi ghi byte (429); cache xác minh bằng chứng theo kích thước và mtime; `touch` bỏ commit SQLite khi vừa truy cập |
| Audit lần 2 (PR #113) | `15a37e2` | `CHID` không còn dấu chấm (FDS dừng với ERROR 108, trước đây vẫn `MAPPING_VERIFIED`); `audit` không nhận `accepted_source_defects` từ manifest, mỗi lỗi được miễn là finding P2 trong báo cáo; ngưỡng hình học mặc định 1e-9 (trước 1 mm / 0,1% / 0,999), lỗ mở giữ nhiễu Boolean cũ qua `PASSAGE_NOISE_M`; `_dispatch` tách khỏi vòng lập lịch; hạn chót job dùng `time.monotonic`; `verified.yml` khai `permissions`; test baseline ghi ra `tmp_path`; xóa shim `fire/mesh_gate.py`. B vẫn `MAPPING_VERIFIED` (218 MATCHED) với ngưỡng mới; FZK, Duplex, Institute trùng `main` |
| Đối chiếu PyroSim (PR #114) | `d32dd7b` | `scripts/compare-fds-decks.py` so không gian do OBST/GEOM/HOLE lấp đầy của hai deck không cần `! IFC_SOURCE` (thể tích, IoU, vùng lệch, số dòng provenance, HVAC và `LOSS(i,j)`); chạy thử trên deck B thật. Chưa có kết quả so với PyroSim vì máy không có PyroSim |

## A3. Đang bị chặn (chờ đầu vào, không tự suy)
| Mục | Chặn bởi | Cần gì | Đã chuẩn bị sẵn |
|---|---|---|---|
| M1.7 tốc độ A | validation 73 s | không cần đầu vào; làm khi ưu tiên | A 170 s (mục tiêu 120); C đã đạt 293 s |
| M2.4 `effective_geometry` PASS trên A | quyết định kỹ thuật | chọn: đọc cut-cell GEOM từ SMV, hoặc quay mô hình theo từng cánh, hoặc chấp nhận xấp xỉ bậc thang | A 0% OBST vì mọi tường/sàn không thẳng trục; gate đã liệt kê 546 GEOM theo tên |
| M3.1 phân loại phụ kiện | người dùng duyệt bảng họ → loại | xác nhận 7 họ của C: cút 182, chuyển tiết diện vuông–tròn 100, côn 78, gót giày 60, đầu bịt 34, Y 16, tê 8 | phụ kiện hai cổng đã biên dịch được khi có K và chiều dài |
| M3.2 phạm vi hệ thống | B-ext 2 | nghĩa PAD/CEAD/OAD-FAD/RAD/TEAD; hệ nào hút khói, cấp bù | cơ chế `decisions` đã có |
| M3.5 đầu cuối → biên | B-ext 3 | lưu lượng thiết kế từng miệng, K, đường cong quạt (C không có đối tượng quạt) | VENT/AMBIENT đã hỗ trợ |
| Ma sát ống chữ nhật trong FDS | ĐÃ QUYẾT (2026-11-15): dùng `ROUND=.FALSE.` | xem M6.F9: chênh 18% do serializer thiếu cờ `ROUND=.FALSE.`, FDS mặc định dùng đường kính tròn tương đương; không phải giới hạn của FDS | M6.F9 |
| M4.1 preset xe | B-ext 4 | số đo cháy nguyên xe được phép dùng (HRR theo thời gian, năng lượng pin) | có thể phát lại thẳng đường đo (M4.2) |
| M4.3 HF/HCN | B-ext 4 | yield nguyên xe | — |
| M4.4 biên truyền nhiệt | nguồn tính chất vật liệu | tính chất bê tông/thép có trích nguồn | — |
| Bước CI upload 2×150 MiB | chỉ chạy trong stack đầy đủ | không cần đầu vào | job `solver-image` đã đạt trên CI; bước upload đã đo cục bộ bằng Docker |
| Đối chiếu PyroSim (T19–T21) | còn thiếu deck PyroSim mở rồi lưu lại (B/`tee.fds`) | ĐÃ CÓ deck PyroSim 2026.2.0715 nhập từ A, B, C (2026-10-13) và đã so 2026-11-16, xem A4.13 và `docs/evidence/production-roadmap/pyrosim-compare-2026-11-16.json`. Chưa có: deck B/`tee.fds` mở rồi lưu lại bằng PyroSim | `scripts/compare-fds-decks.py` chỉ đọc được phần có thể tích của deck PyroSim; cần bản sao đã làm sạch ID trùng |
| M5.5–M5.7 | các mốc trên + kỹ sư review | QoI nghiệm thu (B-ext 5) | — |

## A4. Vấn đề mở khác
1. 2 test `xfail` nghiêm ngặt từ Giai đoạn 3: FDS rỗng → geometry `PASS`; traceability coi primitive kịch bản cháy là bất ngờ.
2. Giai đoạn 3 đổi hành vi server (job QUEUED → FAILED khi khởi động lại); chưa kiểm client JS có đọc khóa chẩn đoán cũ.
3. `air_path` vẫn dùng Boolean khi có phần tử vỏ bao lệch; khi đó có thể INCONCLUSIVE.
4. `test_sqlite_wal_multi_process_concurrency` từng báo "database is locked" một lần khi máy tải nặng (đã thêm thử lại có thời hạn).
5. Ổ đĩa dự án có 26 thư mục job cũ trong `.jobs/` (ngoài git) do server/test để lại; xóa tay nếu cần dung lượng.
6. **ĐÃ SỬA (PR #118 `e448e11`):** ngưỡng mặc định 1e-9 từng làm 9 phần tử của C thành DEVIATED oan (đo 2026-11-15, `main` `e01e65d`, ngưỡng cũ khai tường minh so với mặc định mới, cùng mã và cache; bằng chứng `docs/evidence/production-roadmap/tolerance-A-C.json`). A: 0 phần tử đổi (546 MATCHED, 22 UNSUPPORTED như trước). C tám tầng hầm: 697 → 688 MATCHED, 9 → DEVIATED (8 `IfcCovering`, 1 `IfcColumn`), finding `geometry` 1 → 10; verdict vẫn REJECTED. Cả 9 có khoảng cách bề mặt ≤ 7e-15 m, IoU ≥ 0,9999995, sai số thể tích tương đối 1,6e-8 … 5,2e-7, tức nhiễu Boolean trên phần tử mỏng chứ không lệch thật. Đo trực tiếp: phần tử lớn nhất 7,55 m³ trên 44,5 m² lệch 3,9e-6 m³, tức lớp vỏ 0,09 µm (đỉnh nguồn lệch trục ~1e-7 m). Sửa: `within_tolerance` chấp nhận lệch thể tích/IoU không lớn hơn diện tích × `surface_tolerance_m`, và `surface_tolerance_m` mặc định 1 µm. Chạy lại `convert` sau sửa: A 546 MATCHED, C 697 MATCHED, 0 DEVIATED; trạng thái từng phần tử của cả hai trùng hệt lượt dùng ngưỡng 1 mm cũ. Lệch 1 mm thật vẫn bị loại.
7. Duplex: finding `representation` "Manifest openings differs from independent policy" xuất hiện ở một số lần chạy và không ở lần khác (cả trên `main` và trên nhánh audit; `verdict-snapshot` trên `main` không có, `convert` trực tiếp trên `main` có). Đọc lại IFC thì manifest và kết quả đọc lại khớp từng trường; nguyên nhân chưa tìm ra. Đây là chập chờn đã ghi ở M0.4.
8. `PASSAGE_NOISE_M` (1 mm quy theo diện tích/thể tích lỗ mở) là hằng dung sai nhiễu Boolean có `shortcut:`; bỏ khi lối đi được chứng minh bằng nhau chính xác cho mọi vật cản.
9. Workflow CI chính ghim action theo tag (`@v4`); workflow release đã ghim theo SHA.
10. **Còn hoãn từ audit HVAC và kiến trúc (2026-11-15):** (a) bỏ `build_hvac_network` khỏi đường audit để cổng `hvac` kiểm trực tiếp từ deck (chưa có ca lỗi thủy lực nào lọt qua, viết lại lớn); (b) kiểm mặt đỡ VENT từ OBST/MESH đọc trực tiếp từ deck (HVAC-D4), hiện dựa vào việc cổng hình học đối chiếu OBST với nguồn; (c) đối chứng đa nguồn IFC, rebase, transform (HVAC-D3); (d) F2-SMV với đa MESH, lưới không đều, hai VENT cùng bề mặt trên nhiều lưới (HVAC-D6, thiếu fixture); (e) ARCH-02 chỉ mới khóa cạnh `validation → fire`, chưa có ratchet toàn gói hay phát hiện vòng nhiều gói.
11. Smoke EV-PACK-01 gọi loader trực tiếp trên image; chưa kiểm qua `compose.production.yml` và `serve` thực chạy.
12. `scripts/verdict-snapshot.py --compare` không đọc được `real-{A,B,C}.json` (lược đồ tổng hợp, thiếu `element_statuses`); `real-B.json` ghi INCONCLUSIVE đã cũ vì B nay `MAPPING_VERIFIED`. Lượt đo A ngày 2026-11-16 mất 544 s nhưng không có phép đối chứng cùng phiên, không dùng để kết luận hiệu năng.
13. **Đối chiếu với deck PyroSim (2026-11-16, `main` `60fd3b0`; số tổng hợp ở `pyrosim-compare-2026-11-16.json`).** Deck PyroSim không phải chuẩn đối chứng: **77% (C), 82,6% (B) và 97% (A) số `OBST` của nó là hộp dày bằng 0** (thể tích 0, vẫn chắn dòng trong FDS), nên đo thể tích bỏ qua phần lớn. Hệ tọa độ: A = deck của ta + vector rebase `(578753, 2318413, 0)`, C trùng khung, B PyroSim tự dời về gốc nên chưa so thể tích được. Trong miền MESH của PyroSim: C IoU 0,48 (2.640 m³ ta so với 2.143 m³ PyroSim), A IoU 0,29 (1.688 so với 916 m³). Theo từng cấu kiện (ghép mã Revit cuối ID): giữa các cấu kiện khớp, tỷ lệ thể tích PyroSim/ta có trung vị 1,03 đến 1,07, nhưng IoU trung vị chỉ 0,62 (C) và 0,17 (A; nhiều khả năng do tường xiên khoảng 40° bị xấp xỉ bậc thang theo lưới 0,2 m, chưa kiểm riêng). Cấu kiện của ta không có `OBST` có thể tích trong PyroSim hầu hết có mặt dưới dạng `OBST` mỏng (A 345/352, B 111/113, C 144/152); chỉ A 7, B 2, C 8 không thấy ở đâu. PyroSim thêm ống gió, bọc ống, ống nước dưới dạng `OBST` (C: ống gió chữ nhật 224 bản ghi 173 m³, bọc ống 58 bản ghi 43 m³), thứ ta cố ý xuất thành HVAC/tham chiếu, nên đó là khác biệt về quyết định mô hình hóa, không phải lỗi chuyển đổi. Kết luận sơ bộ: chưa thấy dấu hiệu sai lệch hệ thống về vị trí hay mất cấu kiện (chưa kiểm từng cấu kiện); không thể dùng IoU với PyroSim làm tiêu chí nghiệm thu. Còn lại: nên thêm vào `compare-fds-decks.py` đọc `OBST` dày 0 (diện tích), cắt theo miền và ghép theo cấu kiện, rồi so lại khi có deck PyroSim lưu lại (B/`tee.fds`).

## A5. Dữ liệu thật (ngoài repo, không commit; trong repo chỉ dùng bí danh và số tổng hợp)
Thư mục `D:\User\HUCE\NCKH\Resources\IFC_Tòa nhà\`. Cả ba IFC2X3, placement hợp lệ 100%, không có CRS; vị trí Site là mặc định phần mềm dựng.

| | A `Ham2Tang.ifc` | B `Tang7.ifc` | C `ALL_FDS_2027.ifc` |
|---|---|---|---|
| Nội dung | hầm 2 tầng, 793 sản phẩm, mm | một tầng, 279 sản phẩm, mm | tổng hợp + MEP, 5.641 sản phẩm, **foot** |
| Đặc điểm | 356 tường, 177 lỗ, 546/583 phần tử là GEOM; 21 cửa không-manifold | cửa, tường kính, lan can | 63 tầng (hai hệ cao độ trộn), 296 ống gió chữ nhật, 38 ống mềm, 588 ống nước, 478 phụ kiện, 130 đầu cuối, 68 hệ thống (SPR, PAD, CEAD, OAD/FAD, RAD, TEAD), 534 cổng `SOURCEANDSINK` |
| Lần đo cuối | 253 s cache lạnh kèm solver (M2.4); 22 UNSUPPORTED (cửa lỗi nguồn); deck CLI và web trùng từng byte (10.096.250 byte) | 218 MATCHED, 61 SEMANTIC_ONLY, ngưỡng hình học mới; deck CLI và web trùng từng byte | 670 s; 1.722 phần tử `NONE`, 89 finding bảo toàn, 4 UNSUPPORTED; tầng hầm 293 s cold |
| Verdict | REJECTED | **MAPPING_VERIFIED** | REJECTED |

A và B lệch nhau > 1.000 km trên trục Y sau khi đọc: không tự ghép được.

## A6. Cách chạy
- Môi trường: `uv sync --locked --extra test`; Python = `.venv/Scripts/python.exe`; đặt `PYTHONIOENCODING=utf-8`, `IFCFDS_SOLVER_AUTODISCOVERY=0`.
- Toàn suite (~3 phút): `python -m pytest -q -m "not solver and not browser and not slow" -p no:cacheprovider -o faulthandler_timeout=90` (test không còn ghi đè `tests/baseline/snapshots/baseline_metrics.json`).
- Cổng nợ nguồn trước khi đẩy PR: `PYTHONUTF8=1 python scripts/quality/source_quality_budget.py --git-base <merge-base với origin/main>`.
- Đo cold: đặt `IFCFDS_GEOMETRY_CACHE` tới thư mục mới ngoài repo. **Không chạy hai phép đo cùng lúc** (đã gây số đo sai trong phiên trước).
- So verdict: `scripts/verdict-snapshot.py <ifc> --compare docs/evidence/production-roadmap/baseline-<n>.json`.
- Profile: `scripts/stage-profile.py <ifc> -o <out.json>`.
- Solver: `python scripts/install-fds.py` (FDS 6.11.1 vào `.deps/`), rồi `IFCFDS_SOLVER=<.deps/.../fds_openmp.exe> python -m pytest -q -m solver`.
- Kết quả chạy file thật ghi ra ngoài repo.

---

# Phần B — Kế hoạch

## B0. Quy tắc làm việc
1. Mỗi bước = 1 commit/PR nhỏ: viết test hỏng → sửa → toàn suite → so verdict → commit.
2. **Không sửa snapshot đóng băng để test xanh** trừ khi đã so từng trường và ghi lý do trong commit.
3. Mọi thay đổi ở `geometry/mesh.py`, `component_union.py`, `normalization.py`, `engine.py` phải qua bộ fixture M0.3 và `verdict-snapshot --compare` trên 3 mẫu + B.
4. Thay đổi **nới** quy tắc kiểm định (cho qua thứ trước đây bị chặn) phải nêu rõ trong commit và có fixture cả hai phía (ca được cho qua, ca vẫn bị chặn).
5. Số đo ghi vào `docs/evidence/production-roadmap/` chỉ ở dạng tổng hợp; kèm ngày và commit.
6. Hết mỗi mốc: cập nhật Phần A của file này.

Lỗi suite "đã biết" tại thời điểm viết: 3 test cache ở A4.5 (sẽ xử lý ở M1.5).

## M0 — Ổn định và khép 5.8 (1–2 ngày)

- [x] **M0.1 Sửa hồi quy hợp nhất.** *(commit `883433a`; chọn biến thể: quét tự giao cắt cho mesh ≤ `SCAN_FACE_LIMIT`=5000 mặt khi thể tích chung = 0, mesh nặng giữ lối tắt)*
  File: `ifc_to_fds/geometry/component_union.py` (`_fuse`). Bỏ lối thoát sớm "thể tích chung ≈ 0": luôn thử union khi hộp bao thành phần chồng nhau và mọi thành phần là volume; giữ các kiểm tra còn lại (solid hợp lệ, cận thể tích, oracle).
  Test mới trong `tests/test_component_union.py`: hai hộp chạm nhau có cặp tam giác bị báo xuyên, thể tích chung 0 → sau `prepare_source_mesh` là `CLEAN`.
  Kiểm: `tests/baseline` xanh **không sửa snapshot**; FZK và Duplex `DEVIATED` = 0.
  Nếu chi phí oracle tăng rõ (đo trên A): chỉ chạy oracle khi thể tích chung > 0; khi = 0 thì đủ điều kiện `|V(union) − Σ V_i| ≤ tol`.
- [x] **M0.2 Chốt prefetch song song.** *(GIỮ, tối đa 4 worker. A cold: 383 s → 221 s, validation 246 → 72 s, kết quả giống hệt. Lần "bất thường" trước đó do script đo thiếu `if __name__ == "__main__"` trên Windows, không phải lỗi mã sản phẩm.)*
  `mesh.py` `prefetch_self_intersection`: mặc định `workers` tối đa 4. Chạy `convert` A cold một mình, ghi wall, CPU từng worker, RSS đỉnh.
  Giữ nếu A nhanh hơn ≥ 20% và không worker nào vượt 2× thời gian tuần tự của mesh nặng nhất; ngược lại gỡ lời gọi trong `validation/preflight.py` (giữ hàm và test).
- [ ] **M0.3 Bộ fixture phân loại tiếp xúc.** *(hoãn: test FZK trực tiếp trong `test_component_union.py` đã giữ hồi quy; làm khi có ca biên mới)*
  Trích mesh thật đã từng gây lỗi thành JSON nhỏ ở `tests/fixtures/contacts/` (chỉ đỉnh/mặt, không tên/GUID): cửa sổ FZK chạm-không-thể-tích, cửa Duplex chạm mép (ULP), cửa B còn `DEVIATED`, hai hộp chạm mặt, chồng lấn thật, lồng nhau. Mỗi file kèm verdict mong đợi của `self_intersection_evidence` và của `prepare_source_mesh`.
  Test tham số hóa `tests/test_contact_fixtures.py`, chạy ở cả hai chế độ tessellation nếu có liên quan.
- [x] **M0.4 Đo lại và tạo lại mốc.** *(mốc verdict và real-A/B đã tạo lại; real-C chưa đo lại; thời gian KHÔNG ghi nhận được vì máy chậm ~5,6× lúc đo, xem lưu ý dưới)*
  Cold, tuần tự từng mô hình: FZK, Duplex, Institute, B, A, C. Ghi `baseline-{fzk,duplex,institute}.json` và `real-{A,B,C}.json`. Chạy `verdict-snapshot --compare` hai lần liên tiếp cho Duplex để xác nhận hết chập chờn (A4 cũ: finding `representation`).
- [x] **M0.5 Sửa tài liệu.** Viết lại `phase5-topology.md` theo số M0.4 (xóa kết luận "chồng lấn ≥ 1 mm"); cập nhật Phần A.
- [x] **M0.6 Kiểm client đọc khóa chẩn đoán.** *(grep js/ và index.html: không có chỗ đọc khóa cũ)* `grep -rn "error_type\|job_id" js/ ifc_to_fds/` cho đường đọc `diagnostics.json`; sửa nếu có.
- [x] **M0.7 Dọn và đưa lên.** *(PR #109 `feat/production-m0-geometry-ready`; đã xóa 5 nhánh + 4 worktree; CI phát hiện và đã sửa: race khởi tạo `JobRepository` nhiều tiến trình ('database is locked' khi `PRAGMA journal_mode=WAL'), nợ import/except mới)* Commit hoàn chỉnh thay WIP; xóa 5 nhánh và 4 worktree (A1); push; mở PR vào `main` gồm Giai đoạn 0–5.
- **Cổng M0:** suite = đúng 3 lỗi đã biết; CI của PR xanh (ubuntu + windows); FZK/Duplex `DEVIATED` = 0.

> **Lưu ý đo thời gian (2026-11-14, cuối phiên):** mã Giai đoạn 2 từng chạy FZK 8,1 s nay mất 46 s trên cùng máy, tức máy chậm ~5,6× lúc đo.
> Mọi lần đo thời gian cần kèm một phép đối chứng (chạy `../IFCtoFDS-wt-phase2` hoặc cùng một mô hình cố định) và chỉ so cùng phiên.
> Số hiện có đáng tin: A cold 221 s (có prefetch) so với 383 s (không prefetch), cùng phiên. Kết quả verdict không phụ thuộc tốc độ.

## M1 — Hình học file thật sạch (1,5–2 tuần)

- [x] **M1.1 Cửa không-manifold của A (21).** *(CHẨN ĐOÁN XONG, KHÔNG SỬA: giả thuyết hàn đỉnh bị bác bỏ. Tắt hàn đỉnh không cứu cửa nào (21 hỏng khi hàn, 23 khi không hàn); mesh có ~3.800 cạnh hở, 858 cạnh ngược chiều, 21 cạnh non-manifold, tức bề mặt nguồn hở. Đây là lỗi dữ liệu nguồn: giữ `UNSUPPORTED` kèm lý do; cần kỹ sư xử lý trong Revit hoặc loại các cửa này khỏi phạm vi. Còn có thể thử: tessellate từng representation item riêng.)*
  Bước 1 chẩn đoán (không sửa): với 1 cửa, so `inspect_mesh_quality` của (a) mesh hiện tại, (b) tessellate với `WELD_VERTICES=False`, (c) từng representation item riêng. Ghi kết quả.
  Nếu do hàn đỉnh giữa item: tessellate không hàn rồi hàn trong từng thành phần liên thông (`geometry/engine.py` / `normalization.py`). Nếu là lỗi nguồn: giữ `UNSUPPORTED`, ghi lý do đọc được trong report.
  Kiểm: fixture từ 1 cửa A; `UNSUPPORTED` của A giảm hoặc có lý do rõ; 3 mẫu không đổi verdict.
- [x] **M1.2 Ca còn bị chặn ở B (8) và A (≤ 2).** *(cả 8 ca của B có chung witness `COMPONENT_VOLUME_OVERLAP` do nhiễu Boolean cỡ 1e-17 m³ vì điều kiện `volume > 0`; nay ngưỡng `NUMERICAL_OVERLAP_VOLUME_M3`=1e-9 trong chế độ phân loại. B: DEVIATED 8 → 0, verdict REJECTED → INCONCLUSIVE; cổng bắt buộc còn lại là `air_path` (thể tích rò âm −1,3 lít trên mô hình chỉ một tầng, nghi phép Boolean/đường bao không kín; chưa điều tra). A: xem số đo.)*
  Sau M0.1 đo lại trước. Với mỗi ca còn lại: ghi `component_union.reason`; thử union theo cụm liên thông chồng lấn thay vì toàn cấu kiện. Ca không sửa được bằng công cụ → viết file duyệt mẫu `accepted_source_defects` cho B (đặt ngoài repo) và mục hướng dẫn sử dụng trong README.
- [x] **M1.3 Hình học tham chiếu không chặn cổng bảo toàn.** *(`geometry/package.py`: phần tử strategy `NONE` có mesh lưu byte-giống nguồn thì qua, ghi `reference_only`; phần tử phát ra FDS vẫn bị chặn. `tests/test_reference_geometry_preservation.py` có cả hai phía. Chưa đo lại trên C.)*
  `geometry/package.py` (`audit_package`): phần tử `mapping_strategy` `NONE`/`REFERENCE_GEOMETRY` (không xuất ra FDS) → lỗi tự giao cắt ghi thành thông tin, không `fail`. Test với fixture MEP có sẵn (`tests/baseline/fixtures/mep.ifc`).
  Kiểm: C không còn finding `geometry_preservation` từ phụ kiện tham chiếu.
- [x] **M1.4 Georeference và chọn tầng.** *(`SourceMetadata.georeference.status=SOFTWARE_DEFAULT_SITE_LOCATION` khi Site là vị trí mặc định Revit (Boston) và không có CRS, kèm finding P2 `georeference`; `ifc_site_count`; mô hình > 1 `IfcSite` bắt buộc `scope.storeys` hoặc `scope.bounding_box`, nếu không lỗi mã 3. A và C là Boston mặc định; C có 5 IfcSite.)*
  Finding P2 khi Site có tọa độ mặc định và không có CRS. Khi mô hình có > 1 `IfcSite` hoặc tầng trùng cao độ/âm lẫn lộn như C: yêu cầu `--storey`, thoát mã 3 kèm danh sách tầng. Test trên fixture tổng hợp.
- [x] **M1.5 Ba test cache cũ.** *(NGUYÊN NHÂN: giới hạn đường dẫn Windows 260 ký tự. Tên file tạm của cache gồm SHA 64 + UUID 32 ký tự nên vượt giới hạn khi thư mục dài; `write_package` lỗi và bị nuốt âm thầm nên cache không bao giờ được ghi. CI bật đường dẫn dài nên không gặp. Đã rút ngắn tên file tạm ở `geometry/storage.py`, `geometry/cache.py`, `geometry/preview_cache.py`. Suite: 0 lỗi.)* Tìm nguyên nhân từng cái (nghi khóa cache/đường dẫn cache trong test). Sửa mã hoặc sửa test; xóa chỉ khi hành vi được test không còn tồn tại, ghi lý do.
- [x] **M1.6 Hai test `xfail`.** *(FDS rỗng: cổng `geometry` giờ `INCONCLUSIVE` khi không so sánh được solid nào, thay assertion 'mọi cổng INCONCLUSIVE' của runner cũ bằng test hợp đồng thật; test primitive kịch bản cháy giữ `xfail` có chủ ý: engine chỉ audit deck gốc.)* FDS rỗng: cho các cổng phụ thuộc deck thành `INCONCLUSIVE` khi không có primitive nào. Traceability primitive kịch bản: để nguyên `xfail`, ghi quyết định "engine chỉ audit deck gốc" vào docstring.
- [~] **M1.7 Hiệu năng.** *(C ĐẠT, A CHƯA. Đo cold, tuần tự, cùng phiên với đối chứng FZK 11 s: **C tầng hầm 293 s toàn bộ** (đích 300; đường đọc lại 350 → 106 s), **A 170 s** (212,7 → 169,7 cùng phiên; đích 120: hình học và chuẩn bị khoảng 48, đọc lại 42, validation 73, audit gói 6). Đã làm (`c849461`): oracle `winding_numbers` dùng khối 2^13 cặp điểm×tam giác (đo từ 2^10 tới 2^22), chạy khối song song bằng thread với lưới từ khoảng 4.000 tam giác, và chỉ tính điểm nằm trong hộp bao (`_inside`): trên 1.500 phần tử của C đường đọc lại 252 → 71 s; `DiskPackage.mesh` đọc payload một lần (audit gói A 15,2 → 6,2 s). Verdict từng phần tử không đổi (Duplex và A: 0 khác biệt cũ so với mới). Đã đo và loại: `parse_fds` chỉ khoảng 5 s thật (13 s là do cProfile phóng đại); tiền quét phạm vi không tính khoang cửa nhanh 3,8 lần nhưng không còn cần cho C. **Còn mở cho A:** validation 73 s (quét tự giao cắt 4 worker khoảng 35 s, `compare_solids` 11, `passage_metrics` 9, `mesh_quality` 12); tái dùng bằng chứng tự giao cắt cho instance cùng `geometry.id`; lọc chiếu cho mesh cong. Chữ ký mốc: `docs/evidence/production-roadmap/real-{A,B,C}.json`.)*
  Mục tiêu gốc và thứ tự thử: Mục tiêu A ≤ 120 s, C (chọn tầng hầm) ≤ 300 s.
  Thứ tự thử, đo sau mỗi bước bằng `stage-profile.py`:
  1. Tái dùng bằng chứng tự giao cắt cho các instance cùng `geometry.id`: quét ở **tọa độ cục bộ** một lần (kết quả là thuộc tính của hình, không phụ thuộc vị trí). Cần truyền mesh cục bộ + ma trận tới preflight; chứng minh bằng test: verdict cục bộ = verdict thế giới trên bộ fixture M0.3.
  2. Giảm cặp ứng viên cho mesh cong nặng: lọc theo khoảng chiếu lên pháp tuyến trước số học chính xác.
  3. Audit gói (C: 117 s): bỏ lần so sánh lặp khi mesh đã chứng minh giống byte.
- **Đã làm thêm ở review (commit sau `a498915`):** phần tử `NONE` bị bỏ qua trong preflight tự giao cắt (không chặn cổng sau, đỡ quét hàng nghìn mesh MEP); `JobRepository` thử lại theo ngân sách thời gian (không theo số lần).
- **Cổng M1:** B `MAPPING_VERIFIED`, hoặc chỉ còn lỗi nguồn đã duyệt có ghi vết; A không còn `UNSUPPORTED` do công cụ; thời gian đạt mục tiêu (hoặc ghi số thật và lý do); suite không còn lỗi "đã biết".

## M2 — Hình học hiệu dụng cấp solver (2–3 tuần)

- [x] **M2.0 Có FDS.** *(`python scripts/install-fds.py` cài bản ghim hash vào `.deps/` (gitignore, không cài hệ thống); `IFCFDS_SOLVER=<.deps/.../fds_openmp.exe> pytest -m solver`: 11 test solver đạt trên máy dự án.)* Cài FDS 6.11.1 trên máy dự án (Windows) hoặc dùng WSL; `-m solver` chạy được tại chỗ. Xác nhận job `solver` của CI đang xanh.
- [x] **M2.1 Hộp phủ cho tường trực giao có lỗ.** *(XONG, MẶC ĐỊNH BẬT từ M2.5; `IFCFDS_OBST_BOX_SETS=0` tắt. `geometry/rectilinear.py`: tổng quát hóa `OBST` thành một hoặc nhiều `&OBST`; chỉ nhận solid MỘT vỏ, lỗ phải được chứng minh đã trừ khỏi host (`_openings_are_cut`, không bao giờ lấp lỗ), hộp phủ phải qua chính `compare_solids` của cổng kiểm định (`is_exact_match`). Cửa và cửa sổ nhiều thành phần giữ `GEOM`. ĐO TRÊN A: 0% OBST. Cả 356 tường, 17 tường khác và 63 sàn của A đều không thẳng trục (tòa nhà có nhiều cánh theo các hướng khác nhau, hướng trội khoảng 40° chỉ chiếm khoảng 14% số mặt), nên không thể là hộp. Muốn có OBST trên A phải quay mô hình về lưới theo từng cánh hoặc chấp nhận xấp xỉ bậc thang; cả hai là quyết định kỹ thuật cần phê duyệt. Lợi ích thực của M2.1 nằm ở mô hình thẳng trục như FZK.)*
- [x] **M2.5 Làm `air_path` đáng tin trên mặt trùng nhau.** *(XONG: khi MỌI phần tử vỏ bao đều có chứng minh `is_exact_match` từ so sánh hình học (cùng cổng kiểm định, không dùng exporter) thì `air_path` PASS với `method=ALL_ENCLOSURES_PROVEN_EQUAL` và không chạy Boolean; các trường hợp còn lại giữ đường Boolean cũ. Lý do: solid bằng nhau thì không thể rò, còn Boolean của Manifold trên mặt trùng cho thể tích âm hoặc rò giả (Duplex từng báo rò 2,32 hoặc 2,54 m³ tùy cách tessellate cùng một IFC; FZK nguyên tòa nhà ra −0,10 m³). Kết quả: FZK, Duplex và A đều `air_path` PASS (A: 435 vỏ bao). Hộp phủ bật mặc định. Test Duplex cũ đã sửa theo yêu cầu của người dùng: bỏ assert rò 2,32 m³ và 8/9 khoang (là nhiễu), thay bằng kiểm bằng chứng từng phần tử. Hai snapshot parity b và c chỉ đổi các trường GEOM→OBST (chiến lược, ID, số lượng, hash manifest), không đổi trạng thái hay finding. GIỚI HẠN: mô hình có phần tử vỏ bao lệch vẫn đi đường Boolean và có thể INCONCLUSIVE.)*
  `mapping/policy.py` thêm chiến lược; `mapping/exporter.py` xuất nhiều `&OBST` cho một phần tử; `plan_validation.py`, manifest, parser nhận nhiều primitive cho một entity.
  Thuật toán: mesh là đa diện trực giao (mọi pháp tuyến song song trục) → lưới từ tọa độ đỉnh duy nhất → giữ ô có tâm trong solid (winding number, hàm đã có ở `component_union.winding_numbers`) → gộp tham lam thành hộp.
  Chứng minh: `compare_solids(mesh nguồn, [các hộp])` phải `surface_proven`. Không chứng minh được → giữ `GEOM`.
  Test: tường 1 lỗ, 2 lỗ, lỗ chạm mép, tường chữ L; tường nghiêng vẫn `GEOM`.
  Đo: % vật cản OBST/OBST_SET trên A.
- [x] **M2.2 Cổng hiệu dụng theo phần tử.** *(XONG: `validation/effective.py` không còn từ chối cả deck vì có `GEOM`, `VENT` hay `CTRL_ID`. `GEOM` thành INCONCLUSIVE riêng phần tử (evidence `elements`), còn lỗi thật ở OBST hoặc VENT vẫn là FAIL nên không bị che. `VENT` phẳng: đọc từ SMV thật (VENTORIG và bảng VENT, chỉ số đã snap), kiểm tồn tại, không collapse, không lệch ô; vent cắt ngang ranh giới hai mesh đã kiểm bằng solver thật. OBST có `CTRL_ID` hoặc `DEVC_ID` vẫn nằm trong bảng OBST của SMV: kiểm biên ở trạng thái đóng, và các cặp tĩnh (trạng thái mở) kiểm khe; cặp có vật điều khiển được bỏ qua vì khi đóng nó được phép bịt khung. Sửa dung sai: SMV in 5 chữ số thập phân nên lưới không tròn (A: 0,19952 m) lệch tới 5e-6 so với FDS, và `atol` 1e-7 cũ luôn báo "lưới không đều" trên mô hình thật (`SMV_PRECISION_M`). `HOLE` vẫn INCONCLUSIVE cả deck. Fixture SMV do FDS 6.11.1 sinh ra nằm ở `tests/data/effective/`.)*
- [x] **M2.3 Cổng độ phân giải lối thông.** *(XONG: `validation/passage_resolution.py`, gate `passage_resolution` thuộc nhóm mô phỏng nên không đổi hợp đồng mapping. Lỗ mở hộp có nhịp thông dưới 2 ô, hoặc vách vỏ bao có hai mặt cùng snap về một mặt phẳng lưới, thành FAIL kèm tên phần tử và cỡ ô đề xuất; finding có `verification_level=simulation`. Ca ô 1,0 m trên fixture opening: mapping vẫn MAPPING_VERIFIED, simulation REJECTED; dùng cỡ ô đề xuất thì PASS. GIỚI HẠN: lỗ không phải hộp trục (A: 177 lỗ) chưa ước lượng được nên gate INCONCLUSIVE thay vì PASS giả.)*
- [~] **M2.4 Chạy thật.** *(FZK và A đã chạy với FDS 6.11.1 qua `convert`. A (253 s, cache lạnh): solver PASS (khởi tạo thành công), `air_path` PASS, `effective_geometry` INCONCLUSIVE vì cả 546 phần tử là GEOM (liệt kê tên từng phần tử), `passage_resolution` INCONCLUSIVE (177 lỗ không phải hộp), verdict vẫn REJECTED do 22 cửa UNSUPPORTED (lỗi nguồn). CHƯA ĐẠT mục tiêu `effective_geometry` PASS trên A vì A hoàn toàn là GEOM; cần đọc đầu ra cut-cell của GEOM hoặc thay bằng OBST, xem M2.1. THAM CHIẾU: nhánh `feat/p1-2-fds-geom-cutcell-probes` (PR #107, đã đóng vì xung đột với `main`) có phép chạy DEVC đo thể tích khí và diện tích mặt mở của một GEOM kín, đối chiếu hash deck/solver/CSV, kiểm bằng FDS 6.11.1 trên tứ diện; port lại trên nền `main` khi làm M2.4.)*  A: `convert --solver <fds>` với `T_END=0`; lưu bằng chứng tổng hợp.
- **Cổng M2:** A: solver `PASS`; `effective_geometry` `PASS` cho mọi OBST/VENT; ≥ 90% vật cản là OBST/OBST_SET; phần GEOM còn lại có danh sách review.

## M3 — HVAC vận hành trên C (3–4 tuần; cần đầu vào B-ext 1–3)

- [ ] **M3.1 Phân loại phụ kiện theo tên họ** (IFC2X3 không có `PredefinedType`): bảng cấu hình tên họ → {cút, côn/chuyển tiết diện, tê, nắp bịt}; phần tử không khớp → `REVIEW_REQUIRED`. File: `mep/classifier.py`. *(CHƯA LÀM, cần người dùng duyệt bảng vì bộ phân loại hiện cố ý không đoán từ tên. Dữ liệu thật của C: 478 `IfcFlowFitting` thuộc 7 họ: cút ống gió vuông 182, chuyển tiết diện vuông–tròn 100, côn ống gió vuông 78, gót giày 60, đầu bịt 34, Y 16, tê 8. C không có quạt hay van gió riêng (IFC2X3 không có `IfcFan`), nên lưu lượng phải đến từ thiết kế từng miệng. 84 phụ kiện (gót giày, Y, tê) có từ 3 cổng nên cần tổn thất nút.)*
- [ ] **M3.2 Phạm vi hệ thống.** `system_decisions` gán từng hệ (PAD/CEAD/…) là hút khói / cấp bù / ngoài phạm vi; ống nước SPR → vật cản thụ động hoặc loại có lý do. *(CHƯA LÀM: cần B-ext 2.)*
- [~] **M3.3 Mở rộng spec** `domain/mep/hvac.py`: spec theo loại (duct, fitting 2 cổng với `loss=(K_thuận,K_ngược)` + chiều dài đường tâm, junction với `LOSS(I,J)`, fan với lưu lượng hoặc đường cong, damper với điều khiển); `EndpointSpec.vent_xb` có trường frame WORLD/REBASED. *(XONG: duct, fitting hai cổng, quạt lưu lượng cố định và **junction** (tê, Y, gót giày từ 3 tới 10 cổng) qua `JunctionSpec`: danh sách `losses` `{from_port, to_port, k}`, bắt buộc đủ mọi cặp cổng có thứ tự (3 cổng 6 cặp, 4 cổng 12 cặp), K không âm, quy chiếu theo vận tốc ống đích. CHƯA: đường cong quạt, damper, trường frame của `vent_xb`.)*
- [x] **M3.4 Biên dịch.** `mep/network.py` bỏ guard chỉ-ống-thẳng theo từng loại đã hỗ trợ; `mep/fds_records.py` sinh `&HVAC` tương ứng; `validation/parser.py` + `checkers/hvac.py` nhận. Hướng dòng của cổng `SOURCEANDSINK` suy từ quạt/đầu cuối đã duyệt; không suy được → lỗi rõ ràng. *(XONG: guard theo loại; phụ kiện hai cổng cần K và chiều dài đường tâm đã duyệt; quạt cần lưu lượng và cổng SINK/SOURCE, không bao giờ suy hướng. Junction: mọi cổng của phần tử tê gộp thành MỘT nút FDS; mỗi cổng phải nối đúng một ống; hai junction liền kề bị từ chối; nút có vị trí là trọng tâm các cổng; `LOSS(i,j)` ghi theo thứ tự `DUCT_ID` của nút; phần tử tê là chủ sở hữu nút trong manifest. Parser và checker độc lập kiểm chỉ số `LOSS(i,j)` trong 1..số ống, i≠j, giá trị hữu hạn không âm; đổi một K trong deck rồi cập nhật hash thì cổng `hvac` FAIL.)*
- [ ] **M3.5 Đầu cuối → biên.** 130 `IfcFlowTerminal` → `VENT` trên mặt OBST gần nhất hoặc `AMBIENT`, theo quyết định duyệt. *(CHƯA LÀM: cần B-ext 3.)*
- [x] **M3.6 Kiểm chứng bằng FDS.** (a) quạt + ống + cút: Δp–Q so lời giải tay ±5%; (b) tê: bảo toàn khối lượng < 1%; (c) đảo chiều. *(XONG (a), (b), (c) với FDS 6.11.1, `tests/test_hvac_fds_pressure.py` và `tests/test_hvac_junction.py` (`-m solver`), deck sinh từ IFC thật qua `convert`. (a): thuận 12,02 Pa vs tay 12,08 Pa; đảo chiều 23,97 vs 24,08. (b) tê K(thân→nhánh1)=2,0, K(thân→nhánh2)=0,5: lưu lượng tách khớp lời giải tay trong 5% và q1+q2=0,3 trong 1%; hợp dòng (hai nhánh −0,1 và −0,2 vào tê): dòng ra −0,3 trong 1%. ĐO ĐƯỢC về FDS: `LOSS(I,J)` của nút quy chiếu theo vận tốc ống đích J (đối chiếu hai giả thuyết với diện tích nhánh khác nhau: q1=0,0672 khớp dự đoán tới 4 chữ số). PHÁT HIỆN CẦN KỸ SƯ QUYẾT: (1) `ROUGHNESS=0` nghĩa là KHÔNG ma sát trong FDS, không phải ống trơn; (2) FDS tính ma sát theo đường kính tương đương tròn √(4A/π) và bỏ qua `PERIMETER`, khớp 0,2% cả ba ca đo; với ống chữ nhật 0,5×0,3 m ma sát thấp hơn công thức sách giáo khoa (D_h = 4A/P) khoảng 18%. Cổng `hvac` báo cả hai thành finding P2 `verification_level=simulation`.)*
- **Cổng M3:** một nhánh hút khói thật của C biên dịch đủ, FDS chạy tới `T_END`, lưu lượng miệng hút ±10% thiết kế.

## M4 — Cháy xe điện (3–4 tuần; cần đầu vào B-ext 4)

- [ ] **M4.1 Preset.** Thêm `e-moped`/`e-motorbike`, sửa `auto-nmc` trong `reference-cases/ev-library/` theo số đo whole-vehicle; mỗi preset có citation, miền áp dụng. *(BỊ CHẶN: cần B-ext 4. Trong lúc chờ, số đo được phép dùng có thể phát lại thẳng bằng M4.2.)*
- [x] **M4.2 Replay đường HRR đo** (CSV → `RAMP`) trong `fire/scenario_emitter.py`. *(XONG: `EVSelection.hrr_curve_kw` (thời gian sau đánh lửa s, HRR kW) cùng `hrr_curve_source` bắt buộc một dòng. Từ chối đường không bắt đầu ở t=0, thời gian không tăng, giá trị âm, hoặc `peak_hrr_mw` mâu thuẫn; đỉnh suy từ đường đo và vẫn phải nằm trong miền của preset. RAMP phát đúng từng điểm (có độ trễ đánh lửa); `assess_scenario_physics` đọc lại năng lượng từ deck. Việc đọc tệp CSV để dựng danh sách điểm là của phía gọi.)*
- [ ] **M4.3 HF/HCN.** Xác minh cú pháp với FDS User's Guide 6.11.1 và chạy setup **trước khi viết mã**; yield từ dữ liệu nguyên xe. *(BỊ CHẶN: cần B-ext 4.)*
- [ ] **M4.4 Biên truyền nhiệt.** `MATL` + `SURF` có `MATL_ID`/`THICKNESS` cho bê tông/thép, tính chất có nguồn. *(BỊ CHẶN: cần nguồn tính chất vật liệu được duyệt.)*
- [~] **M4.5 Kiểm chứng.** Ca 1 xe khoang nhỏ: `_hrr.csv` khớp `RAMP` ±5%; năng lượng khớp `assess_scenario_physics`. *(XONG trên ca tổng hợp với FDS 6.11.1, `tests/test_hrr_curve_replay.py` (`-m solver`): năng lượng 8,402 MJ so với 8,4 MJ (0,02%); trung bình vùng đỉnh 45–80 s 119,98 kW so với 120 kW; đạt nửa đỉnh ở 21 s so với 20 s. ĐIỀU CHỈNH TIÊU CHÍ: HRR tức thời của FDS dao động khoảng ±10% do rối và trễ khoảng 1 s so với nhiên liệu cấp vào, nên so từng điểm ±5% không có ý nghĩa vật lý; test so năng lượng (±1%), trung bình vùng đỉnh (±5%) và thời điểm. CHƯA: ca trên A, cần preset và vị trí xe.)*
- **Cổng M4:** kịch bản 1 xe máy điện + 1 ô tô trên A chạy tới `T_END`; báo cáo nêu miền áp dụng và bất định.

## M5 — Vận hành API và nghiệm thu (2–3 tuần; phần API làm song song từ sau M1)

- [x] **M5.1** `TMPDIR` về volume jobs (`compose.production.yml`); smoke test upload 2×150 MiB trong `container.yml`. *(XONG phần mã: lỗi gốc là Starlette ghi phần multipart lớn vào `TMPDIR`, mặc định `/tmp` của container chỉ là tmpfs 256 MiB trong khi một job được tới 500 MiB. Compose đặt `TMPDIR=/var/lib/ifctofds/jobs/.upload-tmp` (trên volume); `serve` tạo thư mục này, dọn phần sót của lần upload bị ngắt, và từ chối khởi động nếu không chuẩn bị được thay vì âm thầm quay về `/tmp`. ĐO BẰNG DOCKER 29.9.3 trên image mặc định với đúng cờ production (root read-only, bỏ mọi capability, `/tmp` tmpfs 256 MiB): upload 2×150 MiB KHÔNG có `TMPDIR` bị từ chối (HTTP 400 "error parsing the body", tức đây là lỗi thật của cấu hình hiện hành); CÓ `TMPDIR` trên volume thì HTTP 202 trong 2 giây. `scripts/production-upload-smoke.py` stream 2×150 MiB tới `POST /api/jobs`, mong HTTP 202 rồi hủy và xóa job; bước mới trong job `container` của CI chạy nó qua HTTPS. Bước CI mới chạy qua HTTPS trong stack đầy đủ; bước đó chưa chạy trên CI.)*
- [x] **M5.2** Job dài (C ~10 phút): timeout scheduler, RSS đỉnh, tiến độ trên web; tải gần hạn mức; khởi động lại giữa chừng. *(XONG trên C: `scripts/long-job-drill.py` chạy một server thật, ở chế độ local và ở `IFCFDS_ENV=production` (API key, danh sách host, khóa thư mục job, SQLite đồng bộ đầy đủ), với giới hạn production (bộ nhớ worker 4096 MiB, timeout 1800 s, hàng đợi 2). Job C 8 tầng hầm cold COMPLETED trong 260–266 s, RSS đỉnh 1.235–1.242 MiB, không chạm giới hạn; tiến độ đổi qua 16 mốc giai đoạn; hàng đợi: 2 job nhận, 2 bị 429; kill cứng giữa chừng rồi khởi động lại trên cùng thư mục: job bị ngắt thành FAILED ("Process terminated unexpectedly during server restart"), kết quả job đã xong giữ nguyên từng byte, job mới COMPLETED, khóa thư mục production được giải phóng. Verdict C vẫn REJECTED do lỗi nguồn, không phải lỗi vận hành. Bằng chứng: `docs/evidence/production-roadmap/m5-2-drill-C.json` (production) và `m5-2-drill-C-local.json`. GIỚI HẠN: chạy trên máy dự án (Windows), không phải Compose trên Linux; chưa thử nhiều client tải song song thật.)*
- [x] **M5.3** Diễn tập backup/restore (`operations/offline_backup.py`). *(XONG: `tests/test_backup_restore_drill.py` chạy một chuyển đổi thật tới COMPLETED, dừng `JobService`, `create_offline_backup`, `restore_offline_backup` vào gốc mới, mở lại `JobService` trên bản khôi phục và so kết quả cùng hash từng tệp artifact. Test cũ chỉ dùng job tổng hợp. Lưu ý Windows: gốc thư mục phải ngắn vì đường dẫn artifact vượt MAX_PATH 260.)*
- [x] **M5.4** Image có FDS 6.11.1 (hash cố định). *(XONG phần mã: `Dockerfile` có stage `runtime`, target tùy chọn `solver` và stage cuối `image` = `runtime` nên `docker build` mặc định không đổi. Target `solver` tải bản Linux chính thức `FDS-6.11.1_SMV-6.11.2_lnx.sh`, kiểm SHA-256 cả tệp (`ba8793b9…`, khớp digest GitHub công bố) và của `fds_openmp` (`5e7cab03…`), cắt tar nhúng đúng như bộ cài rồi chỉ giữ solver OpenMP và MPI đi kèm (~175 MB), đặt `IFCFDS_SOLVER` và đường thư viện. Đã kiểm trong WSL Ubuntu: giải nén, `ldd` đầy đủ khi có `LD_LIBRARY_PATH`, set-up deck fixture thành công, SMV Linux trùng từng dòng với SMV Windows trong `tests/data/effective/`. ĐÃ BUILD VÀ CHẠY CỤC BỘ bằng Docker: image `solver` 1,66 GB, hash cả hai khớp trong lúc build, probe `solver_gates` + `effective_geometry` đạt trong container với root read-only, bỏ mọi capability, `/tmp` noexec; image mặc định không có `/opt/fds`. Job CI mới `solver-image` build target và chạy `scripts/container-solver-probe.py` (`solver_gates` + `effective_geometry` của dự án) với root read-only, bỏ mọi capability, `/tmp` noexec.)*
- [x] **M5.5** CLI và web cho cùng deck (so hash) trên A. *(XONG: `scripts/cli-web-deck-parity.py` chạy `convert` bằng CLI rồi cùng IFC qua `POST /api/jobs` trên server thật, so SHA-256 `model.fds`. A: deck 10.096.250 byte TRÙNG TỪNG BYTE (CLI 184 s, web 166 s), cùng verdict REJECTED (22 cửa lỗi nguồn). B: TRÙNG TỪNG BYTE và verdict `MAPPING_VERIFIED` (B từng bị chặn bởi `air_path`; M2.5 gỡ). Test hồi quy `tests/test_cli_web_parity.py` (`-m slow`) trên fixture nhỏ. Bằng chứng: `docs/evidence/production-roadmap/m5-5-cli-web-parity.json`.)*
- [ ] **M5.6** Nghiên cứu lưới 3 mức cho QoI đã chốt (`fire/grid_sensitivity_*`).
- [ ] **M5.7** Kỹ sư PCCC độc lập review deck + báo cáo; ghi giờ công so với dựng tay.
- **Cổng cuối (Definition of Done):**
  - CLI và web cho `MAPPING_VERIFIED` (hoặc `REJECTED` chỉ với lỗi nguồn thật đã xác nhận) trên A.
  - Deck có HVAC hút khói + kịch bản cháy xe chạy FDS 6.11.1 tới `T_END`.
  - Thời gian chuyển đổi + audit đo và ghi (mục tiêu < 10 phút cho A, C).
  - Kỹ sư ký nhận; mọi giới hạn nằm trong báo cáo.

## M6 — Khắc phục audit 2026-11-15 (Codex, đo ở `8ed1f38`; XONG 2026-11-16)
Nguồn đã chuyển vào [docs/history/audit-2026-11-15/](../history/audit-2026-11-15/): [audit gốc](../history/audit-2026-11-15/AUDIT_2026-11-15_ifctofds-chuyen-doi-hvac-fds.md), [đối chứng HVAC](../history/audit-2026-11-15/AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md), [kiến trúc và Docker](../history/audit-2026-11-15/AUDIT_2026-11-15_kien-truc-docker.md), cùng [kế hoạch M6](../history/audit-2026-11-15/m6-implementation-plan.md) và [kế hoạch xử lý phần ngoài M6](../history/audit-2026-11-15/audit-followup-plan.md). Giữ ID của audit. Quyết định của người dùng (2026-11-15): F9 dùng `ROUND=.FALSE.`; F1 MESH chồng nhau là FAIL; F4 áp cho mọi OBST. F6 đã đóng ở #92. Mỗi mục có test hỏng-trước-sửa trong PR; Verified và Quality xanh trên SHA merge.
- [x] **M6.0 Chuẩn bị.** #119 `6dce86f`: bản audit, test `compare_solids` thật cho quy tắc lớp vỏ của #118.
- [x] **M6.F1 (P1) Cổng `domain` kiểm độ phủ thật.** #120 `2e00f82`. MESH ghép sát PASS; hở dải hoặc chồng nhau FAIL kể cả khi tổng thể tích bằng nhau.
- [x] **M6.F3 (P1) `passage_resolution` không PASS khi còn lỗ chưa đo.** #121 `354654f`. Chỉ đổi verdict mô phỏng.
- [x] **M6.F4 (P2) Vật cản bị lưới xóa.** #122 `0bcf211`. Mọi OBST co về điểm trên ít nhất hai trục là FAIL; ca đồng thời có lỗ chưa đo vẫn FAIL, evidence giữ `openings_not_estimated`.
- [x] **M6.F9 (P2) `ROUND=.FALSE.` cho ống `AREA/PERIMETER`.** #124 `4d1b2ad`. Deck cũ thiếu cờ nhận finding `HVAC-FRICTION-0002` P2, không FAIL; re-audit bundle trước F9 giữ `MAPPING_VERIFIED`, `hvac=PASS`. **Đính chính M3.6:** ma sát ống chữ nhật thấp hơn 18% là do serializer thiếu cờ, không phải giới hạn của FDS; nay FDS tính theo `D_h = 4A/P`.
- [x] **M6.F7 (P2) Sai số float khi tính số ô.** #125 `5c44de3`. Thương sát số nguyên không sinh thêm ô; vượt giới hạn thật vẫn bị chặn.
- [x] **M6.F2 (P1) VENT HVAC trên đúng hộp OBST được ghi ra.** #123 `42051e4`. Với FDS 6.11.1: deck VENT trong ô cửa trả `ERROR(818)`, deck tường đặc khởi tạo thành công.
- [x] **M6.F5 (P2) Đường dẫn dài Windows.** #126 `493a243`. Báo lỗi trước khi ghi, bundle cũ nguyên vẹn.
- [x] **M6.F8 (P2) README.** #127 `e82a2eb`.
- [x] **Phần audit ngoài M6, cùng đợt.** F2-SMV (P2) #132 `7429ab6`: ghép VENT trong SMV theo `ORDINAL` và bỏ các hàng ngoại biên do solver sinh; deck tường đặc từ `effective_geometry=FAIL` thành `PASS`. HVAC-D1/D2 #129 `e0faf41`: `pipeline.audit` báo VENT thiếu mặt đỡ là `hvac=FAIL` (trước đó ném `ValueError`); deck bị sửa tay (dời VENT, VENT ra không gian hở, mất VENT) đã FAIL từ trước nhờ so bản ghi. ARCH-01 #130 `fdbacea`: cổng mesh không còn import `fire`. EV-PACK-01 (P1) #131 `16efd48`: image runtime có thư viện preset EV, smoke chạy trong `container.yml`.
- [x] **M6.9 Đóng audit.** Ba tệp audit chuyển sang `docs/history/audit-2026-11-15/`; phần chưa làm thành mục mở A4.10–A4.12. Số đo ở `docs/evidence/production-roadmap/m6-close-2026-11-16.json` (tổng hợp, `main` `16efd48`, cache lạnh, tuần tự).
- **Cổng M6:** đạt. Verdict không đổi: FZK, Duplex, Institute `REJECTED`; B `MAPPING_VERIFIED` (218 MATCHED, 61 SEMANTIC_ONLY, 0 finding); A `REJECTED` với 546 MATCHED, 210 SEMANTIC_ONLY, 22 UNSUPPORTED, 15 REVIEW_REQUIRED, trùng `tolerance-A-C.json`. So với đo trước M6 (`e448e11`): FZK 0 khác biệt, Institute trùng trạng thái, witness và finding từng phần tử; Duplex `passage_resolution` 55 → 56, gồm ba phần tử đổi tên từ "Thin solid collapses" sang "Solid vanishes on the grid" (co trên ít nhất hai trục) và một phần tử mới bị bắt, đúng thay đổi có chủ ý của F4; gate vẫn FAIL. Finding `representation` của Duplex lại chập chờn (A4.7), không phải hồi quy. **C (8 tầng hầm, đo lại 2026-11-16 ở `60fd3b0`):** `REJECTED`, 697 MATCHED, 0 DEVIATED, 1 UNSUPPORTED, 183 REVIEW_REQUIRED, 66 SEMANTIC_ONLY, 1.528 REFERENCE_PRESERVED, 3.165 EXCLUDED_SCOPE, finding trùng từng số với `tolerance-A-C.json`; điểm mới duy nhất là `passage_resolution` INCONCLUSIVE (154 lỗ mở chưa đo, 406 đã xử lý), đúng thay đổi có chủ ý của F3, kết luận mapping không đổi. Thời gian 619 s không dùng để kết luận: FZK đối chứng 34 s trước và 33 s sau (mốc cũ khoảng 10 s). Solver trên A/C `NOT_RUN`.

## B-ext. Đầu vào từ người dùng/kỹ sư (hỏi ngay, chặn M3–M5)
1. C và A có cùng không gian hầm không; nếu có, transform chung giữa hai file.
2. Nghĩa của PAD / CEAD / OAD-FAD / RAD / TEAD; hệ nào hút khói, hệ nào cấp bù.
3. Hệ số tổn thất K, đường cong quạt, lưu lượng thiết kế từng miệng hút.
4. Dữ liệu đo cháy xe nguyên chiếc được phép dùng (HRR theo thời gian, yield).
5. QoI nghiệm thu (nhiệt độ/tầm nhìn tại lối thoát, độ cao lớp khói) và kỹ sư review.
6. Đối chiếu PyroSim (T19–T21 trong kế hoạch kiểm thử thực tế): deck `.fds` do PyroSim sinh khi nhập A/B/C (ghi phiên bản, chế độ khối hay solid, khoảng nới lỗ mở) và deck B / `tee.fds` đã mở rồi lưu lại bằng PyroSim, hoặc một máy có PyroSim.

## Thứ tự và phụ thuộc
`M0 → M1 → M2 → M3 → M4 → M5.5–5.7`. M5.1–M5.4 song song từ sau M1. M3 và M4 độc lập nhau sau M2, làm song song được nếu có hai người.
Ước lượng một kỹ sư: M0 2 ngày, M1 2 tuần, M2 3 tuần, M3 4 tuần, M4 4 tuần, M5 3 tuần ≈ 3,5–4 tháng. Ước lượng thô; xem lại sau M1.

## Ánh xạ sang số bước của bản 1
5.5→M1.2, 5.6→M1.1, 5.7→M1.3, 5.8→M0.1–M0.4+M1.7, 5.9→M1.4, Giai đoạn 6→M2, 7→M3, 8→M4, 9→M5.1–5.4, 10→M5.5–5.7.
