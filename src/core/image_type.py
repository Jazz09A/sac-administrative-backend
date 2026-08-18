"""Validación de imágenes por firma mágica (no confiar en Content-Type del cliente)."""

from __future__ import annotations

import base64
import binascii

MAX_IMAGE_BYTES = 10 * 1024 * 1024

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_TAG = b"WEBP"

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def sniff_image_content_type(data: bytes) -> str:
    """Devuelve el MIME sniffado o lanza ValueError si el formato no está permitido."""
    if not data:
        raise ValueError("La imagen es obligatoria")
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if len(data) >= 12 and data.startswith(_WEBP_RIFF) and data[8:12] == _WEBP_TAG:
        return "image/webp"
    raise ValueError("Formato no permitido. Use JPG, PNG o WEBP")


def decode_base64_image(payload: str, *, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    raw = payload.split(",", 1)[1] if "," in payload else payload
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Imagen base64 invalida") from exc
    if not data or len(data) > max_bytes:
        raise ValueError("Imagen vacia o demasiado grande")
    sniff_image_content_type(data)
    return data
