# Đánh giá chức năng và chất lượng đầu ra theo module

Đây là đánh giá trước đợt sửa hình học/timeout và mở rộng kiểm chứng. Kết quả triển khai tiếp theo được ghi tại [báo cáo 16](16-ket-qua-sua-hinh-hoc-va-kiem-chung.md).

## 1. Phạm vi và cách đọc kết quả

Đánh giá mã đang có trong working tree trên nhánh `chore/research-acceptance-hardening`, HEAD nền `f0c6d9c02342312266f2cfb8f9102833640061c3`. Working tree chứa các thay đổi tổ chức mã chưa commit; HEAD không đại diện đầy đủ cho mã đã được kiểm tra.

Mục đích là xác định từng chức năng tạo ra gì, bằng chứng hiện có chứng minh đến đâu và điều kiện còn thiếu để nghiệm thu. Việc tách thư mục thành module và việc test đạt được đánh giá riêng với độ đúng của kết quả chuyển đổi.

Các mức kết luận dùng trong báo cáo:

| Mức | Ý nghĩa |
| --- | --- |
| Đạt trong phạm vi đã kiểm tra | Có kết quả thực tế hoặc assertions phù hợp với chức năng và ca kiểm tra được nêu rõ. |
| Có điều kiện | Có phần hoạt động và bằng chứng tích cực, nhưng còn giới hạn về dữ liệu, chế độ hoặc loại đầu ra. |
| Chưa đủ bằng chứng | Thiếu dữ liệu, kiểm tra hoặc bộ đối chiếu để kết luận. Không đồng nghĩa chức năng chắc chắn sai. |
| Không đạt ở ca cụ thể | Có gate thất bại, assertion sai hoặc timeout trong ca được nêu. Chưa suy rộng nguyên nhân sang mọi mô hình. |

Không quy đổi số test thành phần trăm chất lượng hay độ chính xác. Không coi file được tạo, checksum đúng hoặc job hoàn thành là bằng chứng mô hình đã được nghiệm thu.

### Bằng chứng kiểm tra

| Nguồn | Kết quả | Phạm vi diễn giải |
| --- | --- | --- |
| Chạy lại Python trong lần rà soát này | **113 passed, 17 warnings**, 23,55 giây | Architecture; BIM; FDS; jobs ports; artifact lifecycle; reference governance; traceability mutation; simulation boundary policy. Warnings từ phép tính mesh trong các ca hình học không hợp lệ/mutation. |
| Chạy lại frontend trong lần rà soát này | **14/14 harness PASS** | Lifecycle, module wiring, worker parity, UI recovery, selection/workbench, golden workflow, artifacts, verified regressions, worker export, openings. Không phải 14 phiên kiểm thử trình duyệt thật. |
| Đợt Python đầy đủ đã lưu trước đó | **377 ca duy nhất PASS**, không FAIL/SKIP trong ba báo cáo được hợp nhất | Không cộng thành 553 ca vì các lần chạy chồng lặp; cũng không cộng thêm 113 ca chạy lại vào tổng này. |
| Browser thật đã lưu trước đó | 5 test PASS; HTTP, Web-IFC, Verified download thành công | Không chạy lại browser trong lần đánh giá này. |
| FDS thật đã lưu trước đó | 2 test PASS; FDS 6.11.1 initialization và kiểm tra phạm vi OBST được hỗ trợ | Không chạy lại solver trong lần đánh giá này. |
| Migration manifest | SHA-256 của **51/51 implementation target** vẫn khớp | Liên hệ mã đã di chuyển với bằng chứng trước đó; không chứng minh toàn bộ môi trường và mọi file khác bất biến. |

Log mới: [Python](../../.cache/module-quality-review.log), [JUnit](../../.cache/module-quality-review.xml), [frontend results](../../.cache/module-quality-js/results.json). Bằng chứng cũ: [Python summary](../../.cache/layout-final-summary.json), [browser](../../scripts/out/layout-browser/results.json), [solver initialization](../../scripts/out/solver-evidence/initialization.json), [effective geometry](../../scripts/out/solver-evidence/effective_geometry.json).

## 2. Kết quả đầu ra thực tế quan trọng nhất

| Dữ liệu/luồng | Kết quả thực tế | Nhận định chất lượng |
| --- | --- | --- |
| Python Verified — tiny | `MAPPING_VERIFIED`; 1 solid matched; 0 missing; 0 deviated; simulation `INCONCLUSIVE` | Đạt ánh xạ cho fixture nhỏ. Chưa nghiệm thu mô phỏng cháy. |
| Python Verified — opening | `MAPPING_VERIFIED`; 1 solid matched; opening gate PASS; simulation `INCONCLUSIVE` | Đạt bảo toàn lỗ mở trong fixture này. Chưa suy rộng sang mọi loại cửa, lỗ xuyên hoặc hình học phức tạp. |
| Python Verified — MEP fixture | `INCONCLUSIVE`; 0 solid matched; thiếu hình học vật lý hợp lệ, domain và phân loại hệ thống có chứng cứ | Giữ được graph ngữ nghĩa; chưa có đầu ra hình học MEP đủ điều kiện nghiệm thu. |
| Python Verified — Institute, lần hoàn tất đã lưu | `REJECTED`; `geometry` và `geometry_preservation` FAIL; khoảng 129,10 giây sau refactor | Không đạt nghiệm thu hình học ở ca này dù nhiều gate khác PASS. |
| Python Verified — Institute, phép đo so sánh gần nhất | Bản hiện tại cold vượt **300 giây**, warm chưa chạy | Chưa đạt nghiệm thu hiệu năng. Không có số thời gian/RAM hợp lệ cho lần chạy hiện tại bị timeout. |
| JavaScript Quick — public fixtures | FDS trước/sau tổ chức mã giống byte ở các ca đã lưu | Đạt tương thích đầu ra; chưa chứng minh độ đúng hình học. Ba assertion số tam giác cũ vẫn thất bại. |
| FDS thật — mẫu OBST một MESH | Initialization PASS; đối chiếu hình học hiệu dụng từ SMV PASS | Bằng chứng solver thật có phạm vi hẹp, không bao phủ GEOM, HOLE, VENT hoặc nhiều MESH. |

Đầu ra tiny/opening/MEP và toàn bộ report/manifest/inventory/FDS được lưu tại [layout-python-parity-final](../../scripts/out/layout-python-parity-final). Các run này không cấu hình solver; vì vậy solver/effective-geometry của tiny/opening là `INCONCLUSIVE`, dù máy có bản FDS đã được dùng trong bộ test solver riêng.

## 3. Module BIM — đọc và hiểu dữ liệu IFC

Mã: [bim](../../ifc_to_fds/modules/bim). Đầu ra chính: inventory, metadata nguồn, placement, scale đơn vị và MEP graph.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Đọc IFC, lập inventory | Danh sách IfcProduct, STEP ID/GlobalId, loại, tầng, quan hệ | Đạt trên tập kiểm tra: FZK có 127 product, 17 opening; Duplex có 295 product; các product được đối soát đầy đủ. | Đủ inventory không đồng nghĩa mọi product là vật cản FDS. Các phần tử phi vật lý vẫn cần được giải trình. |
| Đơn vị | Hệ số chuyển sang mét | Đạt các ca mét, milimét chuyển đúng một lần và đơn vị chuyển đổi lồng nhau; inch có scale 0,0254. | Chưa chứng minh mọi IFC thực tế khai báo đơn vị nhất quán hoặc đầy đủ. |
| Placement và nguồn liên kết | Transform, bounds, danh tính theo nguồn | Có kiểm tra transform, trùng GUID giữa các nguồn và phát hiện sửa nguồn/manifest. | Mô hình nhiều nguồn cần xác nhận hệ tọa độ chung; không được tự căn chỉnh theo phỏng đoán. |
| Quan hệ opening/host | Opening gắn với phần tử chủ | Giữ được 17 opening liên kết host ở FZK; ca thiếu filling không làm mất opening hoặc gây crash. | Có quan hệ chưa chứng minh phép cắt hình học đã đúng; phần đó thuộc geometry/verification. |
| MEP graph | System, member, port, cạnh kết nối có nguồn IFC | Fixture giữ được 1 system, 2 member, 2 port, 1 kết nối IFC tường minh; không có orphan port. | Fixture không tạo Representation 3D cho hai member. System vẫn `UNRESOLVED`; tên “Smoke Extract” không được dùng thay chứng cứ phân loại. |
| Preview dữ liệu nguồn | Metadata và dữ liệu phục vụ hiển thị | Có luồng preview/browser đã kiểm tra. | Preview phục vụ quan sát; không phải kết quả kiểm chứng ánh xạ. |

**Kết luận:** inventory và truy nguyên nguồn có bằng chứng tốt trên fixtures. MEP mới chứng minh bảo toàn một graph đơn giản; chưa chứng minh chuyển đổi hệ HVAC/PCCC thực tế có hình học, thiết bị và vận hành đầy đủ.

Bằng chứng: [inventory tests](../../tests/modules/bim/test_inventory.py), [MEP fixture generator](../../tests/baseline/generate_baseline.py), [MEP output](../../scripts/out/layout-python-parity-final/mep/after/evidence.json).

## 4. Module Geometry — hình học và chất lượng mesh

Mã: [geometry](../../ifc_to_fds/modules/geometry). Đầu ra chính: mesh chuẩn hóa, chỉ số hình học, kết quả boolean, dữ liệu payload/cache và bằng chứng so sánh.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Trích xuất hình học IFC | Vertices, triangles, bounds theo tọa độ/đơn vị đã chuẩn hóa | Tiny/opening qua kiểm chứng độc lập. | Institute có geometry FAIL; MEP fixture thiếu hình học. Chưa thể nhận đầu vào IFC bất kỳ là hợp lệ. |
| Boolean và lỗ mở | Solid sau khi trừ opening | Opening fixture đạt; frontend regression giữ được 3 void trong ca tương ứng. | Chưa bao phủ mọi kiểu boolean, lỗ xuyên nghiêng hoặc mesh lỗi trong mô hình thực tế. |
| Mesh quality và sealing | Kiểm tra suy biến, kín khối, giao cắt và bằng chứng sửa/chấp nhận | Có tests và mutation tests; có chặn trường hợp không đủ bằng chứng. | Giao cắt tự thân/đối chiếu nguồn là điểm cần profiling ở ca lớn; không được bỏ kiểm tra chỉ để giảm thời gian. |
| So sánh hình học | Volume, bounds, IoU/sai lệch theo chính sách cấu hình | Phát hiện các biến đổi cố ý; tiny/opening đạt. | Institute có geometry-preservation FAIL. Ngưỡng mặc định trong mã chưa tự động là ngưỡng nghiệm thu kỹ thuật cho mọi công trình. |
| Package hình học và lazy payload | Archive, binary payload, checksum; nạp khi cần | Có kiểm tra binary, checksum, thay đổi payload và vòng đời cache. | Checksum chỉ chứng minh toàn vẹn dữ liệu đã ghi; không chứng minh hình học nguồn đã được diễn giải đúng. |

**Kết luận:** đạt có điều kiện trên hình học đại diện nhỏ; chưa đạt nghiệm thu ở Institute. Chưa xác định nguyên nhân gốc của các sai lệch hình học và biến động thời gian chỉ từ các log hiện có.

Với Quick JavaScript, ba sai lệch số tam giác tồn tại cả trước và sau refactor:

| Ca | Expected | Actual | Chênh lệch |
| --- | ---: | ---: | ---: |
| Institute hybrid | 2.890 | 2.854 | 36 |
| Institute GEOM | 41.371 | 41.335 | 36 |
| Duplex GEOM | 5.214 | 5.212 | 2 |

Cần truy ngược face/element và đánh giá sai lệch bề mặt/thể tích/lỗ mở. Chưa có cơ sở kết luận các tam giác khác biệt là vô hại hoặc do refactor mới gây ra. Bằng chứng: [legacy failures](../../.cache/inherited-legacy-failures.json), [Institute completed result](../../scripts/out/layout-benchmark/AC20-Institute-Var-2/after/cold/result.json).

## 5. Module Simulation — phạm vi và chính sách ánh xạ

Mã: [simulation](../../ifc_to_fds/modules/simulation). Tên module hiện bao phủ chuẩn bị phạm vi/chính sách, chưa tương đương một bộ mô phỏng cháy hoàn chỉnh.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Chọn full model/tầng/bounding box | Scope với phần tử trong/ngoài phạm vi | Có tests đối soát scope, loại trừ và kiểm chứng lại nguồn. | Clipping trong viewer không tự động là scope xuất FDS; cấu hình scope xuất phải được xác nhận riêng. |
| Miền tính toán | Domain và ràng buộc liên quan | Tiny/opening có domain gate PASS; MEP thiếu domain được báo `INCONCLUSIVE`. | Không nên coi bounds mô hình là domain vật lý đã được kỹ sư phê duyệt. |
| Chính sách mapping | MappingPlan, representation, quyết định/review | Có kiểm tra kế hoạch, nguồn gốc quyết định và boundary mutations. | Có kế hoạch chưa chứng minh mọi representation được solver xử lý đúng. |
| Biên và tiếp xúc với domain | Quyết định boundary, bằng chứng, lỗi theo entity | Bộ boundary policy và kiểm tra sửa primitive đạt; test solver thật phát hiện sửa XB dù manifest đã được hash lại. | Bằng chứng solver hiện giới hạn subset hỗ trợ. |
| Điều kiện mô phỏng cháy | Các yêu cầu physics/scenario/mesh/operational model | Chưa có bằng chứng nghiệm thu đầy đủ. | Không được suy ra vật liệu, nguồn cháy, quạt, lưu lượng, chế độ vận hành hoặc độ hội tụ từ tên IFC. |

**Kết luận:** phần scope/mapping có chức năng và kiểm tra rõ ràng. Đầu ra hiện tại chưa phải mô hình mô phỏng cháy đã được nghiệm thu.

## 6. Module FDS — sinh tệp và manifest

Mã: [fds](../../ifc_to_fds/modules/fds). Đầu ra chính: nội dung `.fds`, record/ID và manifest truy nguyên.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Serialize mô hình | FDS records và văn bản | Tiny/opening có syntax PASS; trước/sau tổ chức mã giữ nguyên evidence/FDS ở fixtures đã lưu. | Parser nội bộ đọc được không đồng nghĩa FDS/PyroSim chấp nhận mọi record và tổ hợp. |
| Parse lại FDS | Cấu trúc namelist độc lập với serializer | Dùng để audit lại nội dung đã ghi; có mutation tests ở các workflow. | Không thay thế quá trình khởi tạo solver thật. |
| Sinh manifest | Ánh xạ entity nguồn → output ID/record, hash, quyết định | Có kiểm tra traceability và sửa manifest/record; không chỉ tin metadata do converter khai báo. | Manifest nhất quán vẫn có thể mô tả một đầu ra hình học sai; cần kiểm chứng nguồn và hình học. |
| Khả năng dùng trong FDS | Tệp đầu vào solver | Đã có FDS 6.11.1 chạy initialization thành công trên mẫu được hỗ trợ. | Chưa có bằng chứng solver thực cho mọi file GEOM/HOLE/VENT hoặc mô hình lớn. |
| Khả năng nhập PyroSim | Dự án nhập từ `.fds` | Chưa có bằng chứng E2E nhập PyroSim trực tiếp trong tập kiểm tra này. | Chưa thể cam kết tương thích đầy đủ chỉ từ syntax PASS hoặc solver mẫu PASS. |

**Kết luận:** sinh tệp và truy nguyên hoạt động trên ca đại diện. Chất lượng nội dung cần được đánh giá bằng report tương ứng; tệp tồn tại không đồng nghĩa đủ điều kiện dùng cho nghiên cứu cháy.

## 7. Module Verification — kiểm chứng và kết luận nghiệm thu

Mã: [verification](../../ifc_to_fds/modules/verification). Luồng production dùng [application/engine.py](../../ifc_to_fds/modules/verification/application/engine.py); cấu trúc runner/checkers không tự thay thế engine đang chạy.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Đọc lại nguồn và artifacts | Bộ bằng chứng độc lập với trạng thái converter trong bộ nhớ | Có tests thay nguồn, sửa tọa độ, sửa mapping và rehash. | Tính độc lập ở mức quy trình/đối chiếu không có nghĩa đã có một bộ CAD kernel thứ hai cho mọi phép hình học. |
| Gates theo nhóm yêu cầu | PASS/FAIL/INCONCLUSIVE/NOT_APPLICABLE cùng lý do | Phân biệt tiny/opening đạt, MEP thiếu bằng chứng, Institute không đạt. | Gate PASS trên tập rỗng không chứng minh chức năng đã xử lý dữ liệu thực: MEP PASS ở mô hình không có MEP là ví dụ. |
| Findings và traceability | Severity, entity liên quan, sai lệch, report JSON/Markdown | Có mutation tests phát hiện sửa thông tin dù checksum tổng được tính lại. | Không có findings vẫn có thể còn gate `INCONCLUSIVE`; phải đọc verdict và gates. |
| Tổng hợp mapping verdict | `MAPPING_VERIFIED`, `REJECTED`, `INCONCLUSIVE` | Required mapping gate thất bại hoặc finding P0/P1 mức mapping làm kết quả bị từ chối. | `MAPPING_VERIFIED` chỉ áp dụng phạm vi mapping đã cấu hình, không phải nghiệm thu toàn bộ IFC hay mô phỏng cháy. |
| Chạy solver | Version, command, exit code, timeout và logs | FDS 6.11.1 thật có return code 0 trên ca initialization; thiếu solver/timeout không được gắn PASS. | Initialization thành công chưa chứng minh đúng vật lý hoặc hội tụ. |
| Hình học solver thực dùng | Đối chiếu OBST từ chỉ số SMV, dịch lưới, bề dày và khoảng hở | Đã PASS trên **OBST, một MESH** trong ca đã lưu. | Adapter trả `INCONCLUSIVE` khi input có GEOM/HOLE/VENT hoặc nhiều MESH; một số trường hợp lưới/làm tròn chưa chứng minh cũng bị chặn. |
| Tổng hợp simulation verdict | Trạng thái cấp simulation | [AcceptanceReport.finalize](../../ifc_to_fds/domain/validation/model.py) hiện chỉ gán `REJECTED` hoặc `INCONCLUSIVE` cho `simulation_status`. | Không có nhánh tạo `SIMULATION_VERIFIED` trong hàm tổng hợp hiện tại, dù enum có giá trị này. |

**Kết luận:** module đã có cơ chế hữu ích để phát hiện và thể hiện giới hạn bằng chứng. Tuy nhiên chưa có đường nghiệm thu mô phỏng hoàn chỉnh; adapter hình học hiệu dụng còn giới hạn đáng kể.

Đặc biệt, `structural_completeness=PASS` của MEP fixture không chứng minh bảo toàn kết cấu: fixture đó có 0 structural entities. Tương tự, không dùng `mep=PASS` trên tiny/Institute có graph rỗng để quảng bá khả năng HVAC/PCCC.

## 8. Module Reference — đối chiếu chuẩn độc lập

Mã: [reference](../../ifc_to_fds/modules/reference). Đầu ra chính: candidate/reference bundle, integrity report và parity report.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Tạo candidate | Bundle nguồn, cấu hình, hình học, provenance và checksum | Có kiểm tra đóng gói và tính toàn vẹn. | Candidate sinh từ converter không tự trở thành chuẩn độc lập. |
| Trạng thái/phê duyệt reference | Draft/approved cùng dấu vết phê duyệt | Draft không được dùng để kết luận PASS; integrity đúng nhưng chưa phê duyệt vẫn `INCONCLUSIVE`. | Tests reference approved chủ yếu là dữ liệu kiểm soát; chưa chứng minh có chuẩn công trình thực đã nghiệm thu. |
| Kiểm tra integrity | Phát hiện sửa nguồn, mesh, graph, bundle | Có mutation tests kể cả khi checksum bị tính lại. | Integrity không đảm bảo người phê duyệt đã xác nhận đầy đủ ý nghĩa vật lý. |
| Parity và alias | So sánh hình học/quan hệ thay vì chỉ tên/ID | Alias cần bằng chứng hình học; thay mesh/port network bị phát hiện. | Tiny/opening/MEP đang có golden-reference gate `NOT_APPLICABLE` vì không chọn reference. |

**Kết luận:** nền tảng quản trị reference đã có kiểm tra. Chưa có bằng chứng nghiệm thu đầu ra dự án thực bằng reference độc lập được phê duyệt trong các ca đang đánh giá.

## 9. Module Artifacts — gói kết quả và checkpoint

Mã: [artifacts](../../ifc_to_fds/modules/artifacts). Bộ đầu ra gồm FDS, manifest JSON/CSV, acceptance JSON/Markdown, inventory, MEP graph, configuration, geometry JSON/ZIP, parity và checksums.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Lưu workspace chuyển đổi | File trung gian, dữ liệu geometry | Có kiểm tra lifetime, đường dẫn portable, tên nguồn và cleanup. | Workspace tạm chưa phải một bộ kết quả đã nghiệm thu. |
| Checkpoint | Bộ kết quả có thể tải khi cần chẩn đoán | Có kiểm tra tính nhất quán và resealing. | Checkpoint có thể là `DRAFT_NOT_SEALED`; tải được không có nghĩa verified. |
| Xuất bundle | Bộ file, ZIP, checksum và trạng thái seal | Có kiểm tra lỗi ghi, staging/rollback và bảo toàn bundle trước khi ghi lỗi. | Không suy rộng thành bảo đảm mọi tình huống concurrent publication chưa được kiểm tra. |
| Nhập/đọc bundle và geometry | Dữ liệu đã kiểm tra checksum/cấu trúc | Có chặn ZIP traversal, payload hỏng và sửa geometry dù hash lại. | Toàn vẹn lưu trữ và đúng ngữ nghĩa là hai yêu cầu khác nhau. |
| Artifact E2E FZK | Các file chuyển đổi thực sự được tạo | Test kiểm tra tồn tại file, CSV không rỗng và số record manifest. | Test hiện **không assert `MAPPING_VERIFIED`**; không dùng test này làm bằng chứng nghiệm thu hình học FZK. |

**Kết luận:** chất lượng đóng gói/truy nguyên có bằng chứng tích cực. Chất lượng kỹ thuật của nội dung phụ thuộc report của từng bundle.

Khoảng trống test cụ thể: [test_artifact_storage.py](../../tests/modules/artifacts/test_artifact_storage.py), hàm `test_fzk_haus_e2e_conversion_and_artifacts`. Cần chọn expected verdict theo chất lượng fixture thực; không ép PASS để làm test xanh.

## 10. Module Jobs — thực thi nền và quản lý tài nguyên

Mã: [jobs](../../ifc_to_fds/modules/jobs). Đầu ra chính: job ID, trạng thái/stage, diagnostics và liên kết kết quả.

| Chức năng | Đầu ra | Chất lượng và bằng chứng | Giới hạn |
| --- | --- | --- | --- |
| Queue/dispatch | Job chuyển trạng thái theo tài nguyên/worker | Port tests gọi logic tick production, kiểm tra dispatch, queue timeout và quota RSS. | Chưa có bằng chứng soak/load nhiều người dùng dài hạn. |
| Persistence và startup | Trạng thái SQLite, xử lý job sau khởi động | Có tests lifecycle/startup và storage. | Không tương đương nền tảng distributed job nhiều node. |
| Cancel process tree | CANCELLED, process được dừng, logs | Đã hủy Institute 10,8 MB ở stage IFC_GEOMETRY: khoảng **65,8 ms**, 3 process thuộc job không còn; supervisor đóng xong. | Đây là thời gian gọi backend manager của một lần chạy, chưa bao gồm HTTP/UI và không phải SLA. |
| Timeout/RSS/admission | Dừng hoặc từ chối job vượt giới hạn | Có fake-port tests cho nhánh quyết định, cùng kiểm tra upload/body admission ở interface. | Cần tải thực tế để xác nhận cấu hình máy triển khai phù hợp. |
| Retention | Xóa dữ liệu tạm, giữ artifact durable | Production có nhánh giữ durable và giới hạn đường dẫn cleanup. | Test durable retention hiện tự mô phỏng vòng cleanup, chưa gọi trực tiếp `FilesystemJobRetention.sweep`/production tick cho hành vi cần bảo vệ. |
| Kết quả và diagnostics | Trạng thái job, bundle/report, lý do lỗi | API/UI có kiểm tra tải đúng job, auth, checkpoint lỗi và stale result. | `COMPLETED` mô tả job hoàn thành; phải đọc report để biết mapping có được nghiệm thu hay không. |

**Kết luận:** có bằng chứng tốt cho điều phối/cancel ở mức đã kiểm tra. Cần bổ sung kiểm tra retention production và tải đồng thời trước khi kết luận khả năng vận hành thực tế.

Bằng chứng: [real cancellation](../../scripts/out/layout-job-cancel/results.json), [lifecycle tests](../../tests/modules/jobs/test_job_lifecycle.py), [retention production](../../ifc_to_fds/modules/jobs/infrastructure/retention.py).

## 11. Frontend — chất lượng từng nhóm chức năng

Mã: [frontend features](../../frontend/src/features). Đây là module theo tính năng giao diện; không thay thế các module nghiệp vụ backend.

| Nhóm | Chức năng và đầu ra | Kết quả chất lượng hiện có | Phần chưa chứng minh |
| --- | --- | --- | --- |
| Sources | Nhập IFC, metadata, trạng thái nguồn, chọn nguồn | Có kiểm tra trùng STEP/GUID giữa nguồn, reset và tránh kết quả parse cũ ghi đè nguồn mới. | Độ chính xác metadata phụ thuộc BIM reader; chọn được file chưa chứng minh chuyển đổi thành công. |
| Preview | Hiển thị Web-IFC hoặc backend preview | Browser HTTP/WASM thật đã PASS; lỗi hiển thị được kiểm tra khả năng phục hồi. | Ca preview lớn dùng file khoảng 33 MiB được padding nhưng chỉ 17 wall; chưa chứng minh hiệu năng mô hình hình học phức tạp. Luồng Web-IFC qua `file://` chưa có bằng chứng PASS. |
| Model tree | Cây phần tử, tìm/chọn và đồng bộ selection | Harness selection và ID theo nguồn đạt. | Chưa có benchmark tương tác trên cây hàng chục nghìn phần tử thực. |
| Inspector | Thông tin phần tử, focus/back, hide/show, isolate và khôi phục | Các thao tác và restore/undo đã được kiểm tra bằng harness. | Xem đúng thuộc tính không chứng minh mapping/material vật lý đúng. |
| Scope | Section box, clipping, domain controls và phạm vi xuất | Có kiểm tra wiring/trạng thái và scope backend riêng. | Cần phân biệt thao tác xem với cấu hình xuất; không tự coi hình đang nhìn thấy là toàn bộ nội dung FDS. |
| Conversion | Quick export; Verified job, tiến độ, cancel, lịch sử, kết quả | Quick giữ parity; Verified browser fixture đạt mapping và tải file; harness chặn job/kết quả cũ ghi đè job mới. | Quick còn ba mismatch tam giác đã nêu; Verified kế thừa giới hạn hình học/solver/backend. |
| Audit | Hiển thị report, gates, findings, reference workflow | Golden/audit/regression harness đạt; có trạng thái thiếu bằng chứng. | UI chỉ trình bày bằng chứng; không nâng `INCONCLUSIVE` thành kết quả nghiệm thu. |
| Artifacts | Tải FDS/report/checkpoint, xem geometry, reset download | Harness kiểm tra auth, đúng job, stale URL, lazy concurrency và dispose. Browser download thật đã PASS. | Tải thành công chỉ chứng minh phân phối artifact, không chứng minh nội dung đạt nghiệm thu. |
| App lifecycle | Mount/destroy, listener, canvas và worker cleanup | Browser đã lưu: listeners `[2,2] → [0,0] → [2,2]`; canvas sau destroy bằng 0; harness mới chạy lại PASS. | Chưa có soak test nhiều giờ hoặc mọi trình duyệt/GPU. |

## 12. Chất lượng kiến trúc và tác động đến đầu ra

- Tám module backend có public API/contracts và dependency tests; 51 implementation target đã di chuyển được kiểm tra hash. Các interface HTTP/CLI/worker và application workflow điều phối các module.
- Frontend đã chia theo tính năng, có dependency injection và vòng đời teardown được kiểm tra.
- Nhiều Pydantic domain model vẫn dùng chung tại `ifc_to_fds/domain`; đây là Modular Monolith dùng DDD có chọn lọc, chưa phải các bounded context tách biệt hoàn toàn.
- Các facade tương thích giúp giữ import cũ; số lượng facade và việc engine verification còn lớn vẫn tạo chi phí bảo trì.
- SOLID/ports giúp kiểm tra nhánh lỗi, process và storage dễ hơn. Chúng không tự bảo đảm mesh, ánh xạ MEP hoặc mô phỏng vật lý chính xác.

## 13. Hiệu năng: kết quả nào có thể sử dụng

| Phép đo | Kết quả | Diễn giải đúng |
| --- | --- | --- |
| Tiny, bản hiện tại, cold/warm trong phép đo đã lưu | Khoảng 0,517 / 0,508 giây; khoảng 128 MiB | Thời gian convert+audit không gồm import Python khoảng 1,2 giây; chỉ đại diện fixture rất nhỏ. |
| Institute, lần hoàn tất trước đó | Trước 127,41 giây; sau 129,10 giây; cả hai `REJECTED` | Là phép đo hoàn tất có lưu, nhưng đầu ra không đạt hình học. |
| Institute, phép đo gần nhất, baseline | Cold 134,41 giây / 374,7 MiB; warm 193,19 giây / 382,5 MiB; đều `REJECTED` | RAM này thuộc baseline, không gán sang bản hiện tại bị timeout. |
| Institute, phép đo gần nhất, hiện tại | Cold >300 giây; warm chưa chạy | Không thể nghiệm thu hiệu năng hoặc đưa số RAM/thời gian cuối cùng cho run này. |

Snapshot chẩn đoán từng ghi nhận thời gian tại kiểm tra mesh/`np.unique` và self-intersection dùng số hữu tỉ chính xác. Đây là vị trí cần profiling, chưa phải kết luận nguyên nhân gốc hoặc bằng chứng rằng toàn bộ biến động do một hàm cụ thể.

Bằng chứng: [conversion log](../../.cache/layout-benchmark-conversion.log), [partial results](../../scripts/out/layout-benchmark-conversion/results.json), [diagnostic log](../../.cache/layout-benchmark-diagnostic.log).

## 14. Công việc ưu tiên để nâng chất lượng đầu ra

| Ưu tiên | Việc cụ thể | Bằng chứng cần có để đóng việc |
| --- | --- | --- |
| 1 | Tái hiện Institute; profiling từng stage và entity; giải thích geometry/geometry-preservation FAIL, đồng thời khoanh vùng timeout. | Report chỉ ra entity/metric sai; so sánh before/after có cấu hình cố định và đủ thời gian/RSS/status. Ngưỡng nghiệm thu hiệu năng phải được xác định theo yêu cầu, không tự bỏ kiểm tra hoặc nới tolerance. |
| 2 | Đánh giá IFC MEP/PCCC có hình học thật, ports, phân loại và hệ thống được xác nhận. | Inventory/graph đối chiếu nguồn; geometry hợp lệ; domain rõ; unresolved được xử lý bằng chứng; reference độc lập được phê duyệt. Không tự suy vận hành từ tên thiết bị/hệ thống. |
| 3 | Xác định và bổ sung phạm vi solver/effective-geometry cần hỗ trợ; kiểm tra nhập PyroSim thật. | Có fixtures cho GEOM/HOLE/VENT/nhiều MESH theo phạm vi được chọn; đối chiếu hình học solver thực dùng; ghi rõ trường hợp chưa hỗ trợ. Có kết quả nhập PyroSim cùng phiên bản và diagnostics. |
| 4 | Củng cố test đang tạo cảm giác bao phủ quá mức. | Test durable retention gọi production sweep/tick; FZK E2E xác nhận expected verdict/gates có căn cứ; không chỉ assert file tồn tại. |
| 5 | Truy ngược ba mismatch tam giác Quick. | Danh sách face/entity khác biệt, nguyên nhân, ảnh hưởng volume/bề mặt/openings. Chỉ cập nhật baseline khi có bằng chứng giải thích thay đổi. |
| 6 | Làm rõ phạm vi nghiệm thu simulation và kiểm tra tải vận hành. | Đặc tả physics/scenario/mesh/operational model; chỉ bổ sung đường `SIMULATION_VERIFIED` khi các điều kiện có bằng chứng. Có load/soak/cancel/download/retention test trên cấu hình triển khai thực. |

## 15. Kết luận sử dụng hiện tại

Đã có nền tảng chuyển đổi có truy nguyên, quản lý job, lưu artifacts và kiểm chứng độc lập ở nhiều bước. Có thể sử dụng các fixture đạt để chứng minh phạm vi mapping tương ứng và dùng report để nghiên cứu các ca chưa đạt.

Chưa có cơ sở kết luận mọi IFC đều chuyển đổi đúng, HVAC/PCCC thực tế đã được ánh xạ đầy đủ, mô hình lớn đạt hiệu năng hoặc đầu ra đã sẵn sàng cho nghiệm thu mô phỏng cháy. Hai điểm cần xử lý trước là chất lượng hình học/hiệu năng Institute và bằng chứng MEP thực tế.

Lần rà soát này bổ sung tài liệu đánh giá và chạy lại kiểm tra có chọn lọc; không thay đổi thuật toán hoặc các ngưỡng nghiệm thu.
