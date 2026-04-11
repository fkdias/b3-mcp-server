"""Testes de `yahoo_finance.py`.

Estratégia: mockar `_SESSION.get` via monkeypatch pra isolar do HTTP real.
Cobre:
- `_extrair_ohlcv` (pura — filtragem de candles com None)
- `_buscar_yahoo` com cache hit/miss e resposta inválida
- `obter_cotacao`, `obter_historico`, `obter_cotacao_indice` (wrappers)
"""

from __future__ import annotations

import time
from typing import Any

import pytest
import requests

from b3_mcp.core.services import yahoo_finance
from b3_mcp.core.services.yahoo_finance import (
    _buscar_yahoo,
    _extrair_ohlcv,
    obter_cotacao,
    obter_cotacao_indice,
    obter_historico,
)


# ═══════════════════════════════════════════════
# Fixtures / helpers
# ═══════════════════════════════════════════════
def _fake_chart_response(
    preco: float = 35.50,
    preco_anterior: float = 35.00,
    currency: str = "BRL",
    exchange: str = "SAO",
    n_candles: int = 3,
    incluir_none: bool = False,
) -> dict[str, Any]:
    """Monta um payload idêntico ao retornado por /v8/finance/chart."""
    base_ts = 1_700_000_000  # arbitrário, timezone-agnostic pro teste
    timestamps = [base_ts + i * 86_400 for i in range(n_candles)]

    opens = [preco - 0.5 + i * 0.1 for i in range(n_candles)]
    highs = [preco + 0.3 + i * 0.1 for i in range(n_candles)]
    lows = [preco - 0.7 + i * 0.1 for i in range(n_candles)]
    closes = [preco + i * 0.1 for i in range(n_candles)]
    volumes = [1_000_000 * (i + 1) for i in range(n_candles)]

    if incluir_none and n_candles >= 2:
        # Insere um candle com close None — deve ser filtrado
        opens[1] = None
        closes[1] = None

    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": preco,
                        "chartPreviousClose": preco_anterior,
                        "currency": currency,
                        "exchangeName": exchange,
                        "regularMarketTime": base_ts + n_candles * 86_400,
                    },
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "volume": volumes,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _limpar_cache():
    """Cache em memória é global — zerar antes e depois de cada teste."""
    yahoo_finance._CACHE.clear()
    yield
    yahoo_finance._CACHE.clear()


@pytest.fixture
def mock_session(monkeypatch):
    """Substitui `_SESSION.get` por uma função controlada pelo teste."""
    calls = []

    def _factory(payload: dict, status_code: int = 200):
        def fake_get(url, timeout=15):
            calls.append(url)
            return _FakeResponse(payload, status_code=status_code)

        monkeypatch.setattr(yahoo_finance._SESSION, "get", fake_get)
        return calls

    return _factory


# ═══════════════════════════════════════════════
# _extrair_ohlcv (puro)
# ═══════════════════════════════════════════════
class TestExtrairOhlcv:
    def test_candles_completos(self):
        data = _fake_chart_response(n_candles=5)
        candles = _extrair_ohlcv(data)
        assert len(candles) == 5
        for c in candles:
            assert set(c.keys()) == {"data", "abertura", "maxima", "minima", "fechamento", "volume"}

    def test_filtra_candles_com_none(self):
        data = _fake_chart_response(n_candles=3, incluir_none=True)
        candles = _extrair_ohlcv(data)
        # O do meio tem open/close None → deve ser removido
        assert len(candles) == 2

    def test_valores_arredondados_2_casas(self):
        data = _fake_chart_response(preco=35.5555555, n_candles=1)
        candles = _extrair_ohlcv(data)
        c = candles[0]
        # Cada campo numérico arredondado pra 2 casas
        for campo in ("abertura", "maxima", "minima", "fechamento"):
            # Float com no máximo 2 casas decimais
            assert round(c[campo], 2) == c[campo]

    def test_volume_none_vira_zero(self):
        data = _fake_chart_response(n_candles=1)
        data["chart"]["result"][0]["indicators"]["quote"][0]["volume"][0] = None
        candles = _extrair_ohlcv(data)
        assert candles[0]["volume"] == 0

    def test_formato_data_yyyy_mm_dd(self):
        data = _fake_chart_response(n_candles=1)
        candles = _extrair_ohlcv(data)
        # Formato tem que bater com strftime %Y-%m-%d (10 caracteres, 2 hífens)
        assert len(candles[0]["data"]) == 10
        assert candles[0]["data"].count("-") == 2


# ═══════════════════════════════════════════════
# _buscar_yahoo (cache + HTTP)
# ═══════════════════════════════════════════════
class TestBuscarYahoo:
    def test_primeira_chamada_faz_request(self, mock_session):
        payload = _fake_chart_response()
        calls = mock_session(payload)

        data = _buscar_yahoo("PETR4.SA", periodo="1y", intervalo="1d")

        assert len(calls) == 1
        assert "PETR4.SA" in calls[0]
        assert "range=1y" in calls[0]
        assert "interval=1d" in calls[0]
        assert data == payload

    def test_segunda_chamada_usa_cache(self, mock_session):
        payload = _fake_chart_response()
        calls = mock_session(payload)

        _buscar_yahoo("PETR4.SA", periodo="1y")
        _buscar_yahoo("PETR4.SA", periodo="1y")

        # Só 1 chamada HTTP (a segunda veio do cache)
        assert len(calls) == 1

    def test_cache_key_inclui_periodo_e_intervalo(self, mock_session):
        payload = _fake_chart_response()
        calls = mock_session(payload)

        _buscar_yahoo("PETR4.SA", periodo="1y", intervalo="1d")
        _buscar_yahoo("PETR4.SA", periodo="5d", intervalo="1d")

        # Chaves de cache diferentes → 2 chamadas distintas
        assert len(calls) == 2

    def test_cache_expirado_refaz_request(self, mock_session, monkeypatch):
        payload = _fake_chart_response()
        calls = mock_session(payload)

        # Primeira chamada popula o cache com timestamp atual
        _buscar_yahoo("PETR4.SA", periodo="1y")
        assert len(calls) == 1

        # Força o cache a parecer velho (TTL + 1)
        chave = "PETR4.SA:1y:1d"
        ts_old, dados = yahoo_finance._CACHE[chave]
        yahoo_finance._CACHE[chave] = (ts_old - (yahoo_finance._CACHE_TTL + 1), dados)

        _buscar_yahoo("PETR4.SA", periodo="1y")
        # Deve ter disparado nova request
        assert len(calls) == 2

    def test_resposta_sem_result_raises(self, mock_session):
        # Payload válido em forma mas com chart.result=[]
        mock_session({"chart": {"result": [], "error": None}})
        with pytest.raises(ValueError, match="Sem dados"):
            _buscar_yahoo("XXXX9.SA")

    def test_http_error_propaga(self, mock_session):
        mock_session({"chart": {"result": []}}, status_code=500)
        with pytest.raises(requests.HTTPError):
            _buscar_yahoo("PETR4.SA")


# ═══════════════════════════════════════════════
# obter_cotacao
# ═══════════════════════════════════════════════
class TestObterCotacao:
    def test_retorna_schema_esperado(self, mock_session):
        mock_session(_fake_chart_response(preco=35.50, preco_anterior=35.00))
        r = obter_cotacao("PETR4")

        for chave in (
            "ticker",
            "preco",
            "preco_formatado",
            "variacao",
            "variacao_pct",
            "variacao_formatada",
            "moeda",
            "exchange",
            "horario",
        ):
            assert chave in r

    def test_calculo_variacao_positiva(self, mock_session):
        mock_session(_fake_chart_response(preco=35.50, preco_anterior=35.00))
        r = obter_cotacao("PETR4")
        assert r["preco"] == 35.50
        assert r["variacao"] == 0.50
        assert round(r["variacao_pct"], 2) == round(0.50 / 35.00 * 100, 2)

    def test_calculo_variacao_negativa(self, mock_session):
        mock_session(_fake_chart_response(preco=34.00, preco_anterior=35.00))
        r = obter_cotacao("PETR4")
        assert r["variacao"] == -1.00
        assert r["variacao_pct"] < 0

    def test_preco_anterior_zero_nao_quebra(self, mock_session):
        mock_session(_fake_chart_response(preco=10.0, preco_anterior=0))
        r = obter_cotacao("XPTO4")
        assert r["variacao"] == 0
        assert r["variacao_pct"] == 0

    def test_ticker_limpo_aplicado(self, mock_session):
        mock_session(_fake_chart_response())
        r = obter_cotacao("petr4.sa")
        assert r["ticker"] == "PETR4"

    def test_usa_cache_em_chamadas_subsequentes(self, mock_session):
        calls = mock_session(_fake_chart_response())
        obter_cotacao("PETR4")
        obter_cotacao("PETR4")
        assert len(calls) == 1


# ═══════════════════════════════════════════════
# obter_historico
# ═══════════════════════════════════════════════
class TestObterHistorico:
    def test_retorna_lista_de_candles(self, mock_session):
        mock_session(_fake_chart_response(n_candles=5))
        candles = obter_historico("PETR4", periodo="1mo")
        assert isinstance(candles, list)
        assert len(candles) == 5
        assert "fechamento" in candles[0]

    def test_periodo_propagado_na_url(self, mock_session):
        calls = mock_session(_fake_chart_response())
        obter_historico("PETR4", periodo="3y")
        assert any("range=3y" in c for c in calls)

    def test_default_periodo_1y(self, mock_session):
        calls = mock_session(_fake_chart_response())
        obter_historico("PETR4")
        assert any("range=1y" in c for c in calls)


# ═══════════════════════════════════════════════
# obter_cotacao_indice
# ═══════════════════════════════════════════════
class TestObterCotacaoIndice:
    def test_retorna_campos_minimos(self, mock_session):
        mock_session(_fake_chart_response(preco=130_000, preco_anterior=128_000))
        r = obter_cotacao_indice("^BVSP")
        for chave in ("simbolo", "preco", "variacao", "variacao_pct"):
            assert chave in r

    def test_simbolo_passa_raw(self, mock_session):
        calls = mock_session(_fake_chart_response())
        obter_cotacao_indice("^BVSP")
        # Sem ticker_para_yahoo — deve passar o símbolo como veio
        assert any("^BVSP" in c or "%5EBVSP" in c for c in calls)

    def test_variacao_calculada(self, mock_session):
        mock_session(_fake_chart_response(preco=130_000, preco_anterior=128_000))
        r = obter_cotacao_indice("^BVSP")
        assert r["variacao"] == 2000
        assert round(r["variacao_pct"], 2) == round(2000 / 128_000 * 100, 2)

    def test_anterior_zero_nao_quebra(self, mock_session):
        mock_session(_fake_chart_response(preco=130_000, preco_anterior=0))
        r = obter_cotacao_indice("^BVSP")
        assert r["variacao"] == 0
        assert r["variacao_pct"] == 0
