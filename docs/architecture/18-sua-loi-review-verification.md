# Sửa bốn phát hiện review module Verification

Ngày: 23/10/2026. Nhánh `chore/research-acceptance-hardening`; commit nền `5d715a7df7b7606747285b7073287723f20506f3`. Thay đổi chưa commit/push. Không sửa IFC nguồn và không nâng trạng thái nghiệm thu bằng suy đoán.

## 1. Kết quả sửa mã

| Phát hiện | Thay đổi | Bằng chứng phủ định |
| --- | --- | --- |
| P1 — khe OBST với biên miền bị đóng | `effective_topology.py` kiểm tra sáu khoảng cách biên; dựng phân hoạch chữ nhật chung từ mặt OBST nguồn, mặt OBST hiệu dụng và biên miền. Đối chiếu các thành phần không khí liên thông sáu hướng bằng quan hệ tương ứng, không chỉ đếm tổng số. Nhiều MESH ghép topology trên toàn miền hợp nhất, tránh xem mặt tiếp giáp MESH là biên ngoài. | Sáu ca khe 0,04 m trên lưới 0,1 m phải FAIL; ca hai OBST chéo nhau làm mất đường thông khí phải FAIL dù kiểm tra khe từng cặp mặt bỏ sót. Ca giữ nguyên khe phải PASS; vượt ngân sách phân hoạch phải INCONCLUSIVE. |
| P1 — dung sai thay đổi giữa các bước | `prepare_pyrosim_acceptance.py` resolve một `AuditConfig` từ manifest, sau đó ghi đè các trường được nêu rõ trong `--audit-config`. Cùng cấu hình được dùng cho audit nguồn, đối chiếu xuất lại và các lượt solver. Báo cáo lưu cấu hình đã resolve cùng hash manifest/file ghi đè. | Dịch bản xuất lại 0,5 mm: mặc định 1 mm có thể chấp nhận; cấu hình manifest 0,01 mm bắt buộc FAIL. File ghi đè chỉ có timeout phải giữ nguyên dung sai đã duyệt. Các lượt chạy bản gốc và bản xuất lại đều nhận cùng dung sai. |
| P2 — SURF không gắn với đúng tam giác | `solver_surface.py` đối chiếu đa tập tam giác có hướng kèm chỉ số SURF. Cho phép đổi thứ tự tam giác và đánh số lại vertex khi chứng minh được cùng cặp tam giác–SURF. Hình học tương ứng có dịch chuyển chỉ được xét trong dung sai đã duyệt. Đổi triangulation nhiều SURF chưa chứng minh được vẫn INCONCLUSIVE. | Tráo hai tam giác thuộc hai SURF và giữ danh sách chỉ số phải FAIL; tráo cả tam giác lẫn SURF hoặc đánh số lại vertex đúng phải PASS. Có ca FDS thật với hai SURF. |
| P2 — checksum không tái lập sau checkout | Python dùng LF qua `.gitattributes`; 123 hash facade được đổi từ CRLF sang đúng LF, sau khi chứng minh nội dung chuẩn hóa bằng đúng blob của commit nền. SMV/FDS/BINGEOM native giữ nguyên byte bằng `-text`. Ba SMV khôi phục byte CR cuối tệp bị Git chuẩn hóa, giữ nguyên checksum nguồn gốc. | Checkout qua index Git riêng với cả `core.autocrlf=true` và `false`: 138 tệp khớp SHA-256. Sinh lại ba SMV bằng FDS thật: khớp từng byte với fixture gốc. Không sửa hash provenance để che sai khác. |

Phân hoạch topology giới hạn 2.000.000 ô; ngoài miền hoặc vượt giới hạn trả INCONCLUSIVE. Đây là kiểm chứng liên thông hình học của OBST, không chứng nhận lưu lượng, điều kiện thông gió vận hành hoặc cut-cell GEOM. Adapter ban đầu có phiên bản `static-air-topology-and-bound-surfaces-0.5.3`; hai sửa đổi tiếp theo ở mục 4 dùng phiên bản `0.5.4`. Digest chứng nhận biên bao gồm mã topology mới; thay mã này làm chứng nhận cũ mất hiệu lực.

## 2. Các lượt kiểm tra

| Trạng thái | Kiểm tra | Kết quả / giới hạn |
| --- | --- | --- |
| PASS | Reproducer dùng đúng implementation ở commit nền | Khe biên và đường chéo đổi liên thông đều trả PASS sai trước khi sửa; các test phủ định mới chặn hai trường hợp đó. |
| PASS | Suite không cần HTTP/browser | 474 test đạt trước khi thêm test ràng buộc digest; gồm baseline, geometry, mapping, architecture và verification. JUnit: `.cache/review-offline.xml`. |
| PASS | Jobs không cần HTTP | 5 test đạt; 4 test dùng HTTP không chạy hoàn tất trong sandbox. JUnit: `.cache/review-jobs-final.xml`. |
| PASS | Kiểm tra kiến trúc + Verification + workflow liên quan sau khi thêm test digest | 190 test đạt; 22 test solver được deselect để chạy riêng. Đây là lượt có chồng lặp với suite trên, không cộng vào tổng. JUnit: `.cache/review-targeted-final.xml`. |
| PASS | Solver FDS thật | 22 test đạt, bao gồm 15 ca cũ và 7 ca mới; GEOM nhiều SURF vẫn giữ effective geometry INCONCLUSIVE do thiếu cut-cells. JUnit: `.cache/review-native-approved.xml`. |
| PASS | Kiểm tra cuối sau khi chốt mã và hướng dẫn | 44 test hồi quy đạt, cùng một ca chứng nhận biên FDS thật chạy lại để ràng buộc digest của mã cuối. Chồng lặp với các suite trên, không cộng tổng. JUnit: `.cache/review-last.xml`, `.cache/review-certificate-final.xml`. |
| PASS | Checkout checksum | 138 tệp đạt ở mỗi chế độ autocrlf; `.cache/review-checkout.json`. Không tạo commit trong repo phụ dùng kiểm tra checkout. |
| PASS | Nguồn gốc fixture native | `hole.smv`, `vent.smv`, `geom.smv` sinh lại khớp byte và checksum provenance; `.cache/review-fixture-regeneration.json`. |
| BLOCKED | Suite Python đầy đủ gồm HTTP | Event loop Windows bị kẹt trong `socket._fallback_socketpair` → `accept` khi TestClient khởi tạo. Không coi lượt dừng giữa chừng là PASS. Các test HTTP cần chạy lại ngoài sandbox hoặc trên CI. |
| BLOCKED | Browser và preview HTTP/file | Lượt browser không hoàn tất; backend preview không khởi động được trong cùng môi trường loopback bị chặn. Chưa có bằng chứng khắc phục lỗi preview `file://` đã nêu trong review. |
| NOT_RUN | Ma trận CI GitHub Linux/Windows, Python 3.10–3.12 với lockfile | Chưa push nên chưa có lượt CI cho bản sửa. Checkout checksum được kiểm tra cục bộ, không thay thế toàn bộ ma trận CI. |
| NOT_RUN | Nhập/xuất PyroSim thực tế và nghiệm thu GEOM cut-cells | Chưa có bằng chứng mới; không công bố nghiệm thu toàn module. |

Lượt đầu dùng TEMP mặc định gặp lỗi quyền ghi; lượt FDS đầu gặp lỗi Intel MPI/OFI trước khi đọc mô hình. Các kết quả FAIL ban đầu này được phân biệt với lượt cuối đã cấu hình TEMP trong workspace và MPI bộ nhớ chia sẻ. Không thay đổi kiểm tra hay fixture để bỏ qua lỗi solver.

## 3. Runtime và tái lập

Windows 11 `10.0.26200`, Python 3.12.10, pytest 9.1.1, IfcOpenShell 0.9.0.post1, NumPy 2.5.4, SciPy 1.18.1, trimesh 5.1.1, Pydantic 2.14.1. Đây là runtime `.venv` cục bộ, chưa phải xác nhận mọi phiên bản trong CI.

FDS 6.11.1, executable `.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe`, SHA-256 `dfaf04f1d46dbad77969b1cdd17baaa02a7aa6d63f46e96e93b9d9e635452b55`. Thiết lập `OMP_NUM_THREADS=1`, `I_MPI_FABRICS=shm`; cấu hình MPI được ghi trong evidence solver.

```powershell
New-Item -ItemType Directory -Force .cache/review-runtime-temp | Out-Null
$env:TEMP = (Resolve-Path .cache/review-runtime-temp).Path
$env:TMP = $env:TEMP
$env:IFCFDS_SOLVER = (Resolve-Path '.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe').Path
$env:OMP_NUM_THREADS = '1'
$env:I_MPI_FABRICS = 'shm'

.venv/Scripts/python.exe -m pytest -q tests/architecture tests/modules/verification tests/workflows/test_effective.py tests/workflows/test_mep_geometry_acceptance.py --basetemp .cache/review-reproduce-targeted
.venv/Scripts/python.exe -m pytest -q -m solver --basetemp .cache/review-reproduce-native
```

Ngoài sandbox, chạy lại suite mặc định, suite browser và `scripts/test-conversion-browser.py` trước khi chốt CI. Tài liệu 17 là lịch sử lượt cục bộ trước; số 487 PASS tại đó không chứng minh CI Ubuntu của commit `5d715a7` đạt. Theo review, CI commit nền có 485 PASS và hai lỗi checksum; bản sửa này cần một lượt CI mới để đóng kết luận đó.

## 4. Sửa hai hồi quy phát hiện trong lượt review tiếp theo

Kiểm tra khe biên nay dùng các cột không khí xuyên suốt từ mặt OBST tới biên miền, sau khi hợp toàn bộ OBST nguồn và toàn bộ OBST hiệu dụng trên cùng phân hoạch. Khoảng cách đã bị một hoặc nhiều OBST khác lấp kín không còn bị coi là khe thông khí. Nếu chỉ một phần mặt bị che, phần khe còn trống bị đóng vẫn phải FAIL. Đối chiếu thành phần liên thông và giới hạn tài nguyên tiếp tục áp dụng.

Adapter kiểm tra tọa độ TRNX/Y/Z trong sai số SMV `1e-7 m` như trước, sau đó suy ra tọa độ hiệu dụng từ chỉ số ô solver và miền lưới đều của FDS gốc. Sai số in như `0.12345002` thành `0.12345` không tạo OBST giả vượt miền hoặc khe không khí giả sát biên. Evidence lưu sai số in lớn nhất theo từng trục và phương pháp suy ra tọa độ. Không thay đổi dung sai nghiệm thu đã duyệt, không kẹp tọa độ OBST nguồn vào miền; nguồn thật sự vượt miền vẫn INCONCLUSIVE.

Thêm 25 ca hồi quy đơn vị và 5 ca FDS thật: mặt bị che bởi một/nhiều OBST, mặt còn khe hở, sai số SMV ở sáu biên, đóng khe thật khi SMV làm tròn vào/ra miền, lưới vượt độ chính xác hỗ trợ và nguồn thật sự vượt miền. Lượt tái lập trước sửa có 20 FAIL và 14 PASS trong 34 ca topology khi đó; sau khi mở rộng thêm hai ca che mặt, cả 36 ca topology nằm trong suite đạt bên dưới.

| Trạng thái | Kiểm tra sau khi chốt mã | Kết quả / bằng chứng |
| --- | --- | --- |
| PASS | Kiến trúc, Verification và workflow effective/MEP liên quan | 222 test đạt, 27 test solver được deselect để chạy riêng. JUnit: `.cache/verification-review-fixes-final-tests.xml`. |
| PASS | FDS 6.11.1 thật | 27 test đạt, gồm 22 ca hồi quy hiện có và 5 ca mới. JUnit: `.cache/verification-review-fixes-final-solver.xml`. Adapter `static-air-topology-and-bound-surfaces-0.5.4`. |
| NOT_RUN | CI GitHub, HTTP/browser và PyroSim thực tế trong lượt sửa này | Chưa có lượt CI mới; giới hạn môi trường và bằng chứng nghiệm thu ở mục 2 vẫn áp dụng. |
| INCONCLUSIVE | Nghiệm thu GEOM cut-cell và toàn module | Chưa bổ sung bằng chứng cut-cell hoặc phiên nhập/xuất PyroSim thật. |

Runtime giữ Windows 11, Python 3.12.10 và các phiên bản dependency ở mục 3; FDS có cùng SHA-256. Dùng TEMP/TMP trong workspace, `I_MPI_FABRICS=shm`, `OMP_NUM_THREADS=1`. Lượt đầu thêm ca FDS với OBST chôn hoàn toàn có 26 PASS và một FAIL tại kiểm kê vì FDS loại ID đó khỏi SMV. Không nới kiểm tra định danh để chấp nhận thiếu ID: ca chôn kín vẫn được kiểm tra trực tiếp ở cấp topology; ca FDS cuối dùng OBST còn mặt lộ ra nhưng khoảng cách tới biên đã bị khối khác lấp kín, nên quan sát được cả hai ID. Không sửa fixture chuẩn hoặc IFC nguồn, chưa commit/push.
