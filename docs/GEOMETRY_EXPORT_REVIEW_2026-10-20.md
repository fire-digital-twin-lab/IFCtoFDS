# Phân tích hình học nguồn và luồng xuất FDS — 20/10/2026

## Kết quả chính

Luồng xuất đã tạo được tệp FDS cho cả tầng 7 và hầm. Hai tệp mới đều được FDS 6.11.1 đọc và khởi tạo thành công ở `T_END=0`, mã thoát 0, có tệp Smokeview. Trạng thái kiểm định toàn mô hình vẫn là `REJECTED`: tầng 7 có 14 phần tử giao bề mặt; hầm có 22 phần tử không đáp ứng yêu cầu khối kín. Việc phần mềm xuất được tệp, FDS khởi tạo được và hình học được chấp nhận là ba kết quả riêng, nay được thể hiện rõ trên UI.

Đã sửa mã trực tiếp trên working tree hiện tại và giữ các sửa đổi có sẵn. Không sửa IFC nguồn, không commit hoặc push. Chưa kiểm tra thao tác import trực tiếp bằng giao diện PyroSim trong môi trường này.

## Dữ liệu và cách xác minh

| Nguồn | Kích thước | SHA-256 |
| --- | ---: | --- |
| Tang7.ifc | 902.871 byte | `df856013a2b3d91d4d53549f8dc496439f910e6e5f4503fbf9e47af2277377f3` |
| Ham2Tang.ifc | 32.655.047 byte | `3fe9482cd52d1c57b53a405903d4700180e1d10b332d5a127f9deb47d16d013a` |

Trích xuất bằng IfcOpenShell 0.9.0.post1/OpenCASCADE, đơn vị đầu ra mét, độ lệch tuyến tính 0,1 mm. Cả hai IFC khai báo đơn vị millimet và precision của context tương đương `1e-5 m`. Kiểm tra topology trên lưới gốc; tách thành phần với `repair=False`. Với các mẫu điều tra sâu, dựng lại ở cả tọa độ thế giới và tọa độ cục bộ. Kiểm định đầu ra mở lại IFC độc lập, không sử dụng cache hình học của converter.

Các kết quả đo đang nằm trong `.cache/deep-geometry/`, `.cache/deep-final-tang7/`, `.cache/deep-final-ham/` và `.cache/deep-solver/`. Các tệp này là bằng chứng cục bộ, không đưa IFC hay payload hình học riêng tư vào git.

## Nguyên nhân hình học ở hầm

793 IfcProduct đã được kiểm kê. Có 21 cửa thuộc hai họ `LNG_CuaThep_2Canh:1200x2200` và `LNG_CuaThep_1Canh:900X2200`, sử dụng sáu representation map. Body của chúng trỏ tới `SurfaceModel` chứa `IfcFaceBasedSurfaceModel`.

| Representation map STEP | Số cửa bị ảnh hưởng | Cạnh hở / cửa | Cạnh non-manifold / cửa |
| --- | ---: | ---: | ---: |
| 186818 | 5 | 3.814 | 21 |
| 329600 | 11 | 3.826 | 9 |
| 345514 | 1 | 389 | 3 |
| 371363 | 2 | 389 | 3 |
| 387267 | 1 | 385 | 2 |
| 402959 | 1 | 385 | 2 |

Mẫu cửa STEP 186833 có 23.672 đỉnh, 45.071 tam giác. Các cạnh hở và non-manifold vẫn tồn tại khi bỏ phép đặt vào tọa độ thế giới. Đây là vấn đề của biểu diễn mặt xuất từ họ cửa đối với yêu cầu khối kín; rebasing hoặc tăng độ chính xác ghi số không thể đóng các mặt này.

Các STEP cửa cần kiểm tra:

`186833, 186846, 329610, 329621, 329632, 329643, 345524, 355459, 355470, 355481, 355492, 355503, 355514, 355525, 355536, 355547, 355558, 371373, 371384, 387277, 402969`.

Phần tử còn lại là **IfcWall STEP 28948**, tên `Basic Wall:T_15_TRÁT TRONG:435851`. Body STEP 28947 là SurfaceModel chứa IfcFaceBasedSurfaceModel STEP 28945. Lưới có 51 đỉnh, 88 tam giác, 26 cạnh hở, một cạnh non-manifold và 26 cạnh sai hướng. Đây là tường, không phải sàn.

`SurfaceModel` là một dạng biểu diễn IFC; tên loại này tự nó không chứng minh tệp IFC hỏng. Kết quả topology ở trên mới chứng minh rằng các mesh cụ thể chưa đáp ứng yêu cầu khối đặc của pipeline. Tích phân thể tích trên mặt hở không được dùng làm thể tích vật lý.

Trước sửa, converter tự thay cửa/window không kín bằng hộp bao. Cách này có thể lấp phần rỗng hoặc tạo vật cản khác nguồn, trong khi auditor đọc lại hình học gốc và từ chối. Đã bỏ thay thế ngầm: giữ nguyên mesh để chẩn đoán, đánh dấu FAILED và ghi rõ phần tử không có ánh xạ khối hợp lệ. Cache converter đổi revision để không đọc lại hộp xấp xỉ từ lần chạy cũ.

## Nguyên nhân ở tầng 7

14 STEP có phát hiện giao bề mặt:

`1654, 3785, 4427, 5058, 6069, 7211, 8193, 12423, 13406, 8271, 8336, 8348, 8412, 8477`.

Các mẫu điều tra sâu đều có topology kín, nhưng gồm nhiều thành phần. Khối kín và không tự giao là hai điều kiện khác nhau.

| Mẫu | Topology | Bằng chứng điều tra sâu |
| --- | --- | --- |
| IfcDoor 1654 | 15 thành phần kín | Có giao thể tích giữa các thành phần; một cặp khoảng `0,000901 m³`. Ở tọa độ cục bộ, tam giác 6 và 532 chồng mặt với diện tích chiếu khoảng `0,0244125 m²`. |
| IfcWindow 8271 | 5 thành phần kín | Cặp tam giác giao: 0/97 ở thế giới, 2/97 ở cục bộ. Boolean từng cặp không tìm thấy giao thể tích dương trong lần đo; cần xem tiếp xúc mặt và cạnh, không quy ngay thành chồng lấn khối lớn. |
| IfcWindow 8477 | 5 thành phần kín | Cặp tam giác giao: 0/68 ở thế giới, 0/70 ở cục bộ. Giá trị giao thể tích khoảng `1,38e-25 m³` không đủ cơ sở để mô tả chồng lấn vật lý đáng kể. |

Một số tọa độ tại vùng tiếp xúc khác nhau khoảng `3,55e-15 m`, nhỏ hơn nhiều precision khai báo của IFC. Đồng thời, phát hiện vẫn xuất hiện trước phép đặt thế giới. Vì vậy, cần phân biệt giao thể tích thực của cụm cửa với tiếp xúc mặt/cạnh và sai số số học trong cụm cửa sổ. Chưa có cơ sở cho phép làm sạch tất cả bằng một ngưỡng chung.

Đã thêm witness gồm loại giao, chỉ số cặp tam giác hoặc thành phần, diện tích/thể tích nếu có. Báo cáo lưu bằng chứng trong `metrics[entity_key].self_intersection` và `preserved:*`, giữ tiêu đề finding ổn định. Không giảm ngưỡng chấp nhận để đổi FAIL thành PASS. Các khối tiếp xúc/chồng nhau cần được xử lý ở họ nguồn hoặc theo một chính sách hợp nhất hình học được kiểm chứng riêng.

## Rà soát và sửa từng chức năng

| Chức năng / tệp | Lỗi tìm thấy | Đã sửa |
| --- | --- | --- |
| Inventory — `core/inventory.py`, `domain/bim/model.py` | Thiếu provenance của Body và mapped representation trong chẩn đoán | Lưu STEP representation/map, kiểu item, số item; thêm diagnostics topology theo phần tử. |
| Trích xuất — `geometry/engine.py` | Thay cửa không kín bằng hộp bao ngầm | Giữ mesh gốc, báo FAILED và chất lượng mesh; áp dụng cùng nguyên tắc cho reader độc lập. |
| Cache — `geometry/cache.py` | Có thể dùng lại hình học theo quy tắc sửa cũ | Đổi revision và giữ diagnostics khi cache hit. |
| Tách mesh — `geometry/mesh.py`, `validation/metrics.py`, `checkers/air_path.py` | Trimesh split mặc định có bước vá lỗ và có thể phụ thuộc networkx | Tất cả các bước kiểm định này dùng `repair=False`; kiểm thử cấm gọi fill_holes. |
| Tự giao — `geometry/mesh.py`, `validation/metrics.py`, `geometry/package.py` | Chỉ trả thông báo chung, không có cặp tam giác | Ghi witness có cấu trúc; giữ ba trạng thái CLEAN/CONFIRMED/UNCERTAIN; bảo vệ dữ liệu cache khỏi sửa qua tham chiếu lồng nhau. |
| Báo cáo — `validation/engine.py` | Số matched bằng 0 dễ bị hiểu thành không xuất được FDS | Thêm số entity/primitive/OBST/GEOM đã ghi, số được kiểm chứng và cờ dừng do nguồn. |
| Tải FDS — `js/app-controller.js`, `js/ui/audit-drawer.js` | Handler ưu tiên FDS trong bộ nhớ của lần cũ, bỏ qua href checkpoint | Drawer tải theo href hiện tại; xóa liên kết và kết quả cũ khi chạy lại. |
| Xác thực tải tệp — `js/ui/audit-drawer.js` | Anchor tải trực tiếp không gửi x-api-key | Fetch các endpoint API với auth header, tải blob, thông báo lỗi HTTP ngay trên UI. |
| Gói hình học — `js/ui/audit-drawer.js` | Tải JSON nhưng đặt tên ZIP | Dùng artifact `geometry_archive`; checkpoint chỉ có index được ghi rõ là JSON. |
| Hiển thị kiểm định — `js/ui/audit-drawer.js` | Màu FAIL và lý do cũ có thể còn sau lần render mới; URL bị ghép vào HTML | Đặt lại màu/lý do; tạo liên kết báo cáo bằng DOM; FDS bị từ chối có nhãn và tên `diagnostic_unaccepted`. |
| Scenario — `scenario-store.js`, controller | Hash rỗng hoặc đổi status có thể bật trạng thái nền hợp lệ; chạy lại còn nền cũ | Kiểm tra cờ nền đã verified và hash; vô hiệu nền lúc chạy lại, giữ hash trước đó để phát hiện STALE khi bundle đổi. |
| Lưu kết quả — `adapters/storage/filesystem.py` | Backup lỗi có thể dẫn đến xóa payload gốc; rollback lỗi vẫn xóa backup | Chỉ hoàn tác phần đã thay đổi; giữ nguyên đích khi backup chưa xong; giữ backup có đường dẫn phục hồi nếu rollback thất bại. |
| CLI — `cli.py` | Workspace tạm mặc định phụ thuộc thư mục hệ thống; nguy cơ ghi checkpoint model.fds vào nơi không mong muốn | Dựng checkpoint trong thư mục công việc riêng cạnh đích và xuất bộ kết quả bằng repository. |
| Benchmark — `benchmark_real_ham2tang_improved.py` | Mô tả còn khẳng định chữa cửa bằng hộp; RSS delta bị gọi là peak; xóa output cũ | Cập nhật đúng trạng thái; tên chỉ số RSS đúng; tạo thư mục theo từng lượt; khởi tạo solver một thread, ghi riêng mapping acceptance. |

Các sửa UI khôi phục Focus/Back, Hide/Show, Isolate/Unisolate, Undo/Show all; hủy tác vụ; worker đọc FDS; cú pháp GEOM Legacy, precision và ID tương thích Windows đã được kiểm tra lại. Chi tiết ở [báo cáo UI trước đó](UI_LOGIC_REVIEW_2026-10-20.md).

## Kết quả chạy toàn luồng

| Chỉ số | Tầng 7 | Hầm |
| --- | ---: | ---: |
| IfcProduct | 279 | 793 |
| GEOM ghi vào FDS | 218 | 546 |
| OBST | 0 | 0 |
| Phần tử đạt so sánh độc lập | 204 | 0 — dừng preflight |
| Phát hiện | 28 — gồm hai bước kiểm tra của 14 phần tử | 23 — gồm 22 topology và một structural completeness |
| Kích thước FDS | 590.943 byte | 10.072.572 byte |
| Cú pháp / truy vết / kiểm kê nguồn / domain | PASS | PASS |
| Geometry | FAIL | FAIL |
| Acceptance | REJECTED | REJECTED |
| Khởi tạo FDS 6.11.1, T_END=0 | exit 0, khoảng 3,73 giây | exit 0, khoảng 3,95 giây |

Hầm có `fail_fast_on_source_errors=true`: 22 mesh nguồn không hợp lệ làm dừng các phép so sánh solid còn lại, openings và air path. Vì vậy matched=0 thể hiện chưa kiểm chứng các khối đã ghi. Trong FDS có đủ 546 primitive đã được phép ánh xạ; 22 phần tử lỗi được ghi trong inventory/manifest/report để xử lý.

Lượt tầng 7 hoàn tất khoảng 33,42 giây. Lượt hầm đầu tiên sau khi đổi revision cache hoàn tất khoảng 285,10 giây: chuẩn bị 131,31 giây, đọc nguồn độc lập 123,35 giây, validation 18,28 giây. Đây là lượt có dựng lại cache và chạy cùng các tác vụ kiểm thử; không dùng để so sánh trực tiếp với số đo warm-cache 162,44 giây ở báo cáo trước. Nút thắt còn lại chủ yếu là dựng hình học nguồn chi tiết hai lần để giữ tính độc lập của kiểm định.

Khởi tạo FDS ở T_END=0 xác nhận khả năng đọc và setup tệp đã sinh. Đánh giá mô phỏng cháy, vật liệu, thông gió và bảo toàn hình học toàn bộ cần các gate tương ứng đạt yêu cầu. Các tệp có nhãn diagnostic/unaccepted giữ nguyên trạng thái đó.

## Kiểm thử

- 303 ca Python đạt trong lượt chính; một ca CLI bổ sung chạy riêng đạt; 6 ca vòng đời tác vụ đạt; 2 ca solver thực đạt: tổng 312 ca khác nhau. Bộ snapshot baseline giữ nguyên; không cập nhật snapshot để che thay đổi kết quả.
- 12 bộ kiểm thử JavaScript đạt, gồm kiểm thử mới thực thi handler tải artifact có auth, checkpoint đúng job, kiểu ZIP/JSON, lỗi HTTP và xóa liên kết cũ. Đã chạy lại nhóm scenario, inspector và tải tệp sau những thay đổi cuối.
- Sau bổ sung evidence cho geometry package, chạy lại 23 ca storage/geometry/baseline: đạt.
- `git diff --check`, kiểm tra cú pháp JavaScript và CLI help đạt.
- Các cảnh báo Trimesh về mass properties khi boolean tạo giao rỗng và deprecation của Starlette còn xuất hiện; chúng không được đổi thành kết quả PASS bằng cơ chế fallback.
- Nhóm HTTP qua TestClient và kiểm thử trình duyệt thật chưa hoàn tất trong sandbox: vòng lặp Windows/socket và khởi chạy browser bị hạn chế như đã ghi ở báo cáo UI. Các handler JavaScript được kiểm tra bằng Node; chưa xác nhận thao tác GUI PyroSim.

JUnit và kết quả kiểm thử: `.cache/pytest-deep-green.xml`, `.cache/pytest-deep-jobs.xml`, `.cache/pytest-deep-solver.xml`, `.cache/pytest-deep-package-check.xml`, `.cache/pytest-deep-final-targeted.xml`, `.cache/deep-js-results.json`.

## Dọn tệp

Đã xác minh 20 mục sinh ra tạm thời: năm bản preview lặp, 12 thư mục làm việc pytest cũ và ba hồ sơ profiler. Tổng 8.165 tệp, 148.337.263 byte, khoảng 141,47 MiB. Danh sách đầy đủ ở `.cache/cleanup-log.json`.

**Chưa xóa:** hệ thống phê duyệt tự động từ chối lệnh xóa thư mục; môi trường không cho yêu cầu cấp quyền sandbox. Đã chuẩn bị [script dọn theo danh sách cố định](../scripts/clean-transient-review.ps1). Script kiểm tra đường dẫn nằm trong `.cache` và từ chối liên kết filesystem. Mặc định chỉ liệt kê; chạy với `-Apply` mới xóa:

```powershell
.\scripts\clean-transient-review.ps1
.\scripts\clean-transient-review.ps1 -Apply
```

Giữ IFC, reference cases, dependency, test suite, cache đang dùng và bằng chứng kết quả mới. Chưa có bằng chứng đủ để xóa tệp mã nguồn đang được tham chiếu; không xóa mã chỉ vì tên giống tệp thử nghiệm.

## Các phần nguồn cần xử lý tiếp

1. Sửa sáu representation map của hai họ cửa thép; xuất Body dưới dạng khối kín và có hướng mặt nhất quán. Kiểm tra cả panel, khung và chi tiết phụ; một chi tiết mặt hở có thể làm cả mesh tổ hợp không đạt.
2. Sửa tường STEP 28948 bằng solid có bề dày theo thiết kế. Giữ quan hệ opening và kiểm tra hình học sau phép trừ lỗ.
3. Kiểm tra cụm cửa tầng 7, xử lý các phần giao hoặc chồng mặt trong họ nguồn. Với window, phân biệt tiếp xúc dự kiến và sai lệch nhỏ trước khi quyết định hợp nhất; thay thế phải có căn cứ về khối chiếm chỗ và lỗ mở.
4. Chạy lại công cụ kiểm tra từng STEP, sau đó Verified Conversion. Một quyết định loại trừ hoặc thay thế hình học cần được ghi rõ trong cấu hình và kiểm định lại.

Công cụ có thể dùng lại:

```powershell
.\.venv\Scripts\python.exe scripts/inspect-source-geometry.py `
  ..\Resources\Ham2tang\Ham2Tang.ifc --step 186833 --step 28948 `
  --output .cache/ham-selected-geometry.json

.\.venv\Scripts\python.exe scripts/inspect-source-geometry.py `
  ..\Resources\Tang7\Tang7.ifc --step 1654 --step 8271 --step 8477 `
  --output .cache/tang7-selected-geometry.json
```

Tham chiếu API: [thiết lập hình học IfcOpenShell](https://docs.ifcopenshell.org/ifcopenshell/geometry_settings.html), [Trimesh split/repair](https://trimesh.org/trimesh.graph.html), [tài liệu chính thức FDS](https://pages.nist.gov/fds/manuals.html). Các số liệu và nhận định theo từng STEP trong báo cáo này dựa trên kiểm tra cục bộ.
