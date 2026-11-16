# Audit IFCtoFDS — Kiến trúc mã nguồn, đóng gói Docker và trạng thái M6

- Thời điểm lập báo cáo · 2026-11-15 17:34:57 +07:00 (Asia/Bangkok, UTC+7).
- Công cụ · Codex, Git, Python AST, pytest.
- Commit phân tích · `e448e11d43d2fe004dff28d95f0fb18cfb58b903`. Mốc lưu audit và kế hoạch M6 · `6d6fdb103a7bf6e3ce4b688bfeb6b94dda98dc95`.
- Phạm vi · Đối chiếu hai bản đề xuất kiến trúc, ba bước ưu tiên và audit gốc. Tham chiếu bản đề xuất 430 dòng bằng SHA-256 `c4907fc4dfa8358a76261a3948d78761849ce6c39a1834887a0dda6dd752bdc3` và bản bổ sung 110 dòng bằng `d0f34cca2cc8a830a3e91c7569a06114713b0957b10156b5bf81e4ccadb88b6a`. Số dòng đề xuất bên dưới dùng để đối chiếu văn bản đính kèm.

| ID | Mức | Phát hiện tại `e448e11` | Dấu hiệu kiểm được |
| --- | --- | --- | --- |
| EV-PACK-01 | P1 | Image runtime mặc định thiếu dữ liệu preset EV | CLI/API đi vào loader sẽ lỗi `Unknown EV preset … (missing auto-nmc.json)` khi thư viện không có |
| F2 | P1 | Chuẩn bị và audit dùng lại cùng compiler HVAC | VENT trong ô cửa lọt qua audit cũ. FDS dừng `ERROR(818)`. VENT bám tường nhưng lệch port có thể qua FDS setup |
| F2-SMV | P2 | Bộ đọc VENT hiệu dụng dùng sai trường ghép ID | FDS ghi ordinal `1`, bộ đọc tra `SURF_INDEX=5` vào danh sách có một mục |
| ARCH-01 | P2 | `validation → fire` giữ đồng thời công thức dịch vụ và I/O nạp preset | Chuyển hàm `calculate_d_star` vẫn để lại lời gọi loader qua `ev_peak_hrr_evidence` |
| ARCH-02 | P2 | Mẫu AST trong đề xuất bỏ sót import tương đối và import gói con qua alias | Có thể thêm cạnh ngược bằng hai câu `from … import …` thông dụng mà test đề xuất vẫn đạt |

F2 và F2-SMV có dữ liệu, công thức, trích dòng và cổng nghiệm thu trong [thiết kế đối chứng HVAC](AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md). [Audit gốc lúc 16:04:27, UTC+7](AUDIT_2026-11-15_ifctofds-chuyen-doi-hvac-fds.md) giữ đủ nội dung hình học, chuyển đổi, HVAC, áp suất, EV, nghiên cứu lưới và đối chiếu PyroSim/QCVN theo mốc của nó.

## EV-PACK-01 — Thiếu thư viện preset trong image runtime

1. `.dockerignore:16` loại `reference-cases` khỏi build context. `Dockerfile:34–44` chỉ chép metadata, mã Python và web tĩnh. Hai tệp dữ liệu mặc định trong Git là `reference-cases/ev-library/auto-nmc.json` và `e-bike-lfp.json`.
2. `ev_library.py:89–110` chọn đường dẫn override `IFCFDS_EV_LIBRARY_DIR` nếu có, sau đó dùng thư mục mặc định tính từ `__file__`. Loader chỉ mở dữ liệu khi resolve preset. `scenario_emitter.py:214–218` đi vào loader khi kịch bản chỉ ra preset. `compose.production.yml:9–23,35–38` cấp cấu hình service và volume jobs. Cấu hình mặc định cần thư viện EV trong image.
3. `container.yml:48–59` build image và kiểm gói hệ điều hành. Healthcheck của Dockerfile chỉ gọi API health. Chuỗi lệnh hiện tại cho phép build và app startup đạt trước khi tính năng EV gặp lỗi. Kết luận đóng gói dựa trên luồng file và cấu hình trong Git.
4. **Đã tái hiện loader** trong venv. Mặc định liệt kê `auto-nmc` và `e-bike-lfp`, `load_ev_preset("auto","nmc").preset_id == "auto-nmc"`. Chuyển riêng biến môi trường của tiến trình thử đến thư mục chưa tồn tại thì danh mục rỗng và loader báo `Unknown EV preset 'auto'/'nmc' (missing auto-nmc.json)`. Docker build/run từ mốc này `NOT_RUN`.

**`.dockerignore` tại `e448e11`, L12–17**

<!-- source e448e11:.dockerignore:12:17 -->
```text
  12 | tests
  13 | docs
  14 | examples
  15 | demo
  16 | reference-cases
  17 | *.zip
```

**`Dockerfile` tại `e448e11`, L29–44**

<!-- source e448e11:Dockerfile:29:44 -->
```text
  29 | WORKDIR /app
  30 |
  31 | RUN groupadd --gid 10001 ifctofds \
  32 |     && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin ifctofds
  33 |
  34 | COPY pyproject.toml uv.lock README.md LICENSE ./
  35 | RUN uv sync --frozen --no-install-project --no-editable
  36 |
  37 | COPY ifc_to_fds ./ifc_to_fds
  38 | COPY js ./js
  39 | COPY css ./css
  40 | COPY index.html guide.html ./
  41 |
  42 | RUN uv sync --locked --no-editable \
  43 |     && mkdir -p /var/lib/ifctofds/jobs \
  44 |     && chown -R 10001:10001 /var/lib/ifctofds
```

**`Dockerfile` tại `e448e11`, L50–60**

<!-- source e448e11:Dockerfile:50:60 -->
```text
  50 | HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  51 |     CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"]
  52 |
  53 | CMD ["python", "-m", "ifc_to_fds", "serve", "--host", "0.0.0.0", "--port", "8000"]
  54 |
  55 | # Optional target (`docker build --target solver`): the runtime image plus FDS 6.11.1 for the solver gates.
  56 | # The official Linux release is a shell header followed by a gzip tar. Instead of running its interactive
  57 | # installer, check the SHA-256 of the whole file (the digest GitHub publishes for the release asset), cut the
  58 | # tar out exactly as the installer does, keep only the OpenMP solver and its bundled MPI runtime, and check the
  59 | # solver binary's hash too.
  60 | FROM runtime AS solver
```

**`ifc_to_fds/fire/ev_library.py` tại `e448e11`, L89–110**

<!-- source e448e11:ifc_to_fds/fire/ev_library.py:89:110 -->
```text
  89 | def library_dir() -> Path:
  90 |     override = os.environ.get("IFCFDS_EV_LIBRARY_DIR")
  91 |     if override:
  92 |         return Path(override)
  93 |     return Path(__file__).resolve().parents[2] / "reference-cases" / "ev-library"
  94 |
  95 |
  96 | def load_ev_preset(vehicle_class: str, chemistry: str) -> EVPreset:
  97 |     name = f"{vehicle_class.strip().lower()}-{chemistry.strip().lower()}.json"
  98 |     target_dir = library_dir().resolve()
  99 |     path = (target_dir / name).resolve()
 100 |     if path.parent != target_dir or "/" in name or "\\" in name:
 101 |         raise ValueError(f"Path traversal detected: {vehicle_class!r}/{chemistry!r}")
 102 |     if not path.is_file():
 103 |         raise ValueError(
 104 |             f"Unknown EV preset {vehicle_class!r}/{chemistry!r} (missing {name})"
 105 |         )
 106 |     try:
 107 |         payload = json.loads(path.read_text(encoding="utf-8"))
 108 |     except json.JSONDecodeError as exc:
 109 |         raise ValueError(f"Invalid EV preset JSON {name}: {exc}") from exc
 110 |     return EVPreset.model_validate(payload)
```

**`ifc_to_fds/fire/scenario_emitter.py` tại `e448e11`, L214–218**

<!-- source e448e11:ifc_to_fds/fire/scenario_emitter.py:214:218 -->
```text
 214 |
 215 | def _resolve_preset(preset_id: str) -> EVPreset:
 216 |     if "-" in preset_id:
 217 |         vclass, chem = preset_id.rsplit("-", 1)
 218 |         return load_ev_preset(vclass, chem)
```

**`.github/workflows/container.yml` tại `e448e11`, L45–59**

<!-- source e448e11:.github/workflows/container.yml:45:59 -->
```text
  45 |       - name: Validate compose expansion
  46 |         run: docker compose -f compose.production.yml config --quiet
  47 |
  48 |       - name: Build runtime image
  49 |         run: docker build --pull --tag ifctofds:ci .
  50 |
  51 |       - name: Verify exact Debian security package versions inside production image
  52 |         shell: bash
  53 |         run: |
  54 |           set -euo pipefail
  55 |           docker run --rm --read-only --entrypoint sh ifctofds:ci -ec '
  56 |             test "$(dpkg-query -W -f="\${Version}" apt)" = "3.0.4"
  57 |             test "$(dpkg-query -W -f="\${Version}" libapt-pkg7.0)" = "3.0.4"
  58 |             test "$(dpkg-query -W -f="\${Version}" zlib1g)" = "1:1.3.dfsg+really1.3.1-1+deb13u1"
  59 |           '
```

### Sửa nhỏ theo thứ tự ưu tiên 1

Cấp lại đúng các JSON preset công khai trong build context và `COPY` tường minh vào `/app/reference-cases/ev-library/` ở stage runtime. Solver image kế thừa stage này. Mẫu cho `.dockerignore` bên dưới thay đúng dòng loại trừ thư mục hiện tại. Đặt các ngoại lệ sau dòng tương ứng vì quy tắc khớp sau cùng có hiệu lực. [Docker build context, `.dockerignore`](https://docs.docker.com/build/concepts/context/#dockerignore-files).

```dockerignore
reference-cases/*
!reference-cases/ev-library/
reference-cases/ev-library/*
!reference-cases/ev-library/*.json
```

```dockerfile
COPY reference-cases/ev-library/ ./reference-cases/ev-library/
```

Xác nhận working directory `/app` và module mặc định mà lệnh `python -m ifc_to_fds serve` thực sự nạp. `uv sync --no-editable` cũng tạo bản cài trong site-packages. Nếu hợp đồng image gồm gọi console script hoặc chạy từ thư mục khác, đặt đường dẫn thư viện tuyệt đối qua `IFCFDS_EV_LIBRARY_DIR` trong image hoặc đóng gói resource đúng chỗ bản cài tìm thấy và kiểm cửa vào tương ứng. Smoke tối thiểu của production chạy sau bước build bằng user image, rootfs chỉ đọc và không bind mount mã hoặc preset. Đây là ví dụ lệnh cho workflow Linux.

```bash
docker run --rm --read-only --entrypoint python ifctofds:ci \
  -c 'from ifc_to_fds.fire.ev_library import load_ev_preset; p = load_ev_preset("auto", "nmc"); assert p.preset_id == "auto-nmc"'
```

Nghiệm thu ghi exit code và kết quả resolve trước/sau trên runtime image. Kiểm preset thứ hai hoặc so danh sách ID công khai cùng lệnh nếu yêu cầu image chứa đủ thư viện. Kiểm đường dẫn mà Compose thực chạy. Việc đổi ID preset công khai hoặc thay giá trị HRR có cổng kiểm kịch bản riêng.

## ARCH-01 — Gỡ phụ thuộc của checker vào bộ nạp EV

`mesh_resolution.py:16` nhập đồng thời hàm `calculate_d_star` và `ev_peak_hrr_evidence` từ `fire.mesh_metrics`. Hàm đầu chỉ tính `D* = (Q̇/1111.4)^0.4` với `Q̇` tính bằng kW. Hàm sau lấy lựa chọn tường minh hoặc tự mở preset ở dòng 50. Khi lấy trung điểm khoảng, nó ghi rõ cơ sở giả định và giá trị khoảng. Vì vậy chỉ di chuyển công thức vẫn giữ cạnh `validation → fire` và tác động của việc thiếu JSON trong checker.

**`ifc_to_fds/validation/checkers/mesh_resolution.py` tại `e448e11`, L15–25**

<!-- source e448e11:ifc_to_fds/validation/checkers/mesh_resolution.py:15:25 -->
```text
  15 |
  16 | from ifc_to_fds.fire.mesh_metrics import calculate_d_star, ev_peak_hrr_evidence
  17 |
  18 | def _indicator_band(ratio: float) -> str:
  19 |     """Describe D*/dx without turning historical validation values into acceptance limits."""
  20 |
  21 |     if ratio < 4.0:
  22 |         return "BELOW_HISTORICAL_4_16_SUBSET"
  23 |     if ratio <= 16.0:
  24 |         return "WITHIN_HISTORICAL_4_16_SUBSET"
  25 |     return "ABOVE_HISTORICAL_4_16_SUBSET"
```

**`ifc_to_fds/fire/mesh_metrics.py` tại `e448e11`, L7–20**

<!-- source e448e11:ifc_to_fds/fire/mesh_metrics.py:7:20 -->
```text
   7 | from ifc_to_fds.fire.ev_library import load_ev_preset
   8 |
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
```

**`ifc_to_fds/fire/mesh_metrics.py` tại `e448e11`, L43–60**

<!-- source e448e11:ifc_to_fds/fire/mesh_metrics.py:43:60 -->
```text
  43 |     preset_id = getattr(ev, "preset_id", None) or (
  44 |         ev.get("preset_id") if isinstance(ev, dict) else None
  45 |     )
  46 |     if preset_id:
  47 |         preset_key = str(preset_id).strip().lower()
  48 |         if "-" in preset_key:
  49 |             vehicle_class, chemistry = preset_key.rsplit("-", 1)
  50 |             preset = load_ev_preset(vehicle_class, chemistry)
  51 |             minimum_mw, maximum_mw = preset.peak_hrr_mw_range
  52 |             return {
  53 |                 "peak_hrr_kw": ((minimum_mw + maximum_mw) / 2.0) * 1000.0,
  54 |                 "peak_hrr_basis": "PRESET_RANGE_MIDPOINT_ASSUMPTION",
  55 |                 "peak_hrr_range_kw": [
  56 |                     minimum_mw * 1000.0,
  57 |                     maximum_mw * 1000.0,
  58 |                 ],
  59 |                 "preset_id": preset.preset_id,
  60 |                 "preset_confidence": preset.confidence,
```

Bước ưu tiên 2 là truyền evidence HRR đã phân giải qua đầu vào checker hiện có ở cửa vào kịch bản. Kiểm các caller `validation.engine` (deck chung), `adapters/jobs/runner.py` (scenario) và nhánh `fire/mesh_plan_evidence.py` của mesh study trước khi chuyển. Giữ đủ `peak_hrr_kw`, `peak_hrr_basis`, khoảng, ID preset và nguồn trích dẫn. Checker tiếp tục lấy HRR từ deck trong các ca được hỗ trợ và giữ lý do `NOT_APPLICABLE`/`INCONCLUSIVE` khi thiếu dữ liệu hoặc có bất đồng. D*/Δx là chỉ báo độ phân giải và ngưỡng nghiệm thu phải thuộc profile hoặc phép nghiên cứu lưới. Đặt công thức thuần ở nơi dùng chung có trách nhiệm rõ ràng nếu hai phía tiếp tục cần cùng biểu thức. PR riêng về việc nạp dữ liệu và công thức dùng bằng chứng hồi quy về chọn preset, sai số số học và báo cáo.

## ARCH-02 — Giới hạn cạnh phụ thuộc bằng baseline tĩnh

Đếm từ tệp do Git theo dõi tại `e448e11` bằng AST, gộp một lần trên mỗi tệp nguồn và gói đích. Có 176 tệp Python sản phẩm (23.909 dòng vật lý), 154 tệp Python kiểm thử (27.799 dòng) và 162 tệp `docs/`. Bảng đếm hai chiều cho thấy coupling cấp gói. Vòng import gây lỗi khởi động còn phụ thuộc module cụ thể, thời điểm import và lối vào.

| Cặp gói | A → B | B → A |
| --- | ---: | ---: |
| `adapters ↔ validation` | 2 | 1 |
| `core ↔ geometry` | 1 | 8 |
| `core ↔ mep` | 1 | 2 |
| `fire ↔ validation` | 8 | 1 |
| `geometry ↔ validation` | 3 | 9 |
| `mapping ↔ validation` | 2 | 4 |

Mẫu trong bản đề xuất 430 dòng, L390–411 kiểm `node.module.startswith("ifc_to_fds.")`. `from ..validation import engine` có `level=2` và `module="validation"`. `from ifc_to_fds import validation` có `module="ifc_to_fds"` và tên package ở `node.names`. Hai trường hợp đều lọt qua. L414–426 chỉ áp hai mệnh đề cho `domain` và cặp `fire↔validation`. Trình đọc import tương đối và alias đã có ở `tests/test_architecture_contracts.py:15–43`. Tệp kiểm thử cũng có phép thử import từ tiến trình mới tại L269. Phép kiểm AST hỗ trợ chặn nợ kiến trúc và phép kiểm tiến trình mới xác nhận hành vi khởi động.

**`tests/test_architecture_contracts.py` tại `e448e11`, L15–43**

<!-- source e448e11:tests/test_architecture_contracts.py:15:43 -->
```text
  15 | def get_imported_modules(py_file: Path) -> Set[str]:
  16 |     """Parse python source using AST and collect all fully-qualified imported module names."""
  17 |     content = py_file.read_text(encoding="utf-8")
  18 |     tree = ast.parse(content, filename=str(py_file))
  19 |     imported = set()
  20 |
  21 |     rel_path = py_file.relative_to(ROOT_DIR.parent)
  22 |     pkg_parts = rel_path.parent.parts
  23 |
  24 |     for node in ast.walk(tree):
  25 |         if isinstance(node, ast.Import):
  26 |             for alias in node.names:
  27 |                 imported.add(alias.name)
  28 |         elif isinstance(node, ast.ImportFrom):
  29 |             if node.level and node.level > 0:
  30 |                 base_len = len(pkg_parts) - (node.level - 1)
  31 |                 base = list(pkg_parts[:max(0, base_len)])
  32 |                 if node.module:
  33 |                     base.extend(node.module.split("."))
  34 |                 module_name = ".".join(base)
  35 |                 imported.add(module_name)
  36 |                 for alias in node.names:
  37 |                     imported.add(f"{module_name}.{alias.name}")
  38 |             else:
  39 |                 if node.module:
  40 |                     imported.add(node.module)
  41 |                     for alias in node.names:
  42 |                         imported.add(f"{node.module}.{alias.name}")
  43 |     return imported
```

Bước ưu tiên 3 là khóa baseline cho các cạnh tĩnh có phạm vi được chọn. Dùng nguồn tương đối trong package và đích đã normalize, giữ tập cạnh legacy tại `e448e11` với lý do. Chấm `actual − allowed` trên chiều bị hạn chế, báo tệp/dòng của mỗi cạnh mới. Việc xóa hoặc chuyển một trách nhiệm được duyệt làm giảm baseline tương ứng. Nếu cần bắt vòng dài hơn hai gói, kiểm thành phần liên thông mạnh trên đồ thị module đã normalize với fixture chu trình ba gói. Định nghĩa rõ phạm vi tĩnh của imports trong hàm, `TYPE_CHECKING`, alias gói, tương đối và `__init__.py`. Import động và vòng runtime có thể kiểm bằng smoke root, CLI, API và audit. Test về F2 vẫn cần phép thử phá dữ liệu và spy đường gọi.

Một lần kiểm trước đó trên mốc này cho thấy tiến trình import root `ifc_to_fds` không nạp `pydantic`, `ifcopenshell`, `trimesh` hoặc `fastapi`. Import `cli` và `pipeline` nạp ba gói đầu và chưa nạp FastAPI. CLI chạy ca fixture smoke tạo deck 693 byte, trả `MAPPING_VERIFIED`. Số liệu mô tả môi trường đã kiểm, còn thời gian khởi động, RSS và tải công việc production cần benchmark riêng.

## Đối chiếu các đề xuất tái cấu trúc

| Đề xuất | Hiện trạng kiểm tại mốc phân tích | Quyết định thiết kế cho phạm vi audit |
| --- | --- | --- |
| Thay cây thư mục bằng `compiler/` và ép giới hạn 350–400 dòng | Không có `ifc_to_fds/application/service.py`. `convert_verified.py` 139 dòng, `audit_conversion.py` 144 và `geometry/engine.py` 336. Các tệp lớn gồm `server.py` 692, `validation/engine.py` 793 và `geometry/mesh.py` 838. | Giữ điểm vào hiện tại. Chọn thay đổi theo hành vi cần đo. F2 cần tách luồng dữ liệu kiểm chứng và test tại `pipeline.audit`. |
| Thêm `SceneIR` và cấm mọi chiều ngang (bản 110 dòng, L19–32, L84–100) | Đã có `CanonicalModel`, `MappingPlan`, `SerializationResult` và các port application. Việc chuyển format giữa mọi pass thêm hợp đồng scope, trạng thái thiếu dữ liệu, provenance và tệp đã lưu. | Tận dụng model và input đã có. Xem lại IR khi một đầu ra thứ hai hoặc nhu cầu đo được đòi hỏi trường dữ liệu mới. |
| Cô lập toàn bộ `ifcopenshell.entity_instance` trong `core/` (L36–41) | `load_sources` chuyển native file cho phần đọc MEP và hình học tham chiếu. Việc đọc quan hệ IFC, placement và BRep cần các API này. Domain và checker thuần cần dữ liệu giới hạn rõ. | Thu port tham chiếu thành dữ liệu chỉ đọc ở điểm file còn mở. Phân định công việc cần IFC kernel bằng test fixture thật. |
| Khôi phục composition root (L43–51) | `bootstrap/container.py:33–51` đã lắp bộ chuẩn bị model, mapper, serializer, geometry writer và workspace theo port. | Bổ sung đầu vào audit ngay tại luồng hiện hành khi triển khai. |
| Đăng ký checker bằng decorator (L55–62) | Đã có `Checker` protocol, `CheckerOutcome`, thứ tự gate và điều kiện `finalize`. Điều kiện chấp nhận phụ thuộc các gate bắt buộc có mặt và có kết quả. | Dùng đăng ký tường minh hiện tại. Một registry tương lai phải phát hiện gate bắt buộc bị thiếu và giữ thứ tự, schema báo cáo và kết luận. |
| Tách nhóm dependencies và lazy import (L66–78) | `pyproject.toml:15–31` hiện cài các runtime dependencies cùng bộ, `test` là extra. Import root đo được đã nhẹ. CLI, server, worker và image cần phạm vi cài khác nhau nếu thay phân phối. | Muốn đổi cách cài cần tiêu chí dung lượng hoặc thời gian, kiểm wheel/CLI/worker và smoke image riêng. |
| Marker `unit`/`integration` sớm và unit dưới ba giây (L104–108) | `pyproject.toml:36–45` đã tách `solver`, `browser`, `slow`, `private`. Đo cặp suite nhỏ ở phần kết quả. | Dùng test tập trung theo đường gọi. Mốc ba giây và điểm “80–85% độ tối ưu” chưa có baseline hoặc thước đo. |

**`ifc_to_fds/bootstrap/container.py` tại `e448e11`, L33–51**

<!-- source e448e11:ifc_to_fds/bootstrap/container.py:33:51 -->
```text
  33 |     def get_convert_verified_use_case(self):
  34 |         """Wire the verified converter through explicit application ports."""
  35 |         from ifc_to_fds.application.use_cases.convert_verified import ConvertVerifiedUseCase
  36 |         from ifc_to_fds.adapters.conversion import (
  37 |             DefaultModelPreparer,
  38 |             DefaultMappingPlanner,
  39 |             DefaultFdsSerializer,
  40 |             DefaultGeometryPackageWriter,
  41 |         )
  42 |         from ifc_to_fds.adapters.storage.conversion_workspace import LocalConversionWorkspaceFactory
  43 |
  44 |         return ConvertVerifiedUseCase(
  45 |             audit_use_case=self.get_audit_conversion_use_case(),
  46 |             model_preparer=DefaultModelPreparer(),
  47 |             mapping_planner=DefaultMappingPlanner(),
  48 |             fds_serializer=DefaultFdsSerializer(),
  49 |             geometry_writer=DefaultGeometryPackageWriter(),
  50 |             workspace_factory=LocalConversionWorkspaceFactory(),
  51 |         )
```

Các thay đổi voxel fallback, nối port và quyết định ngoài hợp đồng HVAC hiện có gồm tác động hình học hoặc vật lý. Mỗi thay đổi cần review riêng, ca đối chứng và kết quả định lượng. Quy tắc origin/units, quan hệ IFC, bằng chứng solver và giới hạn áp dụng QCVN/TCVN đã lưu trong audit gốc. Đối chiếu FDS dạng chữ nhật F9 và đối chứng áp suất có tiêu chí khoa học riêng.

## Đối chiếu ID audit gốc và PR M6

Bảng dựa trên quan hệ Git với `origin/main=e448e11` tại lúc đối chiếu. Các commit ứng viên ở bảng vẫn nằm ngoài `origin/main` tại mốc đo. F6 đã có trong lịch sử `main`. Trạng thái CI dưới đây lấy theo tài liệu bàn giao `cfd5a77`. Ghi chú `M6` trong roadmap tại `6d6fdb1` ghi ba quyết định kỹ thuật. Mesh chồng nhau `FAIL` (F1), F4 áp cho mọi OBST và F9 dùng `ROUND=.FALSE.`. [Mốc M6](https://github.com/fire-digital-twin-lab/IFCtoFDS/blob/6d6fdb103a7bf6e3ce4b688bfeb6b94dda98dc95/docs/plans/production-roadmap.md), [bàn giao M6](https://github.com/fire-digital-twin-lab/IFCtoFDS/blob/cfd5a77/docs/plans/m6-review-handover.md).

| ID | Nội dung gốc | Commit ứng viên | Cần lưu ý |
| --- | --- | --- | --- |
| F1 | Hở miền MESH | `d063832` (#120) | Kiểm độ phủ và chồng lấn. Đối chứng hiện có báo B giữ `MAPPING_VERIFIED`. |
| F2 | VENT trên khoảng trống vượt cửa kiểm định | `cd64c09` (#123) | Chặn tại lúc dựng xuất. Bàn giao ghi test `pytest.approx` lồng nhau lỗi trên CI tại thời điểm đó. Đối chứng độc lập và F2-SMV có thiết kế riêng. |
| F3 | Bỏ lỗ mở chưa đo nhưng passage PASS | `6debb08` (#121) | Một số ca đổi gate mô phỏng có chủ ý. Bàn giao ghi cùng sửa `passage_resolution.py` với F4. |
| F4 | Solid mỏng co về đường/điểm trên lưới | `4f47dee` (#122) | Bàn giao ghi cần giải quyết xung đột F3/F4. A và C còn lượt xác minh sau khi tích hợp. |
| F5 | Lưu bundle lỗi trên đường dẫn Windows dài | `82d56a1` (#126) | Bàn giao ghi cổng nợ nguồn vướng import trong hàm. Lượt test dùng temp mặc định của audit này tại `e448e11` tái hiện lỗi ở `geometry/storage.py:54`. |
| F6 | Underflow khi đo xu hướng lưới | `beb435f` (#92) | Commit là tổ tiên của `origin/main` và ID đã đóng trong audit gốc. |
| F7 | Ô lưới thừa do `ceil` gần số nguyên | `5cd9e55` (#125) | Theo dõi snapshot từng mô hình khi tích hợp. |
| F8 | README lệch hợp đồng mesh/HVAC | `3bf41e5` (#127) | Phần README liên quan F2/F9 cần đi sau bản sửa tương ứng để đúng hành vi. |
| F9 | Thiếu `ROUND=.FALSE.` với ống `AREA/PERIMETER` | `6891bb5` (#124) | Bàn giao ghi 8 ca solver đạt. Deck đã lưu cần được đọc lại theo hướng tương thích đã chọn và ghi cảnh báo khoa học. |

## Tiêu chí bàn giao và kết quả

| ID | Kết quả tại thời điểm audit |
| --- | --- |
| AUD-D1 · Lưu toàn bộ các phần tại `docs/audit`, ghi thời gian và mốc | Khôi phục nguyên nội dung audit gốc 1.362 dòng từ `6d6fdb1`, SHA-256 `dbb9a9479adb28613e336ed58c2c360e1ce1695ba98c3c94f16dee744eb66996`. Hồ sơ F2 và hồ sơ này nối với cùng ID và mốc. |
| AUD-D2 · Audit logic và kiến trúc có chứng cứ từng dòng | Phân tích theo nguồn Git pin, review hai bản đề xuất, đo AST, nạp EV và đối chứng F2. Các code block đánh số là trích theo nguyên dòng của commit ghi trên block. |
| AUD-D3 · Thiết kế đối chứng độc lập và bằng chứng phân biệt port với mặt đỡ | Probe IFC/FDS thực tế cho F2, ca tường đặc, ca lệch port và ba probe số. Chi tiết kết quả và tiêu chí `HVAC-D1…D7` trong thiết kế. |
| AUD-D4 · Trạng thái kiểm thử | Lượt `pytest` với temp mặc định lỗi `WinError 3` ở bước ghi artifact (3 lỗi, 39 đạt, 2 deselected). Chạy lại với `--basetemp` ngắn dưới `.cache`, nguồn và test giống `e448e11` cho **42 đạt, 2 deselected trong 22,77 giây**. |
| AUD-D5 · Xác nhận các thay đổi đề xuất | Docker runtime build, kiểm CLI/API với checker mới, suite M6 tích hợp và phép đo trên A/B/C có trạng thái `NOT_RUN` trong lượt này. |

Lệnh kiểm thử tại workspace Windows dùng Python của venv dự án. Dùng `--basetemp` riêng cho từng lượt vì pytest làm trống thư mục này khi khởi động.

```powershell
$env:PYTHONUTF8 = '1'
$env:IFCFDS_SOLVER_AUTODISCOVERY = '0'
$hvacAuditTemp = '.cache/hva-' + [guid]::NewGuid().ToString('N').Substring(0,6)
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp $hvacAuditTemp tests/test_hvac_network.py tests/test_architecture_contracts.py -o faulthandler_timeout=90
```
