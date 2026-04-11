"""Atualiza os datasets offline baixando nova janela (3 anos) do Yahoo Finance.

Sobrescreve todos os JSONs em `src/b3_mcp/core/data/samples/`. Uso:

    python atualizar_datasets.py

Exit codes:
    0 — todos os tickers atualizados com sucesso
    1 — atualização parcial (alguns tickers falharam)
    2 — falha total (nenhum ticker atualizado)

Logs são acumulados em `relatorios/update_log_YYYY-MM-DD.txt` (modo append,
um arquivo por dia). O script é idempotente: pode ser rodado múltiplas vezes
sem efeitos colaterais além do log crescer.

Janela de dados: 3 anos (~750 candles), configurada em `gerar_datasets_v2.py`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

# Reaproveitamento total de gerar_datasets_v2.py: TICKERS dict, função
# baixar_historico (que já respeita o range=3y) e OUTPUT_DIR.
sys.path.insert(0, os.path.dirname(__file__))
from gerar_datasets_v2 import TICKERS, baixar_historico, OUTPUT_DIR  # noqa: E402

LOG_DIR = os.path.join(os.path.dirname(__file__), "relatorios")
os.makedirs(LOG_DIR, exist_ok=True)

# Rate limit entre requests (igual ao gerar_datasets_v2.py pra evitar ban).
SLEEP_BETWEEN_REQUESTS = 1.5


def _log(msg: str, fh) -> None:
    """Escreve no stdout e no arquivo de log, com flush imediato."""
    print(msg)
    fh.write(msg + "\n")
    fh.flush()


def main() -> int:
    log_path = os.path.join(
        LOG_DIR, f"update_log_{datetime.now():%Y-%m-%d}.txt"
    )

    with open(log_path, "a", encoding="utf-8") as fh:
        _log("=" * 60, fh)
        _log(f"Inicio: {datetime.now().isoformat(timespec='seconds')}", fh)
        _log(f"Total tickers: {len(TICKERS)}", fh)
        _log(f"Diretorio saida: {OUTPUT_DIR}", fh)
        _log("=" * 60, fh)

        sucesso = 0
        erros: list[tuple[str, str]] = []
        t0 = time.time()

        for ticker, nome in sorted(TICKERS.items()):
            arquivo = os.path.join(
                OUTPUT_DIR, f"{ticker.lower()}_diario.json"
            )
            try:
                candles = baixar_historico(ticker)
                if not candles:
                    raise ValueError("nenhum candle retornado")
                with open(arquivo, "w", encoding="utf-8") as f:
                    json.dump(candles, f, ensure_ascii=False, indent=2)
                ultima = candles[-1]["data"]
                primeira = candles[0]["data"]
                _log(
                    f"  [OK] {ticker} ({nome}): {len(candles)} candles "
                    f"[{primeira} -> {ultima}]",
                    fh,
                )
                sucesso += 1
            except Exception as e:
                _log(f"  [ERRO] {ticker} ({nome}): {e}", fh)
                erros.append((ticker, str(e)))
            time.sleep(SLEEP_BETWEEN_REQUESTS)

        duracao = time.time() - t0
        _log("=" * 60, fh)
        _log(
            f"Fim: {sucesso}/{len(TICKERS)} ok, {len(erros)} erros, "
            f"{duracao:.1f}s",
            fh,
        )
        if erros:
            _log("Tickers com erro:", fh)
            for t, e in erros:
                _log(f"  - {t}: {e}", fh)
        _log("=" * 60 + "\n", fh)

    if sucesso == len(TICKERS):
        return 0
    if sucesso > 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
