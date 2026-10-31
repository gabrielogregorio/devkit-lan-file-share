from server.lockout import LOCK_SECONDS, MAX_FAILURES, MAX_TRACKED_ADDRESSES, LoginGuard

ADDRESS = "192.168.0.20"


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def fail(guard: LoginGuard, attempts: int) -> None:
    for _ in range(attempts):
        guard.record_failure(ADDRESS)


def test_last_failure_under_the_limit_does_not_lock() -> None:
    guard = LoginGuard(FakeClock())

    fail(guard, MAX_FAILURES - 1)

    assert not guard.is_locked(ADDRESS)


def test_reaching_the_limit_locks() -> None:
    guard = LoginGuard(FakeClock())

    fail(guard, MAX_FAILURES)

    assert guard.is_locked(ADDRESS)


def test_stays_locked_until_the_last_instant() -> None:
    clock = FakeClock()
    guard = LoginGuard(clock)
    fail(guard, MAX_FAILURES)

    clock.now += LOCK_SECONDS - 0.1

    assert guard.is_locked(ADDRESS)


def test_lock_ends_and_the_count_starts_over() -> None:
    clock = FakeClock()
    guard = LoginGuard(clock)
    fail(guard, MAX_FAILURES)
    clock.now += LOCK_SECONDS

    assert not guard.is_locked(ADDRESS)
    fail(guard, MAX_FAILURES - 1)
    assert not guard.is_locked(ADDRESS)


def test_success_clears_the_failures() -> None:
    guard = LoginGuard(FakeClock())
    fail(guard, MAX_FAILURES - 1)

    guard.record_success(ADDRESS)
    fail(guard, MAX_FAILURES - 1)

    assert not guard.is_locked(ADDRESS)


def test_one_address_does_not_lock_another() -> None:
    guard = LoginGuard(FakeClock())

    fail(guard, MAX_FAILURES)

    assert not guard.is_locked("192.168.0.21")


def test_tracked_addresses_never_grow_past_the_limit() -> None:
    guard = LoginGuard(FakeClock())

    for number in range(MAX_TRACKED_ADDRESSES + 1):
        guard.record_failure(f"address-{number}")

    assert len(guard.counts) == 1
