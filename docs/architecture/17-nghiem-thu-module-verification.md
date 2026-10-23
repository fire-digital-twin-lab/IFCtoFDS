# Hoàn thiện kiểm chứng ánh xạ và bàn giao PyroSim

> Đính chính sau review commit `5d715a7`: kết quả cục bộ trong tài liệu này không chứng minh CI đạt. CI Ubuntu được review có 485 test đạt và hai lỗi checksum. Bốn phát hiện về khe biên, dung sai, tam giác–SURF và checksum cùng kết quả sửa được ghi tại [báo cáo 18](18-sua-loi-review-verification.md). Nghiệm thu toàn module vẫn chưa hoàn tất.

Ngày cập nhật: 23/10/2026. Nhánh `chore/research-acceptance-hardening`, HEAD nền `f0c6d9c02342312266f2cfb8f9102833640061c3`. Các thay đổi nằm trong working tree, chưa commit/push. Tài liệu này tiếp nối [báo cáo 16](16-ket-qua-sua-hinh-hoc-va-kiem-chung.md).

## 1. Phạm vi và điều kiện kết thúc

Module Verification kiểm tra độc lập IFC nguồn, FDS đã ghi, dữ liệu hình học thực do solver xuất và bằng chứng bàn giao qua editor. Hoàn thành một phần kiểm chứng không tự động hoàn thành các phần khác.

| Kết luận | Điều kiện |
| --- | --- |
| `MAPPING_VERIFIED` | Các gate ánh xạ bắt buộc đạt sau khi đọc lại IFC và artifacts. |
| `handoff: PASS` | Syntax, ánh xạ, setup, chạy có bước thời gian, đối chiếu bản xuất lại, chạy bản xuất lại và bằng chứng nhập editor được review đều đạt. |
| `verification: PASS` | Đạt handoff và hình học hiệu dụng của cả bản gốc lẫn bản xuất lại. |
| Mô phỏng cháy | Không được chứng nhận từ những kết luận trên; vẫn `NOT_VERIFIED`/`INCONCLUSIVE`. |

Gate còn thiếu, chưa hỗ trợ hoặc không chạy phải xuất hiện trong `requirements` và `pending`. Lỗi có ưu tiên cao hơn trạng thái thiếu GUI. `--require-ready` trả mã 1 khi có lỗi, 2 khi thiếu bằng chứng và 0 khi verification trong phạm vi tĩnh đã đạt. Chạy công cụ chuẩn bị gói mà không yêu cầu `--require-ready` có thể trả 0 khi chuẩn bị thành công; phải đọc verdict trong report.

## 2. Hai lỗi thực tế đã sửa

### Lưới 3D chỉ có một/hai ô theo một chiều

Mẫu MEP trước sửa có `IJK=15,12,2`. Setup `T_END=0` đạt, nhưng khi chạy `T_END>0`, FDS báo `ERROR(426): MESH 1 Poisson initialization error: 1`.

Serializer hiện sinh tối thiểu ba ô theo mỗi chiều của lưới Cartesian 3D. Chỉ tinh chỉnh lưới; không đổi domain, vertices, faces hoặc IFC. Mẫu MEP thành `IJK=15,12,3`. Đây là điều kiện chạy tối thiểu của phạm vi exporter hiện tại, không phải chứng minh độ hội tụ hoặc lưới đủ mịn cho cháy/sprinkler/ống mỏng. Không áp dụng quy tắc này như một đặc tả cho mọi mô hình FDS 2D.

### Nhận nhầm sai số số học thành lỗi nghiêm trọng

Biểu thức cũ bắt mọi chuỗi `ERROR:`, nên nhận nhầm các dòng `Maximum Pressure Error` và `Maximum Velocity Error` trong log chạy thành lỗi. Bộ đọc mới chỉ nhận dạng các dòng chẩn đoán nghiêm trọng theo định dạng FDS, vẫn ưu tiên lỗi thực và exit code khác 0.

Bộ đọc completion phân biệt `SETUP_ONLY`/`TRANSIENT`; chạy transient phải có bước thời gian dương, log kết thúc bình thường và thời gian quan sát đạt yêu cầu. Dòng “completed successfully” đơn lẻ không đủ. Dung sai 0,000005 giây chỉ dùng cho độ làm tròn năm chữ số của log FDS 6.11.1, không phải dung sai vật lý hay hình học.

Các reproducer và log cũ ở [module1](../../.cache/module1); lỗi setup thực ở [module1-probe](../../scripts/out/module1-probe). Không thay dữ liệu nguồn để làm test đạt.

## 3. Các adapter kiểm chứng đã bổ sung

### 3.1. OBST/HOLE và cửa biên OPEN

[effective_openings.py](../../ifc_to_fds/modules/verification/application/effective_openings.py) đọc grid và chỉ số nguyên trong SMV do FDS tạo. Không dùng bảng tọa độ hiển thị chưa snap làm bằng chứng hình học hiệu dụng.

- So sánh mặt nạ ô vật rắn theo từng OBST nguồn sau phép trừ HOLE với toàn bộ fragment của đối tượng trong SMV.
- Phát hiện phần lỗ mở bị solver đóng, ô rắn thêm/mất và sai danh tính, kể cả khi một OBST bị chia thành nhiều fragment có cùng ID.
- Giữ riêng trường hợp baffle có độ dày bằng 0 trong miền; chỉ cho phép remnant trên mặt biên sẵn có trong phạm vi được kiểm chứng.
- Đối chiếu `VENTORIG`, ordinal và bảng VENT, gán bề mặt OPEN, footprint ô hiệu dụng và vùng ô kề thông thoáng.
- Ghi số thành phần không khí liên thông sáu hướng, số ô thoáng/bị chắn tại mỗi HOLE. Không suy ra lưu lượng hoặc chủ đích thông gió từ các số này.
- Giới hạn tài nguyên cho tổng mặt nạ theo từng đối tượng; vượt ngân sách trả `INCONCLUSIVE`.

Phạm vi: một lưới Cartesian đều; OBST/HOLE thẳng hàng rõ ràng với lưới; cửa OPEN phẳng trên biên ngoài và không bị vật rắn che. Lưới không đều, bounds không thẳng hàng, nhiều MESH có HOLE/VENT, cửa trong miền hoặc patch bị che cần bằng chứng riêng. Những trường hợp đó không được gắn PASS theo suy đoán. Adapter OBST nhiều MESH liền kề trước đây vẫn giữ phạm vi riêng.

### 3.2. GEOM thực được solver đọc và ghi

[bingeom.py](../../ifc_to_fds/modules/verification/infrastructure/fds/bingeom.py) đọc BINGEOM little-endian của FDS 6.11.1, kiểm tra Fortran record markers, lengths, counts, tọa độ hữu hạn và chỉ số vertices/faces/surfaces. Không hỗ trợ terrain hay thể tích tetrahedron trong adapter này.

[solver_surface.py](../../ifc_to_fds/modules/verification/application/solver_surface.py) đối chiếu đủ inventory GEOM → BINGEOM, hình học toàn solid và gán bề mặt theo face. Thiếu/thừa/đổi tên file hoặc sửa tọa độ/chỉ số phải bị phát hiện. Evidence có SHA-256 từng binary, primitive ID, metric và phạm vi `SOLVER_STATIC_GEOM_SURFACES_ONLY`.

**BINGEOM chứng minh bề mặt GEOM do solver phát ra; chưa chứng minh thể tích ô cắt và topology đường khí sau khi xây cut-cells.** Vì vậy `solver_surface_geometry: PASS` không nâng `effective_geometry` của GEOM thành PASS. Mẫu MEP có thể giữ đủ tám solid và chạy có bước thời gian, trong khi verification toàn phần vẫn chưa đủ bằng chứng.

Nguồn định dạng: [FDS-6.11.1 geom.f90](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/geom.f90), phần `READ_GEOM`/`WRITE_GEOM`; [dump.f90](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/dump.f90), bảng `SURFACE`, `OBST`, `VENTORIG`, `VENT`. Các fixture native được giữ tại [tests/fixtures/solver/fds-6.11.1](../../tests/fixtures/solver/fds-6.11.1/provenance.json) cùng hash nguồn đầu ra để tái kiểm tra.

### 3.3. Đối chiếu sau khi xuất lại từ PyroSim

- Giữ inventory và alias một-một; alias vẫn phải qua chứng minh hình học.
- Kiểm tra domain/lưới, solid toàn phần, HOLE/VENT trong subset tĩnh, định nghĩa/gán bề mặt.
- Chặn GEOM có surface index không hợp lệ. Khi GEOM nhiều bề mặt bị đổi thứ tự/triangulation, giữ `INCONCLUSIVE` nếu chưa chứng minh được tương ứng face–surface.
- Chạy lại solver trên file xuất lại. Nếu file vẫn setup-only, tạo ca chạy ngắn riêng để chứng minh tiến thời gian.

## 4. Bằng chứng editor và tính toàn vẹn

`--import-evidence` nhận chứng nhận của người review kèm phiên bản PyroSim, thời gian có múi giờ, kết quả nhập, nhận xét cảnh báo và hash của FDS gốc/FDS xuất lại/PSM/diagnostics. Các file bằng chứng phải có nội dung, hash phải khớp. Đây là **chứng nhận thủ công có ràng buộc artifacts**, không phải robot đã quan sát GUI. Report luôn giữ `gui_automated=false`; tài liệu đầu vào không được đổi nó thành true.

Công cụ giữ riêng bytes đầu vào để ràng buộc các phép kiểm tra. Không cho thư mục đầu ra ghi đè IFC, FDS gốc, bản xuất lại hoặc các file bằng chứng đã được cung cấp. Tạo `*_cold.fds` chỉ đổi `TIME.T_END`; không thêm lửa, quạt, đầu phun hoặc sửa hình học. Ca chạy có hash/derivation riêng và không thay thế FDS mapping đã nghiệm thu.

## 5. Cách tái lập và bàn giao

Chạy từ root repository, bằng Python trong `.venv`. Ví dụ dưới đây dùng fixture tự tạo, không phải IFC của công trình thực.

```powershell
$solver = (Resolve-Path '.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe').Path
.\.venv\Scripts\python.exe -m scripts.prepare_pyrosim_acceptance `
  scripts/out/verification-completion/mep/mep.fds `
  --output scripts/out/verification-completion/mep/pyrosim `
  --ifc examples/mep-fire-geometry.ifc `
  --manifest scripts/out/verification-completion/mep/mep_manifest.json `
  --geometry-package scripts/out/verification-completion/mep/mep_geometry.json `
  --solver $solver --duration 1 --require-ready
```

Thiếu GUI/bản xuất lại và cut-cell GEOM, mã trả về kỳ vọng là 2. Không diễn giải thành PASS hoặc lỗi thuật toán ánh xạ. Gói thực tế: [README](../../scripts/out/verification-completion/mep/pyrosim/README.md), [acceptance.json](../../scripts/out/verification-completion/mep/pyrosim/acceptance.json), [FDS gốc](../../scripts/out/verification-completion/mep/mep.fds), [ca chạy ngắn](../../scripts/out/verification-completion/mep/pyrosim/mep_cold.fds).

Khi có PyroSim, dùng File > Import FDS/CAD File, lưu diagnostics và PSM, kiểm tra GEOM/ống rỗng/lỗ mở/đơn vị/tọa độ, rồi xuất FDS ra file khác. Kiểm tra cài đặt FDS GEOM theo đúng phiên bản để tránh đổi biểu diễn khi xuất. Tham khảo [hướng dẫn chính thức](https://www.thunderheadeng.com/docs/2026-1/pyrosim/fds-files/import/).

Ví dụ schema chứng nhận; các trường trống phải được người review điền sau thao tác thực, không dùng làm bằng chứng mẫu đã chạy:

```json
{
  "pyrosim_version": "",
  "reviewer": "",
  "imported_at": "",
  "import_result": "PENDING",
  "warnings_review": "",
  "source_sha256": "",
  "exported_sha256": "",
  "project": {"file": "model.psm", "sha256": ""},
  "diagnostics": {"file": "import-diagnostics.txt", "sha256": ""}
}
```

Chạy lại công cụ với đầy đủ đối số trên và thêm `--roundtrip PATH --import-evidence PATH`; nếu primitive đổi tên thì thêm `--aliases PATH`. Công cụ tự chạy lại đối chiếu và solver của bản xuất lại. Phải ghi đúng phiên bản solver đang được PyroSim sử dụng; kết quả của FDS 6.11.1 không tự chứng nhận một bản FDS khác.

## 6. Trạng thái nghiệm thu hiện tại

| Phần | Kết luận |
| --- | --- |
| Syntax, mapping và hình học nguồn của fixture MEP | Có bằng chứng từ audit đọc lại IFC. |
| OBST một/nhiều MESH theo subset | Có bằng chứng solver hiệu dụng. |
| HOLE và cửa OPEN trong subset mới | Có fixture native và mutation test; có chạy solver thật. |
| Surface GEOM trong BINGEOM | Có kiểm tra native và phát hiện binary bị sửa. |
| GEOM cut-cells và đường khí trong mọi trường hợp | `INCONCLUSIVE`, cần adapter/chứng cứ bổ sung. |
| Nhập/xuất PyroSim thực tế | `BLOCKED`: chưa tìm thấy executable được cấu hình/khả dụng qua PATH, registry và vị trí cài đặt thông dụng. |
| Institute | Không thay nguồn hoặc tự nâng verdict. Kết quả hình học `REJECTED` ở báo cáo 16 vẫn chưa được giải quyết. |
| Nghiệm thu cháy/HVAC/PCCC vận hành | Ngoài phạm vi kiểm chứng tĩnh; chưa được chứng nhận. |

Không thể tuyên bố đã hoàn tất nghiệm thu toàn module cho mọi IFC/PyroSim. Những phần đã triển khai được đóng trong phạm vi trên; hai khoảng trống GUI PyroSim và cut-cell GEOM vẫn xuất hiện rõ ở verdict tổng.

## 7. Log và kết quả tái lập

Lượt cuối: **487 test mặc định PASS**, 20 ca deselect theo cấu hình (15 solver, 5 browser); **15 test solver thật PASS** trong lượt riêng, không FAIL/SKIP. Không cộng thêm 168 test chạy có chọn lọc vì có chồng lặp với suite mặc định. Suite mặc định có 97 warnings, solver có một warning. Mẫu MEP có 8 solid matched, `MAPPING_VERIFIED`; cold-flow đạt 1 giây/3 bước thời gian, kiểm tra đủ 8 GEOM BINGEOM đạt. `handoff` và `verification` vẫn `BLOCKED` theo các bằng chứng còn thiếu được liệt kê trong acceptance.json.

- [Tổng hợp kết quả, runtime và hashes](../../scripts/out/verification-completion/summary.json).
- [Ma trận FDS native](../../scripts/out/verification-completion/solver-matrix/results.json).
- [Suite mặc định](../../.cache/verification-completion/final.xml) và [log](../../.cache/verification-completion/final.log).
- [Suite solver thật](../../.cache/verification-completion/native-final.xml) và [log](../../.cache/verification-completion/native-final.log).
- [Kiểm tra có chọn lọc](../../.cache/verification-completion/targeted.xml).

Các warning mesh trong ca lỗi/mutation được giữ lại. Không chạy lại browser vì không sửa frontend. Không thay snapshot hoặc nới dung sai để làm kết quả đạt.
