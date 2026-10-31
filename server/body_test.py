import io
from email.message import Message

import pytest

from server.body import BLOCK_BYTES, BodyError, read_body


def headers(**values: str) -> Message:
    message = Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value

    return message


def read_all(data: bytes, message: Message) -> bytes:
    return b"".join(read_body(io.BytesIO(data), message))


def test_sized_body() -> None:
    assert read_all(b"hello", headers(Content_Length="5")) == b"hello"


def test_sized_body_ignores_what_comes_after_it() -> None:
    assert read_all(b"hello, more", headers(Content_Length="5")) == b"hello"


def test_big_body_comes_in_blocks() -> None:
    size = BLOCK_BYTES + 1

    blocks = list(read_body(io.BytesIO(b"x" * size), headers(Content_Length=str(size))))

    assert [len(block) for block in blocks] == [BLOCK_BYTES, 1]


def test_chunked_body() -> None:
    data = b"6\r\nhello \r\n5;ext=1\r\nphone\r\n0\r\nTrailer: x\r\n\r\n"

    assert read_all(data, headers(Transfer_Encoding="chunked")) == b"hello phone"


def test_empty_chunked_body() -> None:
    assert read_all(b"0\r\n\r\n", headers(Transfer_Encoding="Chunked")) == b""


@pytest.mark.parametrize("data", [b"", b"zz\r\n", b"-5\r\n\r\n0\r\n\r\n"])
def test_bad_chunk_size_is_refused(data: bytes) -> None:
    with pytest.raises(BodyError):
        read_all(data, headers(Transfer_Encoding="chunked"))


def test_chunk_cut_short_is_refused() -> None:
    with pytest.raises(BodyError):
        read_all(b"a\r\nhello", headers(Transfer_Encoding="chunked"))


def test_sized_body_cut_short_is_refused() -> None:
    with pytest.raises(BodyError):
        read_all(b"hi", headers(Content_Length="5"))


@pytest.mark.parametrize("length", ["-1", "abc", ""])
def test_bad_content_length_is_refused(length: str) -> None:
    with pytest.raises(BodyError):
        read_all(b"hello", headers(Content_Length=length))


def test_missing_length_is_refused() -> None:
    with pytest.raises(BodyError):
        read_all(b"hello", headers())
