# Kết quả sửa hình học, hiệu năng và kiểm chứng đầu ra

## 1. Phạm vi thực hiện

Triển khai tiếp các ưu tiên trong [đánh giá chất lượng đầu ra](15-danh-gia-chat-luong-dau-ra.md), trên working tree của nhánh `chore/research-acceptance-hardening`, HEAD nền `f0c6d9c02342312266f2cfb8f9102833640061c3`. Không commit/push và không thay đổi các IFC gốc FZK/Institute/Duplex.

| Hạng mục | Kết quả |
| --- | --- |
| Institute — xử lý và hiệu năng | Hoàn tất hai mẫu cold/warm dưới giới hạn chạy 300 giây, có report đầy đủ. Nghiệm thu hình học vẫn `REJECTED` do lỗi được phát hiện. |
| IFC MEP/PCCC có hình học | Bổ sung fixture tự tạo với 8 solid, 14 port, 6 kết nối; đạt `MAPPING_VERIFIED`. Không gắn nhãn dữ liệu công trình thực. |
| Solver thật | Ma trận OBST/GEOM/HOLE/VENT/nhiều MESH; negative GEOM; MEP và boundary pipeline đã được chạy. |
| Hình học hiệu dụng | Mở rộng OBST từ một MESH sang các MESH đồng kích thước ô, liền kề và xếp dọc một trục; kiểm tra cả khoảng hở qua biên MESH. |
| PyroSim | Có công cụ chuẩn bị gói nhập và đối chiếu FDS xuất lại; GUI import thực tế `BLOCKED` vì chưa tìm thấy executable khả dụng. |
| Test chỉ kiểm tra tạo file | Bổ sung kiểm tra verdict/gates/identity/hình học và mutation; retention/RSS gọi production tick thay vì sao chép thuật toán vào test. |

## 2. Sửa thuật toán hình học

### 2.1. Predicate chính xác và chi phí tính toán

Trước đây kiểm tra giao cắt thực hiện nhiều phép `numpy.cross` trên vector ba số và chuyển các trường hợp sát biên sang `Fraction`. Thay đổi mới:

- Mã hóa tọa độ binary64 thành số nguyên với cùng mẫu số là lũy thừa của hai. Các dấu định thức và tỷ lệ cắt đoạn được tính chính xác bằng số nguyên; không tăng epsilon.
- Chuẩn bị cạnh và pháp tuyến chính xác của mỗi tam giác một lần, dùng lại trong narrow phase.
- Chứng minh riêng trường hợp 12 tam giác phủ đúng sáu mặt hộp: phải có đủ tám góc, mỗi mặt gồm hai tam giác chia theo đường chéo. Đây là chứng minh từ toàn bộ bề mặt, không thay mesh bằng bounding box.
- Đóng gói cạnh thành khóa số nguyên để đếm topology, thay phép sắp xếp hàng hai chiều đắt hơn. Có nhánh tránh tràn số.
- Dùng lại kết quả kiểm tra chất lượng vừa tính trong extraction thay vì tính lại ngay lần thứ hai.

Mã chính: [exact_predicates.py](../../ifc_to_fds/modules/geometry/algorithms/exact_predicates.py), [mesh.py](../../ifc_to_fds/modules/geometry/algorithms/mesh.py), [extraction.py](../../ifc_to_fds/modules/geometry/infrastructure/ifcopenshell/extraction.py).

Test dùng oracle `Fraction` độc lập trên nhiều độ lớn, trường hợp subnormal, tiếp xúc cạnh, đầu đoạn, tam giác gần song song và giao cắt thật. Có test đảm bảo hộp có mặt bị thay/đè không được nhận chứng minh hộp sạch; lỗi backend trên prism nghiêng vẫn là thiếu bằng chứng.

### 2.2. Chẩn đoán và timeout

Engine cập nhật tiến độ validation theo nhóm phần tử, có entity đang xử lý. Benchmark lưu cả report, lỗi tiến trình/exit code, thời gian và RAM; watchdog in stack là lựa chọn chẩn đoán riêng, mặc định không tham gia mẫu hiệu năng. Các run có tiến trình kết thúc bất thường trước đó không được tính là mẫu hoàn tất; nguyên nhân native chưa được kết luận chỉ từ stack log.

Package audit phân biệt lỗi `source` với lỗi `saved` theo operand của bằng chứng. Lỗi nguồn không còn bị mô tả thành hỏng artifact. Source IFC không được tự sửa hoặc thay bằng hộp để làm verdict đạt.

## 3. Kết quả Institute

Nguồn: `examples/AC20-Institute-Var-2.ifc`, 10.786.515 byte; SHA-256 `a06b9cf1922cc0a1e200719189054510dd3e1d188292325f66614f7c1fdb37b4`.

| Mẫu | Convert + audit | RSS peak được lấy mẫu | Mapping |
| --- | ---: | ---: | --- |
| Lần gần nhất trước sửa đã ghi trong báo cáo 15 | >300 giây | Không có giá trị hoàn tất hợp lệ | Chưa hoàn tất |
| Bước sửa trung gian, cold | 192,75 giây | Xem result JSON | `REJECTED` |
| Thuật toán đã tối ưu, cold | **143,22 giây** | **397,23 MiB** | `REJECTED` |
| Thuật toán đã tối ưu, warm | **123,55 giây** | **375,43 MiB** | `REJECTED` |

Cold/warm có cùng fingerprint FDS, geometry, inventory, graph MEP, gates và verdict. Warm chỉ dùng lại cache của converter; independent audit vẫn đọc lại IFC và hình học nguồn. Có 149 solid matched, 857 findings trong cả mẫu trung gian và mẫu tối ưu; geometry và geometry-preservation vẫn FAIL. Bốn phần tử có chẩn đoán topology nguồn gồm STEP 22131, 58306, 124264 và 177032; các lỗi giao cắt còn lại có operand và triangle witness trong metrics.

Đây là kết quả chạy cụ thể, không phải SLA hoặc bằng chứng mọi lần chạy đều dưới 300 giây. Đợt lịch sử từng hoàn tất khoảng 129 giây cũng được giữ trong báo cáo 15; không dùng mẫu đó hoặc số >300 để suy ra một hệ số tăng tốc có kiểm soát. Các mẫu thời gian ở đây được ghi trước lần chỉnh nhãn thông báo nguồn/saved; thuật toán hình học tương ứng không thay đổi sau đó.

Bằng chứng: [cold/warm results](../../scripts/out/institute-geometry-fix-v4/results.json), [cold acceptance report](../../scripts/out/institute-geometry-fix-v4/AC20-Institute-Var-2/after/cold/run/acceptance_report.json), [warm acceptance report](../../scripts/out/institute-geometry-fix-v4/AC20-Institute-Var-2/after/warm/run/acceptance_report.json).

Kết quả này xử lý được timeout trong các mẫu đã chạy và cải thiện chẩn đoán. Hình học Institute chưa được nghiệm thu; cần xử lý/kiểm tra lại các family và opening được chỉ ra tại nguồn, hoặc áp dụng quy trình sửa hình học có bằng chứng và phê duyệt riêng.

## 4. IFC MEP/PCCC và đầu ra

Fixture: [mep-fire-geometry.ifc](../../examples/mep-fire-geometry.ifc); mô tả và giới hạn: [mep-fire-geometry.md](../../examples/mep-fire-geometry.md).

| Nội dung | Kết quả |
| --- | --- |
| Hình học vật lý | 8/8 phần tử được đối chiếu và bảo toàn |
| VENTILATION | 4 nguồn, 4 hình học verified, 4 đối tượng FDS |
| FIRE_SUPPRESSION | 4 nguồn, 4 hình học verified, 4 đối tượng FDS |
| Ports | 14; không có port thiếu chủ sở hữu |
| Explicit connections | 6/6 quan hệ nguồn được đối soát |
| Mapping | `MAPPING_VERIFIED` |
| Vận hành thiết bị | `NOT_CONFIGURED` |
| Solver thật | Initialization PASS trên FDS 6.11.1 |
| Hình học hiệu dụng GEOM | `INCONCLUSIVE`; chưa có adapter cut-cell đầy đủ |
| Simulation | `INCONCLUSIVE` |

Tests kiểm tra cả thể tích giải tích và khoảng rỗng trong ống gió. Đầu ra bị dịch vị trí dù manifest đã được tính hash lại phải bị từ chối; graph mất một kết nối cũng phải bị từ chối.

Bộ đầu ra: [FDS](../../scripts/out/mep-geometry-acceptance/mep.fds), [acceptance report](../../scripts/out/mep-geometry-acceptance/mep_acceptance_report.json), [run summary](../../scripts/out/mep-geometry-acceptance/run-summary.json).

Fixture có Body 3D thực nhưng vẫn là dữ liệu kiểm thử tự tạo. Chưa thay thế được nghiệm thu một IFC HVAC/PCCC của công trình thực cùng reference độc lập đã phê duyệt.

## 5. Solver và PyroSim

### 5.1. FDS thật

Ma trận kiểm tra gồm:

| Ca | Initialization | Effective geometry |
| --- | --- | --- |
| OBST một MESH | PASS | PASS |
| GEOM | PASS | INCONCLUSIVE |
| HOLE | PASS | INCONCLUSIVE |
| VENT | PASS | INCONCLUSIVE |
| OBST chia qua hai MESH liền kề, đồng kích thước ô | PASS | PASS |
| GEOM có chỉ số đỉnh không hợp lệ | FAIL như kỳ vọng | INCONCLUSIVE |
| Fixture MEP có 8 GEOM | PASS | INCONCLUSIVE |

Đây là ma trận initialization và hình học hiệu dụng theo phạm vi ghi rõ. PASS initialization không chứng minh vận hành cháy, hội tụ hoặc hiệu quả thông gió/PCCC.

Adapter nhiều MESH xác nhận từng GRID/OBST từ SMV, từng phần vật cản và khoảng hở qua biên MESH. Các bố trí không liền kề, kích thước ô khác nhau hoặc ngoài phạm vi vẫn `INCONCLUSIVE`. Test sửa chỉ số của một MESH và test khe hở bị đóng sau snap đều phải FAIL.

Certificate boundary được ràng buộc thêm với implementation của predicates/metrics/multiple-mesh adapter. Certificate cũ không được dùng để chứng thực implementation đã thay đổi; test real boundary tạo lại chứng cứ phù hợp.

Mã: [effective_multimesh.py](../../ifc_to_fds/modules/verification/application/effective_multimesh.py). Chạy ma trận tái lập bằng `python -m scripts.verify_solver_matrix --solver PATH --output OUTPUT`.

### 5.2. PyroSim

Đã kiểm tra PATH, vị trí cài đặt thông dụng và thông tin đăng ký ứng dụng; chưa tìm thấy executable PyroSim khả dụng. Trạng thái chạy nhập trực tiếp là `BLOCKED: PYROSIM_EXECUTABLE_UNAVAILABLE`.

Đã bổ sung:

- [prepare_pyrosim_acceptance.py](../../scripts/prepare_pyrosim_acceptance.py): chuẩn bị FDS, danh sách đối tượng mong đợi và quy trình lưu diagnostics/PSM/FDS xuất lại.
- [roundtrip.py](../../ifc_to_fds/modules/verification/application/roundtrip.py): kiểm tra inventory, domain/lưới và toàn bộ solid OBST/GEOM trước/sau xuất lại. Đổi ID cần alias một-một và chứng minh hình học tương đương.
- Test mất/thêm solid, đổi domain, dịch hình học, chỉ số GEOM sai và alias không hợp lệ; HOLE/VENT round-trip chưa được gắn PASS.

[Gói chuẩn bị nhập MEP vào PyroSim](../../scripts/out/pyrosim-mep-acceptance/README.md) ghi rõ trạng thái. Đối chiếu round-trip là một gate hình học tĩnh; không được dùng riêng để khẳng định đã chạy GUI hoặc mô phỏng đúng vật lý.

Quy trình nhập tham khảo tài liệu chính thức [PyroSim 2026.1 — Importing FDS Files](https://www.thunderheadeng.com/docs/2026-1/pyrosim/fds-files/import/). Chưa suy đoán cờ CLI nhập file hoặc coi thao tác chuẩn bị gói là import thành công.

## 6. Củng cố tests và retention

### 6.1. Verdict thay cho việc chỉ tạo file

- FZK artifact E2E xác nhận đủ 127 record và report `REJECTED`, các gate hình học/opening tương ứng FAIL, inventory PASS và có finding cho STEP 14502. Không ép fixture có lỗi thành ca PASS.
- Các test MEP mới kiểm tra GlobalId, port, graph, checksum, representation, thể tích, khoảng rỗng và verdict; có negative mutations.
- Kiểm tra round-trip phát hiện hình học sai ngay cả khi có file đầu ra và ID/alias hợp lệ.

### 6.2. Sửa lỗi production được phát hiện qua tests

- Durable retention và RSS lifecycle gọi `JobService.tick()` thật; bỏ bản sao thuật toán bên trong test.
- Startup cleanup dùng thời điểm kết thúc/truy cập thay vì mtime thư mục, giữ job đang hoạt động và artifact vừa được truy cập.
- Không theo symlink/junction ra ngoài root job khi dọn orphan; sweep không xóa nội dung ngoài root được sở hữu.
- Có test production cho durable, expired, active, download, startup cleanup và đường dẫn resolve ra ngoài root.

### 6.3. Chỉnh baseline có kiểm chứng

So sánh FZK xác nhận đúng **28 title** đổi từ `Invalid saved ...` sang `Invalid source ...`; mỗi thay đổi có bằng chứng self-intersection operand `source`. Mọi giá trị baseline khác giữ nguyên. Hai gate bổ sung trước đó vẫn được xử lý theo chính sách parity hiện có.

[diagnostic_changes.json](../../tests/baseline/diagnostic_changes.json) lưu hash trước/sau và từng title/entity. Test riêng phục hồi văn bản trước sửa và kiểm tra hash, để việc chỉnh nhãn không thể kèm thay đổi âm thầm về hình học, verdict hoặc số lượng đối tượng.

## 7. Kiểm chứng cuối cùng

Kiểm chứng cuối: **416 test mặc định PASS**, 14 test được deselect theo cấu hình (9 solver và 5 browser); **9 test solver thật PASS** trong lượt chạy riêng. Không có FAIL/SKIP trong các lượt này. Suite mặc định có 97 warnings và solver có 1 warning, chủ yếu liên quan phép tính mesh không hợp lệ trong các ca lỗi/mutation, cùng cảnh báo thư viện testclient. Không tắt cảnh báo hoặc coi chúng là bằng chứng hình học đạt.

Ruff kiểm tra các file mới đạt. Các log/JUnit nằm tại:

- [Tổng hợp runtime, hash implementation và kết quả](../../scripts/out/geometry-hardening-summary.json).
- [Ma trận solver và expected verdict](../../scripts/out/solver-matrix-expanded/results.json).
- [Python suite](../../.cache/geometry-review/final-tests.xml).
- [Solver thật](../../.cache/geometry-review/solver-final.xml).
- [Log Python](../../.cache/geometry-review/final-tests.log).
- [Log solver](../../.cache/geometry-review/solver-final.log).

Tests trình duyệt không được chạy lại trong đợt sửa backend này; không có thay đổi frontend/worker bundle. Các giới hạn còn lại là nghiệm thu nguồn Institute, dữ liệu MEP công trình thực, adapter hình học hiệu dụng GEOM/HOLE/VENT và GUI PyroSim trực tiếp.
