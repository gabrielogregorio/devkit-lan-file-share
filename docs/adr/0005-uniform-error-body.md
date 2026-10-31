# 5. One error body for every route

**Status:** accepted

Every error answers `{"code", "detail", "request_id"}`: a stable code for programs, a sentence for people and an id to
find the same request in the log.

**Consequences:** the app decides by the HTTP status alone, so the body can grow without a new app. `send_error` is
overridden so even a malformed request gets this body instead of the HTML page of `http.server`.
