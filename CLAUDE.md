@AGENTS.md

# CLAUDE.md — IFCtoFDS

## Thực hiện và giao việc

- Claude Code trực tiếp triển khai và kiểm chứng trong phạm vi được giao. Áp dụng mức kiểm tra nhỏ, vừa hoặc lớn trong `AGENTS.md`. Khi tiếp tục một mốc production, đọc [kế hoạch production](docs/plans/production-roadmap.md) và kiểm tra trạng thái Git thực tế.
- Dùng subagent sẵn có cho các phần độc lập hoặc review chỉ đọc khi hữu ích. Giao mục tiêu, tiêu chí theo ID, tệp được phép sửa, hành vi cần giữ và phép kiểm. Trong cùng worktree chỉ có một bên ghi tại một thời điểm.
- Khi các phần độc lập cần ghi song song, mỗi phần dùng một worktree, nhánh và môi trường riêng. Nếu worktree tự động bị từ chối, dùng `git worktree add` vào thư mục anh em có đường dẫn ngắn, ví dụ `../IFCtoFDS-wt-review`, khi có quyền ghi ở đó. Chạy `uv sync --locked --extra test` trong từng worktree. Dùng cache và output kiểm thử riêng. Nếu hướng dẫn hoặc prompt chưa có trong HEAD của worktree, chuyển nội dung cần thiết trong lượt giao việc. Nếu không có quyền tạo worktree ngoài repo, thực hiện tuần tự. Kiểm tra diff và chạy lại hồi quy liên quan sau tích hợp.
- Codex CLI là tùy chọn khi shell của Claude có `codex`. Nếu người dùng yêu cầu đích danh Codex mà CLI, xác thực hoặc sandbox chặn, báo phần không thực hiện được và làm tiếp phần độc lập đã được phép. Chỉ đổi phương thức cho phần đó khi người dùng đồng ý.

## Giữ yêu cầu qua các phiên

Khi người dùng chỉ định prompt `.md`, dùng đường dẫn đó và giữ ID tiêu chí khi giao việc. Đọc lại phần liên quan trước mỗi lượt giao. Nếu agent con không đọc được tệp, chỉ truyền nội dung cần thiết đã được phép chia sẻ. Nhắc agent con báo kết quả theo tiêu chí và giới hạn quyền của lượt giao, gồm quyền ghi, commit và các thao tác với remote.

Khi bắt đầu phiên mới, tiếp tục hoặc sau `/compact`, mở lại prompt và bản ghi tiến độ nếu đã được chỉ định. Với việc nhiều phiên, lưu đường dẫn prompt, SHA, bằng chứng theo tiêu chí và bước tiếp theo vào nơi theo dõi đã được phép. Nếu chưa có nơi theo dõi, ghi các thông tin đó trong bàn giao để phiên sau dùng lại. Ví dụ yêu cầu mở phiên với đường dẫn thực tế thay cho đường dẫn minh họa dưới đây.

> Đọc `<đường dẫn tệp yêu cầu .md>` (hiện repo chưa có thư mục `docs/tasks/`), thực hiện trong phạm vi tệp này và đối chiếu từng tiêu chí nghiệm thu trước khi bàn giao.

## Codex CLI tùy chọn trên Windows

Kiểm tra `Get-Command codex`, `codex --version` và `codex exec --help` trong chính shell gọi Codex. Khi các cờ có sẵn, dùng ví dụ sau với `$handoff` là nội dung giao việc đã chuẩn bị. Có thể nạp tệp giao việc có sẵn bằng `Get-Content -LiteralPath $handoffPath -Raw -Encoding UTF8`.

```powershell
$repo = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw 'Chưa xác định được worktree Git.' }

& {
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $handoff | codex exec -C $repo --sandbox read-only -
}
$codexExit = $LASTEXITCODE
```

Dùng `read-only` cho review. Chỉ chuyển sang `workspace-write` khi được giao sửa và đã giới hạn đường dẫn trong nội dung giao việc. Kiểm tra mã thoát và stderr khi lỗi. Giữ nguyên sandbox và cơ chế phê duyệt.

## Xác nhận kết quả đã giao

- Claude kiểm tra diff, kể cả tệp mới và thay đổi ngoài phạm vi. Với việc vừa hoặc lớn, chạy lại phép kiểm liên quan và đối chiếu từng tiêu chí với bằng chứng. Với việc lớn, so với trạng thái Git đầu lượt và dùng đối chứng độc lập theo `AGENTS.md`. Khi phép kiểm thiếu môi trường, ghi rõ phần `NOT_RUN` hoặc `BLOCKED`.
- Khi có lỗi thuộc phạm vi, giao lại cùng ca tái hiện và bằng chứng. Sau tối đa ba vòng cho cùng lỗi, đánh giá lại nguyên nhân và chỉ thử tiếp khi có hướng kỹ thuật mới có căn cứ. Trước bàn giao, mở lại prompt gốc và áp dụng quy tắc commit tiếng Việt nếu đã được phép commit.
