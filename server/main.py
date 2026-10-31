"""LAN File Share server: receives files from the phone into a folder on this PC. See docs/api.md."""

import logging
import socket
import threading

from server.config_store import load_config
from server.discovery import serve_discovery
from server.http_api import FileShareServer
from server.settings import SETTINGS
from server.storage import remove_leftovers

LISTEN_ADDRESS = "0.0.0.0"

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    config = load_config(SETTINGS.config_dir)
    remove_leftovers(config.target_folder)
    server = FileShareServer((LISTEN_ADDRESS, SETTINGS.port), SETTINGS.config_dir, SETTINGS.pc_name)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((LISTEN_ADDRESS, SETTINGS.port))
    threading.Thread(target=serve_discovery, daemon=True,
                     args=(udp_socket, SETTINGS.port, server.fingerprint, SETTINGS.pc_name)).start()
    logger.info('LAN File Share on port %d, saving to "%s"', SETTINGS.port, config.folder)
    server.serve_forever()


if __name__ == "__main__":
    main()
