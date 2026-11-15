# Audit IFCtoFDS — Kiến trúc chuyển đổi, hình học, HVAC và kiểm định FDS

| Mục | Giá trị |
|---|---|
| Ngày audit | 15/11/2026, giờ địa phương Asia/Bangkok (UTC+07:00) |
| Bắt đầu ghi nhận | 15:28:14 +07:00 |
| Thời điểm lập bản báo cáo | 15/11/2026, 16:04:27 +07:00 |
| Công cụ audit | Codex, Git, Python môi trường dự án, Node.js và FDS 6.11.1 |
| Phiên bản trích mã và tái kiểm | `8ed1f38b3b1de803ce2da996f334731920d4ca26` (ngắn `8ed1f38`), nhánh `fix/volume-noise-abs`, commit lúc 15:56:34 +07:00 |
| Phiên bản đo ban đầu | `66174f02669d1c1a7c760c4278a513647db0aa46` (ngắn `66174f0`), nhánh `docs/cleanup-misleading`, commit lúc 15:26:17 +07:00 |
| Trạng thái ban đầu | `git status --short --branch` chỉ có dòng nhánh. Diff đã stage và chưa stage rỗng. Ở `66174f0`, `docs/audit/` có README quy ước. Khi chuyển sang nhánh hiện tại, các hồ sơ audit cũ xuất hiện trở lại. Báo cáo giữ quy ước tên và các ID đã có. |
| Phạm vi | CLI/API/Workbench, IFC → chuẩn hóa → ánh xạ → FDS → kiểm định, mạng HVAC, kịch bản EV, giới hạn đối chiếu PyroSim và PCCC |
| Điều kiện thực nghiệm | Windows, Python 3.13.18, IfcOpenShell 0.9.0.post1, NumPy 2.5.4, Shapely 2.2.0, Manifold3D 3.5.4, pytest 9.1.1, Node.js 26.13.0.0, FDS `FDS-6.11.1-0-gff928db-release`. IFC mẫu công khai và mô hình tổng hợp. |
| Hướng tải đánh giá | Một kỹ sư chạy CLI hoặc một instance Workbench/API có hàng đợi và worker cô lập. Các phép chạy dưới đây kiểm tra logic và hồi quy. Dữ liệu A/B/C, tải đồng thời trên Docker production và mô phỏng nghiệm thu công trình cần đợt riêng. |

IFCtoFDS biên dịch đối tượng BIM sang đầu vào CFD, lưu danh mục và quyết định theo `entity_key` rồi đọc lại IFC và deck FDS để kiểm định. Workbench có luồng xem trước trên trình duyệt và luồng Verified qua API. Bộ sinh EV dùng nền mapping đã xác minh và bổ sung nguồn cháy, đầu đo, sự kiện cửa cùng bằng chứng riêng cho kịch bản.

Trong phiên, workspace chuyển HEAD từ `66174f0` sang `8ed1f38`. Diff runtime giữa hai mốc gồm `domain/validation/model.py`, `fire/grid_sensitivity_analysis.py`, `geometry/package.py`, `validation/engine.py` và `validation/metrics.py`. Lần tái kiểm chuyển đổi lại fixture, lặp F1/F3, so snapshot FZK và chạy hồi quy phần thay đổi. Các phép đo HVAC/FDS ở mốc đầu dùng serializer, builder và adapter solver có nội dung trùng ở hai commit.

Bảng dưới có 8 việc đang mở. F6 giữ nguyên ID của quan sát ở mốc đầu và có kết quả đóng ở mục 6. Số trong trích đoạn là dòng nguyên văn, đếm từ 1 tại `8ed1f38`.

| ID | Mức độ | Cần xử lý | Bằng chứng chính |
|---|---|---|---|
| F1 | P1 | `domain` xác nhận cả khoảng trống giữa các MESH | 40% miền tổng hợp nằm ngoài các MESH, audit vẫn `MAPPING_VERIFIED` |
| F2 | P1 | `VENT` HVAC kiểm tra mặt hộp bao của tường đã chia OBST | `hvac=PASS` nhưng FDS trả `ERROR(818)`. Ca đặt lên phần tường đặc khởi tạo thành công |
| F3 | P1 | `passage_resolution` trả `PASS` khi còn lỗ mở chưa đánh giá | Lỗ mở qua biên mesh bị bỏ qua, hai OBST được đếm và làm gate đạt |
| F4 | P2 | Cổng trước solver bỏ qua dầm nhỏ có thể biến mất trên lưới | Hộp 0,08 × 0,08 × 0,80 m mất khỏi kiểm kê SMV. Cùng hộp mang kiểu tường được cảnh báo |
| F5 | P2 | Staging artifact trên Windows vượt giới hạn đường dẫn với tên payload dài | Cùng IFC mẫu và tên đích, thư mục 67 ký tự xuất được, 163 ký tự lỗi `WinError 3` |
| F7 | P2 | `ceil` trên thương gần số nguyên có thể tăng số ô hoặc chạm trần cell | `0.07 / 0.01` cho `7.000000000000001`, sinh 80.000 ô khi đối chứng số thập phân là 70.000 |
| F8 | P2 | README còn mô tả sai cổng D*/Δx và chưa ghi đúng khả năng HVAC đã triển khai | Ca D*/Δx ≈ 9,1 vẫn `INCONCLUSIVE` theo test. Fitting, tê và quạt áp đặt lưu lượng đã có hồi quy |
| F9 | P2 | Serializer bỏ `ROUND=.FALSE.` cho ống có tiết diện tổng quát | Ống chữ nhật 1,20 Pa theo deck hiện hành, 1,46 Pa khi thêm cờ, đối chứng 1,47 Pa |

## 1. Phát hiện còn mở và ca đối chứng

### F1 — Miền CFD mất vùng bên trong nhưng audit vẫn cấp MAPPING_VERIFIED

Trong `run_independent_validation`, `union_xb` là hộp chữ nhật nhỏ nhất bao tất cả `MESH`. Mỗi biên chỉ được so với cực trị tương ứng của `model.simulation_domain`. Khi kiểm tra vị trí primitive, thuật toán tiếp tục lấy chính hộp bao đó. Một primitive có thể cắt qua vùng ngoài mọi mesh mà vẫn nằm trong hộp bao. Cổng `domain` nằm trong các gate mapping bắt buộc. [Danh sách gate](../../ifc_to_fds/domain/validation/model.py#L31-L58)

[ifc_to_fds/validation/engine.py:L113–L137](../../ifc_to_fds/validation/engine.py#L113-L137)

~~~text
113 |     raw_domains = [r.values.get("XB") for r in parsed.records if r.kind == "MESH"]
114 |     domains: List[List[float]] = [
115 |         [float(x) for x in d] for d in raw_domains if isinstance(d, (list, tuple)) and len(d) == 6
116 |     ]
117 |     union_xb: Optional[List[float]] = None
118 |     if model.simulation_domain is None:
119 |         unknown("domain", "Explicit simulation domain missing for selected scope")
120 |     elif not domains:
121 |         finding("domain", "No serialized MESH found in FDS output")
122 |     else:
123 |         union_xb = [
124 |             min(d[0] for d in domains),
125 |             max(d[1] for d in domains),
126 |             min(d[2] for d in domains),
127 |             max(d[3] for d in domains),
128 |             min(d[4] for d in domains),
129 |             max(d[5] for d in domains),
130 |         ]
131 |         if any(
132 |             abs(float(a) - b) > 1e-4
133 |             for a, b in zip(union_xb, model.simulation_domain.to_xb())
134 |         ):
135 |             finding("domain", "Serialized MESH differs from declared simulation domain")
136 |         else:
137 |             mesh_record = next(r for r in parsed.records if r.kind == "MESH")
~~~

[ifc_to_fds/validation/engine.py:L197–L215](../../ifc_to_fds/validation/engine.py#L197-L215)

~~~text
197 |         if p.kind in ("OBST", "GEOM"):
198 |             try:
199 |                 solid = p.mesh()
200 |                 bounds = bounds_for_vertices(solid.vertices)
201 |                 if bounds and (union_xb or domains):
202 |                     xb = union_xb or domains[0]
203 |                     coordinates = bounds.to_xb()
204 |                     if any(
205 |                         coordinates[i] < xb[i] - 1e-6
206 |                         if i % 2 == 0
207 |                         else coordinates[i] > xb[i] + 1e-6
208 |                         for i in range(6)
209 |                     ):
210 |                         finding(
211 |                             "geometry",
212 |                             f"Primitive outside computational mesh: {p.id}",
213 |                             key,
214 |                         )
215 |                 primitives.setdefault(key, []).append(solid)
~~~

**Ca tái hiện.** Dùng `tests/baseline/fixtures/tiny.ifc`. Miền và vật cản gốc đều có `XB=[0,2,0,1,0,3]` m. Thay duy nhất bản ghi lưới trong một bản FDS thử bằng `XB=[0,0.6,0,1,0,3]` và `XB=[1.4,2,0,1,0,3]`, mỗi mesh `IJK=10,10,10`. Tính lại SHA-256 FDS và dấu niêm phong của bản manifest thử để phép kiểm truy nguyên nhận đúng phiên bản thử. Giữ IFC và gói hình học gốc khi gọi `pipeline.audit`.

- Hộp bao hai lưới vẫn có thể tích 6,0 m³. Tổng thể tích hai mesh rời là 3,6 m³. Dải `0,6 < X < 1,4` rộng 0,8 m chứa 2,4 m³, bằng 40% miền và 40% vật cản trong ca này.
- Quan sát `syntax=PASS`, `domain=PASS`, `geometry=PASS`, `traceability=PASS`, `air_path=PASS`, `passage_resolution=PASS` và một phần tử `MATCHED`. `mapping_status=MAPPING_VERIFIED`, `simulation_status=INCONCLUSIVE`, solver đã tắt trong phép kiểm này.
- Hậu quả trực tiếp là cổng bắt buộc xác nhận một miền CFD khác miền đã khai báo. Trường hợp này đi qua đường `audit` khi deck được dựng/chỉnh bên ngoài. Bộ chia miền của exporter thường sinh các khối nối tiếp và cần giữ ca đó làm đối chứng dương.

**Sửa tối thiểu đề xuất.** Kiểm hợp các hộp MESH so với miền dự kiến và phát hiện khoảng không được lưới nào bao. Khi hợp lưới được phép có hình dạng đặc biệt, dùng chính sách miền công khai để kiểm vùng cho phép và kiểm riêng độ phủ của mỗi vật cản/lỗ mở. Ca hai mesh ghép sát cùng miền phải đạt, ca để hở dải phải bị chặn ở `domain`. Kèm ca mesh giao nhau để tránh tổng thể tích bù trừ giữa chồng lấn và lỗ hổng.

### F2 — VENT HVAC lọt qua bước kiểm mặt OBST vì dùng hộp bao

`on_face` nhận một `BoundingBox`. Với tường gồm nhiều hộp OBST, đường kiểm truyền `representation_bounds or bounding_box` của cả phần tử. Exporter phát từng hộp của `box_set_for`. Một mặt phẳng có thể qua kiểm tra ở hộp bao tường dù tại vị trí đó chẳng có mặt hộp nào được ghi ra FDS. Cổng HVAC dựng lại bằng cùng `build_hvac_network` rồi so bản ghi nên lặp lại giả định này.

[ifc_to_fds/mep/network.py:L101–L115](../../ifc_to_fds/mep/network.py#L101-L115)

~~~text
101 |         if node.boundary and node.boundary.kind == "VENT":
102 |             xb = node.boundary.vent_xb
103 |             domain = model.simulation_domain
104 |             if domain is None or any(xb[i] < domain.to_xb()[i] - 1e-8 if i % 2 == 0 else xb[i] > domain.to_xb()[i] + 1e-8 for i in range(6)):
105 |                 raise ValueError("HVAC CFD vent must lie within the declared simulation domain")
106 |             if any(node.xyz[i] < xb[2*i] - 0.001 or node.xyz[i] > xb[2*i+1] + 0.001 for i in range(3)):
107 |                 raise ValueError("HVAC source endpoint must lie on its CFD vent")
108 |             axis = next(i for i in range(3) if xb[2*i] == xb[2*i+1])
109 |             def on_face(bounds):
110 |                 box = bounds.to_xb()
111 |                 return (any(abs(xb[2*axis] - box[j]) < 1e-8 for j in (2*axis, 2*axis+1))
112 |                         and all(box[2*i] <= xb[2*i] + 1e-8 and box[2*i+1] >= xb[2*i+1] - 1e-8 for i in range(3) if i != axis))
113 |             if not on_face(domain) and not any(e.mapping_strategy == MappingStrategy.OBST and e.bounding_box and on_face(e.representation_bounds or e.bounding_box) for e in model.elements):
114 |                 raise ValueError("HVAC vent must lie on a supported OBST or mesh boundary face; GEOM vent coupling is not yet supported")
115 |         nodes.append(node)
~~~

[ifc_to_fds/mapping/exporter.py:L334–L347](../../ifc_to_fds/mapping/exporter.py#L334-L347)

~~~text
334 |         if strategy == MappingStrategy.OBST and elem.bounding_box:
335 |             # One box, or the exact box cover of a rectilinear host (wall with openings).
336 |             boxes = (
337 |                 [(elem.representation_bounds or elem.bounding_box).to_xb()]
338 |                 if is_axis_aligned_box(elem.mesh)
339 |                 else box_set_for(elem.mesh)
340 |             )
341 |             for xb in boxes:
342 |                 prim_counter += 1
343 |                 prim_id = f"OBST_{prim_counter}_{clean_fds_id(elem.name, 'obs')}"
344 |                 elem.fds_primitive_ids.append(prim_id)
345 |
346 |                 lines.append(format_source_comment(elem))
347 |                 lines.append(f"&OBST ID='{prim_id}', XB={format_xb(xb)}, SURF_ID='{surface_for_element(elem)}' /")
~~~

[ifc_to_fds/validation/checkers/hvac.py:L36–L50](../../ifc_to_fds/validation/checkers/hvac.py#L36-L50)

~~~text
 36 |     def check(self, context):
 37 |         if context.parsed is None or context.model is None:
 38 |             return CheckerOutcome(self.name, GateResult(status=GateStatus.INCONCLUSIVE, reason="FDS text/source missing"))
 39 |         try:
 40 |             plan = build_hvac_network(context.model)
 41 |             expected = {(kind, tuple(values.get("TYPE_ID", [])), values["ID"][0]): (values, keys)
 42 |                         for kind, values, keys in network_records(plan)}
 43 |             actual = {(r.kind, tuple(r.values.get("TYPE_ID", [])), r.id): r
 44 |                       for r in context.parsed.operational_records}
 45 |             if set(expected) != set(actual):
 46 |                 raise ValueError("Serialized HVAC record set differs from reviewed source network")
 47 |             for identity, (values, keys) in expected.items():
 48 |                 r = actual[identity]
 49 |                 if r.values != values or sorted(r.source.get("entity_keys", [])) != sorted(keys):
 50 |                     raise ValueError(f"HVAC parameters, topology or provenance changed: {identity}")
~~~

**Ca tái hiện.** Chuẩn bị canonical model từ fixture `opening.ifc` với miền `[-1,5,-1,2,-1,4]` m. Thêm một ống tổng hợp trong bộ nhớ từ mẫu `connected-ducts.ifc`. Giữ hai port, khai báo VENT và AMBIENT tường minh. Tại VENT, tọa độ port là tâm hình chữ nhật dưới đây. Port AMBIENT cùng X/Z và Y = −0,8 m. Hai OBST của tường sau serialize có `XB=[0,4,0,0.3,2.1,3]` và `XB=[1,4,0,0.3,0,2.1]` m.

| Ca | `vent_xb` (m) | Diện tích | `hvac` | FDS 6.11.1, `T_END=0` |
|---|---|---:|---|---|
| VENT trong khoảng trống | `[0.2,0.8,0,0,0.8,1.2]` | 0,24 m² | `PASS` | `FAIL`, `ERROR(818)`, solver không gắn được VENT lên mặt |
| Đối chứng VENT trên tường đặc | `[2.0,2.6,0,0,0.8,1.2]` | 0,24 m² | `PASS` | `PASS`, khởi tạo được |

Ca dùng mô hình canonical tổng hợp để cô lập hành vi builder, checker và solver. `effective_geometry` của đối chứng là `INCONCLUSIVE`, vì vậy kết quả dương chỉ chứng minh khởi tạo FDS.

**Sửa tối thiểu đề xuất.** Dùng cùng tập hộp được serializer phát để chứng minh hình chữ nhật VENT nằm trọn trên mặt tiếp xúc rắn–khí, hoặc kiểm trên mặt biên CFD hợp lệ. Ca trên vùng rỗng phải bị chặn từ bước lập mạng với thông báo chỉ rõ port. Ca trên tường đặc và ca VENT trên biên miền vẫn chạy. Hình học sau snap tiếp tục cần bằng chứng SMV. Tự sinh khối đỡ dưới miệng gió sẽ thêm vật cản ngoài mô hình được duyệt và làm thay đổi bài toán.

### F3 — Lỗ mở qua biên mesh bị bỏ qua nhưng passage_resolution vẫn PASS

`check_opening_grid_alignment` chỉ ước lượng khi đúng một MESH bao toàn bộ lỗ mở đã cắt theo host. Khi trả `INCONCLUSIVE`, vòng lặp cộng `not_estimated`. Cùng bộ đếm `assessed` tăng khi duyệt OBST. Cuối hàm, chỉ nhánh `not assessed` mới xét `not_estimated` để hạ trạng thái. Vì vậy phép kiểm của các hộp tường có thể làm gate đạt dù lỗ mở bị bỏ qua.

[ifc_to_fds/validation/effective.py:L49–L62](../../ifc_to_fds/validation/effective.py#L49-L62)

~~~text
 49 |     # Ignore the portion of a through-cut tool protruding outside the host.
 50 |     box[2 * normal:2 * normal + 2] = host[2 * normal:2 * normal + 2]
 51 |     meshes = [record for record in parsed.records if record.kind == "MESH"]
 52 |     covering = [
 53 |         (index, record) for index, record in enumerate(meshes)
 54 |         if all(record.values["XB"][i] <= box[i] + tolerance
 55 |                and record.values["XB"][i + 1] >= box[i + 1] - tolerance for i in (0, 2, 4))
 56 |     ]
 57 |     if len(covering) != 1:
 58 |         return {"status": "INCONCLUSIVE", "reason": "Opening is not contained in one emitted mesh"}
 59 |
 60 |     index, record = covering[0]
 61 |     xb, ijk = record.values["XB"], record.values["IJK"]
 62 |     spacing = [(xb[i + 1] - xb[i]) / n for i, n in zip((0, 2, 4), ijk)]
~~~

[ifc_to_fds/validation/passage_resolution.py:L72–L89](../../ifc_to_fds/validation/passage_resolution.py#L72-L89)

~~~text
 72 |         for e in model.elements:
 73 |             for opening in getattr(e, "openings", []):
 74 |                 if not getattr(opening, "mesh", None) or getattr(e, "bounding_box", None) is None:
 75 |                     not_estimated += 1
 76 |                     continue
 77 |                 grid = check_opening_grid_alignment(opening.mesh, e.bounding_box, parsed)
 78 |                 if grid["status"] != "ESTIMATED":
 79 |                     not_estimated += 1
 80 |                     continue
 81 |                 assessed += 1
 82 |                 if grid["risk_sealed_by_grid"]:
 83 |                     span = min(grid["clear_spans_m"])
 84 |                     report(
 85 |                         e.entity_key,
 86 |                         f"Opening narrower than {MIN_CELLS_ACROSS_PASSAGE} cells: {e.global_id}",
 87 |                         f"Opening {opening.opening_global_id} in {e.ifc_type} {e.global_id} has a clear span of "
 88 |                         f"{span:.3f} m on cells of {max(grid['mesh_spacing_m']):.3f} m and may be sealed by the grid. "
 89 |                         f"Use cells of at most {_round_down_mm(span / MIN_CELLS_ACROSS_PASSAGE):.3f} m.",
~~~

[ifc_to_fds/validation/passage_resolution.py:L113–L140](../../ifc_to_fds/validation/passage_resolution.py#L113-L140)

~~~text
113 |         metrics = {"passage_resolution": {"assessed": assessed, "openings_not_estimated": not_estimated}}
114 |         if findings:
115 |             return CheckerOutcome(
116 |                 gate_name=self.name,
117 |                 result=GateResult(
118 |                     status=GateStatus.FAIL,
119 |                     reason=f"{len(findings)} passage(s) or solid(s) are not resolved by the grid: "
120 |                     + "; ".join(f.title for f in findings[:3]),
121 |                     evidence=metrics["passage_resolution"],
122 |                 ),
123 |                 findings=findings,
124 |                 metrics=metrics,
125 |             )
126 |         if not assessed:
127 |             status = GateStatus.INCONCLUSIVE if not_estimated else GateStatus.NOT_APPLICABLE
128 |             reason = (
129 |                 f"{not_estimated} opening(s) are not axis-aligned boxes; their resolution was not estimated"
130 |                 if not_estimated
131 |                 else "No openings or enclosure obstructions to assess"
132 |             )
133 |             return CheckerOutcome(gate_name=self.name, result=GateResult(status=status, reason=reason), findings=[], metrics=metrics)
134 |         return CheckerOutcome(
135 |             gate_name=self.name,
136 |             result=GateResult(
137 |                 status=GateStatus.PASS,
138 |                 reason=f"{assessed} openings and enclosure solids resolved on the grid; {not_estimated} opening(s) not estimable",
139 |                 evidence=metrics["passage_resolution"],
140 |             ),
~~~

**Ca tái hiện.** Fixture `opening.ifc` có lỗ rộng 1,0 m, cao 2,1 m, qua chiều dày tường 0,30 m. Đối chứng mặc định chạy với một mesh `IJK=(20,2,15)`, `XB=(0,4,0,0.3,0,3)` m, trả `passage_resolution=PASS` với lỗ mở thực sự được ước lượng. Giữ nguyên tường và opening, chia lại miền theo seam X = 0,50 m như sau. Thao tác đọc lại tương tự F1.

~~~fortran
&MESH ID='M1', IJK=1,2,15, XB=0,0.5,0,0.3,0,3 /
&MESH ID='M2', IJK=2,2,15, XB=0.5,4,0,0.3,0,3 /
~~~

- ΔX hai phía lần lượt là 0,50 m và 1,75 m. Lỗ mở dài từ X = 0 đến 1 m, cắt cả hai mesh. Không mesh nào bao đủ lỗ mở. FDS chưa được chạy trong ca seam này.
- `openings=PASS` cho hình học deck trước khi ép lưới. `passage_resolution=PASS` với `assessed=2` và `openings_not_estimated=1`. Cả hai lượt được đếm đều đến từ các primitive OBST.
- Hậu quả là report có thể được đọc như đã đo độ phân giải của đường khói, trong khi lỗ mở liên quan vẫn thiếu bằng chứng. Gate này điều chỉnh `simulation_status`. Cổng xác minh mô phỏng hiện vẫn giữ trạng thái chưa kết luận.

**Sửa tối thiểu đề xuất.** Giữ ưu tiên `FAIL` nếu đo được suy biến. Nếu còn lỗ mở cần đánh giá và thiếu bằng chứng, trả `INCONCLUSIVE` ngay cả khi một số OBST hoặc lỗ khác đạt. Bổ sung riêng ca lỗ qua seam, ca hình học lỗ không thẳng trục và ca mọi lỗ đã được đo. Một thuật toán dự báo qua nhiều mesh cần kiểm vị trí mặt ô thực tế ở hai phía seam.

### F4 — Dầm mỏng có thể mất khỏi lưới trước khi passage_resolution cảnh báo

`ENCLOSURE_TYPES` có tường, sàn và mái. Bộ lọc này bỏ qua `IfcBeam` trước khi kiểm mặt nào snap về cùng chỉ số. Rủi ro mang ID `B-06`/`C-02` trong bản đính kèm liên quan trực tiếp đến nhánh này khi dầm có vai trò cản khói đã được xác nhận.

[ifc_to_fds/validation/passage_resolution.py:L14–L22](../../ifc_to_fds/validation/passage_resolution.py#L14-L22)

~~~text
 14 | ENCLOSURE_TYPES = {
 15 |     "IFCWALL",
 16 |     "IFCWALLSTANDARDCASE",
 17 |     "IFCCURTAINWALL",
 18 |     "IFCSLAB",
 19 |     "IFCROOF",
 20 | }
 21 |
 22 | MIN_CELLS_ACROSS_PASSAGE = 2
~~~

[ifc_to_fds/validation/passage_resolution.py:L29–L41](../../ifc_to_fds/validation/passage_resolution.py#L29-L41)

~~~text
 29 | def _collapsed_axes(xb, mesh):
 30 |     """Axes on which both faces of the box snap to the same grid plane of this mesh."""
 31 |     domain, ijk = mesh.values["XB"], mesh.values["IJK"]
 32 |     if any(min(xb[2 * a + 1], domain[2 * a + 1]) <= max(xb[2 * a], domain[2 * a]) for a in range(3)):
 33 |         return []
 34 |     out = []
 35 |     for axis in range(3):
 36 |         step = (domain[2 * axis + 1] - domain[2 * axis]) / ijk[axis]
 37 |         low = math.floor((xb[2 * axis] - domain[2 * axis]) / step + 0.5)
 38 |         high = math.floor((xb[2 * axis + 1] - domain[2 * axis]) / step + 0.5)
 39 |         if low == high:
 40 |             out.append((axis, xb[2 * axis + 1] - xb[2 * axis], step))
 41 |     return out
~~~

[ifc_to_fds/validation/passage_resolution.py:L92–L109](../../ifc_to_fds/validation/passage_resolution.py#L92-L109)

~~~text
 92 |         meshes = [r for r in parsed.records if r.kind == "MESH"]
 93 |         for primitive in parsed.primitives:
 94 |             key = (getattr(primitive, "source", None) or {}).get("entity_key")
 95 |             element = elements.get(key)
 96 |             if primitive.kind != "OBST" or element is None or element.ifc_type.upper() not in ENCLOSURE_TYPES:
 97 |                 continue
 98 |             xb = primitive.values.get("XB", [])
 99 |             if len(xb) != 6:
100 |                 continue
101 |             assessed += 1
102 |             for mesh in meshes:
103 |                 for axis, thickness, step in _collapsed_axes(xb, mesh):
104 |                     report(
105 |                         key,
106 |                         f"Thin solid collapses on the grid: {element.global_id}",
107 |                         f"{primitive.id} ({element.ifc_type} {element.global_id}) is {thickness:.3f} m thick on "
108 |                         f"{'XYZ'[axis]} but both faces snap to one plane of the {step:.3f} m grid. "
109 |                         f"Use cells of at most {_round_down_mm(thickness):.3f} m.",
~~~

**Ca tái hiện.** Dùng fixture canonical `box_model` từ `tests/conftest.py`, thay khối bằng `XB=[0.34,0.42,0.34,0.42,1.0,1.8]` m, miền `[0,2]³` m, Δ = 0,20 m cả ba trục. Bề rộng X và Y là 0,08 m, nhỏ hơn một nửa chiều ô. Hai biên X cho `floor(0.34/0.2+0.5)=2` và `floor(0.42/0.2+0.5)=2`. Trục Y tương tự. Quan sát FDS 6.11.1 khởi tạo thành công nhưng `effective_geometry=FAIL` với lý do `Solver obstruction inventory differs from input`. Ca đối chứng chỉ đổi kiểu `IfcBeam` thành `IfcWall`.

| Kiểu | `passage_resolution` | FDS khởi tạo | `effective_geometry` |
|---|---|---|---|
| `IfcBeam` | `NOT_APPLICABLE` | `PASS` | `FAIL` |
| `IfcWall` | `FAIL`, có finding thu gọn chiều dày | `PASS` | `FAIL` |

**Sửa tối thiểu đề xuất.** Thêm các vật cản được gán vai trò bảo vệ luồng khói vào phép kiểm độ phân giải, giữ ID nguồn và thông báo mesh/trục. Điều kiện đủ cần xét đúng dạng hình học và vị trí so với lưới. Một chiều bị snap phẳng có thể thành tấm mỏng. Hai chiều rất nhỏ có thể làm vật cản bị bỏ. Nếu ép từ 0,08 m lên một ô 0,20 m, sai lệch chiều dày riêng theo trục là `(0.20 − 0.08)/0.08 = 150%`. Cần giữ ca dầm dày đủ phân giải làm đối chứng và dùng SMV xác nhận. [FDS User’s Guide 6.11.1, Thin Obstructions và Specified Versus Actual Areas](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L1162-L1174)

### F5 — CLI tạo được kết quả trong bộ nhớ nhưng lưu artifact thất bại ở đường dẫn dài

CLI chuyển đổi xong rồi ghi deck, manifest, báo cáo, index hình học và payload vào staging cùng ổ đĩa với thư mục đích. Tên đường dẫn thực tế gồm cả `.ifcfds-work-*` hoặc `.staging-<UUID>`, thư mục `*_geometry.payloads` và tên băm 64 ký tự. `copy_package` dùng `shutil.copytree` cho payload. Trên Windows trong phiên audit, `LongPathsEnabled=0`.

[ifc_to_fds/adapters/storage/filesystem.py:L19–L32](../../ifc_to_fds/adapters/storage/filesystem.py#L19-L32)

~~~text
 19 |         target_path = Path(output).resolve()
 20 |         target_dir = target_path.parent
 21 |         target_dir.mkdir(parents=True, exist_ok=True)
 22 |         base_stem = target_path.stem
 23 |
 24 |         # Use an isolated staging directory in the same filesystem for atomic publication
 25 |         staging_dir = target_dir / f".staging-{uuid4().hex}"
 26 |         staging_dir.mkdir(parents=True, exist_ok=True)
 27 |
 28 |         emitted_filenames: List[str] = [target_path.name]
 29 |         try:
 30 |             # 1. Staging write: FDS simulation input
 31 |             staging_fds = staging_dir / target_path.name
 32 |             staging_fds.write_bytes(result["fds_text"].encode("utf-8"))
~~~

[ifc_to_fds/adapters/storage/filesystem.py:L62–L70](../../ifc_to_fds/adapters/storage/filesystem.py#L62-L70)

~~~text
 62 |
 63 |             # 4. Staging write: Geometry package and archive
 64 |             geom_json_name = f"{base_stem}_geometry.json"
 65 |             emitted_filenames.append(geom_json_name)
 66 |             staging_geom_json = staging_dir / geom_json_name
 67 |             copy_package(result["geometry_package"], staging_geom_json)
 68 |
 69 |             geom_zip_name = f"{base_stem}_geometry.zip"
 70 |             emitted_filenames.append(geom_zip_name)
~~~

[ifc_to_fds/geometry/storage.py:L199–L209](../../ifc_to_fds/geometry/storage.py#L199-L209)

~~~text
199 | def copy_package(package, path):
200 |     path = Path(path)
201 |     path.parent.mkdir(parents=True, exist_ok=True)
202 |     if isinstance(package, DiskPackage):
203 |         if package.path.resolve() != path.resolve():
204 |             shutil.copyfile(package.path, path)
205 |             shutil.copytree(
206 |                 payload_dir(package.path), payload_dir(path), dirs_exist_ok=True
207 |             )
208 |     else:
209 |         path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
~~~

**Ca tái hiện.** Mở tiến trình Python mới với solver tự dò tắt. Chạy `python -m ifc_to_fds convert tests/baseline/fixtures/tiny.ifc -o <gốc>/tiny.fds` hai lần, một gốc tuyệt đối dài 67 ký tự, một thư mục con làm gốc dài 163 ký tự. Ở 67 ký tự CLI trả 0 và có tệp. Ở 163 ký tự CLI trả 3 và báo `[WinError 3]` khi sao payload. Một đường dẫn `.bin` trong lỗi dài 278 ký tự. Lần smoke đầu với thư mục tạm mặc định của sandbox gặp cùng dạng lỗi.

**Sửa tối thiểu đề xuất.** Kiểm cả nguồn và đích của payload lồng sâu khi publish rồi báo lỗi có ngữ cảnh nếu môi trường không hỗ trợ. Khi hỗ trợ I/O đường dẫn dài, dùng cách nhất quán cho tạo thư mục, ghi, sao, đổi tên và rollback. Giữ cùng filesystem cho bước publish và kiểm thêm lần ghi đè lỗi để bảo toàn bundle đã có. Ca ngắn làm đối chứng. Việc tự đổi vị trí đích của người dùng cần giữ ngoài hợp đồng sửa lỗi này.

### F7 — ceil tạo thêm ô ở biên số nguyên do biểu diễn float

Bộ chia lưới dùng `math.ceil(L / cell_size)` trên ba trục rồi nhân số ô trước khi kiểm trần. Với kích thước thập phân có thương nguyên trên giấy, sai số biểu diễn có thể làm thương binary64 nhích lên trên số nguyên.

[ifc_to_fds/mapping/exporter.py:L93–L110](../../ifc_to_fds/mapping/exporter.py#L93-L110)

~~~text
 93 | def compute_mesh_grid(
 94 |     bounds: BoundingBox, cell_size: float = 0.2, max_total_cells: int = 50_000_000
 95 | ) -> Tuple[List[int], List[float]]:
 96 |     if not math.isfinite(cell_size) or cell_size <= 0:
 97 |         raise ValueError("cell_size must be finite and positive")
 98 |     xb = bounds.to_xb()
 99 |     ijk = [
100 |         max(1, math.ceil((xb[1] - xb[0]) / cell_size)),
101 |         max(1, math.ceil((xb[3] - xb[2]) / cell_size)),
102 |         max(1, math.ceil((xb[5] - xb[4]) / cell_size)),
103 |     ]
104 |     total_cells = ijk[0] * ijk[1] * ijk[2]
105 |     if total_cells > max_total_cells:
106 |         raise ValueError(
107 |             f"Total mesh cells ({total_cells:,}) exceeds maximum safety limit of {max_total_cells:,}. "
108 |             f"Increase cell_size (current: {cell_size}m) or restrict simulation domain."
109 |         )
110 |     return ijk, xb
~~~

**Ca tái hiện.** Gọi `compute_mesh_grid` với `XB=[0,0.07,0,1,0,1]` m và `cell_size=0.01` m. Đối chứng số học thập phân cho `IJK=[7,100,100]`. Python trả `0.07/0.01=7.000000000000001` và hàm trả `[8,100,100]`. Bước thực trục X thành `0.07/8=0.00875` m. Với `max_total_cells=70000`, API ném `Total mesh cells (80,000) exceeds maximum safety limit of 70,000`. Ca này minh họa biên tính toán của API hàm với trần chỉ định. Trần mặc định của exporter là 50 triệu ô.

**Sửa tối thiểu đề xuất.** Xử lý rõ sai số biểu diễn ở sát thương nguyên rồi áp trần trên lưới đã tính. Kiểm một thương dư thật tiếp tục dùng `ceil` và hành vi tăng số ô khi bước thực vượt kích thước đã yêu cầu. Mức phân giải và thể tích miền do bài toán quyết định.

### F8 — README lệch hợp đồng mesh gate và khả năng HVAC hiện hành

README mục 9.4 còn ghi khoảng `4 ≤ D*/Δx ≤ 16` là `PASS`, dưới 4 là `FAIL`. `_indicator_gate` hiện trả `INCONCLUSIVE` cho chỉ báo đơn lẻ trên nguồn cháy dương hợp lệ. Ca `total_peak_hrr_mw=5.0`, `cell_size=0.2` có tỷ số khoảng 9,1. Test xác nhận `INCONCLUSIVE` và `historical_4_16_is_acceptance_rule=False`. Người đọc theo bảng README có thể dùng sai bằng chứng để chọn lưới.

[README.md:L487–L497](../../README.md#L487-L497)

~~~text
487 | ### 9.4. Hiểu mesh gate và file kịch bản
488 |
489 | Backend tạo phản ứng đơn/composite, RAMP, SURF, vật thể xe và VENT nguồn cháy. Mesh gate đọc lưới thực từ FDS đã ghép, đánh giá D*/Δx theo chính sách hiện tại:
490 |
491 | | Tỷ số | Kết quả thông thường |
492 | |---|---|
493 | | D*/Δx < 4 | FAIL: lưới quá thô theo gate |
494 | | 4 ≤ D*/Δx ≤ 16 | PASS |
495 | | D*/Δx > 16 | INCONCLUSIVE: ngoài miền kiểm chứng của gate |
496 |
497 | Tỷ số này không tự chứng minh hội tụ lưới hoặc tính đúng vật lý. `mesh_status=PASS` và `simulation_status=NOT_RUN` có thể cùng xuất hiện.
~~~

[ifc_to_fds/validation/checkers/mesh_resolution.py:L82–L106](../../ifc_to_fds/validation/checkers/mesh_resolution.py#L82-L106)

~~~text
 82 |     evidence: Dict[str, Any] = {
 83 |         "d_star_m": first["d_star_m"],
 84 |         "cell_size_m": first["cell_size_m"],
 85 |         "d_star_over_dx": first["d_star_over_dx"],
 86 |         "peak_hrr_kw": first["peak_hrr_kw"],
 87 |         evidence_key: evaluations,
 88 |         "scientific_interpretation": "INDICATOR_ONLY",
 89 |         "historical_4_16_is_acceptance_rule": False,
 90 |         "grid_sensitivity_required": True,
 91 |         "reference": "NIST_FDS_VALIDATION_GUIDE_6_11_1",
 92 |         "cell_size_basis": "CALLER_SUPPLIED_UNVERIFIED_LOCALITY",
 93 |         "local_source_mesh_resolved": False,
 94 |     }
 95 |     if geometry_metrics:
 96 |         evidence["critical_geometry_resolution"] = geometry_metrics
 97 |     return GateResult(
 98 |         status=GateStatus.INCONCLUSIVE,
 99 |         reason=(
100 |             "D*/dx is reported as a plume-resolution indicator only; current FDS "
101 |             "validation studies span a wide range of D*/dx values. Mesh adequacy "
102 |             "requires scenario-specific grid sensitivity and relevant geometry "
103 |             "resolution evidence before PASS can be issued."
104 |         ),
105 |         evidence=evidence,
106 |     )
~~~

[tests/test_fire_mesh_gate.py:L41–L51](../../tests/test_fire_mesh_gate.py#L41-L51)

~~~text
 41 | def test_mesh_gate_does_not_promote_historical_4_16_subset_to_pass():
 42 |     """A D*/dx value inside the historical subset remains indicator-only."""
 43 |     scenario_5mw = {"total_peak_hrr_mw": 5.0}
 44 |     res = check_mesh_resolution(scenario_5mw, cell_size=0.2)
 45 |     assert res.status == GateStatus.INCONCLUSIVE
 46 |     assert res.evidence["d_star_over_dx"] == pytest.approx(9.1065, rel=1e-2)
 47 |     assert (
 48 |         res.evidence["source_evaluations"][0]["indicator_band"]
 49 |         == "WITHIN_HISTORICAL_4_16_SUBSET"
 50 |     )
 51 |     assert res.evidence["historical_4_16_is_acceptance_rule"] is False
~~~

Mục 8.5 và lộ trình ngắn của README cũng cần phản ánh fitting hai cổng có chiều dài và `LOSS` đã duyệt, tê có tổn thất theo từng cặp cổng, và quạt áp đặt `VOLUME_FLOW` có `SINK/SOURCE`. Thứ tự xuất theo `SINK → SOURCE` nếu có hướng. Mục 8.3 hiện chỉ mô tả dấu theo thứ tự port trong inventory. [Hướng dẫn HVAC hiện tại](../../README.md#L422-L451) · [Builder và thứ tự port](../../ifc_to_fds/mep/network.py#L22-L43) · [Sắp thứ tự trước khi phát DUCT](../../ifc_to_fds/mep/network.py#L119-L133) · [Test cho fitting và quạt](../../tests/test_hvac_fittings.py#L56-L92) · [Test cho tê](../../tests/test_hvac_junction.py#L127-L153)

**Sửa tối thiểu đề xuất.** Cập nhật bảng minh họa cùng nguồn với code và các test. Tách năng lực nhận cấu hình đã duyệt khỏi việc tự suy diễn thông số từ IFC. Gắn một ví dụ dấu lưu lượng theo `NODE_ID` trong FDS, cho thấy cách đối chiếu `SINK/SOURCE` và kết quả solver.

## 2. Kiến trúc và đường đi của dữ liệu

~~~mermaid
flowchart TD
    CLI[CLI convert / audit] --> P[Facade pipeline.py]
    WEB[Workbench Verified] --> API[FastAPI và hàng đợi SQLite]
    API --> W[Worker chuyển đổi]
    W --> P
    P --> M[Đọc IFC và lập canonical model]
    M --> A[Scope và mapping plan]
    M --> H[Graph MEP và HVAC đã duyệt]
    A --> E[Chuyển thành FDS và geometry package]
    H --> E
    E --> D[Checkpoint trên đĩa]
    D --> V[Parse lại FDS và so với IFC mở lại]
    M2[IfcOpenShell đọc nguồn lần hai] --> V
    V --> R[Report, manifest, checksums]
    R --> S[Sinh kịch bản EV từ nền đã duyệt]
    Q[Quick ở trình duyệt] --> QD[Preview hoặc xuất nhanh]
~~~

| Lớp | Trách nhiệm thực tế và nơi kiểm tra |
|---|---|
| Điểm vào | `python -m ifc_to_fds`/CLI và worker job gọi `pipeline.convert`. Facade lấy use case từ bootstrap. `pipeline.audit` gọi use case đọc lại FDS. [Facade](../../ifc_to_fds/pipeline.py#L39-L70) · [Worker](../../ifc_to_fds/adapters/jobs/runner.py#L151-L176) |
| Hợp đồng | `domain/bim` giữ mesh và IFC chuẩn hóa, `domain/scope` giữ phạm vi và miền, `domain/mapping` giữ quyết định và manifest, `domain/mep` giữ đồ thị và thông số, `domain/validation` giữ verdict. [Gói domain](../../ifc_to_fds/domain) |
| Điều phối | `ConvertVerifiedUseCase` chuẩn bị → lập mapping → serialize → lưu checkpoint → đọc lại `read_fds()` → audit → kết quả. Adapter sản xuất được inject. Nhánh dựng use case trực tiếp còn fallback cho tương thích. [Bootstrap](../../ifc_to_fds/bootstrap/container.py#L29-L54) · [Use case](../../ifc_to_fds/application/use_cases/convert_verified.py#L47-L113) |
| Kiểm toán | `AuditConversionUseCase` mở nguồn lại với `reference=True`, so parse FDS, nguồn, gói mesh, MEP và golden nếu có. Chế độ đọc manifest lấy thông tin dựng lại, chừa `audit` và `accepted_source_defects` cho cấu hình của người gọi. [Use case audit](../../ifc_to_fds/application/use_cases/audit_conversion.py#L28-L74) |
| Lưu trữ và vận hành | `server.py` nhận upload, giữ slot rồi giao job. Repository SQLite theo dõi trạng thái. Worker tạo bundle, lưu checksum và đọc bằng chứng khi tải/kiểm toán job. [Nhận job](../../ifc_to_fds/server.py#L289-L315) · [JobRepository](../../ifc_to_fds/adapters/jobs/repository.py#L32-L87) · [Chỉ mục bằng chứng](../../ifc_to_fds/adapters/jobs/evidence_index.py#L146-L177) |
| Workbench | Verified gửi file và cấu hình lên `/api/jobs`, poll đến `COMPLETED` rồi đọc `/result`. Luồng Quick dựa trên parser/export worker JS, còn viewer có web-ifc WASM để dựng hình hiển thị. Viewer clipping chỉ phục vụ quan sát. [Verified](../../js/verified-workflow.js#L208-L239) · [Quick controller](../../js/app-controller.js#L1257-L1328) · [Worker hiển thị](../../js/workers/web-ifc-display-worker.js) |
| Vận hành Compose | Một app quản lý root job, mặc định 2 job chờ, worker giới hạn 4.096 MiB theo cấu hình mẫu và timeout 1.800 s. Upload spool chỉ định `TMPDIR` trên volume, trong khi `/tmp` tmpfs phục vụ phần tạm khác. Docker có target solver với FDS ghim phiên bản và target mặc định runtime. [Compose](../../compose.production.yml#L9-L23) · [Dockerfile](../../Dockerfile#L53-L72) |

[ifc_to_fds/application/use_cases/convert_verified.py:L93–L105](../../ifc_to_fds/application/use_cases/convert_verified.py#L93-L105)

~~~text
 93 |         manifest.reseal()
 94 |         manifest = workspace.write_draft(model, configuration, manifest)
 95 |         # The auditor reopens the source. Release the converter's full meshes
 96 |         # before constructing that independent model, rather than retaining both.
 97 |         source_timings = dict(model.timings)
 98 |         exported_bounds = model.exported_bounds
 99 |         del mapping_plan, model
100 |         gc.collect()
101 |         fds = workspace.read_fds()
102 |         audited, manifest, report = self.audit_use_case.execute(
103 |             paths, fds, manifest, configuration, geometry_package
104 |         )
105 |         timings = dict(
~~~

[ifc_to_fds/application/use_cases/audit_conversion.py:L45–L69](../../ifc_to_fds/application/use_cases/audit_conversion.py#L45-L69)

~~~text
 45 |         if configuration is None:
 46 |             # An artifact can reproduce placement and mapping, but cannot set
 47 |             # the tolerance or choose an executable for its own audit.
 48 |             manifest_config = manifest.configuration or {}
 49 |             configuration = {k: v for k, v in manifest_config.items() if k not in ARTIFACT_CONFIG_EXCLUDED}
 50 |         configuration = validate_configuration(configuration)
 51 |         manifest_config = manifest.configuration or {}
 52 |         if "mep_graph" not in configuration and "mep_graph" in manifest_config:
 53 |             configuration["mep_graph"] = manifest_config["mep_graph"]
 54 |         source_start = perf_counter()
 55 |         model = prepare_model(paths, configuration, reference=True)
 56 |         source_done = perf_counter()
 57 |         digests, stale = self._reviewed_defects(model, configuration)
 58 |         with accepted_source_defects(digests):
 59 |             config = AuditConfig.model_validate(configuration.get("audit", {}))
 60 |             audit_start = perf_counter()
 61 |             report = run_independent_validation(model, fds_text, manifest, config)
 62 |             validation_done = perf_counter()
 63 |             report.requested_level = (
 64 |                 "simulation" if configuration.get("profile") == "simulation" else "mapping"
 65 |             )
 66 |             apply_independent_source_integrity(
 67 |                 model, fds_text, manifest, geometry_package, report, config
 68 |             )
 69 |             apply_mep_and_coverage(model, report, configuration)
~~~

[ifc_to_fds/server.py:L295–L315](../../ifc_to_fds/server.py#L295-L315)

~~~text
295 |     try:
296 |         manager.reserve_upload()
297 |     except OverflowError as exc:
298 |         raise HTTPException(429, "Job queue is full; retry after existing jobs finish") from exc
299 |     try:
300 |         configuration = config() if callable(config) else config
301 |         directory, paths = await store_uploads(uploads)
302 |         queued = False
303 |         try:
304 |             job = manager.submit(paths, configuration, directory, mode=mode)
305 |             queued = True
306 |             return job
307 |         except OverflowError as exc:
308 |             raise HTTPException(429, str(exc)) from exc
309 |         except JobPersistenceError as exc:
310 |             raise HTTPException(503, "Job metadata storage unavailable; retry later") from exc
311 |         finally:
312 |             if not queued:  # any failure, including OSError on a full disk, must not leave the upload behind
313 |                 shutil.rmtree(directory, ignore_errors=True)
314 |     finally:
315 |         manager.release_upload()
~~~

Hai lần đọc cho phép phát hiện deck/manifest sai sau serialize. Cả hai gắn với IfcOpenShell và một phần chính sách hình học chung. Đường reference tách phép lặp hình học và bước kiểm lại hở lỗ. Điều này để lại rủi ro chung thư viện/kernel nếu cả hai luồng cùng hiểu sai một representation IFC. Bằng chứng nâng mức độc lập là solid đối chứng giải tích, đọc deck/SMV bằng đường khác hoặc đo thực nghiệm. [Load nguồn và nhánh reference](../../ifc_to_fds/core/federation.py#L48-L67) · [Dựng reference](../../ifc_to_fds/geometry/engine.py#L287-L330)

### Thống kê tại HEAD và hướng phụ thuộc

Đếm tệp Git theo dõi theo hậu tố, gồm toàn bộ dòng vật lý, dòng trắng, dòng chú thích và JS vendored/generated. `ifc_to_fds/` có 176 tệp Python, 23.909 dòng. `tests/` có 154 tệp Python, 27.799 dòng. `js/` có 48 tệp JavaScript, 88.333 dòng. `application/service.py` trong bản mô tả cũ đã tách thành các use case/dịch vụ. Các kích thước hiện tại là `convert_verified.py` 139, `audit_conversion.py` 144, `geometry/engine.py` 336, `server.py` 692, `validation/engine.py` 793, `geometry/mesh.py` 838 và `js/app-controller.js` 1.823 dòng.

Duyệt AST của mỗi tệp Python đã theo dõi dưới các gói con `ifc_to_fds/`. Chuẩn hóa `from .` theo đường dẫn. Mỗi tệp nguồn đóng góp tối đa một lần cho cùng gói đích, gồm cả import trong hàm.

| Gói X | Gói Y | Số tệp X import Y | Số tệp Y import X |
|---|---|---:|---:|
| `adapters` | `validation` | 2 | 1 |
| `core` | `geometry` | 1 | 8 |
| `core` | `mep` | 1 | 2 |
| `fire` | `validation` | 8 | 1 |
| `geometry` | `validation` | 3 | 9 |
| `mapping` | `validation` | 2 | 4 |

Cặp phụ thuộc tĩnh giải thích nơi thay đổi dễ ảnh hưởng chéo. Lỗi tải module `F-01` cần chứng cứ ở tiến trình mới. `validation/checkers/mesh_resolution.py` lấy công thức từ `fire/mesh_metrics.py`. `fire/__init__.py` hiện xuất API scenario, mesh plan và grid sensitivity. Smoke CLI khởi động mới đã qua với fixture `tiny.ifc`. Phụ thuộc đáng chú ý của mapping vào validation là dùng `opening_residual` ngay khi xét giữ lỗ. F2 cho thấy còn một giả định dùng chung giữa đường lập kế hoạch và đường đọc lại. [Import mapping](../../ifc_to_fds/mapping/policy.py#L3-L8) · [Import mesh checker](../../ifc_to_fds/validation/checkers/mesh_resolution.py#L8-L25) · [Public API fire](../../ifc_to_fds/fire/__init__.py#L3-L45)

Nút tê khác với đóng gói đồ thị thường. `_junction` duyệt danh sách cạnh cho từng port của từng tê. Với tổng P port ở các tê và E cạnh, chi phí phần dò là O(P × E), ngoài bước gom nút. Ca có nhiều tê cùng tăng theo E sẽ tiến tới chi phí bậc hai ở đoạn này. Chỉ số thời gian V&V trong roadmap cho thấy đường audit hình học đang chiếm phần đáng kể trên A. Phiên này đo theo fixture. Chưa định lượng mức đóng góp của vòng quét tê trên C. [Vòng tìm duct kề](../../ifc_to_fds/mep/network.py#L136-L149) · [Số đo lịch sử M1.7 và M5.2](../plans/production-roadmap.md#L124-L146)

## 3. Tính toán hình học và điều kiện xác minh

### 3.1. Đơn vị, hệ tọa độ và phạm vi

`get_length_unit_scale` lấy đúng một `LENGTHUNIT` trong project units, xác minh chuỗi chuyển đổi kết thúc ở mét và hệ số dương hữu hạn. `source_id` lấy SHA-256 nội dung IFC. `entity_key = source_id:step_id` định danh từng đối tượng trong federated model. `GlobalId` và tên tệp được giữ làm metadata. Quan hệ lỗ mở gồm khóa host, khóa opening, khóa quan hệ rỗng và các fill liên kết bằng `IfcRelFillsElement`. [Định danh nguồn](../../ifc_to_fds/core/inventory.py#L142-L170) · [Quan hệ lỗ và fill](../../ifc_to_fds/core/inventory.py#L223-L258) · [Định danh phần tử](../../ifc_to_fds/core/inventory.py#L310-L326)

[ifc_to_fds/core/units.py:L20–L41](../../ifc_to_fds/core/units.py#L20-L41)

~~~text
 20 | def get_length_unit_scale(ifc_file):
 21 |     projects = ifc_file.by_type("IfcProject")
 22 |     assignment = getattr(projects[0], "UnitsInContext", None) if projects else None
 23 |     units = [
 24 |         u
 25 |         for u in getattr(assignment, "Units", ())
 26 |         if getattr(u, "UnitType", None) == "LENGTHUNIT"
 27 |     ]
 28 |     if len(units) != 1:
 29 |         raise ValueError(
 30 |             "Exactly one project LENGTHUNIT is required; metres cannot be assumed"
 31 |         )
 32 |     unit = units[0]
 33 |     if not _resolves_to_si_metre(unit):
 34 |         raise ValueError(
 35 |             f"Project LENGTHUNIT {getattr(unit, 'Name', unit.is_a())!r} "
 36 |             "cannot be converted to metres through SI units"
 37 |         )
 38 |     scale = float(ifcopenshell.util.unit.calculate_unit_scale(ifc_file))
 39 |     if not math.isfinite(scale) or scale <= 0:
 40 |         raise ValueError("Invalid IFC length scale")
 41 |     return f"{getattr(unit, 'Prefix', '') or ''}{unit.Name}", scale
~~~

`IfcLocalPlacement` được nhân từ cha xuống con trong một chuỗi ma trận 4 × 4. Phần cơ sở của `IfcAxis2Placement3D` xây trục X từ `RefDirection` sau khi chiếu vuông góc lên trục Z, rồi lập Y bằng tích có hướng. Hệ số IFC đổi đơn vị áp vào phần tịnh tiến của placement. Đối với lưới do IfcOpenShell trả, tùy chọn `convert-back-units=False` giữ mét SI. Nhánh instancing dùng lại lưới local theo representation và đưa từng instance về world bằng `v_world = R v_local + t`. Với ma trận instance có định thức âm, mã đảo thứ tự mặt. [Placement](../../ifc_to_fds/core/placement.py#L33-L117) · [Cấu hình tessellation SI và instancing](../../ifc_to_fds/geometry/engine.py#L56-L101)

[ifc_to_fds/geometry/engine.py:L80–L85](../../ifc_to_fds/geometry/engine.py#L80-L85)

~~~text
 80 | def transformed_mesh_arrays(vertices, faces, matrix):
 81 |     """Apply a 4x4 placement in float64; a mirroring matrix reverses winding to keep normals outward."""
 82 |     world = vertices @ matrix[:3, :3].T + matrix[:3, 3]
 83 |     if np.linalg.det(matrix[:3, :3]) < 0:
 84 |         faces = faces[:, ::-1]
 85 |     return world, faces
~~~

Khi nhập nhiều nguồn cần xác nhận cùng hệ tọa độ hoặc cung cấp transform cho từng nguồn. Cùng transform áp cho mesh, bounds, placement và port. Phép rebase trừ cùng vector để giữ hình học và MEP đồng nhất. Làm tay một ví dụ kiểm tra với translation 2.500 mm → 2,5 m, điểm local 0,4 m và rebase 1,0 m trên cùng trục thì điểm cuối là 1,9 m. Nếu nhân lại `0.001` lên lưới đã SI, kết quả sai theo hệ số 1.000. `TrueNorth`/georeference được lưu làm bằng chứng. Căn xoay lưới theo trục chính công trình là một quyết định kỹ thuật cần transform đã xác nhận. [Điều kiện ghép và reference](../../ifc_to_fds/core/federation.py#L33-L75) · [Biến đổi port](../../ifc_to_fds/core/federation.py#L120-L130) · [Rebase](../../ifc_to_fds/core/federation.py#L229-L274)

Phạm vi phần tử (nguồn, tầng, quan hệ retain) và miền CFD (hộp `simulation_domain`) là hai tham số. Bộ lọc viewer phục vụ hiển thị. Hợp đồng scope ghi lý do loại/truyền tiếp từng phần tử. Chọn bằng định danh tầng để tránh nhập nhằng tên trùng. F1 xảy ra trong lớp kiểm tính phủ của miền sau serialize. [Chọn scope và domain](../../ifc_to_fds/application/services/model_preparer.py#L14-L70) · [Phân biệt phạm vi và viewer](../../README.md#L335-L361)

### 3.2. Tô-pô, OBST, GEOM và lỗ mở

- Diện tích tam giác có ba đỉnh `a,b,c` là `‖(b−a)×(c−a)‖/2`. Code đếm tam giác suy biến bằng đỉnh lặp hoặc norm tích có hướng dưới `1e-12` trong hệ tọa độ mét. Đây là phép đếm lỗi tô-pô. Cạnh mở có một mặt tham gia, cạnh non-manifold có trên hai mặt và hướng cạnh được kiểm nhất quán. Đối chứng thể tích có dấu cho vỏ kín là `Σ a·(b×c)/6`. Điều kiện chỉ dựa vào thể tích dương sẽ bỏ qua tự cắt hoặc lỗi tô-pô. [Các điều kiện valid solid](../../ifc_to_fds/geometry/mesh.py#L177-L249)
- `prepare_source_mesh` lưu bằng chứng trước/sau chuẩn hóa. Nhánh self-intersection hiện phân loại tiếp xúc ngược mặt, tiếp xúc số học và xâm lấn. Pha hợp nhất các thành phần chồng lấn dùng bằng chứng giao nhau và kiểm tra membership/winding-number độc lập. Tiếp xúc bề mặt có thể tích giao bằng 0 và hai interior có thể rời. Giao xuyên có thể thay đổi thể tích hợp. Những trường hợp chưa chứng minh được cần lý do theo từng đối tượng. [Chuẩn hóa lưới](../../ifc_to_fds/geometry/engine.py#L149-L168) · [Kiểm và chứng minh union](../../ifc_to_fds/geometry/component_union.py#L126-L205)
- `OBST` ưu tiên hộp thẳng trục được chứng minh hoặc tập hộp phủ đúng khối trực giao, kể cả tường có lỗ. `GEOM` giữ tam giác của khối hợp lệ/đích biên, ghi `VERTS` với độ chính xác .17g và đổi chỉ số tam giác sang 1-based. `GLASS` là chọn bề mặt cho cửa/cửa sổ. Quyết định dạng khối thuộc mapping policy, trạng thái chắn đường khói còn phụ thuộc hình học và fill từ IFC. `VOXEL` và `OBST_HOLE` chưa được phép qua exporter Verified. [Chọn mapping](../../ifc_to_fds/mapping/policy.py#L106-L166) · [Chứng minh box cover](../../ifc_to_fds/geometry/rectilinear.py#L53-L97) · [Surface và serialize](../../ifc_to_fds/mapping/exporter.py#L71-L89) · [Rào chắn chiến lược](../../ifc_to_fds/mapping/exporter.py#L315-L372)
- So solid dùng `Vi / (Vref + Vout − Vi)` cho IoU, sai số thể tích `|Vref−Vout|/Vref`, khoảng cách bề mặt và số thành phần. Khi dữ liệu tam giác có chứng minh đồng nhất, phép kiểm tránh Boolean trùng mặt. Khi tương ứng bề mặt thiếu bằng chứng đầy đủ, trạng thái là `INCONCLUSIVE`. Ở `66174f0`, bề mặt và sai số thể tích tương đối dùng `1e-9`. Ngưỡng IoU là `1−1e-9`. Tại `8ed1f38`, dung sai bề mặt mặc định là `1e-6 m`. Tiêu chí thể tích và IoU bổ sung phép so với lớp vỏ theo diện tích tham chiếu. Cùng hàm `within_tolerance` được dùng cho deck và geometry package. [So solid](../../ifc_to_fds/validation/metrics.py#L102-L182) · [Ngưỡng mặc định](../../ifc_to_fds/domain/validation/model.py#L89-L102) · [Chuyển kết quả thành verdict](../../ifc_to_fds/validation/engine.py#L582-L611)

[ifc_to_fds/geometry/mesh.py:L207–L228](../../ifc_to_fds/geometry/mesh.py#L207-L228)

~~~text
207 |     if faces is not None:
208 |         a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
209 |         repeated = (
210 |             (faces[:, 0] == faces[:, 1])
211 |             | (faces[:, 1] == faces[:, 2])
212 |             | (faces[:, 2] == faces[:, 0])
213 |         )
214 |         result["degenerate_faces"] = int(
215 |             np.count_nonzero(
216 |                 repeated | (np.linalg.norm(np.cross(b - a, c - a), axis=1) < 1e-12)
217 |             )
218 |         )
219 |         directed = np.concatenate(
220 |             (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])
221 |         )
222 |         n = np.int64(len(verts))  # one int64 key per edge: np.unique on 1-D is far faster than axis=0
223 |         _, occurrences = np.unique(directed[:, 0] * n + directed[:, 1], return_counts=True)
224 |         result["inconsistent_edges"] = int(np.sum(occurrences - 1))
225 |         ends = np.sort(directed, axis=1)
226 |         _, occurrences = np.unique(ends[:, 0] * n + ends[:, 1], return_counts=True)
227 |         result["open_edges"] = int(np.count_nonzero(occurrences == 1))
228 |         result["non_manifold_edges"] = int(np.count_nonzero(occurrences > 2))
~~~

[ifc_to_fds/geometry/mesh.py:L650–L665](../../ifc_to_fds/geometry/mesh.py#L650-L665)

~~~text
650 |                         )
651 |                     )
652 |                     kind = "contact" if facing < 0 else "numerical_contact" if area < NUMERICAL_CONTACT_AREA_M2 else None
653 |                     if kind:
654 |                         if contacts is not None:
655 |                             entry = contacts.setdefault(kind, {"face_pairs": 0, "area_m2": 0.0})
656 |                             entry["face_pairs"] += 1
657 |                             entry["area_m2"] += float(area)
658 |                         continue
659 |                 if area > 0:
660 |                     return witness(
661 |                         "COPLANAR_FACE_OVERLAP",
662 |                         triangles=[int(i), int(j)],
663 |                         projected_area_m2=float(area),
664 |                     )
665 |                 # Exact coplanarity and zero projected area prove no interior
~~~

[ifc_to_fds/mapping/policy.py:L158–L166](../../ifc_to_fds/mapping/policy.py#L158-L166)

~~~text
158 |     if not element.mesh or not valid_solid(element.mesh):
159 |         return MappingStrategy.NONE
160 |     if not force_all_geom and element.boundary_policy != "SOURCE_SOLID_DOMAIN_INTERSECTION":
161 |         if not element.openings and is_axis_aligned_box(element.mesh):
162 |             return MappingStrategy.OBST
163 |         if box_sets_enabled() and is_obstruction_box_set(element.mesh) and _openings_are_cut(element):
164 |             return MappingStrategy.OBST  # rectilinear host, e.g. a wall whose openings are really open
165 |     return MappingStrategy.GEOM
166 |
~~~

**Quy tắc thể tích tại `8ed1f38`.** Trước hết kiểm số thành phần và khoảng cách bề mặt. Nếu có diện tích `Sref` và thể tích `Vref`, code tính `Vshell=Sref·surface_tolerance_m`. Sai số thể tích phải đạt ngưỡng tương đối hoặc đạt `relative_volume_error·Vref ≤ Vshell`. Tương tự, IoU phải đạt ngưỡng hoặc đạt `(1−IoU)·Vref ≤ Vshell`. Khi thiếu diện tích hoặc thể tích, dùng ngưỡng tương đối. Phép nhân với `Vref` trong nhánh IoU là đại lượng mà code dùng để so, khác công thức thể tích hiệu đối xứng chính xác cần thêm thể tích hợp.

[ifc_to_fds/validation/metrics.py:L188–L207](../../ifc_to_fds/validation/metrics.py#L188-L207)

~~~text
188 | def within_tolerance(m, config):
189 |     """True when a `compare_solids` result meets the audit tolerances.
190 |
191 |     Volume noise is judged by the thickness of the shell it would form: a volume or IoU gap is accepted when
192 |     it is no larger than `reference_area * surface_tolerance_m`. A gap of that size is not a smaller solid, it
193 |     is the same surface within tolerance. Measured on a real model (C): a 7.55 m3 insulation box whose source
194 |     vertices lie ~1e-7 m off the axes differs by 3.9e-6 m3 over 44.5 m2, a 0.09 um shell, yet a relative test
195 |     of 1e-9 called it DEVIATED. A 1 mm shift gives 1000x more volume and still fails.
196 |     """
197 |     if m["reference_components"] != m["output_components"] or m["surface_distance_m"] > config.surface_tolerance_m:
198 |         return False
199 |     volume, area = m.get("reference_volume_m3"), m.get("reference_area_m2")
200 |     shell = area * config.surface_tolerance_m if volume is not None and area is not None else 0.0
201 |     volume_ok = m["relative_volume_error"] <= config.relative_volume_tolerance or (
202 |         volume is not None and m["relative_volume_error"] * volume <= shell
203 |     )
204 |     iou_ok = m["solid_iou"] >= config.min_solid_iou or (
205 |         volume is not None and (1.0 - m["solid_iou"]) * volume <= shell
206 |     )
207 |     return volume_ok and iou_ok
~~~

Ca trong test lấy số liệu tổng hợp của C với `Vref≈7.55 m³`, `Sref≈44.5 m²`, chênh thể tích `3.9e-6 m³`. Sai số tương đối khoảng `5.17e-7` vượt mức `1e-9` cũ. Bề dày lớp vỏ quy đổi là `3.9e-6/44.5≈0.0876 µm`, trong mức 1 µm mới. Test ở HEAD đã qua cho ca này, ca chênh 1 mm, ca số thành phần lệch và ca thiếu diện tích/thể tích. Commit ghi 9 phần tử của C đạt dung sai mới. Phiên audit chỉ tái lập test và FZK công khai. Số của C lấy từ bằng chứng lịch sử và nội dung commit. [Số liệu C tại mốc trước](../evidence/production-roadmap/tolerance-A-C.json) · [Các ca hồi quy dung sai](../../tests/test_audit_hardening.py#L93-L120)

Cách kiểm `openings` gồm hai phép riêng. Phần dư là thể tích host còn lấn vào khối lỗ `O` chia cho `V(O)`. Phần thông qua lỗ là `P_ref = O \ ∪C_ref` và `P_out = O \ ∪C_out`, với `C` gồm các vật cản ứng viên kể cả fill. Code so `V(P_ref △ P_out)/V(O)` và số vùng thông rời. Nhánh đã chứng minh các vật cản bằng nhau trả sai khác 0, tránh nhiễu phép giao khi mặt trùng. Hằng `PASSAGE_NOISE_M` trong hồ sơ mở chỉ quy đổi nhiễu Boolean theo diện tích/thể tích lỗ. [Công thức phần thông](../../ifc_to_fds/validation/metrics.py#L307-L360) · [Kiểm host và lỗ](../../ifc_to_fds/validation/engine.py#L616-L669) · [Giới hạn nhiễu](../../ifc_to_fds/validation/metrics.py#L16-L22)

[ifc_to_fds/validation/metrics.py:L334–L359](../../ifc_to_fds/validation/metrics.py#L334-L359)

~~~text
334 |     a = free_volume(reference)
335 |     if _proven_same_obstacles(reference, output):
336 |         # Proven-equal obstacles leave the same passage. The Boolean A∩A is not exact
337 |         # for coincident faces (it lost 1.8-5.4% volume on FZK-Haus), so skip it.
338 |         components = len(a.split()) if len(a.faces) else 0
339 |         return dict(
340 |             source_free_volume_m3=float(a.volume),
341 |             output_free_volume_m3=float(a.volume),
342 |             normalized_symmetric_difference=0.0,
343 |             source_free_components=components,
344 |             output_free_components=components,
345 |         )
346 |     b = free_volume(output)
347 |     intersection = (
348 |         solid_boolean([a, b], "intersection") if len(a.faces) and len(b.faces) else None
349 |     )
350 |     overlap = mesh_volume(intersection) if intersection is not None else 0.0
351 |     return dict(
352 |         source_free_volume_m3=float(a.volume),
353 |         output_free_volume_m3=float(b.volume),
354 |         normalized_symmetric_difference=max(
355 |             0.0, float(a.volume + b.volume - 2 * overlap)
356 |         )
357 |         / max(float(void.volume), 1e-12),
358 |         source_free_components=len(a.split()) if len(a.faces) else 0,
359 |         output_free_components=len(b.split()) if len(b.faces) else 0,
~~~

**Đối chứng đo được.** Fixture `opening.ifc` có lỗ $1,0 \times 0,30 \times 2,1 = 0,63\,\mathrm{m^3}$. Cặp OBST của exporter phủ 1,08 + 1,89 = 2,97 m³. Hộp bao tường 4 × 0,30 × 3 = 3,60 m³. Đọc lại FDS cho `source_residual=0`, `output_residual=0`, thể tích thông 0,63 m³ ở cả hai phía, sai khác chuẩn hóa 0 và cùng 1 thành phần thông. Lưới thực ở ca này lần lượt là 0,20 m, 0,15 m và 0,20 m theo X/Y/Z. Normal Y và snap cho 5 × 11 ô tiếp tuyến. Lấy một hộp bao tường duy nhất sẽ lấp lại toàn bộ 0,63 m³ dù hình dáng cực trị giống nhau.

**FZK-Haus công khai.** Bản ứng viên có 127 record, gồm 79 `MATCHED`, 45 `SEMANTIC_ONLY`, 2 `REVIEW_REQUIRED` và 1 `UNSUPPORTED`. `REJECTED` vì solid nguồn của một `IfcStair` có 29 cạnh non-manifold, 58 cạnh hướng bất nhất và không có thể tích dương theo kiểm source. `geometry=FAIL`, `geometry_preservation=FAIL` còn `openings=PASS` và `air_path=PASS`. Witness self-intersection trong snapshot rỗng. Đối chiếu snapshot có 0 khác biệt trong các trường script so. Trích dẫn lịch sử `B-01` về 15/18 cửa lỗi giả cần gắn phiên bản cũ. Dữ liệu HEAD đo được cho thấy nguyên nhân từ chối hiện tại khác. [Mốc FZK](../evidence/production-roadmap/baseline-fzk.json) · [Các trường snapshot so sánh](../../scripts/verdict-snapshot.py#L23-L62)

### 3.3. Tính lưới và hình học sau FDS

Trên mỗi trục, code lấy `n=max(1,ceil(L/h))` và giữ `XB` từ miền. Bước ô thực `h_eff=L/n`, nên các trục có thể khác nhau. Bộ chia nhiều mesh dùng số ô toàn cục, chia đều theo phần nguyên và phần dư, rồi làm tròn biên phân vùng tới 6 chữ số thập phân. Cần xét độ phù hợp của bước lưới và seam trên deck cuối. F7 là sai số ở thương gần nguyên. F1 là lỗi khác trong xác minh miền khi đọc lại. [Bộ chia và giới hạn cell](../../ifc_to_fds/mapping/exporter.py#L93-L149) · [Tính biên phân vùng](../../ifc_to_fds/mapping/exporter.py#L151-L193)

Ví dụ phân tích quy mô của đề xuất `WP-09`. Với trục Z dài 7,32 m, h = 0,20 m thì K = 37 và ΔZ ≈ 0,19784 m. Nâng K lên 40 trên cùng miền cho ΔZ = 0,183 m. Giữ ΔZ = 0,20 m với K = 40 cần tăng miền thành 8,00 m, thêm 0,68 m. Nếu I = 90 và J = 80 thì số ô tăng từ 266.400 lên 288.000 (+8,11%). Dịch biên có thể đổi vị trí cell face, VENT và độ phân giải lỗ mở. NIST mô tả thừa số nhỏ trong J và K như hiệu suất của FFT mặc định. Solver xử lý I theo trục không dùng FFT. Hai deck đối chứng `IJK=4,4,37` và `4,4,40` cùng `XB=[0,1,0,1,0,7.32]` đã chạy FDS đến `T_END=0.05 s` và trả mã 0. Đây là chứng cứ chấp nhận IJK, còn hiệu năng cần đo với tải thực. [FDS User’s Guide 6.11.1, Choosing the Number of Cells](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L908-L920)

`effective_geometry` đọc lưới và bảng vật cản trong SMV, ghép các mảnh OBST theo ID, ghi VENT và OBST động. `GEOM` được đánh `INCONCLUSIVE` theo phần tử vì chưa đọc dữ liệu cut-cell. Một lỗi OBST/VENT đã đo vẫn có thể làm cổng `FAIL` trong deck lẫn GEOM. `HOLE` hiệu dụng chưa có adapter. Độ chính xác hình học deck, mặt sau snap và giữ đúng trao đổi khí là ba phép kiểm cần quan sát riêng. [Tổng hợp từ SMV](../../ifc_to_fds/validation/effective.py#L86-L178) · [Test solver/SMV và độ chính xác in](../../tests/test_effective_elements.py#L20-L90)

[ifc_to_fds/validation/effective.py:L98–L115](../../ifc_to_fds/validation/effective.py#L98-L115)

~~~text
 98 |     meshes = [r for r in parsed.records if r.kind == "MESH"]
 99 |     if not meshes:
100 |         return GateResult(
101 |             status=GateStatus.INCONCLUSIVE,
102 |             reason="No MESH namelists found in FDS input",
103 |         )
104 |     obstructions = [r for r in parsed.primitives if r.kind == "OBST"]
105 |     # What the SMV cannot confirm is reported per element and never hides a verified failure elsewhere.
106 |     elements = {
107 |         r.id or "GEOM": dict(kind="GEOM", status="INCONCLUSIVE", reason="GEOM cut-cell output is not read from the SMV")
108 |         for r in parsed.records
109 |         if r.kind == "GEOM"
110 |     }
111 |     dynamic = {r.id for r in obstructions if "DEVC_ID" in r.values or "CTRL_ID" in r.values}
112 |     vents = [r for r in parsed.records if r.kind == "VENT"]
113 |     expected = {r.id: r.values["XB"] for r in obstructions}
114 |     lines = smv_text.splitlines()
115 |     evidence = {"smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(), "smv_lines": len(lines)}
~~~

[ifc_to_fds/validation/effective.py:L162–L177](../../ifc_to_fds/validation/effective.py#L162-L177)

~~~text
162 |     evidence["elements"] = elements
163 |     evidence["dynamic_obstructions"] = sorted(dynamic)
164 |     clearance = _check_clearances(expected, actual, evidence, dynamic)
165 |     if clearance.status != GateStatus.PASS:
166 |         return clearance
167 |     failed = [f"{i}: {e['reason']}" for i, e in elements.items() if e["status"] == "FAIL"]
168 |     unknown = [f"{i}: {e['reason']}" for i, e in elements.items() if e["status"] == "INCONCLUSIVE"]
169 |     verified = sum(e["status"] == "PASS" for e in elements.values()) + len(actual)
170 |     if failed:
171 |         return GateResult(status=GateStatus.FAIL, reason="; ".join(failed[:5]), evidence=evidence)
172 |     if unknown:
173 |         return GateResult(
174 |             status=GateStatus.INCONCLUSIVE,
175 |             reason=f"{len(unknown)} element(s) not verifiable ({'; '.join(unknown[:3])}); {verified} OBST/VENT verified",
176 |             evidence=evidence,
177 |         )
~~~

### 3.4. Gate, dữ liệu thiếu và ý nghĩa verdict

`MAPPING_GATE_ORDER` có 12 gate cốt lõi. Báo cáo `tiny_acceptance_report.json` ghi 20 gate sau khi ghép HVAC, mesh, effective, đối chứng package, placement và golden. Số gate cụ thể phụ thuộc lớp kiểm và profile. Khi thiếu solver, lệnh Verified có thể trả `MAPPING_VERIFIED` trong lúc `solver` và `effective_geometry` là `INCONCLUSIVE`. Cơ chế kết luận simulation hiện chỉ sinh `REJECTED` hoặc `INCONCLUSIVE`. `COMPLETED` là trạng thái thực thi job, do đó cần đọc `mapping_status` và `simulation_status` riêng. [Danh sách gate](../../ifc_to_fds/domain/validation/model.py#L31-L70)

[ifc_to_fds/domain/validation/model.py:L235–L258](../../ifc_to_fds/domain/validation/model.py#L235-L258)

~~~text
235 |         if failed:
236 |             self.mapping_status = AcceptanceStatus.REJECTED
237 |         elif mandatory_complete and required and all(
238 |             g.status in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
239 |             and (g.status != GateStatus.NOT_APPLICABLE or g.reason.strip())
240 |             for g in required
241 |         ):
242 |             self.mapping_status = AcceptanceStatus.MAPPING_VERIFIED
243 |         else:
244 |             self.mapping_status = AcceptanceStatus.INCONCLUSIVE
245 |         sim_failed = any(
246 |             g.status == GateStatus.FAIL
247 |             for name, g in self.gates.items()
248 |             if name in simulation
249 |         )
250 |         self.simulation_status = (
251 |             AcceptanceStatus.REJECTED
252 |             if sim_failed or failed
253 |             else AcceptanceStatus.INCONCLUSIVE
254 |         )
255 |         self.status = (
256 |             self.simulation_status
257 |             if self.requested_level == "simulation"
258 |             else self.mapping_status
~~~

Roadmap A4.1 từng ghi deck thiếu vật cản có `geometry=PASS`. HEAD đếm `MISSING` và tạo finding traceability P0 với deck thiếu OBST. Khi không có đối chiếu solid nào hoàn thành, code hạ `geometry` xuống `INCONCLUSIVE`. Test thiếu toàn bộ OBST đã qua trong đợt audit. Một `xfail` nghiêm ngặt còn lại thuộc việc đưa primitive scenario vào kiểm truy nguyên deck nền. Đường vận hành hiện audit nền trước khi compose scenario và kiểm artifact kịch bản qua hợp đồng riêng. [Đếm vật cản thiếu](../../ifc_to_fds/validation/engine.py#L559-L569) · [Làm rõ thiếu đối chiếu](../../ifc_to_fds/validation/engine.py#L673-L684) · [Xfail scenario](../../tests/test_validation_engine.py#L301-L319)

## 4. Đồ thị MEP → mạng HVAC và đối chiếu thủy lực

### 4.1. Hiện trạng từ graph nguồn đến FDS

| Bước | Dữ liệu và rào chắn |
|---|---|
| Đọc graph IFC | Qua `IfcRelAssignsToGroup` để lấy nhóm/system và bằng chứng phân loại. Owner port đến từ `IfcRelConnectsPortToElement` hoặc `IfcRelNests`. `IfcRelConnectsPorts` cung cấp edge, ID khóa theo SHA nguồn/STEP và lưu hướng `FlowDirection`. [Đọc graph](../../ifc_to_fds/mep/mep_graph.py#L19-L165) |
| Lựa chọn | Chỉ đối tượng thông gió/hút khói thuộc scope và có quyết định `HVAC`. Tách hiện diện nguồn, giữ ngữ nghĩa, vật cản thụ động và mạng 1D vận hành. `FIRE_SUPPRESSION`/`PLUMBING` không tự vào HVAC khí. [Thống kê theo hệ](../../ifc_to_fds/application/services/audit_mep_coverage.py#L43-L85) · [Bộ lọc loại](../../ifc_to_fds/mep/network.py#L15-L43) |
| Gom node | Union-find gom cặp port có cạnh `EXPLICIT_IFC`, vị trí trong dung sai kết nối hiện hành. Vị trí giống nhau đơn thuần không tạo cạnh. Mỗi nhóm có ID băm ổn định từ danh sách khóa đã sắp, kèm provenance nhiều phần tử. [Union-find và biên](../../ifc_to_fds/mep/network.py#L55-L100) |
| Segment và fitting hai cổng | `DuctSpec` cần `diameter_m` hoặc cả `area_m2/perimeter_m` với giá trị hữu hạn. Đoạn thẳng có thể dùng dây cung. Fitting cần chiều dài tâm và `loss` đã duyệt. `LOSS` bất đối xứng cần hướng nguồn. [Schema](../../ifc_to_fds/domain/mep/hvac.py#L29-L52) · [Chiều dài và hướng](../../ifc_to_fds/mep/network.py#L119-L133) |
| Tee/Y/take-off | `JunctionSpec` mô hình hóa từ 3 đến 10 port thành một NODE. Mỗi port cần đúng một duct nguồn kề. Với k port phải có k(k−1) tổn thất theo cặp có thứ tự, ví dụ k=3 cần 6 giá trị. Mã map từng cặp sang vị trí 1-based của `DUCT_ID`. X, Y, Z của NODE dùng trung bình tọa độ các port. [Junction](../../ifc_to_fds/mep/network.py#L136-L162) |
| Quạt và đầu biên | Quạt đã duyệt được phát thành DUCT áp đặt `VOLUME_FLOW`, gắn `SINK/SOURCE`. Biên `AMBIENT` và `VENT` cần khai báo riêng. Quạt có đường đặc tính, van, lọc, aircoil và VENT ghép GEOM cần hợp đồng mới nếu muốn chuyển tự động. [Quạt đã duyệt](../../ifc_to_fds/mep/network.py#L36-L43) · [Serializer HVAC](../../ifc_to_fds/mep/fds_records.py#L4-L33) |
| Kiểm toán lại | Checker dựng plan với graph/decision đọc lại, so giá trị, ID, tập node/duct/vent và danh sách khóa trong manifest. `hvac=PASS` chứng minh bản ghi phù hợp với kế hoạch. Tổn áp và lưu lượng dùng solver và đối chứng riêng. F2 minh họa lỗi dùng chung giả định hỗ trợ mặt. [Checker](../../ifc_to_fds/validation/checkers/hvac.py#L33-L64) |

[ifc_to_fds/mep/network.py:L21–L43](../../ifc_to_fds/mep/network.py#L21-L43)

~~~text
 21 |     for e in selected:
 22 |         declared_type = (e.type_class or e.ifc_type).upper().removesuffix("TYPE")
 23 |         if declared_type not in SEGMENT_TYPES + FITTING_TYPES + FAN_TYPES or e.mep_category not in ("VENTILATION", "SMOKE_EXTRACT"):
 24 |             raise ValueError(f"HVAC requires a ventilation duct segment, two-port fitting or fixed-flow fan: {e.entity_key}")
 25 |         if e.decision.get("action") != "HVAC" or not e.decision.get("hvac"):
 26 |             raise ValueError(f"HVAC requires reviewed duct parameters and endpoint boundaries: {e.entity_key}")
 27 |         spec = hvac_spec(e.decision["hvac"])
 28 |         if isinstance(spec, JunctionSpec):
 29 |             if declared_type not in FITTING_TYPES or not 3 <= len(e.ports) <= 10:
 30 |                 raise ValueError(f"HVAC junction losses belong to a fitting with three to ten ports: {e.entity_key}")
 31 |             junctions[e.entity_key] = spec
 32 |         else:
 33 |             specs[e.entity_key] = spec
 34 |             if len(e.ports) != 2:
 35 |                 raise ValueError(f"HVAC duct requires exactly two source ports; a tee, wye or take-off needs reviewed junction losses: {e.entity_key}")
 36 |             if declared_type in FITTING_TYPES and (spec.loss is None or spec.length_m is None):
 37 |                 raise ValueError(f"HVAC fitting needs reviewed loss coefficients and centreline length; the port chord is not its length: {e.entity_key}")
 38 |             directions = {(getattr(p, "flow_direction", None) or "").upper() for p in e.ports}
 39 |             if declared_type in FITTING_TYPES and spec.loss[0] != spec.loss[1] and directions != {"SINK", "SOURCE"}:
 40 |                 raise ValueError(f"HVAC fitting with different forward/reverse losses needs SINK/SOURCE port directions: {e.entity_key}")
 41 |             if declared_type in FAN_TYPES:
 42 |                 if spec.volume_flow_m3_s is None or directions != {"SINK", "SOURCE"}:
 43 |                     raise ValueError(f"HVAC fan needs a reviewed volume flow and SINK/SOURCE port directions; direction is never inferred: {e.entity_key}")
~~~

[ifc_to_fds/mep/network.py:L63–L77](../../ifc_to_fds/mep/network.py#L63-L77)

~~~text
 63 |     for edge in model.mep_graph.connections:
 64 |         a, b = edge.source_port_id, edge.target_port_id
 65 |         if a in ports and b in ports:
 66 |             if edge.relation_type != "EXPLICIT_IFC":
 67 |                 raise ValueError("HVAC topology requires explicit IFC port relationships")
 68 |             if math.dist(ports[a].world_position, ports[b].world_position) > PORT_POSITION_TOLERANCE_M:
 69 |                 raise ValueError("Connected HVAC ports disagree in world position")
 70 |             parent[find(b)] = find(a)
 71 |     for entity_key in junctions:  # all ports of a junction are one FDS node
 72 |         own = [k for k in ports if owners[k] == entity_key]
 73 |         for key in own[1:]:
 74 |             parent[find(key)] = find(own[0])
 75 |     groups = {}
 76 |     for key in sorted(ports):
 77 |         groups.setdefault(find(key), []).append(key)
~~~

[ifc_to_fds/mep/network.py:L150–L162](../../ifc_to_fds/mep/network.py#L150-L162)

~~~text
150 |     if sorted(neighbour.values()) != attached:
151 |         raise ValueError(f"Each HVAC junction port needs its own duct: {entity_key}")
152 |     given = {(x.from_port, x.to_port): x.k for x in spec.losses}
153 |     expected = {(a, b) for a in own for b in own if a != b}
154 |     if set(given) != expected:
155 |         raise ValueError(
156 |             f"HVAC junction needs one reviewed loss for every ordered port pair: {entity_key}; "
157 |             f"missing {len(expected - set(given))}, unknown {len(set(given) - expected)}"
158 |         )
159 |     position = {duct: index + 1 for index, duct in enumerate(attached)}
160 |     loss = sorted((position[neighbour[a]], position[neighbour[b]], k) for (a, b), k in given.items())
161 |     centre = tuple(sum(ports[k].world_position[axis] for k in own) / len(own) for axis in range(3))
162 |     return centre, loss
~~~

[ifc_to_fds/mep/fds_records.py:L18–L32](../../ifc_to_fds/mep/fds_records.py#L18-L32)

~~~text
 18 |         for i, j, k in node.junction_loss:
 19 |             values[f"LOSS({i},{j})"] = [k]
 20 |         records.append(("HVAC", values, node.entity_keys))
 21 |     for duct in plan.ducts:
 22 |         spec = duct.spec
 23 |         values = dict(TYPE_ID=["DUCT"], ID=[duct.id], NODE_ID=list(duct.node_ids), LENGTH=[duct.length_m], ROUGHNESS=[spec.roughness_m])
 24 |         if spec.diameter_m is not None:
 25 |             values["DIAMETER"] = [spec.diameter_m]
 26 |         else:
 27 |             values.update(AREA=[spec.area_m2], PERIMETER=[spec.perimeter_m])
 28 |         if spec.volume_flow_m3_s is not None:
 29 |             values["VOLUME_FLOW"] = [spec.volume_flow_m3_s]
 30 |         if spec.loss is not None:
 31 |             values["LOSS"] = list(spec.loss)
 32 |         records.append(("HVAC", values, [duct.entity_key]))
~~~

Bám hợp đồng của repo, hồ sơ MEP nên đọc bốn khái niệm theo tuần tự. `SOURCE_EXISTS` xác nhận có thực thể IFC. `SEMANTIC_PRESERVED` giữ định danh, phân loại và quan hệ. `GEOMETRY_MAPPED` yêu cầu có biểu diễn hình học đã kiểm. `FUNCTIONALLY_MODELED` có hành vi CFD hay mạng vận hành được cấu hình và cần tiếp tục kiểm solver theo vai trò. Mã báo đếm `source_count`, `semantic_only`, `geometry_verified`, `operational_configured` và `operational_verified` theo category. Ví dụ ống chữa cháy có thể được lưu hình học nguồn, đầu báo/sprinkler có thể được kiểm kê, nhưng chưa thể suy ra flow, control, nhiệt độ kích hoạt hoặc phun nước từ danh mục đối tượng. [Bộ đếm MEP](../../ifc_to_fds/application/services/audit_mep_coverage.py#L43-L88)

### 4.2. Công thức đối chứng và kiểm tra đề xuất gộp nhánh

Tại nút, cân bằng khối lượng cho các duct có chiều quy ước là `Σ σᵢⱼ ρⱼ Qⱼ = 0`. Với khí cùng mật độ trong đối chứng ổn định, `Σ σᵢⱼ Qⱼ = 0`. Trên duct, dùng Darcy–Weisbach với `u=Q/A` để tính độ lớn tổn áp `Δp=ρu²(f L/D + K)/2`. `f`, `L`, `D`, `K` lần lượt là hệ số ma sát, chiều dài, đường kính dùng trong phương trình và tổng hệ số tổn thất cục bộ theo chiều. Tại nhánh đảo dòng, bộ solver dùng hệ số `LOSS` chiều ngược. Với tiết diện tròn `A=πD²/4`, `P=πD`. Với tiết diện chữ nhật `A=WH`, `P=2(W+H)`, `Dₕ=4A/P=2WH/(W+H)`. [Phép tính tay trong test](../../tests/test_hvac_fds_pressure.py#L22-L39) · [FDS 6.11.1, cách cập nhật LOSS và ma sát](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/hvac.f90#L2740-L2778)

Nếu gộp các đoạn nối tiếp ở cùng Q và cùng ρ về tiết diện `Aref`, tổn thất cục bộ cần quy đổi `Kᵢ(Aref/Aᵢ)²`. Với Aref = 0,40 m², Ai = 0,20 m² và K = 0,50 thì phần đóng góp bằng 2,00. Bảo toàn tổng tổn áp còn phải trừ phần ma sát solver sẽ tính cho nhánh đã gộp. Công thức đối chứng tại điểm Q dùng để hiệu chỉnh là

$$
K_\mathrm{eq}(Q) =
\sum_i \left[f_i(Q)L_i/D_i+K_i(Q)\right]\left(A_\mathrm{ref}/A_i\right)^2
- f_\mathrm{ref}(Q) L_\mathrm{eq}/D_\mathrm{ref}.
$$

Ví dụ tổng hợp với `f=0.018` ở điểm so, `L₁=8 m`, `L₂=4 m`, hai tiết diện 0,40 và 0,20 m², chu vi 2,60 và 1,80 m. `D₁=0.61538 m`, `D₂=0.44444 m`. Hai phần ma sát quy về Aref là `0.234 + 0.648 = 0.882`. Một nhánh dùng `L_eq=12 m` và D₁ chỉ tính `0.351`. Thiếu `0.531` nếu code cộng mỗi `K_local` đã quy đổi. Ở `ρ=1.2 kg/m³` và `Q=0.8 m³/s`, `u_ref=2 m/s` nên phần thiếu tương đương `1.2744 Pa`. Hệ số này thay đổi theo điểm làm việc nếu f đổi theo Re. Thu gom thêm quạt hoặc damper sẽ dẫn đến khác biệt về điều khiển, chiều dòng và provenance.

Các đoạn code đính kèm tính được phần cục bộ, song vòng `541–549` của A1 chỉ cộng `k_forward_at_ref_area`, `k_reverse_at_ref_area`, còn constructor cuối trả một `roughness_m` và `length_m` chung. Công thức ở dòng A1:27 cũng chỉ khớp khi phần hiệu chỉnh ma sát đã tính tương đương với `f_ref L_eq/D_ref`. Cần rà diện tích tham chiếu cho từng K và quy đổi riêng từng chiều trước khi dùng đề xuất này. Code HEAD giữ duct cho từng phần tử hai cổng, vì thế tránh bước thu gọn làm mất dữ liệu trên.

Đối với cút 90° với `R_c=0.6154 m`, cút tròn tiếp tuyến lý tưởng có `L_arc=R_c π/2≈0.9667 m`. Công thức dây cung chỉ áp dụng cho cung tròn tương ứng hai tiếp tuyến, cần dữ liệu hình học khác khi có cổ thẳng, offset hoặc cút ghép. Dùng đúng biểu thức mã giả A1:411, 419 và 423 với `f=0.018`, `R_c/D_h=1`, `W/H=1.6` thì `K90≈0.23827`, `Cθ=1.05`, `Crect=1.03`, suy ra `K≈0.25769`. Ví dụ A1:601 ghi 0,247. Sự khác biệt này độc lập với việc kiểm chứng nguồn hệ số. Tham số tự chèn như `K=0.04`, độ nhám mặc định của một vật liệu và chiều dài sàn tối thiểu trong mã giả cần được duyệt theo hệ thực.

`MAX_FLOW` và `MAX_PRESSURE` của quạt bậc hai là hai đầu trên đường đặc tính. Với số liệu mẫu A1 `MAX_FLOW=5 m³/s, MAX_PRESSURE=600 Pa`, solver mô hình hóa 5 m³/s tại 0 Pa và 0 m³/s tại 600 Pa. Một điểm ghi 5 m³/s ở 600 Pa cần dữ liệu hiệu chỉnh bổ sung, theo đường quạt thiết kế. Thuật toán HEAD nhận lưu lượng áp đặt đã duyệt, một lựa chọn khác về vật lý. [FDS User’s Guide 6.11.1, Fan Parameters](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L3523-L3545)

### 4.3. Đo FDS từ các fixture HVAC

Lấy dòng CSV cuối của các ca `test_hvac_fds_pressure.py` và `test_hvac_junction.py` ở 30 s. Dấu của từng giá trị là chiều tương đối với `NODE_ID`. Các bộ giải kiểm áp và lưu lượng bằng phép tính tay tách khỏi exporter.

| Ca | Đối chứng | FDS đo lại ở 30 s |
|---|---|---|
| Ống tròn, nhánh thuận | `Q=+0.2 m³/s`, tổn thất thuận `K=0.4` | `Q=0.19997626 m³/s`, `p_a−p_out=12.02 Pa` |
| Ống tròn, nhánh đảo | `Q=−0.2 m³/s`, tổn thất ngược `K=1.2` | `Q=−0.19998976 m³/s`, `p_a−p_out=−23.97 Pa` |
| `ROUGHNESS=0`, `LOSS=0` | Tổn thất thành ống bằng 0 trong solver này | `Q=0.20000000 m³/s`, `Δp=0 Pa` |
| Tee chia | Với `Q_in=0.3 m³/s`, hai nhánh cùng A và `K_i Q_i²` bằng nhau cho 0,10 và 0,20 m³/s | `0.099999617 + 0.19999793 = 0.299997547 m³/s`, lệch 2,453 × 10⁻⁶ m³/s |
| Tee nhập | Hai nhánh có trị tuyệt đối 0,10 và 0,20 m³/s | `Q_stem=−0.29999668 m³/s`, chênh bảo toàn theo trị tuyệt đối 3,32 × 10⁻⁶ m³/s |

Repo đã có finding `HVAC-FRICTION-0001` cho `ROUGHNESS=0` và `HVAC-FRICTION-0002` cho tiết diện không tròn. Manual tại đoạn mô tả độ nhám nói giá trị 0 tính ma sát ống trơn, còn mã và đối chứng FDS 6.11.1 cấp nhánh ma sát 0 khi `ROUGHNESS ≤ 0`. Phiên bản solver thực thi là căn cứ cho mẫu này. [Finding trong repo](../../ifc_to_fds/validation/checkers/hvac.py#L11-L29) · [Test ma sát bằng 0](../../tests/test_hvac_fds_pressure.py#L96-L100) · [Manual](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L3435-L3443) · [Mã solver](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/hvac.f90#L2740-L2756)

### F9 — Thiếu ROUND=.FALSE. làm FDS đọc ống chữ nhật như tiết diện tròn tương đương (P2)

`fds_records.network_records` phát `AREA/PERIMETER` nhưng để `ROUND` theo mặc định của FDS. FDS 6.11.1 dùng `sqrt(4A/π)` trong nhánh round, chỉ dùng `4A/P` ở nhánh tổng quát khi không cung cấp đường kính. Repo đã cảnh báo `HVAC-FRICTION-0002` và roadmap A3 ghi chênh khoảng 18%. Ca dưới đây cô lập được cờ namelist gây ra chênh lệch. [Mặc định và nhánh hình dạng FDS](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/hvac.f90#L270-L302)

[ifc_to_fds/mep/fds_records.py:L21–L32](../../ifc_to_fds/mep/fds_records.py#L21-L32)

~~~text
 21 |     for duct in plan.ducts:
 22 |         spec = duct.spec
 23 |         values = dict(TYPE_ID=["DUCT"], ID=[duct.id], NODE_ID=list(duct.node_ids), LENGTH=[duct.length_m], ROUGHNESS=[spec.roughness_m])
 24 |         if spec.diameter_m is not None:
 25 |             values["DIAMETER"] = [spec.diameter_m]
 26 |         else:
 27 |             values.update(AREA=[spec.area_m2], PERIMETER=[spec.perimeter_m])
 28 |         if spec.volume_flow_m3_s is not None:
 29 |             values["VOLUME_FLOW"] = [spec.volume_flow_m3_s]
 30 |         if spec.loss is not None:
 31 |             values["LOSS"] = list(spec.loss)
 32 |         records.append(("HVAC", values, [duct.entity_key]))
~~~

[tests/test_hvac_fds_pressure.py:L109–L117](../../tests/test_hvac_fds_pressure.py#L109-L117)

~~~text
109 |     flow, area, perimeter = 0.5, 0.15, 1.6
110 |     section = dict(area_m2=area, perimeter_m=perimeter)
111 |     drop, _ = run(network(flow, section, loss=(0.0, 0.0)), tmp_path)
112 |     equivalent = math.sqrt(4 * area / math.pi)
113 |     hydraulic = 4 * area / perimeter
114 |     as_fds = sum(hand_drop(flow, equivalent, length, 5e-4, 0.0, area) for length in (3.0, 0.5))
115 |     textbook = sum(hand_drop(flow, hydraulic, length, 5e-4, 0.0, area) for length in (3.0, 0.5))
116 |     assert drop == pytest.approx(as_fds, rel=0.05), (drop, as_fds)
117 |     assert abs(textbook - drop) / textbook > 0.05, (drop, textbook)
~~~

**Ca tái hiện.** Dùng deck của `test_rectangular_duct_friction_uses_the_equivalent_round_diameter_not_the_hydraulic_one`. Tiết diện 0,50 × 0,30 m, A = 0,15 m², P = 1,60 m, Q = 0,50 m³/s và độ nhám 0,0005 m. Phần so áp kiểm 3,5 m ống và `K=0`. Chạy tuần tự deck gốc và bản chỉ thêm `ROUND=.FALSE.` vào các DUCT có `AREA=0.15,PERIMETER=1.6`. Cả hai chạy hết 30 s.

| Deck | D dùng cho ma sát | Darcy–Weisbach / Colebrook đối chứng | FDS tại 30 s |
|---|---:|---:|---:|
| Hiện hành, mặc định round | 0,437019 m | 1,21358 Pa | 1,20 Pa |
| Chỉ thêm `ROUND=.FALSE.` | 0,375000 m | 1,47002 Pa | 1,46 Pa |

Deck hiện hành thấp hơn khoảng 18,37% so với tính tay theo 4A/P. Sau khi dùng nhánh tiết diện tổng quát, chênh với đối chứng khoảng 0,68% từ CSV. `ROUND` đã có trong danh sách trường HVAC mà parser nhận. Các trường đo của fixture solver (một số `DEVC` và `DUMP`) nằm ngoài phần cú pháp mà parser Verified của repo dùng cho deck nền. Hậu quả ở bài toán tính tổn áp/phân lưu. Lưu lượng áp đặt của chính ca này vẫn gần 0,50 m³/s. [Trường được parser nhận](../../ifc_to_fds/validation/parser.py#L380-L431) · [Việc mở trong roadmap](../plans/production-roadmap.md#L40-L46)

**Sửa tối thiểu đề xuất.** Chốt cách dùng `ROUND=.FALSE.` cho `AREA/PERIMETER` của tiết diện tổng quát đã duyệt. Giữ nhánh `DIAMETER` của ống tròn và đổi test đối chứng áp. Xử lý deck đã lưu theo phiên bản policy/compatibility bởi checker hiện so đúng tập tham số namelist. Kiểm thêm ca round legacy, ca dòng ngược và ca ảnh hưởng phân lưu. Các ca trên ống thật vẫn cần thông số nhám và tổn thất từ thiết kế.

## 5. Nguồn cháy EV, kiểm định nhiệt và nghiên cứu lưới

`load_verified_scenario_base` yêu cầu bundle SHA-256 hợp lệ, manifest tự tính lại đúng hash, `output_complete` và nền `MAPPING_VERIFIED`. Sau đó gọi verifier của artifact và tái dựng hình học đã phát để kiểm vị trí xe, va chạm và kích thước nguồn. Manifest dẫn lại IFC và nền đã duyệt. `scenario.fds` phát thêm thẻ phản ứng, ramp, bề mặt nguồn, VENT đốt và điều khiển cửa trên các fill đã nhận diện. [Tải nền](../../ifc_to_fds/application/services/scenario_base.py#L101-L145) · [Test nguồn và sự kiện cửa](../../tests/test_scenario_integrity.py#L308-L377)

[ifc_to_fds/application/services/scenario_base.py:L118–L133](../../ifc_to_fds/application/services/scenario_base.py#L118-L133)

~~~text
118 |     for directory in sorted(Path(job_root).iterdir()):
119 |         path = directory / "model_manifest.json"
120 |         if not directory.is_dir() or not path.is_file():
121 |             continue
122 |         raw = json.loads(path.read_text(encoding="utf-8"))
123 |         if raw.get("bundle_sha256") != bundle_sha:
124 |             continue
125 |         manifest = MappingManifest.model_validate(raw)
126 |         if (
127 |             manifest.compute_bundle_sha256() != bundle_sha
128 |             or not manifest.output_complete
129 |             or manifest.mapping_acceptance != "MAPPING_VERIFIED"
130 |         ):
131 |             raise ValueError("Base artifact is unsealed or not MAPPING_VERIFIED")
132 |
133 |         verify_candidate(directory)
~~~

### 5.1. Đường cong HRR và năng lượng

- Code lấy đỉnh MW nhân 1.000 để đổi sang kW, rồi chia cho diện tích VENT đốt để tính `HRRPUA` (kW/m²). Nếu có `hrr_curve_kw` và tài liệu nguồn, từng điểm được chuẩn hóa thành `Fᵢ=Qᵢ/Q_peak`, cộng offset thời gian rồi phát `RAMP`. Năng lượng từ chuỗi tuyến tính từng đoạn là `Σ(tᵢ₊₁−tᵢ)(Qᵢ+Qᵢ₊₁)/2/1000` MJ. Với đường giả lập `t²`, phần phát triển lý tưởng đóng góp `Q_peak t_growth/3` kJ. Phần giữ đỉnh và suy giảm tuyến tính đóng góp lần lượt `Q_peak t_plateau` và `Q_peak t_decay/2`. Việc đọc lại tích phân từ RAMP đã serialize bắt được chênh do lấy mẫu, làm tròn hoặc cắt ở `T_END`. [Phát HRR](../../ifc_to_fds/fire/scenario_emitter.py#L453-L520) · [Đọc lại ngân sách](../../ifc_to_fds/fire/physics_assessment.py#L44-L89)
- Ví dụ tính tay với 3 điểm tổng hợp (0 s, 0 kW), (20 s, 60 kW), (40 s, 0 kW), mỗi đoạn tích phân 600 kJ, tổng 1,20 MJ. Năng lượng danh định nguồn khác điện năng pin ghi nhãn. Ngân sách hóa học cần cả phần pin lẫn nội thất, lốp và vật liệu khác theo hồ sơ nguồn. Cổng có `energy_budget_status=PASS` nếu giá trị danh định nằm trong ngân sách. `physics_status` vẫn `INCONCLUSIVE` khi bước này đạt.
- Hai nhánh phản ứng đang phát công thức đại diện `C=2.0, H=4.0, O=1.0` và các yield CO/soot. `reference-cases/ev-library/auto-nmc.json` có chú dẫn tổng quát và khoảng yield HF. `physics_assessment` báo `hf_status=NOT_MODELED`. Thư viện có số liệu tham khảo cho HF nhưng đường chuyển đổi đang thiếu nguồn phát HF/HCN được xác nhận. Phát lại HRR đã đo không đồng thời xác minh thành phần khói, truyền nhiệt vật liệu, cháy lan giữa xe hoặc QoI thoát nạn. [Phản ứng](../../ifc_to_fds/fire/scenario_emitter.py#L404-L441) · [Preset NMC](../../reference-cases/ev-library/auto-nmc.json#L2-L25) · [Trạng thái vật lý](../../ifc_to_fds/fire/physics_assessment.py#L70-L91)

[ifc_to_fds/fire/scenario_emitter.py:L461–L479](../../ifc_to_fds/fire/scenario_emitter.py#L461-L479)

~~~text
461 |         hrrpua_kw_m2 = (actual_peak_hrr * 1000.0) / burning_area
462 |
463 |         ramp_id = clean_fds_id(f"RAMP_EV_{idx}")
464 |         surf_id = clean_fds_id(f"BURNER_EV_{idx}")
465 |         obst_id = clean_fds_id(f"OBST_EV_{idx}")
466 |         vent_id = clean_fds_id(f"VENT_BURNER_{idx}")
467 |
468 |         t_delay = round(ev.ignition_delay_s, 2)
469 |         q_peak_kw = actual_peak_hrr * 1000.0
470 |         if ev.hrr_curve_kw is not None:
471 |             curve = ev.hrr_curve_kw
472 |             e_total_mj = sum((t2 - t1) * (q1 + q2) / 2 for (t1, q1), (t2, q2) in zip(curve, curve[1:])) / 1000.0
473 |             lines.append(f"! Fire Curve: {ramp_id} replays a measured HRR curve ({len(curve)} points, delay={t_delay:.2f}s)")
474 |             lines.append(f"! HRR curve source: {ev.hrr_curve_source.strip()}")
475 |             lines.append(f"! Energy balance: total fire curve energy = {e_total_mj:.1f} MJ, nominal battery pack = {actual_kwh * 3.6:.1f} MJ")
476 |             if t_delay > 0:
477 |                 lines.append(f"&RAMP ID='{ramp_id}', T=0.000, F=0.000000 /")
478 |             for t, q in curve:
479 |                 lines.append(f"&RAMP ID='{ramp_id}', T={t_delay + t:.3f}, F={q / q_peak_kw:.6f} /")
~~~

[ifc_to_fds/fire/physics_assessment.py:L68–L91](../../ifc_to_fds/fire/physics_assessment.py#L68-L91)

~~~text
 68 |     total = math.fsum(vehicle_energy)
 69 |     total_within_t_end = math.fsum(vehicle_energy_within_t_end)
 70 |     limit = budget.battery_chemical_energy_mj + budget.other_vehicle_energy_mj if budget else None
 71 |     if limit is not None and not math.isfinite(limit):
 72 |         raise ValueError("Total vehicle energy budget must be finite")
 73 |     status = "INCONCLUSIVE" if limit is None else "FAIL" if total > limit else "PASS"
 74 |     reasons = {
 75 |         "INCONCLUSIVE": "No sourced chemical energy budget for the whole vehicle fleet",
 76 |         "FAIL": "Nominal burner energy exceeds the declared fleet budget",
 77 |         "PASS": "Nominal burner energy is within the declared fleet budget",
 78 |     }
 79 |     return {
 80 |         "status": "FAIL" if status == "FAIL" else "INCONCLUSIVE",
 81 |         "energy_budget_status": status,
 82 |         "energy_reason": reasons[status],
 83 |         "nominal_energy_mj": total,
 84 |         "nominal_energy_within_t_end_mj": total_within_t_end,
 85 |         "vehicle_energy_mj": vehicle_energy,
 86 |         "energy_basis": "Serialized HRRPUA and vent area before solver grid snapping",
 87 |         "budget": budget.model_dump() if budget else None,
 88 |         "hf_status": "NOT_MODELED",
 89 |         "hf_library_yield_ranges": bundle.hf_preset_yields,
 90 |         "ev_library_digest": bundle.ev_library_digest,
 91 |     }
~~~

Các bề mặt `CONCRETE`, `STEEL` và `GLASS` của deck nền hiện chủ yếu đặt tên, màu và độ trong suốt. Mô hình vật liệu truyền nhiệt cần thông số `MATL`, chiều dày và liên kết `SURF` thích hợp. Sai số nhiệt độ lớp khói phụ thuộc thời gian và điều kiện biên thực. Cần số liệu kiểm chứng trước khi định lượng. [Bề mặt của deck nền](../../ifc_to_fds/mapping/exporter.py#L295-L301) · [FDS User’s Guide 6.11.1, Thermal Boundary Conditions](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L1917)

### 5.2. D*/Δx và kiểm độ nhạy thật

Công thức của NIST là `D* = [Q̇/(ρ∞ c_p T∞ √g)]^(2/5)`. Dùng kW và kJ/(kg·K) nhất quán. Với nguồn minh họa `Q̇=2000 kW`, hàm tại HEAD cho `D*=1.264922 m`. Lưới 0,20 m cho `D*/Δx=6.3246` và lưới 0,10 m cho `12.6492`. Tỷ số giúp mô tả mức phân giải vùng plume. Tính trạng thái lỗ mở, dòng qua HVAC, dầm cản khói và sai số QoI cần bằng chứng riêng. Tiêu chí 4–16 trong dữ liệu lịch sử của FDS là phạm vi tham khảo, với các ca validation hiện trải rộng hơn. [Hàm repo](../../ifc_to_fds/fire/mesh_metrics.py#L9-L21) · [FDS User’s Guide 6.11.1, Mesh Resolution](https://github.com/firemodels/fds/blob/FDS-6.11.1/Manuals/FDS_User_Guide/FDS_User_Guide.tex#L1102-L1112)

[ifc_to_fds/fire/mesh_metrics.py:L9–L21](../../ifc_to_fds/fire/mesh_metrics.py#L9-L21)

~~~text
  9 | # Reference constant: rho_inf * c_p * T_inf * sqrt(g)
 10 | # 1.204 kg/m3 * 1.005 kJ/(kg K) * 293.15 K * sqrt(9.81 m/s2)
 11 | # ~= 1111.4 kW/m^(5/2), matching the project's historical D* implementation.
 12 | PLUME_COEFFICIENT = 1111.4
 13 |
 14 |
 15 | def calculate_d_star(heat_release_rate_kw: float) -> float:
 16 |     """Calculate characteristic fire diameter D* in metres."""
 17 |
 18 |     if heat_release_rate_kw <= 0.0:
 19 |         return 0.0
 20 |     return float((heat_release_rate_kw / PLUME_COEFFICIENT) ** 0.4)
 21 |
~~~

Đường `grid_sensitivity_analysis` yêu cầu đúng thứ tự thô/trung bình/mịn, refinement ratio tăng, `local_dx_m` giảm, hash bất biến của kịch bản và đúng tập đối tượng quan sát. Đầu ra đo hai sai phân, hai sai số tương đối theo mức lưới mịn hơn và nhãn xu hướng. Phép đo trước/sau sửa underflow F6 ở mục 6. Nó mô tả thay đổi quan sát, chưa tính bậc hội tụ quan sát, ngoại suy Richardson hay GCI được duyệt. Một cổng nghiên cứu cho công trình cần định nghĩa QoI, lưới cho plume và lối thông thực, bất định và ngưỡng thay đổi theo bài toán. Các lưới phải giữ được cùng điều kiện biên và mô hình vật lý đang kiểm. [So trường và hash](../../ifc_to_fds/fire/grid_sensitivity_analysis.py#L66-L138) · [Nghiên cứu QoI ở M5.6 và M5.7](../plans/production-roadmap.md#L188-L195)

## 6. Đối chiếu ba bản phân tích, PyroSim và QCVN/TCVN

| Nguồn giao kèm | Số dòng | SHA-256 tệp văn bản |
|---|---:|---|
| A1 — Đồ thị MEP, đoạn bo, gộp nhánh và ví dụ HVAC | 712 | `8fda5213d0ba06dc9397e4b56369ece6ca1b97deb74652111c31bfd763eed9df` |
| A2 — Kiến trúc repo, hình học, ma trận chức năng | 248 | `70ad79b4916ad47311cdcc0f8426674ab7c23a591996c522936473c1a0f2e6f3` |
| A3 — Hình học, NIST, QCVN/TCVN và PyroSim | 163 | `5a4006d968d14823f520cc0e56177ed681146c92cc9ba71fc2d2e463c4fa8c9c` |

A2 dẫn gói `e01e65d`, A3 nhắc `fd0c26e`. Cả hai commit có trong Git cục bộ. `git diff --name-status e01e65d 66174f0 -- ifc_to_fds tests js scripts` cho một tệp test thay đổi tại mốc đầu. HEAD cuối có thêm các thay đổi được ghi ở đầu báo cáo. `fd0c26e` có nhánh `mep/network.py` chỉ nhận segment. Trong lượt này A3 là tệp văn bản, với câu mở đầu nhắc ZIP đã mất byte. Căn cứ mã nguồn là Git checkout, probe và fixture đã đọc. Các số phần trăm độ chín trong A2 thiếu phép đo chung để so sánh.

| Nhận định gốc | Đối chiếu với `8ed1f38` |
|---|---|
| `F-01`, A2:43,55,156 và A3:88. CLI bị sập do import vòng | Smoke `--help` và `convert` từ tiến trình mới qua ở đường dẫn ngắn. Bảng phụ thuộc tĩnh ở mục 2 ghi cặp hai chiều hiện hành. Lỗi lưu tệp dài là F5. |
| `B-01`, A2:100–102,165 và A3:14. 15/18 cửa báo tự cắt giả | Nhánh phân loại contact và union đã có. Ca FZK-Haus trong phiên từ chối do một stair nguồn không hợp lệ, `openings=PASS`. Con số 15/18 giữ tư cách dữ liệu lịch sử A2/A3. |
| A2:117–120 và A3:22–23. Mọi cửa là `GEOM GLASS` và làm cổng lỗ tự FAIL | `GLASS` là tên SURF, serializer lấy strategy từ policy. Lỗ nguồn, fill nguồn và cả vật cản đã xuất cùng tham gia phép so. Fixture hợp lệ minh họa lỗ giữ nguyên thể tích. Quyết định trạng thái mở/đóng cần được khai báo theo ca để giữ đúng từng đường thông. |
| `B-06`, `C-02`, A3:15,75,158. Dầm mỏng biến dạng hoặc mất | F4 xác nhận hiện tượng với hộp tổng hợp 0,08 × 0,08 × 0,80 m. Duy nhất bề dày 0,08 m chưa đủ kết luận phần tử bị xóa. `THICKEN` làm thay đổi vật cản và cần đối chứng. |
| `WP-09`, A2:126–131 và A3:35,91,101–130. K=37 làm solver dừng | FDS 6.11.1 hoàn thành ca K=37 và 40. Thừa số nhỏ ảnh hưởng hiệu suất FFT, còn benchmark 30–300% trong A3 chưa có ca đối chứng được chạy ở đây. Đề xuất nới biên cần xem là thay đổi miền. |
| A2:134,173 và A3:13. Effective geometry chỉ OBST tĩnh hoặc toàn bộ INCONCLUSIVE | Code đọc thêm VENT và OBST điều khiển ở trạng thái hiệu dụng đã lưu, báo từng GEOM chưa chứng minh. Test trộn GEOM với OBST suy biến vẫn phát hiện FAIL. |
| A1:3, A2:191–199 và A3:47,92. Mọi fitting/fan bị chặn | Đúng với nhánh trong `fd0c26e`. HEAD hỗ trợ fitting hai cổng, junction với `LOSS(i,j)` và quạt lưu lượng duyệt sẵn. F2 và F9 là giới hạn thực tế còn mở. |
| A1:102–114, 140–157, 176, 511–585. Gộp đoạn, tự suy K, tự nối và thêm đế VENT | Giữ riêng ống, fitting và quạt theo từng nguồn bảo toàn topology/điều kiện. Cần hệ số và bằng chứng duyệt trước khi áp dụng mô hình hóa. Mục 4.2 chỉ ra sai số tổn áp trong đề xuất gộp. |
| A2:157–173 và A3:48. 19 gate, hoàn toàn chung đường kiểm | Ca smoke có 20 gate gồm 12 gate lõi. Audit thật sự đọc lại nguồn và bytes FDS. Kernel và một phần logic dùng chung cần đối chứng giải tích/solver để tăng độc lập. |
| A2:179–186 và A3:41–47. Biên vật liệu và hóa học EV chưa đầy đủ | Nhận định thiếu thông số nhiệt cho deck nền còn đúng. Fuel đại diện và `hf_status=NOT_MODELED` còn đúng. Preset có mục HF tham khảo, có đường phát lại HRR đo và test solver EV. |
| A2:208,212 và A3:36–40. Underflow và dải D*/Δx | F6 tái hiện underflow ở mốc đầu và đã đạt hồi quy ở HEAD cuối. F8 chỉ ra dải D*/Δx còn được mô tả sai trong README, trong khi code tính chỉ báo và chưa cấp PASS hội tụ. |
| A2:229. /tmp 256 MiB làm upload 500 MiB thất bại | Compose đã trỏ `TMPDIR` vào volume job. Kiểm ngữ nghĩa cấu hình và hồ sơ M5 trước đây. Phiên audit chưa đo tải Compose đồng thời. [Compose](../../compose.production.yml#L9-L23) · [M5.1 đến M5.4](../plans/production-roadmap.md#L182-L188) |

### 6.1. F6 — Underflow trong xu hướng lưới đã được sửa ở HEAD cuối

Ở `66174f0`, `_trend` dùng dấu của `(medium−coarse)·(fine−medium)`. Hai hiệu ±10⁻²⁰⁰ biểu diễn được nhưng tích độ lớn 10⁻⁴⁰⁰ làm tròn về 0 trong binary64. Điều này làm fall-through sang `PLATEAU_OR_UNRESOLVED`. PR #92 đã merge ở `beb435f`, là tổ tiên của `8ed1f38`. Hàm hiện so dấu riêng của từng hiệu. Nhánh tính sai phân và tỷ lệ cũng từ chối giá trị tràn miền biểu diễn.

[ifc_to_fds/fire/grid_sensitivity_analysis.py:L42–L53](../../ifc_to_fds/fire/grid_sensitivity_analysis.py#L42-L53)

~~~text
 42 | def _trend(coarse: float, medium: float, fine: float) -> str:
 43 |     first = medium - coarse
 44 |     second = fine - medium
 45 |     if first == 0.0 and second == 0.0:
 46 |         return "FLAT"
 47 |     # Không nhân hai sai phân: tích có thể underflow về 0 dù cả hai
 48 |     # đều hữu hạn và khác 0, làm sai phân loại xu hướng vật lý.
 49 |     if (first > 0.0 and second > 0.0) or (first < 0.0 and second < 0.0):
 50 |         return "MONOTONIC"
 51 |     if (first > 0.0 and second < 0.0) or (first < 0.0 and second > 0.0):
 52 |         return "OSCILLATORY"
 53 |     return "PLATEAU_OR_UNRESOLVED"
~~~

Probe chạy `analyze_grid_sensitivity` với các case của `_results()` trong test, thay cùng một quan sát trên ba cấp và giữ nguyên hash/metadata.

| Chuỗi quan sát | Sai phân | `66174f0` | `8ed1f38` |
|---|---|---|---|
| `1, 2, 3` | `1, 1` | `MONOTONIC` | `MONOTONIC` |
| `1e-200, 2e-200, 3e-200` | `1e-200, 1e-200` | `PLATEAU_OR_UNRESOLVED` | `MONOTONIC` |
| `1e-200, 2e-200, 1e-200` | `1e-200, -1e-200` | `PLATEAU_OR_UNRESOLVED` | `OSCILLATORY` |

[Ca hồi quy dưới chuẩn, đổi đơn vị và tràn số](../../tests/test_grid_sensitivity.py#L276-L335) · [Hồ sơ kiểm chứng P4C](../science/P4C_NUMERICAL_TREND_VERIFICATION_2026_11_10.md)

### 6.2. Đối chiếu PyroSim

Tài liệu Thunderhead cho PyroSim 2026.2 mô tả nhập CAD/IFC, xử lý solid/GEOM và các tùy chọn chuyển đổi BIM. Với kiểu Wall, công cụ đơn giản hóa tường thành hộp và nêu giới hạn với tường cong hoặc có góc. Với Door/Window, kết quả chuyển gồm hộp đi cùng lỗ, có tùy chọn khoảng nới lỗ. Tài liệu cũng tách network HVAC thành node và duct với thông số riêng. Các nguồn công khai này xác nhận có nhiều đường nhập/xử lý. Kết luận A3 về thuật toán ray-casting nội bộ, khả năng nhập mọi BRep lỗi, mặc định GEOM và tính độc quyền của IFCtoFDS vẫn cần phép đối chứng, tài liệu kỹ thuật hoặc deck xuất thực. [Thunderhead — Creating Geometry from CAD Files](https://www.thunderheadeng.com/docs/2026-2/pyrosim/geometry/creating-geometry-cad/) · [Thunderhead — HVAC Ducts](https://www.thunderheadeng.com/docs/2026-2/pyrosim/hvac/ducts/) · [Thunderhead — Working with Meshes](https://www.thunderheadeng.com/docs/2026-2/pyrosim/meshes/working-with-meshes/)

Dự án đã có `scripts/compare-fds-decks.py` tính hợp không gian OBST/GEOM/HOLE, thể tích phần lệch, IoU, số dòng provenance và số bản ghi HVAC/`LOSS(i,j)`. Script tính trên deck và báo số đo. Bằng chứng policy hay vật lý cần đánh giá tiếp. Ca PyroSim trực tiếp T19–T21 hiện `BLOCKED` vì thiếu deck thứ hai kèm bản/cài đặt nhập hoặc phiên PyroSim. Có thể đối chiếu hai tầng bằng chứng. Thứ nhất là hình học liên tục và topology trong hai deck. Thứ hai là hình học hiệu dụng và QoI chạy cùng FDS/lưới có nguồn. [Script so deck](../../scripts/compare-fds-decks.py#L43-L108) · [Điều kiện T19–T21](../plans/real-world-test-plan.md#L42-L54)

### 6.3. Giới hạn khi dùng cho PCCC Việt Nam

- Phụ lục D của QCVN 06:2022/BXD gắn `3.000 m²` với vùng khói trong các trường hợp và cách tính ở D.4/D.7, gồm lựa chọn ngăn thật và chia giả định có cơ sở tính. Chú thích D.7 liên hệ chiều hạ màn với chiều dày lớp khói tạo thành. Khi áp dụng cần đọc cả Sửa đổi 1:2023, đặc biệt D.2 và D.8 đã được sửa. Vì vậy rủi ro F4 phải gắn với vai trò thực của dầm và phương án ngăn khói. A3 đưa ra 0,5 m như gợi ý nhưng chưa dẫn điều khoản áp dụng cho công trình đang xét. [QCVN 06:2022/BXD, Phụ lục D](https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/12/06-bxd.pdf) · [Thông tư 09/2023/TT-BXD và Sửa đổi 1:2023](https://congbao.chinhphu.vn/van-ban/thong-tu-so-09-2023-tt-bxd-40285.htm)
- TCVN 5687:2024 có phạm vi thiết kế thông gió và điều hòa không khí công trình dân dụng. Danh mục VSQI ghi TCVN 13657-1:2023 và -2:2023 thuộc hệ thống chữa cháy phun sương áp suất cao. Mật độ xe, đường HRR cụm và trễ quạt trong A3:76 cần dữ liệu dự án hoặc quy định được viện dẫn đúng phạm vi. Không có căn cứ từ những trang công bố này để chuyển chúng thành giá trị mặc định của exporter. [VSQI — TCVN 5687:2024](https://tieuchuan.vsqi.gov.vn/tieuchuan/view?sohieu=TCVN+5687%3A2024) · [VSQI — TCVN 13657-1](https://tieuchuan.vsqi.gov.vn/tieuchuan/view?sohieu=TCVN+13657-1%3A2023) · [VSQI — TCVN 13657-2](https://tieuchuan.vsqi.gov.vn/tieuchuan/view?sohieu=TCVN+13657-2%3A2023)
- Các giá trị `RSET ≤ 0.8·ASET`, mặt cắt `z_floor+1.75 m` và tổ hợp ngưỡng nhiệt/khói/độc trong A3:56–69 chưa có điều khoản, phiên bản tiêu chuẩn và hồ sơ áp dụng tương ứng cho bài toán của repo. `DeviceSelection` nhận tọa độ và quantity khai báo. Cơ chế này chưa xác định tuyến thoát, cao độ relative theo sàn đi bộ, ASET/RSET, dose theo thời gian hoặc tiêu chí sử dụng chính thức. Muốn dùng quan sát người thoát nạn, cần chọn đại lượng và vị trí trong hệ tọa độ CFD đã rebase, kiểm có khí tại vị trí đầu đo, có dữ liệu chất độc phù hợp và xác định RSET từ hồ sơ thoát nạn. [Hợp đồng DeviceSelection](../../ifc_to_fds/fire/scenario_emitter.py#L157-L180) · [ISO 13571:2012, phạm vi đánh giá tenability](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A13571%3Aed-2%3Av1%3Aen)
- ASTM E1355-23 đặt đánh giá dự báo theo mục đích sử dụng, bằng thực nghiệm/đối chứng và bất định mô hình. Mốc này khác bước tái đọc FDS/IFC. Ma trận gate của IFCtoFDS là bằng chứng chuyển đổi cho đầu vào mô phỏng. Thử nghiệm hiện tại thuộc fixture và một số kịch bản solver nhỏ. Những kết luận chuẩn hóa về độ an toàn thiết kế còn cần phạm vi và bằng chứng độc lập theo công trình. [ASTM E1355-23, Scope và Significance and Use](https://store.astm.org/e1355-23.html)

## 7. Lệnh, kết quả và phạm vi còn chờ xác minh

Các phép chạy ban đầu ở `66174f0`. Những phép tái kiểm gắn nhãn `8ed1f38` dùng checkout sau khi chuyển nhánh.

| Phép kiểm | Trạng thái | Kết quả thực tế |
|---|---|---|
| CLI tiến trình mới trên fixture `tiny.ifc` | `PASS` với gốc ngắn | `--help` exit 0. `convert` exit 0, 693 byte, `MAPPING_VERIFIED`. Thời gian lệnh convert quan sát 2,07 s. |
| Suite Verified mặc định ở mốc đầu trong sandbox | `BLOCKED` | Stack faulthandler sau 90 s nằm ở khởi tạo event loop Windows chờ socketpair, trong `test_api_health_and_private_paths`. Lượt đã dừng, trước đó có bài lỗi. Không dùng lượt này để kết luận các lỗi CI. |
| Python chọn lọc về audit, geometry, MEP và lưới | `PASS` | Nhóm 1 `129 passed, 7 deselected, 1 xfailed` trong 9,28 s. Nhóm 2 `26 passed` trong 75,52 s. Xfail là primitive scenario trong audit deck nền. |
| Python chọn lọc kịch bản | `PASS` | `54 passed, 3 deselected` trong 5,90 s. |
| JavaScript | `PASS` | 7 script về worker parity, input contracts, Verified, IFC Quick, HVAC viewer, GEOM opening và EV panel đều exit 0. Hai bundle inline có blob byte-for-byte trùng HEAD. |
| FZK-Haus snapshot | `PASS` cho tái lập snapshot, `REJECTED` cho mapping | Bản ứng viên 127 record, 0 khác biệt ở trường được script so. Tạo ứng viên 11,22 s trên `66174f0`, tái chạy 10,86 s trên `8ed1f38` và tiếp tục 0 khác biệt. Điều kiện cache/tải mỗi lượt riêng, nên số này chỉ ghi thời gian. |
| Tái kiểm `8ed1f38` | `PASS` cho hồi quy | `134 passed, 4 deselected, 1 xfailed` trong 8,62 s. `--help` và `convert` qua. F1/F3 cho lại cùng trạng thái. F6 cho đúng hướng. Các test dung sai lớp vỏ, hình học, openings và mesh gate thuộc lượt này. |
| FDS tích hợp HVAC + SMV | `PASS` sau điều chỉnh môi trường | Lượt đầu 7 ca fail lúc Intel MPI init. Lượt ghim `I_MPI_FABRICS=shm` và một thread chạy được `9 passed, 30 deselected` trong 87,36 s. |
| FDS tích hợp HRR replay + cửa điều khiển | `PASS` | `3 passed, 28 deselected` trong 121,65 s. Faulthandler in stack đang chờ subprocess ở giây 90, sau đó cả ba ca hoàn thành với mã 0. |
| Probe F1, F2, F3, F4, F5, F7, F9 | `PASS` cho tái hiện | Quan sát cụ thể và đối chứng ghi ở từng ID. F1/F3 không chạy solver. F2/F4 dùng setup FDS. F9 có thời gian mô phỏng 30 s. |
| K=37 và K=40 | `PASS` | Hai ca tối giản, mỗi ca đến `T_END=0.05` s, 1 bước và exit 0. |
| Docker/Compose thực, Playwright, tất cả ma trận CI | `NOT_RUN` | Dùng cấu hình và snapshot đã có để đối chiếu. |
| Ca IFC riêng A/B/C và T19–T21 PyroSim | `BLOCKED` | Lượt audit dùng fixture công khai/tổng hợp. Ưu tiên, đầu vào bắt buộc và kết quả lịch sử ở Phần A/B của roadmap. |
| Tính hội tụ, đánh giá ASET/RSET và nghiệm thu công trình | `INCONCLUSIVE` | Cần QoI, mô hình vật liệu, nguồn cháy, thiết bị/đường khí và bằng chứng thực địa được duyệt. |

Các lệnh chính chạy từ gốc repo, với `$p` là Python của `.venv` và `$out` là thư mục thử mới, ngắn, chỉ chứa dữ liệu mẫu. Hạn chế ghi thời gian đo vào snapshot cố định. Giữ bản mốc để xem từng trường khác biệt.

~~~powershell
$p = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:IFCFDS_SOLVER_AUTODISCOVERY = '0'
$out = Join-Path (Get-Location).Path ('.cache/a-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $out | Out-Null
$env:TEMP = $out
$env:TMP = $out
$env:IFCFDS_GEOMETRY_CACHE = Join-Path $out 'g'
& $p -m ifc_to_fds --help
& $p -m ifc_to_fds convert tests/baseline/fixtures/tiny.ifc -o (Join-Path $out 'tiny.fds')
& $p scripts/verdict-snapshot.py examples/AC20-FZK-Haus.ifc -o (Join-Path $out 'fzk-candidate.json')
& $p scripts/verdict-snapshot.py examples/AC20-FZK-Haus.ifc --compare docs/evidence/production-roadmap/baseline-fzk.json

& $p -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=75 --basetemp (Join-Path $out 'p1') tests/test_validation_engine.py tests/test_acceptance_audit.py tests/test_source_topology_self_intersection.py tests/test_placement_rigidity.py tests/test_openings.py tests/test_opening_mutations.py tests/test_effective.py tests/test_effective_elements.py tests/test_hvac_network.py tests/test_hvac_fittings.py tests/test_hvac_junction.py tests/test_mep_graph.py tests/test_fire_mesh_gate.py tests/test_grid_sensitivity.py tests/test_local_mesh_plan.py
& $p -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=75 --basetemp (Join-Path $out 'p2') tests/test_validation_engine_gates.py tests/test_passage_resolution.py tests/test_geometry_export_investigation.py tests/test_geometry_booleans.py tests/test_source_quality_budget.py
& $p -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=75 --basetemp (Join-Path $out 'p3') tests/test_hrr_curve_replay.py tests/test_fire_scenario_emitter.py tests/test_scenario_integrity.py tests/test_scenario_verdict_contract.py

# Tái kiểm ở 8ed1f38
& $p -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=75 --basetemp (Join-Path $out 'p4') tests/test_audit_hardening.py tests/test_validation_engine.py tests/test_acceptance_audit.py tests/test_source_topology_self_intersection.py tests/test_placement_rigidity.py tests/test_openings.py tests/test_opening_mutations.py tests/test_passage_resolution.py tests/test_validation_engine_gates.py tests/test_effective.py tests/test_effective_elements.py tests/test_hvac_fittings.py tests/test_hvac_junction.py tests/test_grid_sensitivity.py tests/test_fire_mesh_gate.py

$env:IFCFDS_SOLVER = (Resolve-Path '.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe').Path
$env:I_MPI_FABRICS = 'shm'
$env:OMP_NUM_THREADS = '1'
& $p -m pytest -q -m solver -o faulthandler_timeout=90 --basetemp (Join-Path $out 's1') tests/test_hvac_fds_pressure.py tests/test_hvac_junction.py tests/test_effective_elements.py tests/test_hvac_network.py
& $p -m pytest -q -m solver -o faulthandler_timeout=90 --basetemp (Join-Path $out 's2') tests/test_hrr_curve_replay.py tests/test_scenario_integrity.py

node scripts/test-worker-bundle-parity.js
node scripts/test-conversion-input-contracts.js
node scripts/test-verified-regressions.js
node scripts/test-ifc-conversion.js
node scripts/test-hvac-viewer.js
node scripts/test-geom-opening-regression.js
node scripts/test-ev-scenario-panel.js
~~~

**Tái lập F1 và F3 bằng fixture.** Chạy Python từ gốc repo với đường dẫn tạm ngắn và `IFCFDS_SOLVER_AUTODISCOVERY=0`. Mỗi deck thử chỉ thay MESH. Giữ nguyên geometry package và đọc lại cùng IFC để cô lập mắt xích kiểm toán.

~~~python
import hashlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.pipeline import audit, convert

cases = {
    "tiny": (
        "&MESH ID='M1', IJK=10,10,10, XB=0,0.6,0,1,0,3 /\n"
        "&MESH ID='M2', IJK=10,10,10, XB=1.4,2,0,1,0,3 /"
    ),
    "opening": (
        "&MESH ID='M1', IJK=1,2,15, XB=0,0.5,0,0.3,0,3 /\n"
        "&MESH ID='M2', IJK=2,2,15, XB=0.5,4,0,0.3,0,3 /"
    ),
}
Path(".cache").mkdir(exist_ok=True)
for name, meshes in cases.items():
    with TemporaryDirectory(dir=".cache", prefix="a-") as out:
        path = f"tests/baseline/fixtures/{name}.ifc"
        base = convert([path], output_directory=out)
        text = re.sub(r"(?m)^&MESH .*? /$", meshes, base["fds_text"], count=1)
        assert text != base["fds_text"]
        manifest = MappingManifest.model_validate(base["manifest"])
        manifest.fds_sha256 = hashlib.sha256(text.encode()).hexdigest()
        manifest.reseal()
        _, _, report = audit(
            [path], text, manifest, base["configuration"], base["geometry_package"]
        )
        print(name, report.mapping_status.value, report.simulation_status.value)
        for gate in ("domain", "geometry", "openings", "passage_resolution"):
            value = report.gates[gate]
            print(gate, value.status.value, value.reason, value.evidence)
~~~

## 8. Tiêu chí bàn giao và liên hệ roadmap

| ID kiểm bàn giao | Bằng chứng |
|---|---|
| KT1 — Đúng vị trí, ngày giờ và phiên bản | Một bản Markdown trong `docs/audit`, tên theo quy ước ngày. Header có commit đầy đủ, nhánh, ngày và giờ địa phương. |
| KT2 — Từng nhận định trọng tâm bám đúng HEAD | Đọc cả ba tệp, ghi fingerprint, đối chiếu `fd0c26e` và `e01e65d`. Mục 6 lưu lại các ID lịch sử và nhận định đã được kiểm. |
| KT3 — Chi tiết mã và ca tái hiện | Tám vấn đề mở có vị trí, trích dòng, dữ liệu, kỳ vọng, kết quả, ảnh hưởng và hướng xử lý. F6 có bằng chứng trước/sau merge. Mục 2–5 mô tả chuỗi gọi và công thức. |
| KT4 — Căn cứ độc lập và giới hạn nghiệm thu | Đối chứng thể tích, Darcy–Weisbach, FDS thực, tests và nguồn chính thức. `PASS` của mapping, setup FDS và xác nhận khoa học được ghi theo phép đo ở mục 7. |

Ánh xạ công việc tiếp theo vào roadmap. **M2** ưu tiên F1 và F3 vì chúng ảnh hưởng độ tin cậy khi đọc verdict và kiểm lỗ qua lưới, sau đó F4 theo vật cản có chức năng. **M3** xử lý F2 ở đường lập HVAC và F9 ở nhánh tham số tiết diện sau khi chốt tương thích artifact cũ. **M4/M5.6** cập nhật bảng diễn giải F8 theo code và test. Nhãn xu hướng F6 đã được xác minh sau merge. **M5** mở hồi quy xuất artifact Windows cho F5. F7 thuộc đơn vị kiểm chia lưới và trần số ô. Việc mở, kết quả lịch sử và cổng mốc vẫn dùng roadmap làm hồ sơ chính. [Kế hoạch production](../plans/production-roadmap.md)

Audit dùng fixture công khai/tổng hợp và áp mức P1/P2 theo hậu quả ở đúng lớp. Dữ liệu A/B/C, browser thực, PyroSim trực tiếp, tải production và thẩm tra vật lý của công trình còn chờ bằng chứng. Ưu tiên chặn F1 và F2 trước khi dùng lại cổng cho các deck được chỉnh độc lập hoặc mạng HVAC đặt VENT trên tường có lỗ.
