import json
import socket
import threading
from unittest import mock

from server.discovery import APP_ID, DISCOVER_MESSAGE, discovery_reply, serve_discovery

FINGERPRINT = "ab" * 32


def test_reply_carries_what_the_phone_needs() -> None:
    reply = discovery_reply(DISCOVER_MESSAGE, 8908, FINGERPRINT, "office")

    assert reply is not None
    assert json.loads(reply) == {"app": APP_ID, "port": 8908, "fingerprint": FINGERPRINT, "name": "office"}


def test_surrounding_whitespace_is_tolerated() -> None:
    assert discovery_reply(DISCOVER_MESSAGE + b"\n", 8908, FINGERPRINT, "office") is not None


def test_any_other_message_gets_no_reply() -> None:
    assert discovery_reply(b"who is there?", 8908, FINGERPRINT, "office") is None


def test_answers_over_udp_on_the_local_network() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        address = server_socket.getsockname()
        threading.Thread(target=serve_discovery, daemon=True,
                         args=(server_socket, address[1], FINGERPRINT, "office")).start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as phone_socket:
            phone_socket.settimeout(2)
            phone_socket.sendto(DISCOVER_MESSAGE, address)

            assert json.loads(phone_socket.recv(1024))["name"] == "office"


def test_senders_outside_the_local_network_get_no_reply() -> None:
    udp_socket = mock.Mock()
    udp_socket.recvfrom.side_effect = [(DISCOVER_MESSAGE, ("8.8.8.8", 5000)), SystemExit]

    try:
        serve_discovery(udp_socket, 8908, FINGERPRINT, "office")
    except SystemExit:
        pass

    udp_socket.sendto.assert_not_called()
