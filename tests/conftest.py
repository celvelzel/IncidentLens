"""Optional CI guard: offline suites must never contact external services."""

import os
import socket

import pytest


@pytest.fixture(autouse=True)
def offline_network_guard(monkeypatch):
    if os.environ.get("INCIDENT_LENS_OFFLINE_TESTS") != "1":
        return
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def check(address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError(f"Offline test blocked network connection to {address[0]}")

    def connect(sock, address):
        check(address)
        return original(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
