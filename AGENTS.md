# AGENTS.md — IFCtoFDS

## Phạm vi làm việc

- Tệp gốc này quy định cách làm việc trong repo. [AGENTS.md của gói ngữ cảnh](docs/agent-context/AGENTS.md) áp dụng khi làm việc trong cây `docs/agent-context/` và là tài liệu tham chiếu cho các phần còn lại của repo. Gói đó có `checksums.json`, nên không sửa tệp trong `docs/agent-context/` nếu chưa cập nhật checksum theo cách gói quy định. Các bước khởi động toàn bộ chương trình trong gói chỉ áp dụng khi được giao rõ ràng. Tra cứu [README](README.md) cho hành vi hiện tại và [chỉ mục ngữ cảnh](docs/agent-context/docs/README.md) cho đặc tả liên quan.
- [Kế hoạch production](docs/plans/production-roadmap.md) là nguồn chính cho trạng thái, mốc và cổng nghiệm thu của chương trình production. Đọc Phần A và mốc liên quan ở Phần B khi tiếp tục công việc. Kiểm tra nhánh và HEAD thực tế trước khi dựa vào các ghi chép về Git. Chỉ đánh dấu xong mốc khi qua cổng và trong phạm vi được phép cập nhật kế hoạch.
- Phân tích, review và lập kế hoạch mặc định chỉ đọc. Khi triển khai, giữ tương thích CLI, API, schema, báo cáo, artifact và job đã lưu nếu yêu cầu chưa cho phép đổi hợp đồng. Giữ giấy phép AGPL, thông báo bản quyền và thông tin trích dẫn nguồn.

| Mức việc | Kiểm tra tối thiểu |
| --- | --- |
| Nhỏ | Câu hỏi chỉ đọc tài liệu hoặc mã liên quan. Với sửa một dòng hoặc tài liệu, xem trạng thái tệp đích, đọc diff và soát whitespace, liên kết hoặc chạy phép kiểm nhỏ phù hợp. |
| Vừa | Với thay đổi hành vi cục bộ, xem `git status --short` và diff liên quan trước khi sửa. Tái hiện lỗi, chạy kiểm thử hồi quy và cổng CI liên quan, rồi kiểm tra diff cuối. |
| Lớn | Với thay đổi hình học, tiêu chí nghiệm thu, hợp đồng công khai, nhiều module hoặc mốc production, ghi nhánh, HEAD, diff đã stage và chưa stage, tệp mới và kết quả kiểm thử trước sửa. Chốt tiêu chí, đối chứng độc lập và chạy suite cùng các cổng của mốc trước khi nghiệm thu. |

## Yêu cầu lưu trong tệp

- Khi người dùng chỉ định prompt `.md`, mở đúng tệp khi bắt đầu, tiếp tục phiên, sau khi rút gọn ngữ cảnh và trước khi bàn giao. Đọc toàn bộ yêu cầu lúc bắt đầu, sau đó đối chiếu phần đang làm cùng các ràng buộc chung. Giữ nguyên prompt và ghi rõ các điều chỉnh được người dùng chấp thuận.
- Giữ ID tiêu chí nghiệm thu của prompt. Nếu chưa có ID, đánh số trong kế hoạch hoặc báo cáo. Đối chiếu từng tiêu chí với diff, kết quả lệnh, kiểm thử hoặc artifact thực tế. Khi thiếu tệp hay quyền đọc, nêu đường dẫn và phần việc bị chặn. Khi yêu cầu nằm trong chat, dùng nội dung người dùng đã giao.
- Với chương trình triển khai IFCtoFDS toàn diện được giao rõ ràng, đọc [START_AGENT_PROMPT.md](docs/agent-context/docs/START_AGENT_PROMPT.md) và [master prompt IFCtoFDS](docs/agent-context/docs/MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md). Các tệp này là tài liệu tham chiếu theo nhiệm vụ và mọi hành động vẫn chịu giới hạn của yêu cầu hiện tại.
- Với nhiệm vụ giao từ agent khác, thực hiện đúng phạm vi được giao, báo cáo theo ID tiêu chí và chuyển các phát hiện ngoài phạm vi về bên giao. Không tự gọi thêm một phiên Codex để giao lại cùng nhiệm vụ.

## Kiến trúc và hợp đồng IFC → FDS

| Khu vực | Điểm vào và ranh giới |
| --- | --- |
| Verified Conversion | `ifc_to_fds/cli.py`, `server.py` và facade `pipeline.py`. Dùng `application/`, `domain/`, `adapters/` và các module `core/`, `geometry/`, `mapping/`, `mep/`, `validation/` theo trách nhiệm hiện có. |
| Workbench và Quick Conversion | `index.html`, `js/`, `js/workers/`. Quick chỉ phục vụ xem trước hoặc xuất nhanh. |
| Kịch bản EV | `ifc_to_fds/fire/`. Xác minh nền và các điều kiện của kịch bản theo hợp đồng hiện có. |
| Kiểm thử và bằng chứng | `tests/`, `reference-cases/`, [workflow Verified](.github/workflows/verified.yml) và [workflow Quality](.github/workflows/quality.yml). |

- Giữ `entity_key = source_id:step_id`, tên nguồn, checksum và provenance. Kiểm kê đủ tập đối tượng thuộc phạm vi và ghi lý do loại trừ, không hỗ trợ hoặc sai lệch. Kiểm tra đơn vị và phép biến đổi tọa độ đã xác nhận khi ghép nhiều IFC.
- Phân biệt phạm vi xuất, miền CFD và clipping của viewer. Giữ lựa chọn tầng tổng quát. Với HVAC/PCCC, phân biệt `SOURCE_EXISTS`, `SEMANTIC_PRESERVED`, `GEOMETRY_MAPPED` và `FUNCTIONALLY_MODELED`.
- Với thay đổi ánh xạ, kiểm định độc lập bằng cách đọc lại IFC nguồn và FDS đã serialize, đối chiếu manifest, số lượng đối tượng, hình học và đường khí liên quan. Dùng ca đối chứng có đơn vị, dung sai và kết quả dự kiến độc lập với exporter. Chỉ báo `MAPPING_VERIFIED` khi đạt các gate của profile. Báo riêng trạng thái job, kết luận mapping và kết quả solver. Đưa `UNSUPPORTED`, `INCONCLUSIVE` và `DEVIATED` cần quyết định kỹ thuật ra review.

## Các lệnh cấm

- Không chạy `git reset --hard`, `git clean -fd` hoặc `git clean -fdx`, force-push, ghi trực tiếp lên `main` hay xóa công việc có sẵn. Chỉ stage đúng phạm vi. Commit, push, mở PR, merge và triển khai đều cần quyền cho thao tác tương ứng.
- Không sửa hoặc đổi tên IFC gốc, tự sinh cấu kiện còn thiếu, tạo port hoặc kết nối giả hay suy diễn lưu lượng, đường đặc tính quạt, sprinkler hoặc thiết bị CO. Không bỏ đối tượng im lặng. Không hardcode B1/B2 hoặc lấy clipping làm phạm vi xuất.
- Không tự đặt ngưỡng chung 1 mm hoặc 5%. Chỉ dùng bbox thay hình học phức tạp nếu đã đo sai số và dung sai được phê duyệt. Không fallback sang `GEOM` làm mất lỗ mở. Dòng `IFC_SOURCE` và việc xuất được `.fds` chỉ là dữ liệu đầu vào cho kiểm định. Quick Conversion giữ trạng thái preview hoặc xuất nhanh.
- Không sửa test, fixture hoặc snapshot để hợp thức hóa hồi quy. Chỉ xác nhận đã triển khai hay kiểm thử khi có bằng chứng thực tế.

## Cổng CI chặn PR

- [Quality](.github/workflows/quality.yml) chặn tăng nợ theo từng tệp Python thay đổi trong `ifc_to_fds/`. Cổng đếm import trong hàm, `except Exception` hoặc `BaseException`, `except:` và handler nuốt lỗi. Báo cáo inventory chạy riêng chỉ đưa số liệu.
- Trên PowerShell, đặt `$env:PYTHONUTF8 = '1'`. Đặt `$prBaseBranch` theo nhánh đích thực tế, rồi lấy `$baseSha = git merge-base HEAD "origin/$prBaseBranch"` từ ref đã cập nhật. Kiểm tra lệnh Git thành công trước khi chạy `python scripts/quality/source_quality_budget.py --git-base $baseSha`. Workflow ngoài PR dùng `HEAD^`.
- Script lấy danh sách tệp từ `git diff <base> HEAD` nhưng đọc mã trên đĩa. Chạy bước xác minh cuối trên đúng commit ứng viên với nội dung tương ứng. Kết quả local có thể bỏ sót tệp mới chỉ sửa hoặc stage. Ghi phần chưa được cổng kiểm nếu chưa có quyền commit. Đối chiếu SHA, base và bước lỗi trên CI khi kết quả khác local.
- [Verified](.github/workflows/verified.yml) chạy `python -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=90`, kiểm tra CLI khởi động mới và chạy các job JS, browser, solver theo workflow. Xem Quality để biết các cổng Ruff, Pyright và hồi quy JS đang áp dụng.
- Trước khi đẩy PR, chạy lại cục bộ phần Quality chạm tới mã đã sửa: `python -m ruff check --select E4,E7,E9,F63,F7,F82 scripts/quality/source_quality_budget.py ifc_to_fds/fire/scenario_verdict.py`, `npx --yes pyright --project scripts/quality/pyrightconfig.json`, cổng nợ nguồn ở trên và `python -m pytest -q tests/test_source_quality_budget.py`. Pyright chỉ kiểm các tệp liệt kê trong `scripts/quality/pyrightconfig.json`.
- CI cài bằng `pip install -e ".[test]"`, còn máy cục bộ dùng `uv sync --locked --extra test` theo `uv.lock`. Khi kết quả hai nơi khác nhau, so phiên bản gói trước khi kết luận.

## Bẫy Windows

- Đặt phần khởi chạy CLI hoặc tiến trình của script dùng `multiprocessing` hay `ProcessPoolExecutor` dưới `if __name__ == "__main__":` để `spawn` có thể import an toàn.
- Giữ đường dẫn worktree, thư mục tạm và cache ngắn. Khi kiểm tra lỗi cache, tính cả tên tệp tạm vào giới hạn Windows 260 ký tự nếu môi trường chưa hỗ trợ đường dẫn dài. CI có thể sử dụng cấu hình khác máy cục bộ.
- Một số test gọi `scripts/measure_architecture_baseline.py` và ghi lại `tests/baseline/snapshots/baseline_metrics.json`. Kiểm tra trạng thái tệp trước suite. Nếu tệp sạch từ đầu và diff sau suite chỉ do test sinh, khôi phục riêng tệp bằng `git restore --worktree -- tests/baseline/snapshots/baseline_metrics.json`. Nếu tệp đã có sửa đổi, bảo toàn bản đó trước khi chạy hoặc dùng worktree khác.

## Dữ liệu, snapshot và hiệu năng

- Giữ IFC thật, output dẫn xuất và thông tin xác thực ngoài repo, prompt và log được chia sẻ. Dùng bí danh A/B/C cùng số liệu tổng hợp trong báo cáo. Khi được phép chạy ca hầm riêng tư, đặt `IFCFDS_PRIVATE_BASEMENT_IFC` tới tệp ngoài repo cho test đánh dấu `private` (hiện chưa có test nào dùng marker này), hoặc chạy trực tiếp `python -m ifc_to_fds convert <ifc ngoài repo> -o <thư mục ngoài repo> --storey <storey_id>` với từng `storey_id` của hầm (tên tầng có thể trùng giữa các hệ cao độ). Lỗi nguồn đã được người xem xét truyền qua `--accepted-source-defects`. Ghi vào báo cáo chỉ bí danh và số liệu tổng hợp. Khi thiếu dữ liệu hoặc solver, báo riêng phép kiểm thực địa bị `BLOCKED` hoặc solver `NOT_RUN`.
- Để cập nhật snapshot đóng băng, giữ mốc cũ và sinh bản ứng viên ra ngoài tệp mốc. Đối chiếu từng trường, gồm các ID thêm hoặc mất, verdict, finding và chính sách sai số khi có. Với verdict, chạy `python scripts/verdict-snapshot.py <ifc> --compare <mốc.json>` rồi xem diff từng trường. Chỉ đưa bản đã được phép vào mốc sau khi giải thích mỗi khác biệt bằng đặc tả hoặc đối chứng. Ghi lý do trong nội dung commit tiếng Việt hoặc trong bàn giao nếu chưa được commit. Khi nới cổng, kiểm cả ca được cho qua và ca vẫn phải bị chặn.
- Đo trước và sau cùng phiên, cùng mô hình, phạm vi, cấu hình và trạng thái cache. Chạy tuần tự và kèm một lượt đối chứng cố định trong phiên, không chạy hai phép đo đồng thời. Với lượt cold, dùng `IFCFDS_GEOMETRY_CACHE` trỏ thư mục mới ngoài repo. Ghi SHA, kết quả đối chứng, thời gian và verdict. Nếu đối chứng lệch lớn, ghi điều kiện đo và chạy lại trước khi kết luận hiệu năng.

## Kiểm thử và bàn giao

Trên Windows dùng PowerShell và Python của môi trường dự án. Chọn phép kiểm theo phần thay đổi. Đối chiếu mục 14 của [README](README.md#kiem-thu) và workflow CI khi cần lệnh đầy đủ.

| Thay đổi | Kiểm tra |
| --- | --- |
| Python, CLI hoặc API | Chạy `python -m pytest -q` với các test liên quan trước. Với CLI, chạy thêm `python -m ifc_to_fds --help` và ca smoke phù hợp. Khi cần chuẩn bị môi trường cục bộ, dùng `uv sync --locked --extra test` theo roadmap. |
| Workbench hoặc worker | `node --check` với tệp JS đã sửa và test hồi quy tương ứng trong `scripts/`. Khi nguồn worker thay đổi, chạy generator tương ứng `node scripts/generate-inline-parse-worker.js` hoặc `node scripts/generate-inline-export-worker.js`, rồi `node scripts/test-worker-bundle-parity.js`. Sửa nguồn và sinh lại bundle `*-inline.js`. |
| Solver hoặc trình duyệt | Chưa có FDS thì chạy `python scripts/install-fds.py` (bản 6.11.1 ghim hash, vào `.deps/` đã gitignore, không cài hệ thống), rồi đặt `IFCFDS_SOLVER` tới `fds_openmp.exe` trong thư mục đó. Đặt `IFCFDS_SOLVER_AUTODISCOVERY=0` khi muốn chặn tự dò solver. Khi liên quan và môi trường đã sẵn sàng, chạy `python -m pytest -q -m solver` hoặc `python -m pytest -q -m browser`. Lượt pytest mặc định loại trừ `solver`, `browser`, `slow`. |
| Chỉ tài liệu | Soát nội dung, đường dẫn, lệnh được ghi và `git diff --check`. Đọc cả tệp mới chưa được Git theo dõi. |

- Bàn giao thay đổi, lệnh và kết quả thực tế. Với việc vừa hoặc lớn, ghi phiên bản đã kiểm tra cùng bằng chứng theo tiêu chí. Tách `PASS`, `FAIL`, `NOT_RUN`, `INCONCLUSIVE` và phần bị `BLOCKED`. Phân biệt kiểm thử triển khai, đối chiếu đặc tả và xác nhận khoa học.

## Git và ngôn ngữ

- Trao đổi, báo cáo và nội dung PR bằng tiếng Việt có dấu. Giữ nguyên định danh kỹ thuật.
- **Mọi commit mới do agent tạo phải viết tiêu đề và nội dung bằng tiếng Việt có dấu.** Dùng dạng `<loại>(<phạm vi>): <mô tả tiếng Việt>` với phạm vi tùy chọn. Ví dụ `fix(mapping): bảo toàn lỗ mở khi xuất hình học`.
- Dùng danh tính Git đã cấu hình. Không đặt Claude làm author hoặc committer và không thêm trailer `Co-Authored-By` cho Claude, dòng `Generated with Claude Code` hay trailer `Claude-Session` vào commit. Quy tắc ghi công Claude cũng áp dụng cho nội dung PR. Trước commit, soát diff đã stage, thông điệp và danh tính. Sau commit, kiểm tra lại bằng `git show -s --format=fuller HEAD`.
