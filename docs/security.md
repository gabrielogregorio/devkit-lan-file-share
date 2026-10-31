# Security

## What protects what

| Layer | How |
| --- | --- |
| Encryption | TLS 1.2+ with keys new on every connection, so a leaked key does not open traffic recorded earlier |
| Server identity | The phone pins the SHA-256 of the certificate, from the QR code or at first pairing |
| Both ends know the secret | HMAC over the certificate fingerprint, in both directions; the secret never goes in a request |
| Keys | 256-bit, in the QR code. Each pairing issues a new one. Old keys work until revoked in the panel |
| Brute force | 5 wrong tries lock the address out for 30 seconds |
| Reach | Only private, loopback and link-local addresses are served, on TCP and on UDP |
| Abuse | 60-second socket timeout and 32 connections at most |
| Planted links | A pairing link from outside needs confirmation, so another app cannot redirect the shares |
| Planted shares | Only `content://` is accepted: a `file://` link could point at the app's own private files |

## Received files

Whatever arrives is data, and the content is not inspected: this is a file drop between your own devices.

- The name comes down to a plain file name: no folders, no hidden files, no control or direction characters.
- Files are written with mode 640, so a received script is never executable.
- A part file is opened with `O_EXCL | O_NOFOLLOW`; a symbolic link planted there is not followed.
- Nothing is overwritten: a taken name gets a number.
- An upload cut short leaves nothing.
- The disk keeps 1 GB free, measured every 16 MB.

## On disk

`~/.config/devkit-lan-file-share` is mode 700. `config.json`, `keys.json` and `key.pem` are mode 600, replaced in one
step, never readable by others even briefly. On the phone, pairing data stays in the app's private storage, with
backups and cleartext traffic off.

## Keep in mind

- Pairing by password with the default `1234` is weak: anyone on your Wi-Fi can guess it. Change it in the icon menu,
  or pair only by QR code.
- A photo of the QR code is a working key until you revoke it. Pairing replaces the QR code, and the old key stays
  valid by design.
- The panel shows the QR code to whoever is looking at your screen.
- A debug build is signed with the debug key, fit for sideloading only.

## Reporting

Open a private security advisory on the repository, with the steps to reproduce.
