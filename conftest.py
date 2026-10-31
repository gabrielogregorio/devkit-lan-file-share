import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from server.config_store import save_config
from server.http_api import FileShareServer

PC_NAME = "test-pc"


@dataclass(frozen=True)
class RunningServer:
    server: FileShareServer
    config_dir: Path
    inbox: Path

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[RunningServer]:
    config_dir = tmp_path / "config"
    inbox = tmp_path / "inbox"
    save_config(config_dir, folder=str(inbox))
    server = FileShareServer(("127.0.0.1", 0), config_dir, PC_NAME)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield RunningServer(server, config_dir, inbox)
    server.shutdown()
    server.server_close()
