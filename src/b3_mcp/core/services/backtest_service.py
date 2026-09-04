"""Serviço de backtesting para estratégias na B3."""

import json
import os
from typing import Any

from ..utils.formatting import formatar_brl, formatar_percentual, ticker_limpo
from .indicators_calc import (
    bollinger_bands,
    calc_hilo_activator,
    ema,
    macd,
    rsi,
    sma,
)
from .yahoo_finance import obter_historico

# Dados offline. Os testes redirecionam para uma cópia congelada via B3_SAMPLES_DIR
# (o pipeline diário sobrescreve o diretório de produção — ver tests/fixtures/README.md).
SAMPLES_DIR = os.environ.get("B3_SAMPLES_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "data", "samples"
)

ESTRATEGIAS_DISPONIVEIS = [
    "hilo",
    "rsi",
    "sma_crossover",
    "ema_crossover",
    "macd",
    "bollinger",
    "todas",
]


def _carregar_dados(ticker: str, offline: bool) -> list[dict]:
    """Carrega dados de candles (online ou offline)."""
    nome = ticker_limpo(ticker).lower()
    if offline:
        caminho = os.path.join(SAMPLES_DIR, f"{nome}_diario.json")
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        raise ValueError(f"Dados offline não disponíveis para {ticker}")
    return obter_historico(ticker, periodo="1y")


def _run_hilo(candles: list[dict], periodo: int = 10) -> list[dict]:
    """Backtest Hi-Lo Activator — **always in market** long/short reversal.

    Semântica "ganhos explosivos" (método do usuário):
    - Hi-Lo COMPRA → abre LONG (ou reverte SHORT → LONG no mesmo candle)
    - Hi-Lo VENDA  → abre SHORT (ou reverte LONG → SHORT no mesmo candle)
    - Antes do 1º sinal: flat por necessidade física (sem direção conhecida)
    - No último candle, fecha posição residual com motivo FIM_PERIODO

    Cada trade tem campo `tipo ∈ {LONG, SHORT}` e P&L calculado conforme:
    - LONG:  lucro = saida - entrada
    - SHORT: lucro = entrada - saida

    Não modela custo de aluguel de BTC nem slippage.
    """
    maximas = [c["maxima"] for c in candles]
    minimas = [c["minima"] for c in candles]
    fechamentos = [c["fechamento"] for c in candles]

    hilo = calc_hilo_activator(maximas, minimas, fechamentos, periodo)
    trades = []
    posicao = None  # dict com tipo/entrada/data_entrada ou None

    def _fechar(pos: dict, preco_saida: float, data_saida: str, motivo: str) -> dict:
        if pos["tipo"] == "LONG":
            lucro = preco_saida - pos["entrada"]
        else:  # SHORT
            lucro = pos["entrada"] - preco_saida
        lucro_pct = (lucro / pos["entrada"]) * 100
        return {
            "tipo": pos["tipo"],
            "data_entrada": pos["data_entrada"],
            "data_saida": data_saida,
            "preco_entrada": pos["entrada"],
            "preco_saida": preco_saida,
            "lucro": round(lucro, 2),
            "lucro_pct": round(lucro_pct, 2),
            "motivo_saida": motivo,
        }

    for i in range(len(candles)):
        sinal = hilo["sinais"][i]
        if sinal == "COMPRA":
            # Fecha SHORT se aberto
            if posicao is not None and posicao["tipo"] == "SHORT":
                trades.append(_fechar(posicao, fechamentos[i], candles[i]["data"], "REVERSAO"))
            # Abre LONG (sempre — reversão ou entrada inicial)
            posicao = {"tipo": "LONG", "entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        elif sinal == "VENDA":
            # Fecha LONG se aberto
            if posicao is not None and posicao["tipo"] == "LONG":
                trades.append(_fechar(posicao, fechamentos[i], candles[i]["data"], "REVERSAO"))
            # Abre SHORT (sempre — reversão ou entrada inicial)
            posicao = {"tipo": "SHORT", "entrada": fechamentos[i], "data_entrada": candles[i]["data"]}

    # Fecha posição residual no último candle
    if posicao is not None:
        trades.append(_fechar(posicao, fechamentos[-1], candles[-1]["data"], "FIM_PERIODO"))

    return trades


def _run_rsi(candles: list[dict], periodo: int = 14, sobrevenda: float = 30, sobrecompra: float = 70) -> list[dict]:
    """Backtest RSI."""
    fechamentos = [c["fechamento"] for c in candles]
    rsi_vals = rsi(fechamentos, periodo)
    trades = []
    posicao = None

    for i in range(len(candles)):
        if rsi_vals[i] is None:
            continue
        if rsi_vals[i] < sobrevenda and posicao is None:
            posicao = {"entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        elif rsi_vals[i] > sobrecompra and posicao is not None:
            lucro = fechamentos[i] - posicao["entrada"]
            lucro_pct = (lucro / posicao["entrada"]) * 100
            trades.append(
                {
                    "data_entrada": posicao["data_entrada"],
                    "data_saida": candles[i]["data"],
                    "preco_entrada": posicao["entrada"],
                    "preco_saida": fechamentos[i],
                    "lucro": round(lucro, 2),
                    "lucro_pct": round(lucro_pct, 2),
                }
            )
            posicao = None

    return trades


def _run_sma_crossover(candles: list[dict], rapida: int = 9, lenta: int = 21) -> list[dict]:
    """Backtest SMA Crossover."""
    fechamentos = [c["fechamento"] for c in candles]
    sma_rapida = sma(fechamentos, rapida)
    sma_lenta = sma(fechamentos, lenta)
    trades = []
    posicao = None

    for i in range(1, len(candles)):
        if sma_rapida[i] is None or sma_lenta[i] is None:
            continue
        if sma_rapida[i - 1] is None or sma_lenta[i - 1] is None:
            continue

        # Golden cross
        if sma_rapida[i - 1] <= sma_lenta[i - 1] and sma_rapida[i] > sma_lenta[i] and posicao is None:
            posicao = {"entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        # Death cross
        elif sma_rapida[i - 1] >= sma_lenta[i - 1] and sma_rapida[i] < sma_lenta[i] and posicao is not None:
            lucro = fechamentos[i] - posicao["entrada"]
            lucro_pct = (lucro / posicao["entrada"]) * 100
            trades.append(
                {
                    "data_entrada": posicao["data_entrada"],
                    "data_saida": candles[i]["data"],
                    "preco_entrada": posicao["entrada"],
                    "preco_saida": fechamentos[i],
                    "lucro": round(lucro, 2),
                    "lucro_pct": round(lucro_pct, 2),
                }
            )
            posicao = None

    return trades


def _run_ema_crossover(candles: list[dict], rapida: int = 9, lenta: int = 21) -> list[dict]:
    """Backtest EMA Crossover."""
    fechamentos = [c["fechamento"] for c in candles]
    ema_rapida = ema(fechamentos, rapida)
    ema_lenta = ema(fechamentos, lenta)
    trades = []
    posicao = None

    for i in range(1, len(candles)):
        if ema_rapida[i] is None or ema_lenta[i] is None:
            continue
        if ema_rapida[i - 1] is None or ema_lenta[i - 1] is None:
            continue

        if ema_rapida[i - 1] <= ema_lenta[i - 1] and ema_rapida[i] > ema_lenta[i] and posicao is None:
            posicao = {"entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        elif ema_rapida[i - 1] >= ema_lenta[i - 1] and ema_rapida[i] < ema_lenta[i] and posicao is not None:
            lucro = fechamentos[i] - posicao["entrada"]
            lucro_pct = (lucro / posicao["entrada"]) * 100
            trades.append(
                {
                    "data_entrada": posicao["data_entrada"],
                    "data_saida": candles[i]["data"],
                    "preco_entrada": posicao["entrada"],
                    "preco_saida": fechamentos[i],
                    "lucro": round(lucro, 2),
                    "lucro_pct": round(lucro_pct, 2),
                }
            )
            posicao = None

    return trades


def _run_macd_strategy(candles: list[dict]) -> list[dict]:
    """Backtest MACD Crossover."""
    fechamentos = [c["fechamento"] for c in candles]
    macd_data = macd(fechamentos)
    hist = macd_data["histograma"]
    trades = []
    posicao = None

    for i in range(1, len(candles)):
        if hist[i] is None or hist[i - 1] is None:
            continue
        if hist[i - 1] <= 0 and hist[i] > 0 and posicao is None:
            posicao = {"entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        elif hist[i - 1] >= 0 and hist[i] < 0 and posicao is not None:
            lucro = fechamentos[i] - posicao["entrada"]
            lucro_pct = (lucro / posicao["entrada"]) * 100
            trades.append(
                {
                    "data_entrada": posicao["data_entrada"],
                    "data_saida": candles[i]["data"],
                    "preco_entrada": posicao["entrada"],
                    "preco_saida": fechamentos[i],
                    "lucro": round(lucro, 2),
                    "lucro_pct": round(lucro_pct, 2),
                }
            )
            posicao = None

    return trades


def _run_bollinger(candles: list[dict]) -> list[dict]:
    """Backtest Bollinger Bands."""
    fechamentos = [c["fechamento"] for c in candles]
    bb = bollinger_bands(fechamentos)
    trades = []
    posicao = None

    for i in range(len(candles)):
        if bb["inferior"][i] is None:
            continue
        if fechamentos[i] <= bb["inferior"][i] and posicao is None:
            posicao = {"entrada": fechamentos[i], "data_entrada": candles[i]["data"]}
        elif fechamentos[i] >= bb["superior"][i] and posicao is not None:
            lucro = fechamentos[i] - posicao["entrada"]
            lucro_pct = (lucro / posicao["entrada"]) * 100
            trades.append(
                {
                    "data_entrada": posicao["data_entrada"],
                    "data_saida": candles[i]["data"],
                    "preco_entrada": posicao["entrada"],
                    "preco_saida": fechamentos[i],
                    "lucro": round(lucro, 2),
                    "lucro_pct": round(lucro_pct, 2),
                }
            )
            posicao = None

    return trades


def _calcular_metricas(trades: list[dict], capital_inicial: float = 10000) -> dict[str, Any]:
    """Calcula métricas de performance do backtest."""
    if not trades:
        return {
            "total_trades": 0,
            "trades_positivos": 0,
            "trades_negativos": 0,
            "taxa_acerto": "0,00%",
            "lucro_total": "R$ 0,00",
            "lucro_total_pct": "0,00%",
            "maior_ganho": "R$ 0,00",
            "maior_perda": "R$ 0,00",
            "media_ganho": "R$ 0,00",
            "media_perda": "R$ 0,00",
            "profit_factor": 0,
            "max_drawdown": "0,00%",
        }

    positivos = [t for t in trades if t["lucro"] > 0]
    negativos = [t for t in trades if t["lucro"] <= 0]

    lucros = [t["lucro_pct"] for t in trades]
    lucro_total_pct = sum(lucros)

    ganhos_total = sum(t["lucro"] for t in positivos) if positivos else 0
    perdas_total = abs(sum(t["lucro"] for t in negativos)) if negativos else 0

    # Max drawdown composto (equity curve correta)
    equity = capital_inicial
    peak = capital_inicial
    max_dd = 0
    for t in trades:
        equity *= 1 + t["lucro_pct"] / 100
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": len(trades),
        "trades_positivos": len(positivos),
        "trades_negativos": len(negativos),
        "taxa_acerto": formatar_percentual(len(positivos) / len(trades) * 100 if trades else 0),
        "lucro_total": formatar_brl(sum(t["lucro"] for t in trades)),
        "lucro_total_pct": formatar_percentual(lucro_total_pct),
        "maior_ganho": formatar_brl(max(t["lucro"] for t in trades)),
        "maior_perda": formatar_brl(min(t["lucro"] for t in trades)),
        "media_ganho": formatar_brl(ganhos_total / len(positivos)) if positivos else "R$ 0,00",
        "media_perda": formatar_brl(-perdas_total / len(negativos)) if negativos else "R$ 0,00",
        "profit_factor": round(ganhos_total / perdas_total, 2) if perdas_total > 0 else float("inf"),
        "max_drawdown": formatar_percentual(-max_dd),
    }


ESTRATEGIA_RUNNERS = {
    "hilo": _run_hilo,
    "rsi": _run_rsi,
    "sma_crossover": _run_sma_crossover,
    "ema_crossover": _run_ema_crossover,
    "macd": _run_macd_strategy,
    "bollinger": _run_bollinger,
}


def executar_backtest(
    ticker: str,
    estrategia: str = "hilo",
    offline: bool = False,
) -> dict[str, Any]:
    """
    Executa backtest de uma estratégia em um ativo da B3.

    Estratégias: hilo, rsi, sma_crossover, ema_crossover, macd, bollinger, todas
    """
    ticker_clean = ticker_limpo(ticker)
    candles = _carregar_dados(ticker_clean, offline)

    if estrategia == "todas":
        resultados = {}
        for nome, runner in ESTRATEGIA_RUNNERS.items():
            trades = runner(candles)
            resultados[nome] = {
                "trades": trades[-5:],  # últimos 5 trades
                "metricas": _calcular_metricas(trades),
            }
        return {
            "ticker": ticker_clean,
            "periodo": f"{candles[0]['data']} a {candles[-1]['data']}",
            "total_candles": len(candles),
            "comparativo": resultados,
        }

    if estrategia not in ESTRATEGIA_RUNNERS:
        raise ValueError(f"Estratégia '{estrategia}' não encontrada. Disponíveis: {', '.join(ESTRATEGIAS_DISPONIVEIS)}")

    runner = ESTRATEGIA_RUNNERS[estrategia]
    trades = runner(candles)
    metricas = _calcular_metricas(trades)

    return {
        "ticker": ticker_clean,
        "estrategia": estrategia,
        "periodo": f"{candles[0]['data']} a {candles[-1]['data']}",
        "total_candles": len(candles),
        "metricas": metricas,
        "ultimos_trades": trades[-10:],
        "todos_trades": trades,
    }
