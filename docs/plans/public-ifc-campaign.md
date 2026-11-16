# Kiểm thử trên IFC công khai

Đợt chạy ngày 2026-11-16 trên `main` `7aed4ea` (ifcopenshell 0.9.0.post1, FDS 6.11.1 ghim hash). Mục đích: tìm lỗi độ bền và lỗi âm thầm của `convert` bằng mô hình không phải của dự án. IFC công khai không nằm trong repo; chỉ có hai script và tài liệu này.

## 1. Chạy lại

```powershell
python -I scripts/public-ifc-fetch.py --root D:\ifc-public            # tải vào thư mục ngoài repo, ghi manifest.json (url, kích thước, sha256, giấy phép)
python -I scripts/public-ifc-run.py --root D:\ifc-public --runs D:\ifc-runs --max-mb 15
python -I scripts/public-ifc-run.py --root D:\ifc-public --runs D:\ifc-runs --min-mb 15 --max-mb 90 --timeout 1500
```

Dùng đường dẫn **ngắn** cho `--runs` (Windows giới hạn 260 ký tự; pipeline từ chối thư mục đầu ra quá sâu). Chạy tuần tự: mỗi tệp một tiến trình, cache hình học nguội, có hạn thời gian (`--timeout`) và ngưỡng RAM (`--mem-guard-mb`). Kết quả nối vào `results.jsonl` nên chạy dở có thể tiếp tục. Lớp kết quả: `REPORT:<status>`, `REFUSED` (mã thoát 3, lỗi có kiểm soát), `TIMEOUT`, `MEMORY_GUARD`, `TRACEBACK` (ngoại lệ chưa bắt), `EXIT<n>`.

An toàn dữ liệu tải về: mỗi nguồn một thư mục riêng, mọi tệp phải bắt đầu bằng tiêu đề STEP, không chạy hay nạp gì từ tệp tải về, Python chạy với `-I` từ thư mục không chứa dữ liệu.

## 2. Nguồn

| Nguồn | Dùng | Ghi chú |
| --- | --- | --- |
| buildingSMART `Sample-Test-Files` | 29 tệp: `Building-*` và bốn loại hạ tầng ở ba schema (IFC2X3, IFC4, IFC4.3), năm tệp ISO reference view | Không khai giấy phép |
| `bim-whale-ifc-samples` | 6 tệp, từ `SimpleWall` đến `BasicHouse` (50 MB) | MIT |
| `IfcOpenShell/files` | 40 tệp: ca từng gây sập, treo hoặc sai hình học (`segfault`, `infiniteLoop`, `wrong-geometry`) và vài tệp thật | Không có tệp giấy phép |
| `buildingsmart-community` | 9 tệp: Duplex (kiến trúc, MEP), Medical-Dental Clinic (kiến trúc, HVAC), Esplanades, Molio, Schependomlaan, ví dụ IFC4 và IFC4.3 | Lưu bằng Git LFS (lấy qua `media.githubusercontent.com`); không có tệp giấy phép |
| TU Wien, mô hình thử thoát hiểm | 1 tệp 7 MB, IFC4, **có hầm gửi xe ngầm** (6 tầng, tầng hầm −2,89 m) | CC BY 4.0 |
| Open IFC Model Repository (Auckland) | **không dùng được** | Trang đã đổi giao diện; mọi liên kết `/_models/` cũ trả về trang HTML 351 byte |
| ISPRS-EuroSDR GeoBIM (Savigliano) | không dùng được | Tệp có hạn chế truy cập, không tìm thấy liên kết tải trực tiếp |
| ITC-KUL-CONSTRUCTOR (hầm gửi xe dưới ba tòa chung cư) | không dùng được | Trang tải ghi "TO BE RELEASED" |

## 3. Kết quả

85 tệp, 393 MB (đợt 1: dưới 15 MB, 78 tệp; đợt 2: từ 15 MB, 7 tệp).

| Kết quả | Số tệp |
| --- | ---: |
| `REPORT:MAPPING_VERIFIED` | 9 |
| `REPORT:INCONCLUSIVE` | 11 |
| `REPORT:REJECTED` | 16 |
| `REFUSED` (lỗi có kiểm soát) | 48 |
| `TIMEOUT` | 1 |
| `TRACEBACK`, `MEMORY_GUARD` | 0 |

Không có tiến trình sập hay ngoại lệ chưa bắt. 48 tệp bị từ chối có kiểm soát, theo lý do:

| Lý do từ chối | Số tệp | Đánh giá |
| --- | ---: | --- |
| Property set hoặc quantity set không có tên (`property_sets.None`) | 26 | **Lỗi, đã sửa** (F1) |
| Nhiều `IfcSite` (chính sách: phải chọn `--storey` hoặc `--bbox`) | 18 | Chính sách có chủ đích; xem F4 |
| Hạn mức số ô lưới (mô hình hạ tầng dài hàng km; một ca là lỗi đơn vị, F2) | 2 | Đúng, trừ ca F2 |
| Không có hoặc nhiều `LENGTHUNIT` ở dự án | 2 | Đúng: pipeline không giả định mét |

Theo schema:

| Schema | Số tệp | Có báo cáo (đạt, chưa kết luận, bị loại) | Bị từ chối | Treo |
| --- | ---: | --- | ---: | ---: |
| IFC2X3 | 56 | 29 (7, 9, 13) | 26 | 1 |
| IFC4 | 20 | 7 (2, 2, 3) | 13 | 0 |
| IFC4.3 | 9 | 0 | 9 (nhiều `IfcSite` ở 8 tệp, hạn mức số ô ở 1 tệp) | 0 |

Chưa có mô hình IFC4.3 nào chạy tới báo cáo, nhưng cả chín lần từ chối đều do chính sách đã biết, không do schema.

Chậm nhưng hoàn tất: `geometrygym_great_court_roof` (3,6 MB, mái BRep phức tạp) 730 s; hầm TU Wien (7 MB) 572 s; `1807_EP_AR_v18` 400 s (1,1 GB); `Molio` 388 s (2,4 GB); `Schependomlaan` 335 s (1,6 GB); `Clinic_Architectural` 334 s; `Clinic_HVAC` 279 s; `BasicHouse` (50 MB) 155 s và **3,0 GB RAM**; `IfcReinforcingBar` (0,7 MB) 96 s và 1 GB.

## 4. Phát hiện

| ID | Mức | Nội dung | Trạng thái |
| --- | --- | --- | --- |
| F1 | P2 | Một `IfcElementQuantity` hoặc `IfcPropertySet` có `Name = $` (hợp lệ theo schema) làm `ifcopenshell.util.element.get_psets` trả khóa `None`; pydantic từ chối và cả mô hình bị dừng (26 tệp). | Đã sửa: #151 |
| F2 | P1 | Tệp ISO `wall-with-opening-and-window` (IFC4) khai milimét nhưng mã native của IfcOpenShell trả tỷ lệ 1,0 (cả hai chế độ `convert-back-units`). Pipeline giả định mét nên tường 3.000 mm thành 3.000 m, và với ô lớn vẫn ra `MAPPING_VERIFIED` ở tỷ lệ sai gấp 1.000 lần. Quét 78 tệp: chỉ một ca lệch, 70 ca nhất quán (mm, m, inch, foot). | Đã sửa bằng chốt từ chối khi tỷ lệ native khác tỷ lệ khai báo (lệch quá 5%): #151 |
| F3 | P3 | `337--buildingElementProxy--wrong-geometry--accept-errors.ifc` (3,5 MB) treo hơn 900 s trong `iterator.initialize()` của IfcOpenShell (đơn luồng hay đa luồng đều treo, RAM thấp); `456--wall--infiniteLoop--augmented.ifc` kẹt cùng chỗ (quá 120 s) và `673--flowController--segfault--augmented.ifc` quá 120 s bên trong vòng lặp iterator (chưa biết có hoàn tất). Hai tệp sau chỉ lộ ra sau khi sửa F1, vì trước đó bị dừng sớm. Lời gọi native **giữ GIL** (thử luồng nhịp tim: không chạy), nên luồng giám sát bằng Python không ngắt được. | **Chưa sửa.** Job phía server vẫn bị chặn bởi `IFCFDS_TIMEOUT_S`; CLI không có giới hạn. Hướng khả dĩ: trích hình học trong tiến trình con có hạn thời gian cho từng khối (tốn công, ảnh hưởng hiệu năng) |
| F4 | Chính sách | Quy tắc nhiều `IfcSite` chặn cả các tệp một tầng (2 `IfcSite`, 1 tầng) như `Building-Architecture` IFC4 và IFC4.3, trong khi bản IFC2X3 của cùng mô hình được nhận. Thông báo nói "nhiều hệ cao độ trộn", không đúng với mô hình một tầng. | Chưa đổi; cần quyết định. Vượt qua được bằng `--storey` kèm `--domain` |
| F5 | Quan sát | Cửa đi và cửa sổ thường là vỏ hở hoặc tự giao cắt khi xuất từ công cụ tạo mô hình: hầm TU Wien có 73/73 cửa đi hở 8 cạnh và 18 cửa sổ tự giao cắt; mô hình A cũng vậy (21 cửa). Trên 31 báo cáo công khai: `IfcWindow` 299 `UNSUPPORTED` và 19 `DEVIATED`, `IfcDoor` 94, `IfcBuildingElementProxy` 192, `IfcFurnishingElement` 104. | Hành vi đúng theo thiết kế (không tự sinh hình học); cần chính sách cho cửa trong thực tế |
| F6 | Quan sát | Hầm TU Wien: `REJECTED`; `passage_resolution` `FAIL` với 2.327 vật rắn mỏng (3.154 `IfcBuildingElementPart` là các lớp cấu tạo), `effective_geometry` `FAIL` ("danh mục vật cản của solver khác đầu vào"). Chưa phân tích xem đó là sai khác thật hay báo động giả như ca C đã sửa ở A4.15. | Chưa phân tích |
| F8 | Thấp | Nếu thư mục tạm dùng tiền tố đường dẫn dài `\?\` thì `offline_backup.py:38` đổi qua `as_uri()` và SQLite báo `invalid uri authority: %3F`; năm test sao lưu và khôi phục hỏng trong môi trường đó (Codex gặp trong sandbox của nó). Đường dẫn Windows thường không bị. | Chưa sửa |
| F7 | Hiệu năng | Thời gian và RAM không tỷ lệ theo kích thước tệp: mái BRep, mô hình nhiều lớp cấu tạo, thanh cốt thép. `BasicHouse` dùng 3 GB. | Ghi nhận cho M1.7 |

Sau khi sửa F1 và F2 (#151), chạy lại các tệp bị ảnh hưởng: nhóm `IfcOpenShell/files` (40 tệp, hạn 120 s) có 32 tệp ra báo cáo (14 `MAPPING_VERIFIED`, 15 `REJECTED`, 3 `INCONCLUSIVE`), 4 tệp bị từ chối vì chính sách và 4 tệp quá hạn (các ca F3 cùng `geometrygym_great_court_roof`, vốn cần khoảng 730 s); tệp ISO sai tỷ lệ bị từ chối với `declared scale=0.001, native applied scale=1`.

## 5. Giới hạn

- Chỉ chạy profile mặc định (`mapping`), không `--storey`, `--domain` hay quyết định đã duyệt; nên phần lớn kết quả `REJECTED` và `INCONCLUSIVE` phản ánh lỗi nguồn và chính sách chứ không phải lỗi chuyển đổi.
- Số liệu thời gian là một lượt mỗi tệp, không có đối chứng cùng phiên.
- Một số tệp lớn của danh mục BIMData (hàng trăm MB, hoặc đóng gói trong tệp zip) chưa thử.
- Các ca `IfcOpenShell/files` mang tên `segfault` không làm sập tiến trình nào trên ifcopenshell 0.9.0.post1; chỉ một ca treo (F3).
