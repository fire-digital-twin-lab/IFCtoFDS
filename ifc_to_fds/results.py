"""Compatibility exports for result metadata and research registry."""

from ifc_to_fds.modules.reference.api import registered_cases, research_context as _research_context
from ifc_to_fds.modules.artifacts.contracts import ARTIFACTS
from ifc_to_fds.application.dto.public_result import public_result as _public_result


def research_context(sources, config, report=None):
    # Preserve the historical module-level override used by integrations/tests.
    return _research_context(sources, config, report, cases=registered_cases())


def public_result(result):
    return _public_result(result, research_reader=research_context)
