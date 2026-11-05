"""Cross-process, single-host exclusion for a writable JobService root.

This lock is deliberately NOT a distributed lease or network filesystem lock.
Do not delete the lock file: only the OS-held lock is authoritative.
"""

import os
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class JobRootInUseError(RuntimeError):
    """A second production scheduler cannot use the same local job store."""


class ExclusiveJobRootLock:
    """Hold a nonblocking OS advisory byte/file lock until explicit release."""

    def __init__(self, root: Path | str):
        path = Path(root) / ".scheduler.lock"
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = None
        try:
            fd = os.open(path, flags, 0o600)
            if os.name == "nt":
                # msvcrt.locking locks a byte range starting at the current
                # file position. Keep one persistent byte in the lock file.
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if fd is not None:
                os.close(fd)
            raise JobRootInUseError(
                "Cannot obtain exclusive scheduler lock; use one API/worker "
                "supervisor for this job root"
            ) from exc
        self._fd = fd

    def release(self) -> None:
        fd = self._fd
        if fd is None:
            return
        try:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            # The file stays on disk; removing it allows separate inodes and
            # breaks process exclusion during deploy/restart overlap.
            os.close(fd)
            self._fd = None
