import ipaddress


def is_lan_address(address: str) -> bool:
    """Only the local network talks to this server, even when the PC has a public address too."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False

    return parsed.is_private or parsed.is_loopback or parsed.is_link_local
