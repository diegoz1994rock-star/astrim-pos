"""Pruebas de `pool_code_generator.py` (funciones puras, sin base de
datos)."""

from __future__ import annotations

import re

from pos.modules.licensing.infrastructure.pool_code_generator import (
    generate_pool_code,
    normalize_pool_code,
    split_hardware_prefixed_code,
)

_CODE_PATTERN = re.compile(r"^ASTR(-[A-HJ-NP-Z2-9]{4}){4}$")
"""4 grupos de 4, alfabeto sin 0/O/1/I."""


def test_generated_code_matches_expected_format() -> None:
    code = generate_pool_code()

    assert _CODE_PATTERN.match(code), code


def test_generated_code_never_contains_ambiguous_characters() -> None:
    for _ in range(200):
        code = generate_pool_code()
        for ambiguous in ("0", "O", "1", "I"):
            assert ambiguous not in code


def test_generating_many_codes_has_no_collisions() -> None:
    codes = {generate_pool_code() for _ in range(5000)}

    assert len(codes) == 5000


def test_normalize_strips_whitespace_and_uppercases() -> None:
    assert normalize_pool_code(" astr-m1a7-k9px-42qd-w8lf ") == "ASTR-M1A7-K9PX-42QD-W8LF"


def test_normalize_rebuilds_dashes_from_spaces() -> None:
    assert normalize_pool_code("ASTR M1A7 K9PX 42QD W8LF") == "ASTR-M1A7-K9PX-42QD-W8LF"


def test_normalize_rebuilds_dashes_when_missing_entirely() -> None:
    assert normalize_pool_code("astrm1a7k9px42qdw8lf") == "ASTR-M1A7-K9PX-42QD-W8LF"


def test_split_hardware_prefixed_code_separates_prefix_and_pool_code() -> None:
    hardware_prefix, pool_code = split_hardware_prefixed_code(
        "1B35-65FA-ASTR-M1A7-K9PX-42QD-W8LF"
    )

    assert hardware_prefix == "1B35-65FA"
    assert pool_code == "ASTR-M1A7-K9PX-42QD-W8LF"


def test_split_hardware_prefixed_code_tolerates_spaces_and_lowercase() -> None:
    hardware_prefix, pool_code = split_hardware_prefixed_code(
        " 1b35 65fa astr m1a7 k9px 42qd w8lf "
    )

    assert hardware_prefix == "1B35-65FA"
    assert pool_code == "ASTR-M1A7-K9PX-42QD-W8LF"
