"""Pose frontal a partir de landmarks MediaPipe (478 puntos)."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees
from typing import Any

YAW_SCALE = 50.0
YAW_Z_SCALE = 140.0
YAW_BLEND_Z = 0.45
GRANT_YAW_ABS = 15.0
GRANT_PITCH_ROLL_ABS = 10.0

LEFT_EYE_IDX = (33, 133, 160, 159, 158, 157, 173, 246)
RIGHT_EYE_IDX = (362, 263, 387, 386, 385, 384, 398, 466)
NOSE_TIP_IDX = 1
CHIN_IDX = 152
LEFT_CHEEK_IDX = 234
RIGHT_CHEEK_IDX = 454


@dataclass(frozen=True)
class Pose:
    yaw: float
    pitch: float
    roll: float


def _as_xyz(landmarks: Any) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for item in landmarks:
        if isinstance(item, dict):
            points.append(
                (float(item["x"]), float(item["y"]), float(item.get("z", 0.0)))
            )
        else:
            z = float(item[2]) if len(item) > 2 else 0.0
            points.append((float(item[0]), float(item[1]), z))
    return points


def _mean(
    points: list[tuple[float, float]], indices: tuple[int, ...]
) -> tuple[float, float]:
    xs = [points[i][0] for i in indices if i < len(points)]
    ys = [points[i][1] for i in indices if i < len(points)]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def pose_from_landmarks(landmarks: Any) -> Pose:
    """Yaw/pitch/roll en grados. yaw < 0 es turn_left."""
    points = _as_xyz(landmarks)
    needed = max(
        LEFT_EYE_IDX
        + RIGHT_EYE_IDX
        + (NOSE_TIP_IDX, CHIN_IDX, LEFT_CHEEK_IDX, RIGHT_CHEEK_IDX)
    )
    if len(points) <= needed:
        raise ValueError("landmarks insuficientes para pose")
    xy = [(p[0], p[1]) for p in points]
    left_eye = _mean(xy, LEFT_EYE_IDX)
    right_eye = _mean(xy, RIGHT_EYE_IDX)
    nose = xy[NOSE_TIP_IDX]
    chin = xy[CHIN_IDX]
    cheek_l = points[LEFT_CHEEK_IDX]
    cheek_r = points[RIGHT_CHEEK_IDX]
    d_left = abs(nose[0] - cheek_l[0])
    d_right = abs(cheek_r[0] - nose[0])
    yaw_xy = YAW_SCALE * (d_left - d_right) / (d_left + d_right + 1e-6)
    yaw_z = (cheek_r[2] - cheek_l[2]) * YAW_Z_SCALE
    if abs(cheek_l[2]) + abs(cheek_r[2]) > 1e-6:
        yaw = (1.0 - YAW_BLEND_Z) * yaw_xy + YAW_BLEND_Z * yaw_z
    else:
        yaw = yaw_xy
    roll = degrees(atan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))
    eye_mid = ((left_eye[0] + right_eye[0]) / 2.0, (left_eye[1] + right_eye[1]) / 2.0)
    pitch = ((nose[1] - eye_mid[1]) / (chin[1] - eye_mid[1] + 1e-6) - 0.40) * 80.0
    return Pose(yaw=float(yaw), pitch=float(pitch), roll=float(roll))


def is_grant_pose(pose: Pose) -> bool:
    return (
        abs(pose.yaw) <= GRANT_YAW_ABS
        and abs(pose.pitch) <= GRANT_PITCH_ROLL_ABS
        and abs(pose.roll) <= GRANT_PITCH_ROLL_ABS
    )
