"""Pruebas de UI de `InvoiceSettingsView` (backend `offscreen`): selección
de tamaño de papel personalizado, casillas fijas de totales, y que
`_dto_from_form()` arme correctamente los campos nuevos (márgenes,
orientación, tamaño de fuente, tamaño personalizado).

No se ejercita el botón "Seleccionar logo" (`QFileDialog.getOpenFileName`
es un diálogo real bloqueante — mismo motivo ya documentado en
`tests/ui/sales/test_sale_view.py` para otros diálogos modales)."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize
from pos.modules.invoice_settings.presentation.invoice_settings_view import InvoiceSettingsView


def _make_view(qtbot: QtBot) -> InvoiceSettingsView:
    view = InvoiceSettingsView(Mock())
    qtbot.addWidget(view)
    return view


def test_custom_paper_size_reveals_width_height_spinboxes(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    custom_index = view._paper_size_combo.findData(PaperSize.CUSTOM)
    assert custom_index >= 0
    view._paper_size_combo.setCurrentIndex(custom_index)

    assert view._custom_size_row.isVisible() or not view.isVisible()
    assert view._current_paper_size() is PaperSize.CUSTOM


def test_fixed_paper_size_hides_custom_width_height(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    letter_index = view._paper_size_combo.findData(PaperSize.LETTER)
    view._paper_size_combo.setCurrentIndex(letter_index)

    dto = view._dto_from_form()
    assert dto.paper_size is PaperSize.LETTER
    assert dto.custom_width_mm is None
    assert dto.custom_height_mm is None


def test_totals_checkboxes_map_to_show_flags(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._show_discounts_check.setChecked(False)
    view._show_taxes_check.setChecked(True)
    view._show_total_check.setChecked(False)

    dto = view._dto_from_form()
    assert dto.show_discounts is False
    assert dto.show_taxes is True
    assert dto.show_total is False


def test_content_order_no_longer_includes_totals_keys(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    dto = view._dto_from_form()
    assert "discounts" not in dto.content_order
    assert "taxes" not in dto.content_order
    assert "total" not in dto.content_order
    assert len(dto.content_order) == 11


def test_dto_from_form_includes_margins_orientation_and_font_size(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._margin_top_spin.setValue(5.0)
    view._margin_right_spin.setValue(6.0)
    view._margin_bottom_spin.setValue(7.0)
    view._margin_left_spin.setValue(9.0)
    view._font_size_spin.setValue(14)
    landscape_index = view._orientation_combo.findData(Orientation.LANDSCAPE)
    view._orientation_combo.setCurrentIndex(landscape_index)

    dto = view._dto_from_form()
    assert dto.margin_top_mm == 5.0
    assert dto.margin_right_mm == 6.0
    assert dto.margin_bottom_mm == 7.0
    assert dto.margin_left_mm == 9.0
    assert dto.base_font_size_pt == 14
    assert dto.orientation is Orientation.LANDSCAPE


def test_save_click_with_empty_company_name_shows_error_and_does_not_save(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._company_name_edit.setText("   ")
    view._show_error = Mock()

    view._on_save_clicked()

    view._show_error.assert_called_once()
    view._view_model.save.assert_not_called()


def test_save_click_with_valid_name_calls_view_model_save(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._company_name_edit.setText("Ferretería El Tornillo")

    view._on_save_clicked()

    view._view_model.save.assert_called_once()
    saved_dto = view._view_model.save.call_args[0][0]
    assert saved_dto.company_name == "Ferretería El Tornillo"


# -- micro-posicionamiento: botones ▲▼ y sincronización del offset -------


def test_selecting_a_directly_addressable_element_enables_move_buttons(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    # "customer" (no "logo": ahora es el primer elemento de content_order,
    # así que su botón de subir estaría deshabilitado por estar al tope).
    view._on_element_selected("customer")

    assert view._properties_panel._move_up_button.isEnabled()
    assert view._properties_panel._move_down_button.isEnabled()


def test_selecting_a_sub_element_of_a_fixed_group_disables_move_buttons(qtbot: QtBot) -> None:
    """"Factura N.º" es parte del grupo fijo "company" — se puede
    micro-posicionar con las flechas, pero no tiene una fila propia en
    `content_order` para reordenar con los botones."""
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._on_element_selected("invoice_number")

    assert not view._properties_panel._move_up_button.isEnabled()
    assert not view._properties_panel._move_down_button.isEnabled()


def test_selecting_totals_disables_move_buttons(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._on_element_selected("totals")

    assert not view._properties_panel._move_up_button.isEnabled()
    assert not view._properties_panel._move_down_button.isEnabled()


def test_move_up_button_reorders_content_order(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    original_order = list(view._content_order)
    customer_index = original_order.index("customer")
    assert customer_index > 0

    view._on_element_selected("customer")
    view._on_move_selected(-1)

    assert view._content_order[customer_index - 1] == "customer"
    assert view._content_order.index("customer") == customer_index - 1


def test_move_down_button_reorders_content_order(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    original_order = list(view._content_order)
    logo_index = original_order.index("logo")

    view._on_element_selected("logo")
    view._on_move_selected(1)

    assert view._content_order[logo_index + 1] == "logo"


def test_move_up_at_first_position_does_nothing(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    original_order = list(view._content_order)

    view._on_element_selected("company")
    view._on_move_selected(-1)

    assert view._content_order == original_order


def test_move_with_nothing_selected_does_nothing(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    original_order = list(view._content_order)

    view._on_move_selected(1)

    assert view._content_order == original_order


def test_spacing_offset_changed_updates_template_without_rebuilding_canvas(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._canvas.set_settings = Mock()

    view._on_spacing_offset_changed("invoice_number", 7.0)

    assert view._template.spacing_offsets == {"invoice_number": 7.0}
    view._canvas.set_settings.assert_not_called()


def test_spacing_offset_persists_through_dto_from_form(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._on_spacing_offset_changed("logo", -3.0)

    dto = view._dto_from_form()
    assert dto.template.spacing_offsets == {"logo": -3.0}


# -- posición libre del logo ----------------------------------------------


def test_logo_double_click_signal_opens_file_picker(qtbot: QtBot) -> None:
    """El doble clic sobre el logo en el lienzo debe abrir el mismo
    selector de archivo que ya usa el botón "Seleccionar logo" — sin
    diálogo nuevo. No se ejercita el diálogo real (bloqueante, mismo
    motivo documentado al inicio del archivo); se verifica el cableado
    directamente."""
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._on_select_logo_clicked = Mock()

    view._canvas.logo_double_clicked.emit()

    view._on_select_logo_clicked.assert_called_once()


def test_logo_position_changed_updates_template_without_rebuilding_canvas(qtbot: QtBot) -> None:
    """Mismo patrón que `test_spacing_offset_changed_updates_template_without_rebuilding_canvas`
    — el lienzo ya movió el logo solo (arrastre nativo de Qt), la vista
    solo debe reflejarlo en `self._template`, nunca pedirle un
    `set_settings()` nuevo al lienzo."""
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._canvas.set_settings = Mock()

    view._on_logo_position_changed(250.0, 140.0)

    logo_style = view._template.image_styles["logo"]
    assert logo_style.absolute_x_pt == 250.0
    assert logo_style.absolute_y_pt == 140.0
    view._canvas.set_settings.assert_not_called()


def test_logo_position_changed_updates_properties_panel_when_logo_selected(qtbot: QtBot) -> None:
    """"Si el usuario arrastra el logo, los valores X e Y deben
    actualizarse automáticamente" (en el panel de propiedades)."""
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._on_element_selected("logo")
    view._properties_panel.update_logo_position = Mock()

    view._on_logo_position_changed(250.0, 140.0)

    view._properties_panel.update_logo_position.assert_called_once_with(250.0, 140.0)


def test_logo_position_changed_does_not_touch_panel_when_logo_not_selected(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._on_element_selected("invoice_number")
    view._properties_panel.update_logo_position = Mock()

    view._on_logo_position_changed(250.0, 140.0)

    view._properties_panel.update_logo_position.assert_not_called()


def test_logo_position_persists_through_dto_from_form(qtbot: QtBot) -> None:
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))

    view._on_logo_position_changed(250.0, 140.0)

    dto = view._dto_from_form()
    logo_style = dto.template.image_styles["logo"]
    assert logo_style.absolute_x_pt == 250.0
    assert logo_style.absolute_y_pt == 140.0


def test_typing_position_x_y_in_panel_moves_logo_immediately(qtbot: QtBot) -> None:
    """"Si el usuario escribe X = 250, Y = 140, el logo debe moverse
    inmediatamente" — vía el camino ya existente de siempre
    (`image_style_changed` → `_on_form_changed` → `set_settings()`)."""
    view = _make_view(qtbot)
    view._on_settings_loaded(InvoiceSettingsDTO(company_name="Mi Negocio"))
    view._canvas.set_settings = Mock()
    view._on_element_selected("logo")

    view._properties_panel._position_x_spin.setValue(250.0)
    view._properties_panel._position_y_spin.setValue(140.0)

    dto = view._canvas.set_settings.call_args[0][0]
    logo_style = dto.template.image_styles["logo"]
    assert logo_style.absolute_x_pt == 250.0
    assert logo_style.absolute_y_pt == 140.0
