"""Gera datasets offline de 12 meses para todos os ativos solicitados."""

import json
import os
import time
import requests

TICKERS = {
    "BBDC4": "Bradesco",
    "BEEF3": "Minerva",
    "BPAC11": "BTG Pactual",
    "BRAP4": "Bradespar",
    "BRAV3": "Brava Energia",
    "BRKM5": "Braskem",
    "CMIN3": "CSN Mineração",
    "COGN3": "Cogna",
    "CSAN3": "Cosan",
    "CSNA3": "CSN",
    "CYRE3": "Cyrela",
    # EMBR3 e MRFG3 removidos: Yahoo Finance retorna 404 persistente pra esses
    # tickers desde sempre (não são servidos via API v8/finance/chart).
    "HAPV3": "Hapvida",
    "ITUB4": "Itaú Unibanco",
    "LREN3": "Lojas Renner",
    "MGLU3": "Magazine Luiza",
    "MRVE3": "MRV Engenharia",
    "PETR4": "Petrobras",
    "PRIO3": "Prio",
    "RDOR3": "Rede D'Or",
    "RENT3": "Localiza",
    "SANB11": "Santander Brasil",
    "SAPR11": "Sanepar",
    "SUZB3": "Suzano",
    "USIM5": "Usiminas",
    "VALE3": "Vale",
    "WEGE3": "WEG",
}

OUTPUT_DIR = os.path.join("src", "b3_mcp", "core", "data", "samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def baixar_historico(ticker: str) -> list[dict]:
    yahoo_ticker = f"{ticker}.SA"
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}"
        f"?range=3y&interval=1d&includePrePost=false"
    )
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i], quote["volume"][i]
        if o is None or h is None or l is None or c is None:
            continue
        candles.append({
            "data": time.strftime("%Y-%m-%d", time.gmtime(ts)),
            "abertura": round(o, 2),
            "maxima": round(h, 2),
            "minima": round(l, 2),
            "fechamento": round(c, 2),
            "volume": v or 0,
        })
    return candles


if __name__ == "__main__":
    sucesso = 0
    erros = []
    for ticker, nome in sorted(TICKERS.items()):
        arquivo = os.path.join(OUTPUT_DIR, f"{ticker.lower()}_diario.json")
        if os.path.exists(arquivo):
            with open(arquivo, "r", encoding="utf-8") as f:
                existente = json.load(f)
            print(f"  [OK] {ticker} ({nome}) - ja existe ({len(existente)} candles)")
            sucesso += 1
            continue
        print(f"Baixando {ticker} ({nome})...", end=" ")
        try:
            candles = baixar_historico(ticker)
            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(candles, f, ensure_ascii=False, indent=2)
            print(f"{len(candles)} candles salvos")
            sucesso += 1
        except Exception as e:
            print(f"ERRO: {e}")
            erros.append(ticker)
        time.sleep(1.5)

    print(f"\nResultado: {sucesso}/{len(TICKERS)} ativos | Erros: {erros if erros else 'nenhum'}")
