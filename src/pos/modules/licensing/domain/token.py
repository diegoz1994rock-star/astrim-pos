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
        )
