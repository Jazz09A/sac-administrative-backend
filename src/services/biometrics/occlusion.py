"""Oclusión de boca/ojos a partir de la malla MediaPipe."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.biometrics.pose import LEFT_EYE_IDX, RIGHT_EYE_IDX, _as_xyz, _mean

MOUTH_UPPER_IDX = 13
MOUTH_LOWER_IDX = 14
EYE_SPAN_MIN = 0.015
MOUTH_OPENING_RATIO = 0.12
MIN_LANDMARKS = 400


@dataclass(frozen=True)
class Occlusion:
    """Flags True = región no usable."""

    mouth: bool
    left_eye: bool
    right_eye: bool

    @property
    def both_eyes_hidden(self) -> bool:
        return self.left_eye and self.right_eye

    @property
    def alignment_ready(self) -> bool:
        return not self.left_eye and not self.right_eye


def _span(points: list[tuple[float, float]], indices: tuple[int, ...]) -> float:
    xs = [points[i][0] for i in indices if i < len(points)]
    ys = [points[i][1] for i in indices if i < len(points)]
    if not xs:
        return 0.0
    return float(max(max(xs) - min(xs), max(ys) - min(ys)))


def assess_occlusion(landmarks: list | None) -> Occlusion:
    """Detecta tapabocas (boca colapsada) y ojos no visibles."""
    if not landmarks or len(landmarks) < MIN_LANDMARKS:
        return Occlusion(mouth=True, left_eye=True, right_eye=True)
    points_xyz = _as_xyz(landmarks)
    xy = [(p[0], p[1]) for p in points_xyz]
    left_hidden = _span(xy, LEFT_EYE_IDX) < EYE_SPAN_MIN
    right_hidden = _span(xy, RIGHT_EYE_IDX) < EYE_SPAN_MIN
    left = _mean(xy, LEFT_EYE_IDX)
    right = _mean(xy, RIGHT_EYE_IDX)
    interocular = ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5
    mouth = True
    if (
        MOUTH_UPPER_IDX < len(xy)
        and MOUTH_LOWER_IDX < len(xy)
        and interocular > 1e-6
    ):
        opening = abs(xy[MOUTH_LOWER_IDX][1] - xy[MOUTH_UPPER_IDX][1])
        mouth = (opening / interocular) < MOUTH_OPENING_RATIO
    return Occlusion(mouth=mouth, left_eye=left_hidden, right_eye=right_hidden)
