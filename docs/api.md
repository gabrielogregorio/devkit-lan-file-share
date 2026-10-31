# Protocol

Everything runs on one port, 8908 by default, TCP for HTTPS and UDP for discovery. `server/` and
`android/src/.../PcClient.java` implement it; the apps already installed depend on it, so `/api/v1` only ever gains
fields.

## Discovery (UDP)

The phone broadcasts `LFS-DISCOVER-1`. The server answers senders on the local network:

```json
{"app": "lan-file-share", "port": 8908, "fingerprint": "<sha-256 of the certificate>", "name": "my-pc"}
```

With a pairing saved, the phone only accepts the fingerprint it pinned, which is how it finds the PC after a new IP.

## Pairing link

The QR code on the panel holds:

```
lanfileshare://pair?host=192.168.0.10&port=8908&fp=<64 hex>&k=<64 hex>
```

`fp` is the certificate to pin and `k` is the current key. Opened from outside the app, the link asks for confirmation
unless it is the PC already paired, since any app can fire it. The scanner does not ask: the person pointed the camera.

## Authentication

Every request carries `X-Auth`, an HMAC-SHA256 over `client|<fingerprint>` with the secret, in lowercase hex. The secret
is a key or the password, and it never travels in a request. `/api/v1/hello` answers with the same HMAC over
`server|<fingerprint>`, so the phone also proves the PC knows the secret. `tests/vectors.txt` holds proofs that Python
and Java are both tested against.

## Routes

| Method and path | Sends | Answers |
| --- | --- | --- |
| `GET /api/v1/hello` | `X-Auth` | `200 {"name", "api", "proof"}`. Changes nothing on the server |
| `POST /api/v1/pair` | `X-Auth`, `X-Device` (percent-encoded) | `200 {"id", "key", "created"}`, a new key, now the current one |
| `PUT /api/v1/files` | `X-Auth`, `X-File-Name` (percent-encoded), body sized or chunked | `201 {"name", "size", "sha256"}`, with the final name |

The phone compares `sha256` with what it read; a difference is reported as a damaged file.

## Errors

Every error has the same body:

```json
{"code": "wrong_secret", "detail": "wrong key or password", "request_id": "3f9a1c07b2de"}
```

| Status | `code` | Meaning |
| --- | --- | --- |
| 400 | `upload_failed` | The body was cut short, malformed or could not be written |
| 401 | `wrong_secret` | Wrong or revoked secret |
| 404 | `not_found` | Unknown route |
| 429 | `locked_out` | 5 wrong tries; this address waits 30 seconds |
| 501 | `bad_request` | Method not supported, or a malformed request |
| 507 | `disk_almost_full` | Storing it would leave under 1 GB free |

`request_id` is also in the server log. Addresses outside the local network and connections past the limit of 32 are
dropped with no answer at all.
