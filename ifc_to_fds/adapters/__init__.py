"""Adapters layer for IFCtoFDS Verified Core.

Implements ports declared by the application layer:
  - ifc: IfcOpenShell integration
  - fds: FDS serializer, parser, solver
  - storage: filesystem and artifact storage
  - reference: golden reference storage
  - jobs: job persistence and subprocess worker runner
"""
