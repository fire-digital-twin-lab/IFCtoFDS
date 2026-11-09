#!/usr/bin/env bash
# Bảo trì OFFLINE cho named volume IFCtoFDS; không chạy khi app/worker còn dùng volume.
# Chỉ thao tác trên backup directory mới hoặc volume khôi phục mới, không ghi đè nguồn.
set -euo pipefail

die() { printf 'Volume maintenance rejected: %s\n' "$*" >&2; exit 2; }

if [[ $# -lt 4 ]]; then
  die "Usage: bash scripts/production-volume-maintenance.sh {backup|restore} IMAGE ABS_BACKUP_BASE BACKUP_NAME [NEW_VOLUME_NAME]"
fi

action=$1
image=$2
backup_base=$3
backup_name=$4
source_volume=${IFCFDS_JOB_VOLUME_NAME:-ifctofds_jobs}

[[ $action == backup || $action == restore ]] || die "Unknown operation"
if [[ $action == backup && $# -ne 4 ]] || [[ $action == restore && $# -ne 5 ]]; then
  die "Incorrect argument count"
fi
[[ $image != -* && $image != *' '* ]] || die "Unsafe image identifier"
[[ $backup_base == /* && $backup_base != *':'* && $backup_base != *','* ]] || die "Backup base must be a safe absolute Linux path"
[[ $backup_name =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ ]] || die "Unsafe backup name"
[[ $source_volume =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$ ]] || die "Unsafe source volume name"

command -v docker >/dev/null 2>&1 || die "Docker CLI is unavailable"
docker info >/dev/null 2>&1 || die "Docker daemon unavailable"
docker image inspect "$image" >/dev/null 2>&1 || die "Release image must already exist; implicit pull is prohibited"
[[ -d $backup_base && ! -L $backup_base ]] || die "Backup base must be an existing non-symlink directory"
[[ $(stat -c '%u:%a' "$backup_base") == "10001:700" ]] || die "Backup base must be owned by UID 10001 with mode 0700"
backup_base=$(realpath -e -- "$backup_base")

docker volume inspect "$source_volume" >/dev/null 2>&1 || die "Source named volume does not exist"
project=$(docker volume inspect "$source_volume" --format '{{index .Labels "com.docker.compose.project"}}')
volume_label=$(docker volume inspect "$source_volume" --format '{{index .Labels "com.docker.compose.volume"}}')
[[ $project == ifctofds && $volume_label == jobs ]] || die "Source is not an approved ifctofds/jobs volume"

# Chặn backup khi bất kỳ container đang chạy nào còn mount volume nguồn.
if [[ -n $(docker ps -q --filter "volume=$source_volume") ]]; then
  die "Source volume is in use: stop app and all workers before offline backup"
fi

run_base=(
  docker run --rm --read-only --tmpfs /tmp:rw,nosuid,nodev
  --cap-drop ALL --security-opt no-new-privileges
  --user 10001:10001
)

if [[ $action == backup ]]; then
  "${run_base[@]}" \
    --mount "type=volume,source=$source_volume,target=/var/lib/ifctofds/jobs" \
    --mount "type=bind,source=$backup_base,target=/backups" \
    "$image" python -m ifc_to_fds.operations.offline_backup backup \
      --job-root /var/lib/ifctofds/jobs \
      --destination "/backups/$backup_name"
  exit 0
fi

target_volume=$5
[[ $target_volume =~ ^ifctofds_jobs_restore_[a-zA-Z0-9_-]+$ ]] || die "Restore volume must have dedicated ifctofds_jobs_restore_ prefix"
[[ $target_volume != $source_volume ]] || die "Never restore into the source volume"
if docker volume inspect "$target_volume" >/dev/null 2>&1; then
  die "Restore volume already exists; no overwrite permitted"
fi

# Volume mới được tạo ngay trước restore; thất bại sẽ để lại volume INCOMPLETE.
# Không tự xóa volume để tránh che giấu lỗi/ghi đè ngoài ý muốn.
docker volume create \
  --label com.docker.compose.project=ifctofds \
  --label com.docker.compose.volume=jobs \
  "$target_volume" >/dev/null

"${run_base[@]}" \
  --mount "type=volume,source=$target_volume,target=/var/lib/ifctofds/jobs" \
  --mount "type=bind,source=$backup_base,target=/backups,readonly" \
  "$image" python -m ifc_to_fds.operations.offline_backup restore \
    --source "/backups/$backup_name" \
    --destination /var/lib/ifctofds/jobs \
    --allow-empty-existing

# Chỉ đọc marker được công bố sau cùng; marker không phải chữ ký số hay validation CFD.
"${run_base[@]}" \
  --mount "type=volume,source=$target_volume,target=/var/lib/ifctofds/jobs" \
  "$image" python -c '
import json
from pathlib import Path
root = Path("/var/lib/ifctofds/jobs")
marker = json.loads((root / ".restore-verified.json").read_text(encoding="utf-8"))
assert marker["status"] == "OFFLINE_RESTORE_VERIFIED"
print("Isolated restore marker: PASS")
'
