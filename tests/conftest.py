import socket

import pytest


@pytest.fixture(autouse=True)
def _disable_default_test_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise RuntimeError("network access is disabled in default pytest")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
