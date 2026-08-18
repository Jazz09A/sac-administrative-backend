"""Motor LBPH con recortes regionales para oclusión (gafas/tapabocas)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from src.models.face_template import FaceRegion
from src.services.biometrics.occlusion import Occlusion, assess_occlusion
from src.services.biometrics.pose import (
    LEFT_EYE_IDX,
    RIGHT_EYE_IDX,
    is_grant_pose,
    pose_from_landmarks,
)

logger = logging.getLogger("biometrics.engine")

RESULT_RECOGNIZED = "recognized"
RESULT_UNKNOWN = "unknown"
RESULT_NO_FACE = "no_face"
RESULT_BAD_POSE = "bad_pose"
RESULT_NO_GALLERY = "no_gallery"
RESULT_NEEDS_DOCUMENT = "needs_document"
RESULT_CALIBRATION_REQUIRED = "calibration_required"

MIN_LANDMARKS = 400
FACE_SIZE = (200, 200)
TOLERANCE = 70.0
GEO_MAX_DISTANCE = 5.5

# Recortes sobre el rostro alineado 200x200.
PERIOCULAR_BOX = (20, 20, 160, 90)  # x, y, w, h
NOSE_BOX = (60, 70, 80, 80)

KEY_LANDMARKS = (
    33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
    362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398,
    1, 2, 98, 327, 168, 6, 197, 195, 5, 4,
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 78, 13, 14, 87, 317,
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365,
    379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93,
    234, 127, 162, 21, 54, 103, 67, 109,
)
MOUTH_LANDMARKS = frozenset(
    (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 78, 13, 14, 87, 317)
)


@dataclass(frozen=True)
class TemplateRecord:
    contributor_id: int
    rif: str | None
    cedula: str | None
    region: FaceRegion
    glasses: bool
    embedding: bytes
    mesh_vector: bytes | None


@dataclass(frozen=True)
class RecognitionOutcome:
    result: str
    message: str
    contributor_id: int | None = None
    rif: str | None = None
    cedula: str | None = None
    confidence: float = 0.0
    occlusion: Occlusion | None = None
    fallback: str | None = None
    region_used: str | None = None


class FaceEngine:
    def parse_landmarks(self, landmarks: list | None) -> np.ndarray | None:
        if not landmarks or len(landmarks) < MIN_LANDMARKS:
            return None
        try:
            pts = np.array(
                [[float(p["x"]), float(p["y"])] for p in landmarks],
                dtype=np.float32,
            )
        except (KeyError, TypeError, ValueError):
            return None
        if np.isnan(pts).any() or np.isinf(pts).any():
            return None
        return pts

    def _bytes_to_image(self, image_bytes: bytes) -> np.ndarray | None:
        if not image_bytes:
            return None
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        return image

    def _mean_point(self, pts: np.ndarray, indices: tuple[int, ...]) -> np.ndarray:
        valid = [i for i in indices if i < len(pts)]
        return pts[valid].mean(axis=0)

    def _landmarks_to_pixels(self, pts: np.ndarray, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        pixels = pts.copy()
        pixels[:, 0] *= w
        pixels[:, 1] *= h
        return pixels

    def align_face(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray | None:
        pts_px = self._landmarks_to_pixels(pts, image)
        if max(LEFT_EYE_IDX + RIGHT_EYE_IDX) >= len(pts_px):
            return None
        left_eye = self._mean_point(pts_px, LEFT_EYE_IDX)
        right_eye = self._mean_point(pts_px, RIGHT_EYE_IDX)
        if np.linalg.norm(right_eye - left_eye) < 8:
            return None

        def third_point(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            delta = b - a
            return a + np.array([-delta[1], delta[0]], dtype=np.float32)

        dest_left = np.array([65.0, 80.0], dtype=np.float32)
        dest_right = np.array([135.0, 80.0], dtype=np.float32)
        src = np.float32([left_eye, right_eye, third_point(left_eye, right_eye)])
        dst = np.float32([dest_left, dest_right, third_point(dest_left, dest_right)])
        matrix = cv2.getAffineTransform(src, dst)
        aligned = cv2.warpAffine(
            image, matrix, FACE_SIZE, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        return cv2.equalizeHist(gray)

    def crop_region(self, face: np.ndarray, region: FaceRegion) -> np.ndarray:
        if region is FaceRegion.PERIOCULAR:
            x, y, w, h = PERIOCULAR_BOX
            return cv2.resize(face[y : y + h, x : x + w], FACE_SIZE)
        if region is FaceRegion.NOSE:
            x, y, w, h = NOSE_BOX
            return cv2.resize(face[y : y + h, x : x + w], FACE_SIZE)
        return face

    def face_to_bytes(self, face: np.ndarray) -> bytes:
        _, encoded = cv2.imencode(".png", face)
        return encoded.tobytes()

    def bytes_to_face(self, data: bytes) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)

    def mesh_vector(self, pts: np.ndarray, *, skip_mouth: bool) -> np.ndarray | None:
        indices = [i for i in KEY_LANDMARKS if not (skip_mouth and i in MOUTH_LANDMARKS)]
        if not indices or max(indices) >= len(pts):
            return None
        left = self._mean_point(pts, LEFT_EYE_IDX)
        right = self._mean_point(pts, RIGHT_EYE_IDX)
        mid = (left + right) / 2.0
        dist = float(np.linalg.norm(right - left))
        if dist < 1e-6:
            return None
        angle = np.arctan2(right[1] - left[1], right[0] - left[0])
        cos_a, sin_a = np.cos(-angle), np.sin(-angle)
        rotation = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
        aligned = (pts - mid) @ rotation.T / dist
        return aligned[indices].flatten().astype(np.float32)

    def extract_regions(
        self, image_bytes: bytes, landmarks: list
    ) -> dict[FaceRegion, bytes] | None:
        image = self._bytes_to_image(image_bytes)
        pts = self.parse_landmarks(landmarks)
        if image is None or pts is None:
            return None
        face = self.align_face(image, pts)
        if face is None:
            return None
        return {
            FaceRegion.FULL: self.face_to_bytes(face),
            FaceRegion.PERIOCULAR: self.face_to_bytes(self.crop_region(face, FaceRegion.PERIOCULAR)),
            FaceRegion.NOSE: self.face_to_bytes(self.crop_region(face, FaceRegion.NOSE)),
        }

    def _preferred_region(self, occlusion: Occlusion) -> FaceRegion:
        if occlusion.mouth:
            return FaceRegion.PERIOCULAR
        return FaceRegion.FULL

    def recognize(
        self,
        image_bytes: bytes,
        landmarks: list,
        templates: list[TemplateRecord],
        *,
        glasses_hint: bool = False,
    ) -> RecognitionOutcome:
        occlusion = assess_occlusion(landmarks)
        if occlusion.both_eyes_hidden or not occlusion.alignment_ready:
            return RecognitionOutcome(
                result=RESULT_NEEDS_DOCUMENT,
                message="Ojos no visibles. Use cédula o RIF.",
                occlusion=occlusion,
                fallback="cedula_rif",
            )
        pts = self.parse_landmarks(landmarks)
        if pts is None:
            return RecognitionOutcome(
                result=RESULT_CALIBRATION_REQUIRED,
                message="Se requiere malla facial",
                occlusion=occlusion,
            )
        try:
            pose = pose_from_landmarks(landmarks)
        except ValueError:
            return RecognitionOutcome(
                result=RESULT_BAD_POSE,
                message="Pose no medible",
                occlusion=occlusion,
            )
        if not is_grant_pose(pose):
            return RecognitionOutcome(
                result=RESULT_BAD_POSE,
                message="Pose fuera de rango",
                occlusion=occlusion,
            )
        image = self._bytes_to_image(image_bytes)
        if image is None:
            return RecognitionOutcome(
                result=RESULT_NO_FACE,
                message="Imagen invalida",
                occlusion=occlusion,
            )
        face = self.align_face(image, pts)
        if face is None:
            return RecognitionOutcome(
                result=RESULT_NO_FACE,
                message="No se alineo el rostro",
                occlusion=occlusion,
            )

        region = self._preferred_region(occlusion)
        probe = self.crop_region(face, region)
        pool = [item for item in templates if item.region is region]
        if glasses_hint:
            with_glasses = [item for item in pool if item.glasses]
            if with_glasses:
                pool = with_glasses
        if not pool:
            return RecognitionOutcome(
                result=RESULT_NO_GALLERY,
                message="No hay plantillas faciales",
                occlusion=occlusion,
                region_used=region.value,
            )

        faces = [self.bytes_to_face(item.embedding) for item in pool]
        labels = np.array([item.contributor_id for item in pool], dtype=np.int32)
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, labels)
        label, confidence = recognizer.predict(probe)

        skip_mouth = occlusion.mouth
        query_geo = self.mesh_vector(pts, skip_mouth=skip_mouth)
        if query_geo is not None:
            geos = []
            for item in pool:
                if item.contributor_id != label or not item.mesh_vector:
                    continue
                stored = np.frombuffer(item.mesh_vector, dtype=np.float32)
                if stored.size == query_geo.size:
                    geos.append(float(np.linalg.norm(query_geo - stored)))
            if geos and min(geos) > GEO_MAX_DISTANCE:
                return RecognitionOutcome(
                    result=RESULT_UNKNOWN,
                    message="Rostro no reconocido",
                    occlusion=occlusion,
                    region_used=region.value,
                )

        matched = next(item for item in pool if item.contributor_id == label)
        if confidence <= TOLERANCE:
            return RecognitionOutcome(
                result=RESULT_RECOGNIZED,
                message="Usuario reconocido",
                contributor_id=matched.contributor_id,
                rif=matched.rif,
                cedula=matched.cedula,
                confidence=max(0.0, 1.0 - confidence / 100.0),
                occlusion=occlusion,
                region_used=region.value,
            )
        return RecognitionOutcome(
            result=RESULT_UNKNOWN,
            message="Rostro no reconocido. Use cédula o RIF.",
            occlusion=occlusion,
            fallback="cedula_rif",
            region_used=region.value,
        )
