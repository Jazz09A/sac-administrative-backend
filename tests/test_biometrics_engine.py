from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.models.face_template import FaceRegion
from src.services.biometrics.engine import (
    RESULT_NEEDS_DOCUMENT,
    RESULT_NO_GALLERY,
    FaceEngine,
    TemplateRecord,
)
from src.services.biometrics.occlusion import assess_occlusion
from src.services.biometrics.pose import is_grant_pose, pose_from_landmarks

LANDMARK_COUNT = 478
LEFT_EYE = (33, 133, 160, 159, 158, 157, 173, 246)
RIGHT_EYE = (362, 263, 387, 386, 385, 384, 398, 466)


def make_landmarks(
    *,
    yaw_deg: float = 0.0,
    mask: bool = False,
    hide_eyes: bool = False,
) -> list[dict[str, float]]:
    pts = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(LANDMARK_COUNT)]
    if hide_eyes:
        for idx in LEFT_EYE + RIGHT_EYE:
            pts[idx] = {"x": 0.5, "y": 0.5, "z": 0.0}
    else:
        for i, idx in enumerate(LEFT_EYE):
            pts[idx] = {"x": 0.32 + i * 0.004, "y": 0.39 + (i % 3) * 0.003, "z": 0.0}
        for i, idx in enumerate(RIGHT_EYE):
            pts[idx] = {"x": 0.62 + i * 0.004, "y": 0.39 + (i % 3) * 0.003, "z": 0.0}
    span = 0.4
    ratio = yaw_deg / 50.0
    d_left = (span + span * ratio) / 2.0
    d_right = (span - span * ratio) / 2.0
    pts[1] = {"x": 0.5, "y": 0.56, "z": 0.0}
    pts[234] = {"x": 0.5 - d_left, "y": 0.50, "z": 0.0}
    pts[454] = {"x": 0.5 + d_right, "y": 0.50, "z": 0.0}
    pts[152] = {"x": 0.5, "y": 0.80, "z": 0.0}
    if mask:
        pts[13] = {"x": 0.5, "y": 0.64, "z": 0.0}
        pts[14] = {"x": 0.5, "y": 0.645, "z": 0.0}
    else:
        pts[13] = {"x": 0.5, "y": 0.62, "z": 0.0}
        pts[14] = {"x": 0.5, "y": 0.70, "z": 0.0}
    return pts


def jpeg_bytes(color: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    image = np.full((240, 240, 3), color, dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def test_mask_marks_mouth_occluded_but_eyes_usable() -> None:
    occlusion = assess_occlusion(make_landmarks(mask=True))
    assert occlusion.mouth is True
    assert occlusion.alignment_ready is True


def test_hidden_eyes_require_document_fallback() -> None:
    occlusion = assess_occlusion(make_landmarks(hide_eyes=True))
    assert occlusion.both_eyes_hidden is True
    engine = FaceEngine()
    outcome = engine.recognize(
        jpeg_bytes(),
        make_landmarks(hide_eyes=True),
        templates=[],
    )
    assert outcome.result == RESULT_NEEDS_DOCUMENT
    assert outcome.fallback == "cedula_rif"


def test_frontal_pose_is_grantable() -> None:
    pose = pose_from_landmarks(make_landmarks())
    assert is_grant_pose(pose)


def test_extract_regions_and_empty_gallery() -> None:
    engine = FaceEngine()
    landmarks = make_landmarks()
    regions = engine.extract_regions(jpeg_bytes(), landmarks)
    assert regions is not None
    assert set(regions) == {FaceRegion.FULL, FaceRegion.PERIOCULAR, FaceRegion.NOSE}
    outcome = engine.recognize(jpeg_bytes((10, 20, 30)), landmarks, templates=[])
    assert outcome.result == RESULT_NO_GALLERY


def test_recognize_with_in_memory_template() -> None:
    engine = FaceEngine()
    landmarks = make_landmarks(mask=True)
    regions = engine.extract_regions(jpeg_bytes((90, 40, 20)), landmarks)
    assert regions is not None
    templates = [
        TemplateRecord(
            contributor_id=7,
            rif=None,
            cedula="V1",
            region=FaceRegion.PERIOCULAR,
            glasses=True,
            embedding=regions[FaceRegion.PERIOCULAR],
            mesh_vector=None,
        )
    ]
    outcome = engine.recognize(
        jpeg_bytes((90, 40, 20)),
        landmarks,
        templates,
        glasses_hint=True,
    )
    assert outcome.result in { "recognized", "unknown" }
    assert outcome.region_used == FaceRegion.PERIOCULAR.value
    if outcome.result == "recognized":
        assert outcome.contributor_id == 7
        assert outcome.cedula == "V1"
