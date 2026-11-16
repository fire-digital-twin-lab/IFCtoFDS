# Kế hoạch xử lý phần audit 2026-11-15 nằm ngoài M6

**Mốc lập** · 2026-11-16, `origin/main=4d1b2ad`. Checkout lập kế hoạch `docs/m6-review-handover@cfd5a77`.

**Nguồn** · [Audit gốc](AUDIT_2026-11-15_ifctofds-chuyen-doi-hvac-fds.md) (F1–F9), [đối chứng HVAC](AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md) (F2-SMV, HVAC-D1…D7), [kiến trúc/Docker](AUDIT_2026-11-15_kien-truc-docker.md) (EV-PACK-01, ARCH-01, ARCH-02), [kế hoạch M6](m6-implementation-plan.md).

## 0. Hiện trạng đã kiểm

| ID | Trạng thái trên `origin/main=4d1b2ad` | Bằng chứng |
| --- | --- | --- |
| F1, F3, F4, F9 | Đã merge (#120, #121, #122, #124) | `gh pr list` |
| F2, F5, F7, F8 | PR mở: #123, #126, #125, #127, bàn giao #128 | `gh pr list` |
| EV-PACK-01 | **Còn mở.** `.dockerignore:16` vẫn loại `reference-cases`, `Dockerfile` không chép thư viện EV | `git show origin/main:.dockerignore` |
| F2-SMV | **Còn mở.** `effective.py:204–205` vẫn đọc `head[7]` | `git show origin/main:…/effective.py` |
| ARCH-01 | **Còn mở.** `mesh_resolution.py:16,143` vẫn gọi `ev_peak_hrr_evidence` | `git grep` |
| ARCH-02 | Chưa có test cạnh phụ thuộc gói | `tests/test_architecture_contracts.py` |
| HVAC-D1…D7 | Chưa triển khai | Audit mục 8 |

Hai tệp `AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md` và `AUDIT_2026-11-15_kien-truc-docker.md` **chưa có trong Git**. Bảng tiến độ cuối `m6-implementation-plan.md` dừng ở #120 và đã cũ so với `main`.

## 1. Quyết định phạm vi

| Đề xuất trong audit | Quyết định | Lý do |
| --- | --- | --- |
| EV-PACK-01: chép preset, smoke trên image | **Làm ngay** | P1, lỗi người dùng gặp thật trên image production, sửa vài dòng |
| F2-SMV: ghép theo ordinal `head[6]` | **Làm** | P2, cổng `effective_geometry` đang `FAIL` oan ở ca dương. Sửa cục bộ, độc lập |
| HVAC-D1/D2/D4/D5: checker đọc deck đã ghi để kiểm mặt đỡ và port | **Làm theo bước, đo trước** | Đây là lỗ hổng thật: compiler và checker dùng chung phép chọn hộp. Trước khi viết mới, đo xem `pipeline.audit` hiện tại bắt được ca nào |
| HVAC mục 5: chuyển toàn bộ kiểm topology/thủy lực ra khỏi `build_hvac_network` ("0 lần gọi builder") | **Hoãn, cần quyết định** | Chưa có ca lỗi thủy lực lọt qua. Viết lại lớn, rủi ro hồi quy cao. Mở lại khi có ca chứng minh |
| HVAC-D3: đa nguồn, transform, rebase | **Hoãn** | Ví dụ mm đã `PASS`. Làm khi có dự án nhiều IFC dùng HVAC |
| HVAC-D6: đa MESH, lưới không đều | **Hoãn sau T2** | Cần fixture FDS riêng. Ghi `NOT_RUN` |
| ARCH-01: checker nhận HRR đã phân giải từ cửa vào | **Làm sau M6** | Bỏ được cạnh I/O `validation → fire` và lỗi thiếu JSON trong checker |
| ARCH-02: baseline cạnh tĩnh toàn gói và SCC | **Thu nhỏ** | Chỉ khóa cạnh `validation → fire` bằng một test sau ARCH-01. Ratchet toàn gói chờ khi có vòng import gây lỗi thật |
| `compiler/`, `SceneIR`, decorator registry, tách deps, marker unit | **Không làm** | Audit kiến trúc đã đối chiếu và bác bỏ, đồng ý |

## 2. Các task

### T0 · Giữ hồ sơ và hoàn tất M6

- [ ] Commit hai audit chưa theo dõi lên một nhánh tài liệu, hoặc gộp vào #128. Nếu không, chúng chỉ còn trên một máy.
- [ ] Hoàn tất M6 theo [kế hoạch M6](m6-implementation-plan.md) P4–P6: #125 → #123 → #126 → #127 → #128. Cập nhật bảng tiến độ của kế hoạch đó theo trạng thái thật.

### T1 · EV-PACK-01 — preset EV trong image runtime

**Tệp** · `.dockerignore`, `Dockerfile`, `.github/workflows/container.yml`.

- [ ] Ghi kết quả trước sửa: build image và chạy smoke dưới đây phải lỗi `Unknown EV preset`.
- [ ] Trong `.dockerignore`, thay dòng `reference-cases` bằng khối ngoại lệ ở audit kiến trúc mục "Sửa nhỏ". Thêm `COPY reference-cases/ev-library/ ./reference-cases/ev-library/` vào stage runtime, cạnh các `COPY` mã nguồn.
- [ ] Xác nhận `ev_library.py` tìm được thư mục trong image với cửa vào thật `python -m ifc_to_fds serve` từ `/app`. Nếu bản cài `--no-editable` trong site-packages được nạp thay mã ở `/app`, đặt `IFCFDS_EV_LIBRARY_DIR=/app/reference-cases/ev-library` trong `Dockerfile`.
- [ ] Thêm một bước vào `container.yml` sau bước build: `docker run --rm --read-only --entrypoint python ifctofds:ci -c '…load_ev_preset("auto","nmc")…; …("e-bike","lfp")…'`. Cả hai preset phải resolve.

**Nghiệm thu** · EV1: smoke lỗi trước sửa, đạt sau sửa trên cùng workflow. EV2: image không chứa tệp khác trong `reference-cases/` (`docker run … ls`). EV3: Container workflow đạt.

### T2 · F2-SMV — đọc bảng VENT của SMV theo ordinal

**Tệp** · `ifc_to_fds/validation/effective.py`, test của module này.

- [ ] Tự xác minh định dạng trong `Source/dump.f90` của FDS 6.11.1 (link ở audit HVAC mục 6). Không chỉ dựa vào audit.
- [ ] Viết test đỏ trước bằng ca tường đặc `V_ROOM` (SMV ở audit mục 6): cổng hiện cho `FAIL`, kỳ vọng `PASS`.
- [ ] Sửa ghép ID theo `head[6]` (ordinal). Thêm ca hai VENT cùng `SURF_INDEX` nhưng ordinal khác nhau, và ca bảng chỉ có patch ngoại biên do FDS sinh. Patch ngoại biên không được tính là VENT bị xóa.
- [ ] Chạy solver: sinh SMV thật từ deck tường đặc của audit mục 7 bằng FDS 6.11.1 đã ghim, lưu làm fixture với SHA của deck và solver.

**Nghiệm thu** · SMV1: ca dương `effective_geometry=PASS`. SMV2: ca F2 trong ô cửa vẫn dừng ở `ERROR(818)` và không bị báo `PASS`. SMV3: test hai VENT cùng SURF đạt. Đa MESH: `NOT_RUN`, theo HVAC-D6.

### T3 · HVAC đối chứng độc lập, bước 1 (sau khi #123 merge)

**Tệp** · `ifc_to_fds/validation/checkers/hvac.py`, test HVAC mới. Không đổi chữ ký CLI/API.

- [ ] **3a. Đo trước.** Trên `main` có #123, viết test qua `pipeline.audit` cho ba ca deck đã sửa tay (cập nhật SHA artifact để không dừng ở checksum): (i) VENT trong ô cửa, (ii) VENT dời sang tường đặc nhưng lệch port, (iii) mất VENT. Ghi ca nào hiện đã `FAIL` và ca nào lọt `PASS`. Đây là HVAC-D2.
- [ ] **3b. Kiểm mặt đỡ từ deck đã parse.** Trong `HvacNetworkChecker`, tính `A_vent/A_supported/A_unsupported/A_unknown` cho mỗi VENT của HVAC từ `OBST`/`MESH` đọc bằng `parse_fds`, theo phân hoạch hình chữ nhật và quy tắc nửa mở ở audit mục 4. Không gọi `emitted_obst_boxes` hay helper của exporter. `HOLE`, `GEOM` hoặc OBST có điều khiển chạm VENT → `INCONCLUSIVE`.
- [ ] **3c. Kiểm port.** Chỉ làm khi 3a cho thấy ca (ii) lọt. So tọa độ port của IFC tham chiếu với `VENT.XB` đọc từ deck, dùng dung sai số học đã đo, không đặt ngưỡng 1 mm.
- [ ] Thứ tự `FAIL > INCONCLUSIVE > PASS`. Finding giữ `HVAC-001`, thêm `audit_id: "F2"` và mã lý do `NO_SUPPORT` / `PORT_OUTSIDE_XB` vào evidence.

**Nghiệm thu** · D1: ca F2 `hvac=FAIL`, `A_unsupported=0.24` m², kể cả khi solver tắt; một test spy chứng minh phép tính mặt đỡ không gọi `emitted_obst_boxes`. D2: ba ca 3a đều `FAIL` hoặc `INCONCLUSIVE` có lý do. D4: các fixture tính tay ở audit mục 4 và 7 (tường đặc, nửa hở 0,20 m², hai hộp đồng phẳng, mối nối MESH, pháp tuyến X/Y/Z). D5: CLI re-audit bundle trước F9 ở `.cache/m6-f9-base` giữ verdict. D7: suite mặc định và `verdict-snapshot --compare` cho FZK/Duplex/Institute giữ verdict, mọi khác biệt có lý do.

### T4 · ARCH-01 (+ phần ARCH-02 thu nhỏ), sau M6

**Tệp** · `validation/checkers/mesh_resolution.py`, `validation/engine.py` hoặc `ValidationContext`, `adapters/jobs/runner.py`, `fire/mesh_plan_evidence.py`, `tests/test_architecture_contracts.py`.

- [ ] Grep mọi caller của `ev_peak_hrr_evidence` và `calculate_d_star`. Phân giải HRR ở cửa vào kịch bản (runner hoặc scenario) và truyền dict evidence qua đầu vào checker hiện có. Checker không gọi loader nữa.
- [ ] Đặt `calculate_d_star` (một dòng công thức) ở nơi cả `fire` và `validation` được phép import. `fire.mesh_metrics` giữ re-export để không vỡ API.
- [ ] Thêm một test kiến trúc: không module nào trong `ifc_to_fds/validation/` import `ifc_to_fds.fire`. Test phải resolve cả `from ..fire import …` và `import ifc_to_fds.fire.x as y`, kèm ca phản chứng cho từng dạng.

**Nghiệm thu** · A1: `IFCFDS_EV_LIBRARY_DIR` trỏ thư mục rỗng vẫn chạy được audit deck chung; checker báo `INCONCLUSIVE`/`NOT_APPLICABLE` có lý do, không còn exception loader. A2: kịch bản EV giữ nguyên `peak_hrr_kw`, `peak_hrr_basis`, khoảng và `preset_id` trong báo cáo, so với snapshot trước sửa. A3: test kiến trúc đỏ khi thêm lại cạnh, xanh sau sửa.

## 3. Thứ tự và song song

```
T0 (M6) ──► T3 (cần #123 trên main)
       └──► T4 (tránh rebase vào validation/ đang đổi)
T1, T2: độc lập, làm ngay, mỗi task một worktree
```

Mỗi task là một PR. Commit tiếng Việt có dấu, giữ ID audit trong tiêu đề, ví dụ `fix(docker): đóng gói thư viện preset EV (EV-PACK-01)`.

## 4. Đóng audit

- Mỗi PR ghi ID, SHA merge và kết quả nghiệm thu vào Phần A của `production-roadmap.md`.
- Audit kiến trúc/Docker đóng khi EV-PACK-01 và ARCH-01 đã merge và ARCH-02 được ghi nhận là thu nhỏ có chủ ý. Audit HVAC đóng khi T2, T3 đã merge và các mục hoãn (mục 5, D3, D6) đã chuyển thành mục mở trong roadmap. Audit gốc đóng khi P6 của M6 xong. Khi đóng, chuyển bằng chứng cần giữ sang `docs/history/` rồi xóa khỏi `docs/audit/`.
