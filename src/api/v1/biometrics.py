"""API biométrica de garita: recognize / enroll."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.image_type import decode_base64_image
from src.core.security import CurrentUser, require_operator
from src.services.biometrics.service import enroll_face, recognize_face

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]
OperatorUser = Annotated[CurrentUser, Depends(require_operator)]


class LandmarkPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    z: float = Field(default=0.0, ge=-1.0, le=1.0)


class RecognizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: str
    landmarks: list[LandmarkPoint] = Field(min_length=400, max_length=478)
    glasses: bool = False


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: str
    landmarks: list[LandmarkPoint] = Field(min_length=400, max_length=478)
    cedula: str = Field(min_length=1, max_length=20)
    rif: str | None = Field(default=None, max_length=20)
    name: str | None = Field(default=None, max_length=255)
    glasses: bool = False

    @field_validator("cedula")
    @classmethod
    def strip_cedula(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Cédula es obligatoria")
        return stripped

    @field_validator("rif")
    @classmethod
    def reject_temp_rif(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido")
        return stripped

    @field_validator("name")
    @classmethod
    def blank_name_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


def _decode_image(payload: str) -> bytes:
    try:
        return decode_base64_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/recognize")
async def recognize(body: RecognizeRequest, db: DbSession, _: OperatorUser):
    outcome = await recognize_face(
        db,
        image_bytes=_decode_image(body.image),
        landmarks=[point.model_dump() for point in body.landmarks],
        glasses_hint=body.glasses,
    )
    occlusion = outcome.occlusion
    return {
        "result": outcome.result,
        "message": outcome.message,
        "contributor_id": outcome.contributor_id,
        "rif": outcome.rif,
        "cedula": outcome.cedula,
        "confidence": outcome.confidence,
        "fallback": outcome.fallback,
        "region_used": outcome.region_used,
        "occlusion": None
        if occlusion is None
        else {
            "mouth": occlusion.mouth,
            "left_eye": occlusion.left_eye,
            "right_eye": occlusion.right_eye,
        },
    }


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(body: EnrollRequest, db: DbSession, _: OperatorUser):
    try:
        contributor = await enroll_face(
            db,
            image_bytes=_decode_image(body.image),
            landmarks=[point.model_dump() for point in body.landmarks],
            cedula=body.cedula,
            rif=body.rif,
            name=body.name,
            glasses=body.glasses,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "result": "ok",
        "contributor_id": contributor.id,
        "rif": contributor.rif,
        "cedula": contributor.cedula,
        "message": "Plantillas faciales registradas",
    }
