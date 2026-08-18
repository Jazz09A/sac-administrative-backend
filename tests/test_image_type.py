import base64
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.core.image_type import decode_base64_image, sniff_image_content_type
from src.services.photo_service import PhotoService


def _jpeg_bytes() -> bytes:
    image = np.full((32, 32, 3), (10, 20, 30), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def test_sniff_jpeg_png_and_webp() -> None:
    assert sniff_image_content_type(_jpeg_bytes()) == "image/jpeg"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert sniff_image_content_type(png) == "image/png"
    webp = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"\x00" * 8
    assert sniff_image_content_type(webp) == "image/webp"


def test_sniff_rejects_non_image() -> None:
    with pytest.raises(ValueError, match="Formato no permitido"):
        sniff_image_content_type(b"%PDF-1.4 fake")


def test_decode_base64_image_requires_magic_bytes() -> None:
    encoded = base64.b64encode(_jpeg_bytes()).decode("ascii")
    assert sniff_image_content_type(decode_base64_image(encoded)) == "image/jpeg"

    with pytest.raises(ValueError, match="Formato no permitido"):
        decode_base64_image(base64.b64encode(b"not-an-image").decode("ascii"))


def test_photo_service_rejects_forged_content_type() -> None:
    service = PhotoService(photo_repo=None, storage_repo=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no coincide"):
        service._validate_file(file_data=_jpeg_bytes(), content_type="image/png")

    sniffed = service._validate_file(file_data=_jpeg_bytes(), content_type="image/jpeg")
    assert sniffed == "image/jpeg"
