"""Pruebas de `generate_ean13_candidate`: el candidato siempre trae un
dígito verificador EAN-13 real (algoritmo mod-10 estándar), no un número
inventado."""

from __future__ import annotations

from pos.modules.products.domain.barcode_generation import (
    _ean13_check_digit,
    generate_ean13_candidate,
)


def test_generate_ean13_candidate_has_thirteen_digits() -> None:
    code = generate_ean13_candidate()
    assert len(code) == 13
    assert code.isdigit()


def test_generate_ean13_candidate_has_a_valid_check_digit() -> None:
    code = generate_ean13_candidate()
    assert int(code[-1]) == _ean13_check_digit(code[:-1])


def test_ean13_check_digit_matches_known_value() -> None:
    assert _ean13_check_digit("690123456789") == 2


def test_generate_ean13_candidate_varies_across_calls() -> None:
    codes = {generate_ean13_candidate() for _ in range(20)}
    assert len(codes) > 1
