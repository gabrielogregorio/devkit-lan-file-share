from collections.abc import Iterator
from email.message import Message
from io import BufferedIOBase

BLOCK_BYTES = 256 * 1024
MAX_CHUNK_LINE_BYTES = 64
MAX_TRAILER_LINE_BYTES = 1024


class BodyError(Exception):
    """The request body is malformed or ended before the client finished it."""


def _read_exactly(stream: BufferedIOBase, size: int) -> Iterator[bytes]:
    remaining = size
    while remaining > 0:
        block = stream.read(min(remaining, BLOCK_BYTES))
        if not block:
            raise BodyError("connection closed")
        remaining -= len(block)
        yield block


def _chunk_size(stream: BufferedIOBase) -> int:
    line = stream.readline(MAX_CHUNK_LINE_BYTES).split(b";")[0].strip()
    try:
        size = int(line, 16)
    except ValueError as error:
        raise BodyError("bad chunk") from error
    if size < 0:
        raise BodyError("bad chunk")

    return size


def _read_chunked(stream: BufferedIOBase) -> Iterator[bytes]:
    while True:
        size = _chunk_size(stream)
        if size == 0:
            while stream.readline(MAX_TRAILER_LINE_BYTES).strip():
                pass

            return
        yield from _read_exactly(stream, size)
        stream.readline(MAX_CHUNK_LINE_BYTES)


def _content_length(headers: Message) -> int:
    try:
        length = int(headers.get("Content-Length", ""))
    except ValueError as error:
        raise BodyError("missing or bad Content-Length") from error
    if length < 0:
        raise BodyError("negative Content-Length")

    return length


def read_body(stream: BufferedIOBase, headers: Message) -> Iterator[bytes]:
    if "chunked" in headers.get("Transfer-Encoding", "").lower():
        yield from _read_chunked(stream)

        return

    yield from _read_exactly(stream, _content_length(headers))
