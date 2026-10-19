"""Offline acceptance guard: allow loopback servers, deny external sockets."""
import ipaddress
import json
import os
import socket
from pathlib import Path

import httpx

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex

def _check(sock, address):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    host = address[0]
    if host == 'localhost':
        return
    try:
        allowed = ipaddress.ip_address(host.split('%')[0]).is_loopback
    except ValueError:
        allowed = False
    if not allowed:
        target = os.environ.get('INCIDENT_LENS_OFFLINE_GUARD_LOG')
        if target:
            with Path(target).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'event': 'external_socket_blocked'}) + '\n')
        raise OSError('External network disabled for offline acceptance')

def _connect(sock, address):
    _check(sock, address)
    return _original_connect(sock, address)

def _connect_ex(sock, address):
    _check(sock, address)
    return _original_connect_ex(sock, address)

socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex

# Block remote HTTP destinations even when a loopback proxy is configured.

_async_send = httpx.AsyncClient.send
_sync_send = httpx.Client.send

def _check_request(client, request):
    transport = client._transport_for_url(request.url)
    if isinstance(transport, (httpx.HTTPTransport, httpx.AsyncHTTPTransport)):
        class Destination:
            family = socket.AF_INET
        _check(Destination(), (request.url.host, request.url.port))

async def _offline_async_send(client, request, *args, **kwargs):
    _check_request(client, request)
    return await _async_send(client, request, *args, **kwargs)

def _offline_sync_send(client, request, *args, **kwargs):
    _check_request(client, request)
    return _sync_send(client, request, *args, **kwargs)

httpx.AsyncClient.send = _offline_async_send
httpx.Client.send = _offline_sync_send
