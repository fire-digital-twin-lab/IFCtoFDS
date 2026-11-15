# Kế hoạch kiểm thử thực tế

Mục đích: chứng minh trên IFC thật và trên stack triển khai thật rằng các cổng của [kế hoạch production](production-roadmap.md) đạt, theo đúng thứ tự phụ thuộc. IFC thật không commit: dùng bí danh A (`Ham2Tang.ifc`), B (`Tang7.ifc`), C (`ALL_FDS_2027.ifc`) trong thư mục `D:\User\HUCE\NCKH\Resources\IFC_Tòa nhà\`; chỉ ghi số tổng hợp vào repo (`docs/evidence/production-roadmap/`).

## Quy tắc chung
- Chạy tuần tự, kèm một lượt đối chứng cố định (FZK cold) cùng phiên; nếu đối chứng lệch quá 20% so với 14 s thì ghi điều kiện và chạy lại trước khi kết luận hiệu năng.
- Cold: `IFCFDS_GEOMETRY_CACHE` trỏ thư mục mới ngoài repo. Đầu ra ngoài repo.
- Mỗi phép kiểm ghi: SHA commit, lệnh, thời gian, RSS đỉnh, verdict từng gate, và tệp bằng chứng.
- Trạng thái: `LÀM ĐƯỢC` (agent tự chạy), `CHỜ ĐẦU VÀO` (cần người), `ĐÃ ĐẠT` (đã có bằng chứng).

## Tầng 1 — Tự động, đã có
| # | Phép kiểm | Tiêu chí | Trạng thái |
|---|---|---|---|
| T1 | Suite mặc định | 0 lỗi | ĐÃ ĐẠT (1280) |
| T2 | Suite solver với FDS 6.11.1 | 0 lỗi | ĐÃ ĐẠT (17) |
| T3 | Container: upload 2×150 MiB, image `solver` dưới profile production | HTTP 202; `solver_gates` và `effective_geometry` PASS | ĐÃ ĐẠT cục bộ; `solver-image` đạt trên CI |
| T4 | Backup/restore job thật | artifact và kết quả giống hệt | ĐÃ ĐẠT |

## Tầng 2 — IFC thật qua CLI
| # | IFC | Lệnh (rút gọn) | Tiêu chí đạt | Trạng thái |
|---|---|---|---|---|
| T5 | A, cold | `python -m ifc_to_fds convert A -o <ra>/a.fds --solver <fds>` | thời gian ≤ 120 s; chỉ có finding của 22 cửa lỗi nguồn; solver PASS; `air_path` PASS | LÀM ĐƯỢC (hiện 211–253 s: cần M1.7) |
| T6 | A + lỗi nguồn đã duyệt | thêm `--accepted-source-defects <json>` (kỹ sư duyệt 22 cửa) | `MAPPING_VERIFIED` hoặc chỉ còn finding có giải thích | CHỜ ĐẦU VÀO (kỹ sư duyệt) |
| T7 | B | `convert B` | tìm nguyên nhân rò âm −1,3 L của `air_path`; sau M2.5 phải PASS hoặc có lý do | ĐÃ ĐẠT: B `MAPPING_VERIFIED` (M2.5 gỡ lỗi rò giả) |
| T8 | C, 8 tầng hầm | `convert C --storey <8 storey_id>` (id lấy từ `inventory`; tên trùng giữa các hệ cao độ) | ≤ 300 s; RSS < 4 GiB; số `EXCLUDED_SCOPE` khớp số phần tử ngoài tầng | ĐÃ ĐẠT: 293 s cold, RSS đỉnh 1,2 GiB (job qua API) |
| T9 | A, kịch bản cháy | emitter với preset e-bike và auto-nmc đặt trong hầm; `T_END` ngắn | FDS chạy tới `T_END` không lỗi; HRR đúng đường đã chọn | LÀM ĐƯỢC |

## Tầng 3 — Web/API
| # | Phép kiểm | Tiêu chí | Trạng thái |
|---|---|---|---|
| T10 | CLI và web (`POST /api/jobs`) trên A | cùng `model.fds` (SHA-256 trùng), cùng verdict | ĐÃ ĐẠT: A và B trùng từng byte, cùng verdict |
| T11 | Job dài C qua web | tiến độ cập nhật; RSS đỉnh ghi lại; không vượt `IFCFDS_TIMEOUT_S` 1800 s | ĐÃ ĐẠT: 260–266 s, 16 mốc tiến độ, RSS 1,2 GiB |
| T12 | Khởi động lại giữa chừng | job đang chạy chuyển FAILED có lý do; job mới chạy bình thường; không mất dữ liệu job xong | ĐÃ ĐẠT (local và production) |
| T13 | Tải gần hạn mức | `IFCFDS_MAX_WAITING`+1 job cùng lúc: phần dư nhận 429, không treo | ĐÃ ĐẠT: 2 nhận, 2 bị 429 |
| T14 | Backup/restore với job C thật | giống T4 trên artifact của C | LÀM ĐƯỢC sau T11 |

## Tầng 4 — Vật lý và nghiệm thu
| # | Phép kiểm | Tiêu chí | Trạng thái |
|---|---|---|---|
| T15 | Tổn áp tê/Y (M3.6b) | bảo toàn khối lượng tại nút < 1%; tổn áp khớp tính tay ±5% | ĐÃ ĐẠT: tách dòng khớp tay 5%, khối lượng 1% (mạng tê tổng hợp) |
| T16 | Nhánh hút khói thật của C chạy tới `T_END` | lưu lượng miệng hút ±10% thiết kế | CHỜ ĐẦU VÀO (B-ext 2, 3) |
| T17 | Nghiên cứu lưới 3 mức cho QoI | xu hướng đơn điệu trước khi tính GCI | CHỜ ĐẦU VÀO (B-ext 5) |
| T18 | Kỹ sư PCCC độc lập review deck và báo cáo, ghi giờ công so với dựng tay | ký nhận; giới hạn nằm trong báo cáo | CHỜ ĐẦU VÀO |

## Tầng 5 — Đối chiếu PyroSim
Công cụ: `python scripts/compare-fds-decks.py <deck A> <deck B> --json <ra.json>`. Script so không gian do OBST/GEOM/HOLE lấp đầy (không cần dòng `! IFC_SOURCE`): thể tích, IoU, phần chỉ một deck có kèm vị trí, mesh/số ô, số dòng provenance còn lại, bản ghi HVAC và số cặp `LOSS(i,j)`. IoU tính từ hai phép hiệu Boolean (phép giao của Manifold mất khoảng 0,3% trên mặt trùng); phần "chỉ có ở một deck" cỡ 1e-4 m³ là nhiễu. Script chỉ đo, không kết luận đạt/không đạt. Audit thường không dùng được cho deck PyroSim: cùng hình học nhưng thiếu `! IFC_SOURCE` thì mọi phần tử bị coi là MISSING.

| # | Phép kiểm | Cách làm | Tiêu chí | Trạng thái |
|---|---|---|---|---|
| T19 | PyroSim giữ provenance khi lưu | mở `model.fds` của B trong PyroSim, lưu thành `b_pyrosim.fds`; chạy script với deck gốc và deck đã lưu | `provenance_lines` của B bằng của A; `comparison.method` là `IDENTICAL_SPACE` hoặc phần chỉ một deck có ≤ nhiễu | CHỜ ĐẦU VÀO (cần PyroSim) |
| T20 | PyroSim giữ mạng HVAC tê/Y | sinh deck tê: `python -c "import pathlib,sys; from tests.test_hvac_junction import build,K; from ifc_to_fds.pipeline import convert; d=pathlib.Path(sys.argv[1]); p,c,_=build(d,K); (d/'tee.fds').write_text(convert([str(p)],c,d/'out')['fds_text'],encoding='utf-8')" <thư mục>`; mở `tee.fds` trong PyroSim, xem cây HVAC, lưu; chạy script | `hvac` = `{'NODE': 4, 'DUCT': 3}` và `node_loss_pairs` = 6 ở cả hai deck; ghi PyroSim hiển thị LOSS của nút ra sao | CHỜ ĐẦU VÀO (cần PyroSim) |
| T21 | So hình học với PyroSim nhập IFC | nhập A/B/C bằng PyroSim (ghi phiên bản, chế độ khối hay solid, khoảng nới lỗ mở), xuất `.fds`; chạy script với deck IFCtoFDS | ghi thể tích, IoU, 10 vùng lệch lớn nhất và nguyên nhân từng vùng; không tự đặt ngưỡng | CHỜ ĐẦU VÀO (cần PyroSim hoặc deck PyroSim) |

Đã kiểm script trên deck B thật: so với bản bỏ hết `! IFC_SOURCE` cho `IDENTICAL_SPACE`, 218/0 dòng provenance; bỏ một GEOM 0,0983 m³ thì phần chỉ có ở deck gốc là 0,0980 m³ (phần còn lại chồng lên tường bên cạnh), nhiễu 2,3e-4 m³, IoU 0,999240 so với kỳ vọng 0,999242.

## Thứ tự chạy
T5 → T8 (đo hiệu năng, sau M1.7) → T7 → T10 → T11–T13 → T14 → T9 → T15. Các phép CHỜ ĐẦU VÀO chạy khi người dùng cung cấp dữ liệu; kế hoạch này không thay thế quyết định kỹ thuật của kỹ sư.
