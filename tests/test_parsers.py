"""Testes do módulo superset_ingest.parsers.

Cobertura: edge cases conhecidos de _parse_num, _parse_trade_entrada, _pf_guard.
Valida também a regressão do bug de whitespace interno em "-R$ 1,49" descoberta
em 2026-04-10 durante a Fase 12.
"""

from __future__ import annotations

import math

import pytest

from b3_mcp.superset_ingest.parsers import (
    _parse_num,
    _parse_trade_entrada,
    _pf_guard,
)


class TestParseNum:
    @pytest.mark.parametrize(
        "inp,expected",
        [
            ("55,50%", 55.5),
            ("R$ 1.234,56", 1234.56),
            ("-12,30%", -12.3),
            ("-R$ 1,49", -1.49),  # regressão do bug descoberto em 2026-04-10
            ("-R$ 0,62", -0.62),
            ("+50,00%", 50.0),
            ("R$ 0,00", 0.0),
            (42.5, 42.5),
            (0, 0.0),
            ("2.5", 2.5),  # formato US sem vírgula
            ("-1.234,00", -1234.0),
        ],
    )
    def test_valores_validos(self, inp, expected):
        assert _parse_num(inp) == expected

    @pytest.mark.parametrize(
        "inp",
        [
            None,
            "N/A",
            "NA",
            "",
            "   ",
            "null",
            "None",
            "-",
            "—",
            float("inf"),
            float("-inf"),
            float("nan"),
        ],
    )
    def test_retorna_none(self, inp):
        assert _parse_num(inp) is None

    def test_nao_string_nao_num(self):
        assert _parse_num([1, 2]) is None
        assert _parse_num({"a": 1}) is None


class TestParseTradeEntrada:
    def test_formato_completo_com_espacos(self):
        assert _parse_trade_entrada("2024-03-15 @ R$ 30,50") == ("2024-03-15", 30.5)

    def test_formato_completo_sem_espacos(self):
        assert _parse_trade_entrada("2024-03-15@R$30,50") == ("2024-03-15", 30.5)

    def test_sem_arroba(self):
        assert _parse_trade_entrada("2024-03-15") == ("2024-03-15", None)

    @pytest.mark.parametrize("inp", [None, "", "   "])
    def test_vazio(self, inp):
        assert _parse_trade_entrada(inp) == (None, None)

    def test_tipo_invalido(self):
        assert _parse_trade_entrada(42) == (None, None)


class TestPfGuard:
    def test_inf_float(self):
        val, is_inf = _pf_guard(float("inf"))
        assert val is None
        assert is_inf is True

    @pytest.mark.parametrize("s", ["inf", "Infinity", "infinito", "+inf", "∞"])
    def test_inf_string(self, s):
        val, is_inf = _pf_guard(s)
        assert val is None
        assert is_inf is True

    @pytest.mark.parametrize(
        "inp,expected_val",
        [
            (2.5, 2.5),
            ("2.5", 2.5),
            ("2,5", 2.5),
            (0, 0.0),
            (1, 1.0),
            (-0.5, -0.5),
        ],
    )
    def test_valor_finito(self, inp, expected_val):
        val, is_inf = _pf_guard(inp)
        assert val == expected_val
        assert is_inf is False

    @pytest.mark.parametrize("inp", [None, "N/A", "", "null"])
    def test_none_ou_invalido(self, inp):
        val, is_inf = _pf_guard(inp)
        assert val is None
        assert is_inf is False

    def test_nan_nao_e_inf(self):
        val, is_inf = _pf_guard(float("nan"))
        assert val is None
        assert is_inf is False
