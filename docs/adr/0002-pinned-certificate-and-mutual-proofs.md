# 2. Pinned certificate and proofs in both directions

**Status:** accepted

A LAN device has no name a public CA would sign, so identity comes from pinning the certificate. A pin alone would let
the first thing that answers become the PC, so both sides also prove they hold the secret, with an HMAC over the
certificate fingerprint.

**Consequences:** the secret never goes in a request, and a proof taken from one server is useless against another,
since it is bound to that fingerprint. The proof is the same on every request, which is safe only because it travels
inside pinned TLS. Encryption comes from TLS, with keys new on every connection, not from the pairing key.
