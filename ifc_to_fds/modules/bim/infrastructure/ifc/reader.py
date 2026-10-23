"""Native IFC implementation of the source and inventory query ports."""

from ifc_to_fds.modules.bim.api import extract_inventory, load_sources


class IfcOpenShellReader:
    def load_sources(self, paths, configured_sources=None, reference=False):
        return load_sources(paths, configured_sources, reference=reference)

    def extract_inventory(self, path):
        model, _ = extract_inventory(str(path))
        return model.model_dump(mode="json")
