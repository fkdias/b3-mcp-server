"""Script para gerar datasets offline de 12 meses para PETR4, VALE3, ITUB4."""

import json
import os
import time

import requests

TICKERS = ["PETR4", "VALE3", "ITUB4"]
OUTPUT_DIR = os.path.join("src", "b3_mcp", "core", "data", "samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})


def baixar_historico(ticker: str) -> list[dict]:
    """Baixa 12 meses de dados diários do Yahoo Finance."""
    yahoo_ticker = f"{ticker}.SA"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1y&interval=1d&includePrePost=false"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    candles = []
    for i, ts in enumerate(timestamps):
        o = quote["open"][i]
        h = quote["high"][i]
        low = quote["low"][i]
        c = quote["close"][i]
        v = quote["volume"][i]
        if o is None or h is None or low is None or c is None:
            continue
        candles.append(
            {
                "data": time.strftime("%Y-%m-%d", time.gmtime(ts)),
                "abertura": round(o, 2),
                "maxima": round(h, 2),
                "minima": round(low, 2),
                "fechamento": round(c, 2),
                "volume": v or 0,
            }
        )
    return candles


def gerar_snapshot_ibov() -> dict:
    """Gera snapshot do IBOVESPA."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?range=5d&interval=1d&includePrePost=false"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    meta = data["chart"]["result"][0]["meta"]

    return {
        "indice": "IBOVESPA",
        "valor": round(meta.get("regularMarketPrice", 0), 2),
        "variacao": round(meta.get("regularMarketPrice", 0) - meta.get("chartPreviousClose", 0), 2),
        "data_geracao": time.strftime("%Y-%m-%d"),
    }


if __name__ == "__main__":
    for ticker in TICKERS:
        print(f"Baixando {ticker}...")
        try:
            candles = baixar_historico(ticker)
            arquivo = os.path.join(OUTPUT_DIR, f"{ticker.lower()}_diario.json")
            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(candles, f, ensure_ascii=False, indent=2)
            print(f"  -> {len(candles)} candles salvos em {arquivo}")
        except Exception as e:
            print(f"  ERRO: {e}")
        time.sleep(1)

    print("Gerando snapshot IBOV...")
    try:
        snapshot = gerar_snapshot_ibov()
        arquivo = os.path.join(OUTPUT_DIR, "ibov_snapshot.json")
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"  -> Salvo em {arquivo}")
    except Exception as e:
        print(f"  ERRO: {e}")

    print("Datasets gerados com sucesso!")
