"""Scientific execution provenance."""

def get_execution_provenance():
    """Captures runtime environment versions for scientific audit reproducibility."""
    import platform
    import sys

    provenance = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
    }
    try:
        import ifcopenshell
        provenance["ifcopenshell_version"] = getattr(ifcopenshell, "__version__", "unknown")
    except ImportError:
        pass
    try:
        import trimesh
        provenance["trimesh_version"] = getattr(trimesh, "__version__", "unknown")
    except ImportError:
        pass
    return provenance
