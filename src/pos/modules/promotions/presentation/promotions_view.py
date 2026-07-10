"""Panel de Promociones y Descuentos: alta, activación y reglas de aplicación."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.promotions.application.dto import PromotionDTO
from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType
from pos.modules.promotions.presentation.promotions_view_model import PromotionsViewModel

_COLUMNS = ["Nombre", "Tipo", "Valor", "Reglas", "Estado"]
_RULE_COLUMNS = ["Tipo de regla", "Valor"]
_DISCOUNT_TYPE_LABELS = {
    DiscountType.PERCENTAGE: "Porcentaje",
    DiscountType.FIXED_AMOUNT: "Monto fijo",
}
_RULE_TYPE_LABELS = {
    PromotionRuleType.PRODUCT: "Producto (id)",
    PromotionRuleType.CATEGORY: "Categoría (id)",
    PromotionRuleType.COMBO: "Combo (id de producto)",
    PromotionRuleType.MIN_QUANTITY: "Cantidad mínima",
    PromotionRuleType.DAY_OF_WEEK: "Día de la semana (mon,tue,...)",
    PromotionRuleType.TIME_RANGE: "Horario (HH:MM-HH:MM)",
}


class _NewPromotionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva promoción")
        form = QFormLayout(self)

        self.name_edit = QLineEdit(self)
        self.description_edit = QLineEdit(self)
        self.type_combo = QComboBox(self)
        for discount_type, label in _DISCOUNT_TYPE_LABELS.items():
            self.type_combo.addItem(label, discount_type)
        self.value_edit = QLineEdit(self)
        self.value_edit.setPlaceholderText("Ej. 10 (10% o $10 según el tipo)")

        form.addRow("Nombre:", self.name_edit)
        form.addRow("Descripción:", self.description_edit)
        form.addRow("Tipo de descuento:", self.type_combo)
        form.addRow("Valor:", self.value_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def discount_value(self) -> Decimal | None:
        try:
            return Decimal(self.value_edit.text().strip())
        except InvalidOperation:
            return None


class PromotionsView(QWidget):
    def __init__(self, view_model: PromotionsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._promotions: list[PromotionDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Promociones y Descuentos")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nueva promoción")
        self._toggle_button = QPushButton("Activar/Desactivar")
        toolbar.addWidget(self._new_button)
        toolbar.addWidget(self._toggle_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setMaximumHeight(220)
        layout.addWidget(self._table)

        rules_toolbar = QHBoxLayout()
        rules_toolbar.addWidget(QLabel("Reglas de la promoción seleccionada:"))
        rules_toolbar.addStretch()
        self._add_rule_button = QPushButton("Agregar regla")
        self._remove_rule_button = QPushButton("Quitar regla seleccionada")
        rules_toolbar.addWidget(self._add_rule_button)
        rules_toolbar.addWidget(self._remove_rule_button)
        layout.addLayout(rules_toolbar)

        self._rules_table = QTableWidget(0, len(_RULE_COLUMNS), self)
        self._rules_table.setHorizontalHeaderLabels(_RULE_COLUMNS)
        self._rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._rules_table)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._add_rule_button.clicked.connect(self._on_add_rule_clicked)
        self._remove_rule_button.clicked.connect(self._on_remove_rule_clicked)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._view_model.promotions_loaded.connect(self._on_promotions_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _selected_promotion(self) -> PromotionDTO | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._promotions[rows[0].row()]

    def _on_new_clicked(self) -> None:
        dialog = _NewPromotionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        value = dialog.discount_value()
        if value is None:
            self._show_error("El valor del descuento debe ser un número válido.")
            return
        self._view_model.create_promotion(
            name=dialog.name_edit.text(),
            description=dialog.description_edit.text(),
            discount_type=dialog.type_combo.currentData(),
            discount_value=value,
        )

    def _on_toggle_clicked(self) -> None:
        promotion = self._selected_promotion()
        if promotion is None:
            self._show_error("Selecciona una promoción.")
            return
        self._view_model.set_active(promotion.id, not promotion.is_active)

    def _on_add_rule_clicked(self) -> None:
        promotion = self._selected_promotion()
        if promotion is None:
            self._show_error("Selecciona una promoción.")
            return
        labels = list(_RULE_TYPE_LABELS.values())
        types = list(_RULE_TYPE_LABELS.keys())
        label, accepted = QInputDialog.getItem(
            self, "Nueva regla", "Tipo de regla:", labels, 0, editable=False
        )
        if not accepted:
            return
        rule_type = types[labels.index(label)]
        value, accepted = QInputDialog.getText(self, "Nueva regla", "Valor:")
        if not accepted or not value.strip():
            return
        self._view_model.add_rule(promotion.id, rule_type, value)

    def _on_remove_rule_clicked(self) -> None:
        promotion = self._selected_promotion()
        if promotion is None:
            self._show_error("Selecciona una promoción.")
            return
        rule_rows = self._rules_table.selectionModel().selectedRows()
        if not rule_rows:
            self._show_error("Selecciona una regla para quitar.")
            return
        rule = promotion.rules[rule_rows[0].row()]
        self._view_model.remove_rule(promotion.id, rule.id)

    def _on_selection_changed(self) -> None:
        promotion = self._selected_promotion()
        self._render_rules(promotion)

    def _on_promotions_loaded(self, promotions: list[PromotionDTO]) -> None:
        self._promotions = promotions
        self._table.setRowCount(len(promotions))
        for row, promotion in enumerate(promotions):
            self._table.setItem(row, 0, QTableWidgetItem(promotion.name))
            self._table.setItem(
                row, 1, QTableWidgetItem(_DISCOUNT_TYPE_LABELS[promotion.discount_type])
            )
            self._table.setItem(row, 2, QTableWidgetItem(str(promotion.discount_value)))
            self._table.setItem(row, 3, QTableWidgetItem(str(len(promotion.rules))))
            self._table.setItem(
                row, 4, QTableWidgetItem("Activa" if promotion.is_active else "Inactiva")
            )
        self._render_rules(self._selected_promotion())

    def _render_rules(self, promotion: PromotionDTO | None) -> None:
        rules = promotion.rules if promotion is not None else []
        self._rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            self._rules_table.setItem(
                row, 0, QTableWidgetItem(_RULE_TYPE_LABELS[rule.rule_type])
            )
            self._rules_table.setItem(row, 1, QTableWidgetItem(rule.rule_value))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Promociones", message)
