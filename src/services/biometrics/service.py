"""Casos de uso biométricos: enroll y recognize contra Postgres."""

from __future__ import annotations

from src.crud.contributors import (
    get_or_create_contributor_by_cedula,
)
from src.crud.face_templates import create_template, list_templates_with_contributors
from src.models.contributor import Contributor
from src.models.face_template import FaceRegion
from src.services.biometrics.engine import FaceEngine, RecognitionOutcome, TemplateRecord
from src.services.biometrics.occlusion import assess_occlusion

engine = FaceEngine()


async def load_gallery(session) -> list[TemplateRecord]:
    rows = await list_templates_with_contributors(session)
    return [
        TemplateRecord(
            contributor_id=contributor.id or 0,
            rif=contributor.rif,
            cedula=contributor.cedula,
            region=template.region,
            glasses=template.glasses,
            embedding=template.embedding,
            mesh_vector=template.mesh_vector,
        )
        for template, contributor in rows
        if contributor.id is not None
    ]


async def enroll_face(
    session,
    *,
    image_bytes: bytes,
    landmarks: list,
    cedula: str,
    rif: str | None = None,
    name: str | None = None,
    glasses: bool,
) -> Contributor:
    regions = engine.extract_regions(image_bytes, landmarks)
    if regions is None:
        raise ValueError("No se pudo extraer el rostro para enrolamiento")

    contributor = await get_or_create_contributor_by_cedula(
        session, cedula, name=name, rif=rif
    )

    occlusion = assess_occlusion(landmarks)
    pts = engine.parse_landmarks(landmarks)
    vector = engine.mesh_vector(pts, skip_mouth=occlusion.mouth) if pts is not None else None
    mesh = vector.tobytes() if vector is not None else None
    if contributor.id is None:
        raise ValueError("Contribuyente sin id tras persistir")
    for region, embedding in regions.items():
        await create_template(
            session,
            contributor_id=contributor.id,
            region=region,
            glasses=glasses,
            embedding=embedding,
            mesh_vector=mesh if region is FaceRegion.FULL else None,
        )
    return contributor


async def recognize_face(
    session,
    *,
    image_bytes: bytes,
    landmarks: list,
    glasses_hint: bool = False,
) -> RecognitionOutcome:
    gallery = await load_gallery(session)
    return engine.recognize(
        image_bytes, landmarks, gallery, glasses_hint=glasses_hint
    )
