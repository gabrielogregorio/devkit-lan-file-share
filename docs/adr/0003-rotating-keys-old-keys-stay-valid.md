# 3. Keys rotate on pairing and old keys stay valid

**Status:** accepted

The QR code is a secret shown on a screen. Each pairing issues a new key to the phone, and that key becomes the one in
the QR code, so a photo taken earlier opens only what it opened before. Old keys keep working until revoked: a second
phone, or a phone that missed the answer, must not lock itself out.

**Consequences:** the panel lists every key with its last use and a Revoke button. The phone keeps 8 keys and tries at
most 4 secrets, one under the lockout limit of the PC, so a stale list cannot lock it out.
