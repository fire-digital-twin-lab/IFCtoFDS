"""Include the independently maintained frontend in binary distributions."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithFrontend(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent / "frontend"
        target = Path(self.build_lib) / "ifc_to_fds" / "_frontend"
        build_root = Path(self.build_lib).resolve()
        if not target.resolve().is_relative_to(build_root):
            raise RuntimeError("Frontend build target escapes build directory")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)


setup(cmdclass={"build_py": BuildWithFrontend})
