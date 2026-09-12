package com.astrim.pos.core.session

import com.astrim.pos.core.network.dto.SessionInfoDto

/**
 * Réplica exacta de `role_label` en `main.py::build_welcome_widget` del
 * escritorio: un Administrador General siempre se muestra como
 * "Administrador" (aunque también tenga su propio `job_position_name`,
 * ej. "Administrador General" — el escritorio prioriza la etiqueta fija
 * para ese caso); cualquier otro cargo muestra su `job_position_name`
 * real, o "Empleado" si no tiene ninguno asignado.
 */
fun roleLabel(session: SessionInfoDto): String =
    if (session.isAdmin) "Administrador" else (session.jobPositionName ?: "Empleado")
