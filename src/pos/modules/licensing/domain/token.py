"""Payload del token de licencia y su serialización determinística.

El "license_key" que el cliente activa es, en la práctica,
`base64(payload_json) + "." + base64(firma_ed25519)`. El payload se
serializa con claves ordenadas y sin espacios para que firmar y verificar
operen siempre sobre los mismos bytes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from pos.modules.licensing.domain.enums import LicenseType


@dataclass(frozen=True)
class LicenseTokenPayload:
    license_uuid: str
    hardware_fingerprint: str
    license_type: LicenseType
    issued_at: datetime
    expires_at: datetime | None
    """`None` únicamente para licencias `PERMANENT`."""
    company_name: str | None = None
    company_nit: str | None = None
    allowed_users: int | None = None
    allowed_branches: int | None = None
    allowed_registers: int | None = None
    max_devices: int = 1
    """Cuántos equipos distintos pueden estar autorizados simultáneamente
    bajo esta licencia (ver `infrastructure/models.py::AuthorizedDevice`).
    Todos los campos nuevos tienen valor por defecto para que una clave ya
    emitida antes de que existieran siga firmando/verificando igual — la
    firma se valida sobre los bytes ya guardados, nunca se recalcula."""

    def to_signable_bytes(self) -> bytes:
        data = asdict(self)
        data["license_type"] = self.license_type.value
        data["issued_at"] = self.issued_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat() if self.expires_at else None
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def from_dict(data: dict[str, object]) -> LicenseTokenPayload:
        expires_at_raw = data["expires_at"]
        return LicenseTokenPayload(
            license_uuid=str(data["license_uuid"]),
            hardware_fingerprint=str(data["hardware_fingerprint"]),
            license_type=LicenseType(data["license_type"]),
            issued_at=datetime.fromisoformat(str(data["issued_at"])),
            expires_at=datetime.fromisoformat(str(expires_at_raw)) if expires_at_raw else None,
            company_name=(
                str(data["company_name"]) if data.get("company_name") is not None else None
            ),
            company_nit=(
                str(data["company_nit"]) if data.get("company_nit") is not None else None
            ),
            allowed_users=(
                int(data["allowed_users"])  # type: ignore[arg-type]
                if data.get("allowed_users") is not None
                else None
            ),
            allowed_branches=(
                int(data["allowed_branches"])  # type: ignore[arg-type]
                if data.get("allowed_branches") is not None
                else None
            ),
            allowed_registers=(
                int(data["allowed_registers"])  # type: ignore[arg-type]
                if data.get("allowed_registers") is not None
                else None
            ),
            max_devices=int(data.get("max_devices", 1)),  # type: ignore[arg-type]
        )
