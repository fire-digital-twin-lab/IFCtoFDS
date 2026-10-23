"""FDS serialization adapter for application workflows."""

from ifc_to_fds.modules.fds.api import serialize_fds


class FdsExporter:
    def serialize_fds(self, model, cell_size=None, mapping_plan=None):
        return serialize_fds(model, cell_size=cell_size, mapping_plan=mapping_plan)
