"""Serviço de dados via Yahoo Finance para ativos da B3."""

import json
import time
from typing import Any

import requests

from ..utils.formatting import ticker_para_yahoo, formatar_brl, formatar_percentual

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# Cache simples em memória (ticker -> (timestamp, dados))
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hora (suficiente para batch operations)


def _buscar_yahoo(ticker_yahoo: str, periodo: str = "1y", intervalo: str = "1d") -> dict:
    """Busca dados OHLCV do Yahoo Finance."""
    cache_key = f"{ticker_yahoo}:{periodo}:{intervalo}"
    agora = time.time()

    if cache_key in _CACHE:
        ts, dados = _CACHE[cache_key]
        if agora - ts < _CACHE_TTL:
            return dados

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_yahoo}"
        f"?range={periodo}&interval={intervalo}&includePrePost=false"
    )
    resp = _SESSION.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("chart", {}).get("result", [])
    if not result:
        raise ValueError(f"Sem dados para {ticker_yahoo}")

    _CACHE[cache_key] = (agora, data)
    return data


def _extrair_ohlcv(data: dict) -> list[dict]:
    """Extrai lista de candles OHLCV de resposta Yahoo."""
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    candles = []
    for i, ts in enumerate(timestamps):
        o = quote["open"][i]
        h = quote["high"][i]
        l = quote["low"][i]
        c = quote["close"][i]
        v = quote["volume"][i]
        if o is None or h is None or l is None or c is None:
            continue
        candles.append({
            "data": time.strftime("%Y-%m-%d", time.localtime(ts)),  # São Paulo time
            "abertura": round(o, 2),
            "maxima": round(h, 2),
            "minima": round(l, 2),
            "fechamento": round(c, 2),
            "volume": v or 0,
        })
    return candles


def obter_cotacao(ticker: str) -> dict[str, Any]:
    """Retorna cotação atual de um ativo da B3."""
    ticker_yahoo = ticker_para_yahoo(ticker)
    data = _buscar_yahoo(ticker_yahoo, periodo="5d", intervalo="1d")
    result = data["chart"]["result"][0]
    meta = result["meta"]

    preco = meta.get("regularMarketPrice", 0)
    preco_anterior = meta.get("chartPreviousClose", meta.get("previousClose", 0))
    variacao = preco - preco_anterior if preco_anterior else 0
    variacao_pct = (variacao / preco_anterior * 100) if preco_anterior else 0

    return {
        "ticker": ticker.upper().replace(".SA", ""),
        "preco": round(preco, 2),
        "preco_formatado": formatar_brl(preco),
        "variacao": round(variacao, 2),
        "variacao_pct": round(variacao_pct, 2),
        "variacao_formatada": formatar_percentual(variacao_pct),
        "moeda": meta.get("currency", "BRL"),
        "exchange": meta.get("exchangeName", "SAO"),
        "horario": meta.get("regularMarketTime", 0),
    }


def obter_historico(ticker: str, periodo: str = "1y") -> list[dict]:
    """Retorna histórico OHLCV diário de um ativo da B3."""
    ticker_yahoo = ticker_para_yahoo(ticker)
    data = _buscar_yahoo(ticker_yahoo, periodo=periodo, intervalo="1d")
    return _extrair_ohlcv(data)


def obter_cotacao_indice(simbolo_yahoo: str) -> dict[str, Any]:
    """Retorna cotação de um índice (^BVSP, USDBRL=X, etc)."""
    data = _buscar_yahoo(simbolo_yahoo, periodo="5d", intervalo="1d")
    result = data["chart"]["result"][0]
    meta = result["meta"]

    preco = meta.get("regularMarketPrice", 0)
    preco_anterior = meta.get("chartPreviousClose", meta.get("previousClose", 0))
    variacao = preco - preco_anterior if preco_anterior else 0
    variacao_pct = (variacao / preco_anterior * 100) if preco_anterior else 0

    return {
        "simbolo": simbolo_yahoo,
        "preco": round(preco, 2),
        "variacao": round(variacao, 2),
        "variacao_pct": round(variacao_pct, 2),
    }
