"""The upload smoke script streams a well-formed multipart body whose Content-Length is exact."""

import email
import runpy
from pathlib import Path

smoke = runpy.run_path(str(Path(__file__).parents[1] / "scripts/production-upload-smoke.py"))


def test_streamed_body_length_and_parts_are_exact():
    length, chunks = smoke["multipart"](files=2, mib=1)
    body = b"".join(chunks)
    assert len(body) == length
    message = email.message_from_bytes(b"Content-Type: multipart/form-data; boundary=ifcfdsUploadSmoke\r\n\r\n" + body)
    parts = message.get_payload()
    assert [p.get_filename() for p in parts] == ["big-0.ifc", "big-1.ifc"]
    assert all(len(p.get_payload(decode=True)) == len(b"ISO-10303-21;\r\n") + (1 << 20) for p in parts)


def test_non_https_origin_is_refused(tmp_path):
    key = tmp_path / "key"
    key.write_text("k")
    assert smoke["main"](["--base-url", "http://x.example", "--api-key-file", str(key)]) == 2
