"""Endpoints `/api/v1/payment-methods` — de solo lectura, espejo exacto de
la configuración de QR/Nequi/Bre-B que ya administra el escritorio
(Administración → Pagos electrónicos) y que Caja consulta al cobrar (ver
`qr_payment_dialog.py`/`nequi_payment_dialog.py`/`breb_payment_dialog.py`,
los tres llaman a `get_default_config()` sin chequeo de permiso adicional
— cualquier cajero autenticado ve el método predeterminado, mismo criterio
acá). Ningún dato inventado: si el escritorio no tiene un método
configurado, el endpoint responde 409 en vez de devolver un objeto vacío o
con valores por defecto, para que Android nunca muestre información falsa.

Deliberadamente NO expone Daviplata, Transferencia Bancaria, alias,
descripción ni instrucciones al cliente — ninguno de esos existe hoy en el
escritorio (ver `qr_payments`/`nequi_payments`/`bre_b_payments`), y este
endpoint es un espejo, no una ampliación de funcionalidad."""

from __future__ import annotations

from pathlib import Path as FilesystemPath

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from pos.core.security.session import ActiveSession
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.sync.server.api.dependencies import get_current_session
from pos.modules.sync.server.api.payment_methods_schemas import (
    BreBPaymentConfigSchema,
    NequiPaymentConfigSchema,
    QrPaymentConfigSchema,
)


def create_payment_methods_router(
    qr_payment_service: QrPaymentService,
    nequi_payment_service: NequiPaymentService,
    breb_payment_service: BreBPaymentService,
) -> APIRouter:
    router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])

    @router.get("/qr", response_model=QrPaymentConfigSchema)
    def get_qr_config(
        _session: ActiveSession = Depends(get_current_session),
    ) -> QrPaymentConfigSchema:
        config = qr_payment_service.get_default_config()
        if config is None:
            raise HTTPException(
                status_code=409,
                detail="No hay un QR configurado en Administración → Pagos electrónicos.",
            )
        return QrPaymentConfigSchema.from_dto(config)

    @router.get("/qr/{config_id}/image")
    def get_qr_image(
        config_id: int, _session: ActiveSession = Depends(get_current_session)
    ) -> FileResponse:
        configs = {c.id: c for c in qr_payment_service.list_configs()}
        config = configs.get(config_id)
        if config is None:
            raise HTTPException(status_code=404, detail="No existe ningún QR con ese id.")
        if not config.image_path:
            raise HTTPException(status_code=404, detail="Este QR no tiene imagen.")
        image_file = FilesystemPath(config.image_path)
        if not image_file.is_file():
            raise HTTPException(
                status_code=404, detail="La imagen de este QR no está disponible."
            )
        return FileResponse(image_file)

    @router.get("/nequi", response_model=NequiPaymentConfigSchema)
    def get_nequi_config(
        _session: ActiveSession = Depends(get_current_session),
    ) -> NequiPaymentConfigSchema:
        config = nequi_payment_service.get_default_config()
        if config is None:
            raise HTTPException(
                status_code=409,
                detail="No hay un número de Nequi configurado en Administración → Pagos "
                "electrónicos.",
            )
        return NequiPaymentConfigSchema.from_dto(config)

    @router.get("/bre-b", response_model=BreBPaymentConfigSchema)
    def get_breb_config(
        _session: ActiveSession = Depends(get_current_session),
    ) -> BreBPaymentConfigSchema:
        config = breb_payment_service.get_default_config()
        if config is None:
            raise HTTPException(
                status_code=409,
                detail="No hay una llave Bre-B configurada en Administración → Pagos "
                "electrónicos.",
            )
        return BreBPaymentConfigSchema.from_dto(config)

    return router
