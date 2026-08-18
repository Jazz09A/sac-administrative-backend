import os
import sys
from datetime import date, time
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("MYSQL_DATABASE_URL", "mysql+asyncmy://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "k" * 32)
os.environ.setdefault("AUTH_PERSON_ID", "V12345678")
os.environ.setdefault("AUTH_PASSWORD", "password1")
os.environ.setdefault("ADMIN_EMAIL", "admin@local")

import src.models.asset  # noqa: F401
import src.models.contributor  # noqa: F401
import src.models.face_template  # noqa: F401
import src.models.fiscal  # noqa: F401
import src.models.photo  # noqa: F401
import src.models.user  # noqa: F401
import src.models.visit  # noqa: F401
from src.api.v1.biometrics import EnrollRequest
from src.models.asset import AssetMovement, AssetMovementDirection, SeniatAsset
from src.models.contributor import Contributor, ContributorType
from src.models.face_template import FaceRegion, FaceTemplate
from src.models.user import UserCreate
from src.models.visit import EXIT_ALLOWED_STATUSES, VisitCreate, VisitPublic, VisitStatus
from src.services.biometrics.engine import TemplateRecord


def test_contributor_has_cedula_for_biometrics_bind() -> None:
    contributor = Contributor(
        rif="J-12345678-9",
        cedula="V12345678",
        name="Persona Natural",
        type=ContributorType.NATURAL,
    )
    assert contributor.cedula == "V12345678"


def test_face_template_regions_support_occlusion() -> None:
    assert {item.value for item in FaceRegion} == {"full", "periocular", "nose"}
    template = FaceTemplate(
        contributor_id=1,
        region=FaceRegion.PERIOCULAR,
        glasses=True,
        embedding=b"png",
    )
    assert template.glasses is True
    assert template.region is FaceRegion.PERIOCULAR


def test_visit_status_includes_desk_flow() -> None:
    assert VisitStatus.EN_ATENCION.value == "en_atencion"
    assert VisitStatus.INCOMPLETO.value == "incompleto"
    assert VisitStatus.REMITIDO.value == "remitido"


def test_gate_officer_manager_roles_are_valid() -> None:
    for role in ("gate", "officer", "manager", "admin", "user"):
        user = UserCreate(
            person_id="V12345678",
            full_name="Operador",
            password="password1",
            role=role,
        )
        assert user.role == role


def test_seniat_asset_is_institutional_not_taxpayer_belonging() -> None:
    asset = SeniatAsset(
        inventory_code="BN-001",
        serial="SN-99",
        brand="Dell",
        model="Latitude",
        category="computacion",
    )
    movement = AssetMovement(
        asset_id=asset.id,
        carrier_user_id=asset.id,
        direction=AssetMovementDirection.OUT,
    )
    assert "seniat_assets" == SeniatAsset.__tablename__
    assert movement.visit_id is None
    assert not hasattr(asset, "contributor_id")
    assert "carrier_user_id" in AssetMovement.model_fields


def test_contributor_rif_and_name_are_optional() -> None:
    """create_all no ALTER: si Postgres ya tenía rif/name NOT NULL, recrear la base."""
    contributor = Contributor(cedula="V1", type=ContributorType.NATURAL)
    assert contributor.rif is None
    assert contributor.name is None
    assert contributor.cedula == "V1"


def test_visit_create_from_cedula_and_department() -> None:
    payload = VisitCreate(
        contributor_cedula="V1",
        department="Taquilla",
        entry_date=date(2026, 8, 17),
        entry_time=time(8, 0),
    )
    assert payload.contributor_rif is None
    assert payload.contributor_name is None
    assert payload.reason is None
    assert payload.fiscal_id is None
    assert "contributor_cedula" in VisitPublic.model_fields
    assert "contributor_rif" in VisitPublic.model_fields
    assert VisitStatus.EN_ATENCION in EXIT_ALLOWED_STATUSES


def test_visit_create_rejects_temp_rif() -> None:
    with pytest.raises(ValidationError):
        VisitCreate(
            contributor_cedula="V1",
            department="Taquilla",
            contributor_rif="TEMP-123",
            entry_date=date(2026, 8, 17),
            entry_time=time(8, 0),
        )


def test_enroll_requires_cedula_not_rif_or_name() -> None:
    assert EnrollRequest.model_fields["cedula"].is_required()
    assert not EnrollRequest.model_fields["rif"].is_required()
    assert not EnrollRequest.model_fields["name"].is_required()
    landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(400)]
    with pytest.raises(ValidationError):
        EnrollRequest.model_validate(
            {"image": "x", "landmarks": landmarks, "cedula": "V1", "rif": "TEMP-1"}
        )


def test_template_record_rif_allows_none() -> None:
    record = TemplateRecord(
        contributor_id=1,
        rif=None,
        cedula="V1",
        region=FaceRegion.FULL,
        glasses=False,
        embedding=b"png",
        mesh_vector=None,
    )
    assert record.rif is None
    assert record.cedula == "V1"
