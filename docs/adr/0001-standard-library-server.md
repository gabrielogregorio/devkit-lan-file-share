# 1. Server on the Python standard library

**Status:** accepted

The server runs from a tray icon on any Ubuntu PC. A dependency would mean a venv to create and keep working, on a
program that only needs HTTPS, UDP and files. Python's `http.server` and `ssl` cover all of it.

**Consequences:** no venv at runtime and nothing to update; the cost is writing the chunked body parser and the thread
limit by hand, both small and tested. The tray adds GTK and segno from apt, which verifies its own signatures.
