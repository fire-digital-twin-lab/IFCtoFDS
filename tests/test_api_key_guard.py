"""The API key check answers 401 to any wrong key, including one with non-ASCII characters (audit finding 1)."""

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds import server

KEY = "test-api-key-guard-0123456789"


@pytest.mark.parametrize("header", [b"caf\xe9", b"\xff\xfe", b"wrong-ascii-key"])
def test_a_wrong_key_is_401_not_a_server_error(monkeypatch, header):
    monkeypatch.setenv("IFCFDS_API_KEY", KEY)
    client = TestClient(server.app, raise_server_exceptions=False)
    assert client.get("/api/scheduler-health", headers={"x-api-key": header}).status_code == 401


def test_the_right_key_still_passes(monkeypatch):
    monkeypatch.setenv("IFCFDS_API_KEY", KEY)
    assert TestClient(server.app).get("/api/scheduler-health", headers={"x-api-key": KEY}).status_code == 200
