import pytest

from server.network import is_lan_address


@pytest.mark.parametrize("address", ["192.168.0.10", "10.0.2.2", "172.16.0.1", "127.0.0.1", "169.254.1.1", "::1"])
def test_local_addresses_are_accepted(address: str) -> None:
    assert is_lan_address(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "172.32.0.1", "2001:4860:4860::8888", "not an address", ""])
def test_anything_else_is_refused(address: str) -> None:
    assert not is_lan_address(address)
