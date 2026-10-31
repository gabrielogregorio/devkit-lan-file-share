import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

MAX_FAILURES = 5
LOCK_SECONDS = 30
MAX_TRACKED_ADDRESSES = 1024


@dataclass
class FailureCount:
    failures: int = 0
    locked_until: float = 0.0


class LoginGuard:
    """Locks an address out after too many wrong proofs: the default password is weak."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.counts: dict[str, FailureCount] = {}

    def is_locked(self, address: str) -> bool:
        with self.lock:
            count = self.counts.get(address)
            if count is None or not count.locked_until:
                return False
            if self.clock() < count.locked_until:
                return True
            del self.counts[address]

            return False

    def record_failure(self, address: str) -> None:
        with self.lock:
            if address not in self.counts and len(self.counts) >= MAX_TRACKED_ADDRESSES:
                self.counts.clear()
            count = self.counts.setdefault(address, FailureCount())
            count.failures += 1
            if count.failures >= MAX_FAILURES:
                count.locked_until = self.clock() + LOCK_SECONDS

    def record_success(self, address: str) -> None:
        with self.lock:
            self.counts.pop(address, None)
