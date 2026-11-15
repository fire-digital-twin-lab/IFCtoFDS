# A2 — Kiểm tra tọa độ và placement IFC (10/11/2026)

**Phạm vi:** preflight các `IfcProduct.ObjectPlacement`; tuyệt đối không thay đổi phép biến đổi hình học trong converter.  
**Baseline triển khai:** `main@424aec19089e891ce9869d287d4799501b3fcf8b`, sau A1.  
**Release:** `NOT_PRODUCTION_READY`. **Scientific/application:** `INCONCLUSIVE`.

## Lý do và bằng chứng code

- `ifc_to_fds/core/placement.py` sử dụng `get_local_placement` rồi đổi translation từ đơn vị IFC sang mét.
- `ifc_to_fds/core/federation.py` dựng geometry ở thế giới nguồn rồi mới auto-rebase theo bounding box; phép đổi gốc sau BREP không chứng minh sai số ở geometry kernel đã được loại trừ.
- IFC hầm hai tầng riêng tư có đơn vị milimét và vị trí công trình lớn. Không được suy rằng mọi tọa độ lớn nằm ở `ObjectPlacement`: một số nguồn có thể đặt trong `IfcGeometricRepresentationContext` hoặc representation vertices.
- Chưa có independent physical oracle (as-built drawing/second CAD kernel); vì vậy A2 là **risk characterization**, không được sử dụng để tự cấp mapping PASS.

## Cách chạy an toàn

`python -m ifc_to_fds coordinate-preflight "<private>.ifc" -o ".local-reference-cases/coordinate-preflight.json"`

Có thể đặt `--max-products 25000` để khống chế số product kiểm tra; báo cáo công khai `PLACEMENT_SCAN_INCOMPLETE` khi vượt giới hạn, không coi kết quả partial là complete.

Source IFC **không được** tải lên GitHub public. JSON xuất riêng tư, không ghi đè và tạo mode 0600 nếu POSIX. Trên Windows phải áp NTFS ACL riêng. Ghi source SHA-256 để đối chiếu với dossier A1 và input FDS về sau. Không xuất STEP ID, GUID, tên, đường dẫn, ma trận hoặc tọa độ chính xác.

## Logic/contract kiểm tra

1. Duyệt chain `IfcLocalPlacement.PlacementRelTo`, phát hiện vòng lặp, ID trùng, unsupported placement và depth quá lớn trước khi gọi IfcOpenShell.
2. Đọc ma trận 4×4 bằng `ifcopenshell.util.placement.get_local_placement`. Kiểm tra ma trận finite, row homogeneous, proper rotation `RᵀR≈I`, `det(R)≈+1`. Đây là **numerical preflight**, không phải chứng cứ placement đã đúng theo bản vẽ.
3. Chỉ nhân cột translation với `unit_scale_to_meters`; không scale rotation, không apply federation transform hoặc rebase trong bước này.
4. Tính band cho giá trị tuyệt đối lớn nhất của translation (dưới 100 m, 100–1000 m, 1–10 km, 10–100 km, ≥100 km). Mốc ≥1 km là **heuristic cảnh báo kiểm tra**, không phải dung sai định lượng PCCC.
5. Phân biệt `READABLE_RIGID`, `MISSING`, `NON_RIGID`, `UNSUPPORTED`, `CYCLE_OR_INVALID_ID`, `MATRIX_UNREADABLE`, `NONFINITE_OR_BAD_SHAPE`, `NONFINITE_TRANSLATION_M`, `DEPTH_EXCEEDED`.
6. Mọi báo cáo có `placement_verdict=REVIEW_REQUIRED`, `geometry_verdict=NOT_EVALUATED`, `mapping_verdict=NOT_EVALUATED`, `solver_verdict=NOT_RUN`, `scientific_verdict=INCONCLUSIVE`.

## Kiểm thử và nghiệm thu

| Tình huống | Oracle |
|---|---|
| 2.000.000 mm trong IFC | magnitude band tương đương 2.000 m nếu input khác có unit m |
| Quay 90° + translation | rotation vẫn orthonormal, translation đổi unit một lần |
| Vòng placement | không gọi geometry/placement recursion vào vòng |
| Grid/unsupported placement | fail closed trong báo cáo |
| Matrix reflection, scale, homogeneous row invalid | bị gắn NON_RIGID |
| Matrix NaN/Inf hoặc nhân unit tràn | bị gắn non-finite, không xuất ma trận |
| 25.001 products với max 25.000 | `PLACEMENT_SCAN_INCOMPLETE` |
| Source SHA thay đổi khi đang parse | từ chối report |
| Public IFC integration | chạy IfcOpenShell thật, schema IFC4, output JSON private |
| Real `Ham2Tang.ifc` | chạy local/private runner, so source hash A1, tài liệu review, không gửi coords/GUID ra public |

**CI gate:** Source Quality, Conversion Correctness Linux/Windows, Production Container, Release Image Security PASS trên final HEAD; sau merge phải có main push CI. Không được merge khi Pending/Failed, không hạ threshold hay bỏ test để qua gate.

## Giới hạn / dependency A2b

A2 **không kiểm tra**:
- tọa độ geometry vertices trước OpenCASCADE, `IfcGeometricRepresentationContext.WorldCoordinateSystem`, `IfcMapConversion`, true north, geo CRS;
- sai số kernel ở BREP lớn, snapping và hiệu dụng FDS;
- double-rebase trong pipeline thực vì chưa biến đổi geometry hoặc FDS;
- physical placement correctness so as-built drawing.

Bước A2b chỉ được triển khai sau khi có hình học/reference đủ để thiết kế differential test: IFC translation/rotation invariance, bbox/volume/opening preserved, raw and rebased FDS equivalence, no duplicate translation. Không sửa `USE_WORLD_COORDS`, `convert-back-units` hay `auto_rebase_origin` chỉ dựa vào magnitude band.

## Rollback

Revert module/CLI/tests/docs A2; không thay mapping, geometry, FDS output hoặc dữ liệu job. Việc mở rộng hoặc tự động bật sửa tọa độ phải tạo PR riêng, có numerical oracle và regression.
