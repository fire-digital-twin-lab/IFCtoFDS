"""Locate public assets in a checkout or an installed wheel."""

from pathlib import Path


def frontend_root() -> Path:
    packaged = Path(__file__).resolve().parent / "_frontend"
    if packaged.is_dir():
        return packaged
    checkout = Path(__file__).resolve().parent.parent / "frontend"
    if checkout.is_dir():
        return checkout
    raise RuntimeError("Frontend assets are missing; reinstall the complete IFCtoFDS distribution")
