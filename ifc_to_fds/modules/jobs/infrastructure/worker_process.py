"""Worker subprocess and resource monitoring adapter."""
from pathlib import Path
import subprocess
import sys
import psutil


class LocalWorkerProcesses:
    def launch(self, directory):
        with (Path(directory) / 'error.txt').open('a', encoding='utf-8') as errors:
            return subprocess.Popen(
                [sys.executable, '-m', 'ifc_to_fds.jobs', str(directory)],
                stdout=subprocess.DEVNULL, stderr=errors,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )

    def rss(self, process):
        parent = psutil.Process(process.pid)
        total = parent.memory_info().rss
        for child in parent.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total

    @staticmethod
    def stop(process):
        if process and process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
                process.wait(timeout=10)
            except (psutil.NoSuchProcess, subprocess.TimeoutExpired):
                pass

