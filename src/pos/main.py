"""Punto de entrada de la aplicación de escritorio.

Es la raíz de composición (composition root): el único lugar que conoce
todas las piezas del núcleo y las conecta entre sí. Ningún módulo de
negocio debe replicar este cableado — todos reciben sus dependencias ya
resueltas desde aquí (vía el contenedor de DI) o desde el bus de eventos.

Requiere que el esquema de base de datos ya exista (`alembic upgrade head`)
antes del primer arranque; ver README.md.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from pos.core.config.bootstrap import BootstrapConfig, load_bootstrap_config
from pos.core.database.session import init_engine
from pos.core.di.container import Container, get_container
from pos.core.events.bus import EventBus, get_event_bus
from pos.core.logging.config import setup_logging
from pos.core.security.session import SessionManager
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.shared_ui.theme.theme_manager import ThemeManager


def bootstrap_core(container: Container) -> BootstrapConfig:
    """Inicializa logging, el engine de base de datos y registra los
    servicios transversales del núcleo en el contenedor de DI.

    Debe ejecutarse una única vez, antes de construir cualquier ventana.
    """
    config = load_bootstrap_config()
    setup_logging(config.log_dir, level=_parse_log_level(config.log_level))
    init_engine(config.database_url)

    event_bus = get_event_bus()
    container.register_instance(EventBus, event_bus)
    container.register_singleton(SessionManager, SessionManager)
    container.register_singleton(
        BusinessSettingsService, lambda: BusinessSettingsService(event_bus)
    )
    return config


def _parse_log_level(level_name: str) -> int:
    import logging

    return logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)


def build_application() -> QApplication:
    """Crea la instancia de QApplication con metadata básica de la app."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema POS")
    app.setOrganizationName("POS")
    return app


def build_main_window(theme_manager: ThemeManager) -> QMainWindow:
    """Crea la ventana principal vacía.

    El cableado de la pantalla de login real (módulo `auth`) llega en la
    siguiente etapa de desarrollo (M4); por ahora solo aplica el tema por
    defecto y muestra una ventana vacía para validar el arranque completo
    del núcleo.
    """
    theme_manager.apply_light()
    window = QMainWindow()
    window.setWindowTitle("Sistema POS")
    window.resize(1280, 800)
    return window


def main() -> int:
    """Arranca la aplicación de escritorio."""
    container = get_container()
    bootstrap_core(container)

    app = build_application()
    theme_manager = ThemeManager(app)
    container.register_instance(ThemeManager, theme_manager)

    window = build_main_window(theme_manager)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
