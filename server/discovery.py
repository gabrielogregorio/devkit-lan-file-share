import json
import socket

from server.network import is_lan_address

DISCOVER_MESSAGE = b"LFS-DISCOVER-1"
APP_ID = "lan-file-share"
MAX_MESSAGE_BYTES = 64


def discovery_reply(message: bytes, port: int, fingerprint: str, pc_name: str) -> bytes | None:
    if message.strip() != DISCOVER_MESSAGE:
        return None

    return json.dumps({"app": APP_ID, "port": port, "fingerprint": fingerprint, "name": pc_name}).encode()


def serve_discovery(udp_socket: socket.socket, port: int, fingerprint: str, pc_name: str) -> None:
    while True:
        message, sender = udp_socket.recvfrom(MAX_MESSAGE_BYTES)
        reply = discovery_reply(message, port, fingerprint, pc_name)
        if reply and is_lan_address(sender[0]):
            udp_socket.sendto(reply, sender)
