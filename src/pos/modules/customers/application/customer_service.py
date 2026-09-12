"""Casos de uso de administración de clientes, créditos y puntos de fidelidad."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.customers.infrastructure.models import (
    CreditMovementType,
    Customer,
    LoyaltyPointsMovementType,
)
from pos.modules.customers.infrastructure.repository import CustomerRepository

_HAS_DEBT_MESSAGE = (
    "No es posible eliminar este cliente porque tiene deudas pendientes. "
    "Primero debe cancelar todas sus facturas."
)


def _to_dto(customer: Customer, current_debt: Decimal) -> CustomerDTO:
    return CustomerDTO(
        id=customer.id,
        full_name=customer.full_name,
        document_id=customer.document_id,
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        credit_limit=customer.credit_limit,
        current_debt=current_debt,
        loyalty_points_balance=customer.loyalty_points_balance,
        credit_history_cleared_at=customer.credit_history_cleared_at,
    )


class CustomerManagementService:
    """CRUD de clientes, más movimientos manuales de crédito/deuda y puntos
    de fidelidad (el cargo automático al facturar una venta a crédito lo
    hará el módulo de Ventas, reutilizando `register_credit_movement`)."""

    def list_customers(self) -> list[CustomerDTO]:
        with session_scope() as session:
            repo = CustomerRepository(session)
            return [
                _to_dto(customer, repo.get_current_debt(customer.id))
                for customer in repo.list_all()
            ]

    def get_customer(self, customer_id: int) -> CustomerDTO | None:
        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get(customer_id)
            if customer is None:
                return None
            return _to_dto(customer, repo.get_current_debt(customer.id))

    def create_customer(
        self,
        *,
        full_name: str,
        document_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        credit_limit: Decimal = Decimal(0),
    ) -> CustomerDTO:
        full_name = full_name.strip()
        if not full_name:
            raise BusinessRuleViolationError("El nombre del cliente es obligatorio.")
        if credit_limit < 0:
            raise BusinessRuleViolationError("El cupo de crédito no puede ser negativo.")
        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.create(
                full_name=full_name,
                document_id=document_id,
                email=email,
                phone=phone,
                address=address,
                credit_limit=credit_limit,
            )
            return _to_dto(customer, Decimal(0))

    def remove_customer(self, customer_id: int) -> None:
        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get(customer_id)
            if customer is None:
                raise NotFoundError(f"No existe el cliente con id={customer_id}.")
            if repo.get_current_debt(customer_id) != Decimal(0):
                raise BusinessRuleViolationError(_HAS_DEBT_MESSAGE)
            repo.set_deleted(customer, True)

    def clear_credit_history(self, customer_id: int) -> None:
        """"Borrar historial" (Cuentas por Cobrar): nunca borra facturas,
        ventas ni recibos — solo mueve la fecha de corte que oculta lo ya
        saldado de las dos tablas de historial (`BillingService.
        list_customer_debt_history`/`list_customer_payment_receipts`),
        para que el módulo de crédito se vea vacío y se pueda "empezar de
        nuevo". Solo permitido con deuda exactamente en cero, igual que la
        validación de `remove_customer`."""
        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get(customer_id)
            if customer is None:
                raise NotFoundError(f"No existe el cliente con id={customer_id}.")
            if repo.get_current_debt(customer_id) != Decimal(0):
                raise BusinessRuleViolationError(_HAS_DEBT_MESSAGE)
            customer.credit_history_cleared_at = datetime.now(UTC)

    def register_credit_movement(
        self,
        *,
        customer_id: int,
        movement_type: CreditMovementType,
        amount: Decimal,
        reference: str | None = None,
        created_by_user_id: int | None = None,
    ) -> Decimal:
        """Registra un cargo o abono a la cuenta de crédito del cliente y
        devuelve el nuevo saldo de deuda."""
        if amount <= 0:
            raise BusinessRuleViolationError("El monto debe ser mayor que cero.")

        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get(customer_id)
            if customer is None:
                raise NotFoundError(f"No existe el cliente con id={customer_id}.")

            current_debt = repo.get_current_debt(customer_id)
            if movement_type is CreditMovementType.CHARGE:
                new_balance = current_debt + amount
                if new_balance > customer.credit_limit:
                    raise BusinessRuleViolationError(
                        f"El cargo excede el cupo de crédito disponible "
                        f"(deuda actual {current_debt}, cupo {customer.credit_limit})."
                    )
            else:
                new_balance = current_debt - amount
                if new_balance < 0:
                    raise BusinessRuleViolationError(
                        f"El abono ({amount}) es mayor que la deuda actual ({current_debt})."
                    )

            repo.add_credit_movement(
                customer_id=customer_id,
                movement_type=movement_type,
                amount=amount,
                balance_after=new_balance,
                reference=reference,
                created_by_user_id=created_by_user_id,
            )
            return new_balance

    def register_loyalty_movement(
        self, *, customer_id: int, points: int, movement_type: LoyaltyPointsMovementType
    ) -> int:
        """Registra puntos ganados o canjeados y devuelve el nuevo saldo."""
        if points <= 0:
            raise BusinessRuleViolationError("Los puntos deben ser un número mayor que cero.")

        with session_scope() as session:
            repo = CustomerRepository(session)
            customer = repo.get(customer_id)
            if customer is None:
                raise NotFoundError(f"No existe el cliente con id={customer_id}.")

            if movement_type is LoyaltyPointsMovementType.REDEEMED:
                if points > customer.loyalty_points_balance:
                    raise BusinessRuleViolationError(
                        f"No hay suficientes puntos: disponibles "
                        f"{customer.loyalty_points_balance}, solicitados {points}."
                    )
                customer.loyalty_points_balance -= points
            else:
                customer.loyalty_points_balance += points

            repo.add_loyalty_movement(
                customer, points=points, movement_type=movement_type, reference=None
            )
            return customer.loyalty_points_balance
