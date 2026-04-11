"""Testes de `screener_provider.py`.

Estratégia:
- `_formatar_resultados` é puro sobre um DataFrame do pandas → testa direto.
- `maiores_altas`/`maiores_baixas`/`maiores_volumes` são wrappers sobre a Query
  do tradingview_screener → mock via monkeypatch de `Query.get_scanner_data`.
- `_check_tv` tem branch ImportError → simulado com monkeypatch.
"""

from __future__ import annotations

import pandas as pd
import pytest

from b3_mcp.core.services import screener_provider
from b3_mcp.core.services.screener_provider import (
    _check_tv,
    _formatar_resultados,
    maiores_altas,
    maiores_baixas,
    maiores_volumes,
)


# ═══════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════
def _fake_rows(linhas: list[dict]) -> pd.DataFrame:
    """Monta um DataFrame no formato que o TV screener retorna."""
    return pd.DataFrame(linhas)


@pytest.fixture
def mock_scanner(monkeypatch):
    """Substitui Query.get_scanner_data por um callable controlado."""

    def _install(rows: pd.DataFrame, count: int = None):
        count = count if count is not None else len(rows)

        def fake_get_scanner_data(self):
            return count, rows

        # Patcheia o método na classe Query importada pelo módulo
        from tradingview_screener import Query

        monkeypatch.setattr(Query, "get_scanner_data", fake_get_scanner_data)

    return _install


# ═══════════════════════════════════════════════
# _formatar_resultados
# ═══════════════════════════════════════════════
class TestFormatarResultados:
    def test_dataframe_vazio_retorna_lista_vazia(self):
        df = _fake_rows([])
        assert _formatar_resultados(df) == []

    def test_rows_sem_to_dict_retorna_vazio(self):
        """Quando a entrada não tem .to_dict (ex: None), deve retornar []."""
        assert _formatar_resultados(None) == []
        assert _formatar_resultados([]) == []

    def test_schema_completo(self):
        df = _fake_rows(
            [
                {
                    "name": "BMFBOVESPA:PETR4",
                    "close": 35.5555,
                    "change": 2.3456,
                    "change_abs": 0.80,
                    "volume": 12_345_678,
                    "market_cap_basic": 500_000_000_000.0,
                    "description": "PETROBRAS PN",
                }
            ]
        )
        r = _formatar_resultados(df)
        assert len(r) == 1
        item = r[0]
        assert item["ticker"] == "PETR4"  # prefixo BMFBOVESPA: removido
        assert item["preco"] == 35.56  # round 2 casas
        assert item["variacao_pct"] == 2.35
        assert item["variacao_abs"] == 0.80
        assert item["volume"] == 12_345_678
        assert isinstance(item["market_cap"], float)
        assert item["nome"] == "PETROBRAS PN"

    def test_remove_prefixo_exchange(self):
        df = _fake_rows(
            [
                {
                    "name": "BMFBOVESPA:VALE3",
                    "close": 60,
                    "change": 1,
                    "change_abs": 0.6,
                    "volume": 1,
                    "market_cap_basic": 0,
                    "description": "",
                },
                {
                    "name": "ITUB4",
                    "close": 30,
                    "change": -0.5,
                    "change_abs": -0.15,
                    "volume": 1,
                    "market_cap_basic": 0,
                    "description": "",
                },
            ]
        )
        r = _formatar_resultados(df)
        tickers = [x["ticker"] for x in r]
        assert "VALE3" in tickers
        assert "ITUB4" in tickers

    def test_filtra_tickers_fracionarios_com_f_final(self):
        df = _fake_rows(
            [
                {
                    "name": "BMFBOVESPA:PETR4F",
                    "close": 35,
                    "change": 1,
                    "change_abs": 0.35,
                    "volume": 1,
                    "market_cap_basic": 0,
                    "description": "",
                },
                {
                    "name": "BMFBOVESPA:PETR4",
                    "close": 35,
                    "change": 1,
                    "change_abs": 0.35,
                    "volume": 1,
                    "market_cap_basic": 0,
                    "description": "",
                },
            ]
        )
        r = _formatar_resultados(df)
        tickers = [x["ticker"] for x in r]
        assert "PETR4F" not in tickers
        assert "PETR4" in tickers

    def test_tipos_numericos_garantidos(self):
        """Mesmo se vier string numérica, deve converter."""
        df = _fake_rows(
            [
                {
                    "name": "PETR4",
                    "close": "35.50",
                    "change": "2.34",
                    "change_abs": "0.80",
                    "volume": "1000000",
                    "market_cap_basic": "5e11",
                    "description": "PETRO",
                }
            ]
        )
        r = _formatar_resultados(df)
        assert isinstance(r[0]["preco"], float)
        assert isinstance(r[0]["volume"], int)
        assert isinstance(r[0]["market_cap"], float)


# ═══════════════════════════════════════════════
# _check_tv
# ═══════════════════════════════════════════════
class TestCheckTv:
    def test_tv_disponivel_nao_raise(self, monkeypatch):
        monkeypatch.setattr(screener_provider, "TV_DISPONIVEL", True)
        _check_tv()  # não deve levantar

    def test_tv_indisponivel_raises(self, monkeypatch):
        monkeypatch.setattr(screener_provider, "TV_DISPONIVEL", False)
        with pytest.raises(RuntimeError, match="tradingview-screener"):
            _check_tv()


# ═══════════════════════════════════════════════
# maiores_altas / maiores_baixas / maiores_volumes
# ═══════════════════════════════════════════════
def _sample_df(n: int, change_sign: int = 1) -> pd.DataFrame:
    """Gera N linhas com change positivo (+1) ou negativo (-1)."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "name": f"BMFBOVESPA:TCK{i}",
                "close": 10 + i,
                "change": change_sign * (10 - i * 0.1),
                "change_abs": change_sign * 1.0,
                "volume": 1_000_000 * (i + 1),
                "market_cap_basic": 1e9,
                "description": f"Ticker {i}",
            }
        )
    return pd.DataFrame(rows)


class TestMaioresAltas:
    def test_respeita_limite(self, mock_scanner):
        mock_scanner(_sample_df(30, change_sign=1))
        r = maiores_altas(limite=10)
        assert len(r) == 10

    def test_limite_default_10(self, mock_scanner):
        mock_scanner(_sample_df(30, change_sign=1))
        r = maiores_altas()
        assert len(r) == 10

    def test_fewer_rows_nao_quebra(self, mock_scanner):
        mock_scanner(_sample_df(3, change_sign=1))
        r = maiores_altas(limite=10)
        assert len(r) == 3

    def test_cada_item_tem_campos(self, mock_scanner):
        mock_scanner(_sample_df(5, change_sign=1))
        r = maiores_altas(limite=5)
        for item in r:
            for campo in ("ticker", "preco", "variacao_pct", "variacao_abs", "volume", "market_cap", "nome"):
                assert campo in item

    def test_raise_se_tv_indisponivel(self, monkeypatch):
        monkeypatch.setattr(screener_provider, "TV_DISPONIVEL", False)
        with pytest.raises(RuntimeError, match="tradingview-screener"):
            maiores_altas()


class TestMaioresBaixas:
    def test_respeita_limite(self, mock_scanner):
        mock_scanner(_sample_df(30, change_sign=-1))
        r = maiores_baixas(limite=5)
        assert len(r) == 5

    def test_variacao_negativa(self, mock_scanner):
        mock_scanner(_sample_df(5, change_sign=-1))
        r = maiores_baixas(limite=5)
        for item in r:
            assert item["variacao_pct"] < 0

    def test_raise_se_tv_indisponivel(self, monkeypatch):
        monkeypatch.setattr(screener_provider, "TV_DISPONIVEL", False)
        with pytest.raises(RuntimeError):
            maiores_baixas()


class TestMaioresVolumes:
    def test_respeita_limite(self, mock_scanner):
        mock_scanner(_sample_df(20))
        r = maiores_volumes(limite=7)
        assert len(r) == 7

    def test_cada_item_tem_volume(self, mock_scanner):
        mock_scanner(_sample_df(5))
        r = maiores_volumes(limite=5)
        for item in r:
            assert isinstance(item["volume"], int)
            assert item["volume"] > 0

    def test_raise_se_tv_indisponivel(self, monkeypatch):
        monkeypatch.setattr(screener_provider, "TV_DISPONIVEL", False)
        with pytest.raises(RuntimeError):
            maiores_volumes()

    def test_filtra_fracionarios_no_fluxo_completo(self, mock_scanner):
        df = pd.concat(
            [
                _sample_df(3),
                _fake_rows(
                    [
                        {
                            "name": "BMFBOVESPA:TCK0F",
                            "close": 10,
                            "change": 1,
                            "change_abs": 0.1,
                            "volume": 999,
                            "market_cap_basic": 0,
                            "description": "frac",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        mock_scanner(df)
        r = maiores_volumes(limite=10)
        tickers = [x["ticker"] for x in r]
        assert "TCK0F" not in tickers
