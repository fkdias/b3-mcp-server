"""Serviços específicos B3: setorial, índices, screener, trade plan, fibonacci."""

import os
from typing import Any

from ..data.b3_indices import INDICES, get_constituintes
from ..data.b3_sectors import SETORES, TODOS_ATIVOS, get_ativos_setor, get_setor
from ..utils.formatting import formatar_brl, formatar_percentual, ticker_limpo
from .hilo_service import _carregar_offline, analisar_hilo
from .indicators_calc import calc_hilo_activator
from .yahoo_finance import obter_historico

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "samples")


def _tem_offline(ticker: str) -> bool:
    nome = ticker_limpo(ticker).lower()
    return os.path.exists(os.path.join(SAMPLES_DIR, f"{nome}_diario.json"))


# ═══════════════════════════════════════════
# 1. Visão Setorial
# ═══════════════════════════════════════════
def visao_setorial(offline: bool = False) -> dict[str, Any]:
    """Scanner de todos os setores da B3 com tendência Hi-Lo e momentum."""
    resultado = {}

    for setor, ativos in SETORES.items():
        setor_data = {"ativos_alta": 0, "ativos_baixa": 0, "ativos": [], "total": 0}
        ativos_analisados = []

        for ticker in ativos:
            if offline and not _tem_offline(ticker):
                continue
            try:
                analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
                tendencia = analise.get("hilo", {}).get("tendencia", "N/A")
                if tendencia == "ALTA":
                    setor_data["ativos_alta"] += 1
                elif tendencia == "BAIXA":
                    setor_data["ativos_baixa"] += 1
                ativos_analisados.append(
                    {
                        "ticker": ticker,
                        "tendencia": tendencia,
                        "preco": analise["preco"]["formatado"],
                        "var_tendencia": analise["hilo"].get("variacao_na_tendencia", "N/A"),
                        "dias": analise["hilo"].get("dias_na_tendencia", 0),
                    }
                )
            except Exception:
                continue

        setor_data["total"] = len(ativos_analisados)
        if setor_data["total"] > 0:
            setor_data["pct_alta"] = round(setor_data["ativos_alta"] / setor_data["total"] * 100)
        else:
            setor_data["pct_alta"] = 0
        setor_data["ativos"] = sorted(ativos_analisados, key=lambda x: x.get("dias", 0), reverse=True)
        setor_data["momentum"] = (
            "FORTE" if setor_data["pct_alta"] >= 70 else "MODERADO" if setor_data["pct_alta"] >= 40 else "FRACO"
        )
        resultado[setor] = setor_data

    # Ordenar setores por % em alta
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda x: x[1].get("pct_alta", 0), reverse=True))
    return resultado_ordenado


# ═══════════════════════════════════════════
# 2. Scanner por Setor
# ═══════════════════════════════════════════
def scanner_setor(setor: str, offline: bool = False) -> dict[str, Any]:
    """Análise detalhada de todos os ativos de um setor."""
    ativos = get_ativos_setor(setor)
    if not ativos:
        raise ValueError(f"Setor '{setor}' não encontrado. Disponíveis: {', '.join(SETORES.keys())}")

    resultados = []
    for ticker in ativos:
        if offline and not _tem_offline(ticker):
            continue
        try:
            analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
            mr = analise.get("metricas_risco", {})
            resultados.append(
                {
                    "ticker": ticker,
                    "tendencia": analise["hilo"]["tendencia"],
                    "preco": analise["preco"]["formatado"],
                    "activator": analise["hilo"]["activator_formatado"],
                    "dias_tendencia": analise["hilo"]["dias_na_tendencia"],
                    "rsi": analise["indicadores"].get("rsi_14"),
                    "win_rate": mr.get("win_rate", "N/A"),
                    "retorno_12m": mr.get("retorno_acumulado", "N/A"),
                    "profit_factor": mr.get("profit_factor", "N/A"),
                }
            )
        except Exception:
            continue

    return {
        "setor": setor,
        "total_ativos": len(resultados),
        "ativos": sorted(resultados, key=lambda x: x.get("dias_tendencia", 0), reverse=True),
    }


# ═══════════════════════════════════════════
# 3. Análise de Índice
# ═══════════════════════════════════════════
def analise_indice(indice: str, offline: bool = False) -> dict[str, Any]:
    """Análise Hi-Lo dos constituintes de um índice da B3."""
    constituintes = get_constituintes(indice)
    if not constituintes:
        raise ValueError(f"Índice '{indice}' não encontrado. Disponíveis: {', '.join(INDICES.keys())}")

    resultados = []
    alta_count = 0
    baixa_count = 0

    for ticker in constituintes:
        if offline and not _tem_offline(ticker):
            continue
        try:
            analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
            t = analise["hilo"]["tendencia"]
            if t == "ALTA":
                alta_count += 1
            elif t == "BAIXA":
                baixa_count += 1
            resultados.append(
                {
                    "ticker": ticker,
                    "setor": get_setor(ticker),
                    "tendencia": t,
                    "preco": analise["preco"]["formatado"],
                    "dias_tendencia": analise["hilo"]["dias_na_tendencia"],
                    "rsi": analise["indicadores"].get("rsi_14"),
                }
            )
        except Exception:
            continue

    total = len(resultados)
    return {
        "indice": indice,
        "total_analisados": total,
        "em_alta": alta_count,
        "em_baixa": baixa_count,
        "pct_alta": formatar_percentual(alta_count / total * 100) if total > 0 else "N/A",
        "breadth": "BULL"
        if alta_count / total > 0.6
        else "BEAR"
        if alta_count / total < 0.4
        else "NEUTRO"
        if total > 0
        else "N/A",
        "ativos": sorted(resultados, key=lambda x: x.get("dias_tendencia", 0), reverse=True),
    }


# ═══════════════════════════════════════════
# 4. Screener B3
# ═══════════════════════════════════════════
def screener_b3(
    filtro_tendencia: str | None = None,
    filtro_setor: str | None = None,
    min_profit_factor: float = 0,
    ordenar_por: str = "retorno",
    offline: bool = False,
) -> dict[str, Any]:
    """Screener de ações da B3 com filtros."""
    resultados = []

    for ticker in TODOS_ATIVOS:
        if offline and not _tem_offline(ticker):
            continue
        if filtro_setor:
            setor = get_setor(ticker)
            if setor and filtro_setor.lower() not in setor.lower():
                continue

        try:
            analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
            t = analise["hilo"]["tendencia"]

            if filtro_tendencia and t != filtro_tendencia.upper():
                continue

            mr = analise.get("metricas_risco", {})
            pf = mr.get("profit_factor", 0)
            if isinstance(pf, str):
                pf = 0
            if pf < min_profit_factor:
                continue

            resultados.append(
                {
                    "ticker": ticker,
                    "setor": get_setor(ticker),
                    "tendencia": t,
                    "preco": analise["preco"]["formatado"],
                    "dias_tendencia": analise["hilo"]["dias_na_tendencia"],
                    "rsi": analise["indicadores"].get("rsi_14"),
                    "win_rate": mr.get("win_rate", "N/A"),
                    "retorno_12m": mr.get("retorno_acumulado", "N/A"),
                    "profit_factor": mr.get("profit_factor", "N/A"),
                    "max_drawdown": mr.get("max_drawdown", "N/A"),
                    "_retorno_num": mr.get("equity_final", 100) - 100,
                    "_pf_num": pf,
                }
            )
        except Exception:
            continue

    # Ordenar
    if ordenar_por == "profit_factor":
        resultados.sort(key=lambda x: x.get("_pf_num", 0), reverse=True)
    elif ordenar_por == "dias":
        resultados.sort(key=lambda x: x.get("dias_tendencia", 0), reverse=True)
    else:
        resultados.sort(key=lambda x: x.get("_retorno_num", 0), reverse=True)

    # Limpar campos internos
    for r in resultados:
        r.pop("_retorno_num", None)
        r.pop("_pf_num", None)

    return {
        "filtros": {
            "tendencia": filtro_tendencia,
            "setor": filtro_setor,
            "min_profit_factor": min_profit_factor,
            "ordenar_por": ordenar_por,
        },
        "total": len(resultados),
        "resultados": resultados,
    }


# ═══════════════════════════════════════════
# 5. Plano de Trade
# ═══════════════════════════════════════════
def plano_trade(ticker: str, offline: bool = False) -> dict[str, Any]:
    """Gera plano de trade completo para um ativo."""
    analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
    hilo = analise.get("hilo", {})
    sr = analise.get("suporte_resistencia", {})
    mr = analise.get("metricas_risco", {})
    preco = analise["preco"]["atual"]
    activator = hilo.get("activator", preco)

    if hilo["tendencia"] == "ALTA":
        entrada = preco
        stop = round(activator * 0.98, 2)
        alvo1 = round(sr.get("resistencia_20d", preco * 1.05), 2)
        alvo2 = round(alvo1 * 1.03, 2)
        risco = abs(entrada - stop)
        retorno1 = abs(alvo1 - entrada)
        rr1 = round(retorno1 / risco, 2) if risco > 0 else 0
        retorno2 = abs(alvo2 - entrada)
        rr2 = round(retorno2 / risco, 2) if risco > 0 else 0
        tipo = "COMPRA"
        motivo = "Hi-Lo Activator em tendência de ALTA"
    elif hilo["tendencia"] == "BAIXA":
        entrada = None
        stop = round(activator * 1.02, 2)
        alvo1 = round(sr.get("suporte_20d", preco * 0.95), 2)
        alvo2 = round(alvo1 * 0.97, 2)
        risco = 0
        rr1 = 0
        rr2 = 0
        tipo = "AGUARDAR"
        motivo = "Hi-Lo Activator em tendência de BAIXA — aguardar reversão"
    else:
        tipo = "NEUTRO"
        motivo = "Tendência indefinida"
        entrada = stop = alvo1 = alvo2 = risco = rr1 = rr2 = None

    return {
        "ticker": ticker_limpo(ticker),
        "tipo_operacao": tipo,
        "motivo": motivo,
        "tendencia": hilo["tendencia"],
        "preco_atual": formatar_brl(preco),
        "entrada_sugerida": formatar_brl(entrada) if entrada else "Aguardar sinal de COMPRA",
        "stop_loss": formatar_brl(stop) if stop else "N/A",
        "alvo_1": formatar_brl(alvo1) if alvo1 else "N/A",
        "alvo_2": formatar_brl(alvo2) if alvo2 else "N/A",
        "risco_retorno_alvo1": f"1:{rr1}" if rr1 else "N/A",
        "risco_retorno_alvo2": f"1:{rr2}" if rr2 else "N/A",
        "activator": hilo.get("activator_formatado", "N/A"),
        "rsi": analise["indicadores"].get("rsi_14"),
        "volume": analise.get("volume", {}).get("volume_classificacao", "N/A"),
        "historico_hilo": {
            "win_rate": mr.get("win_rate", "N/A"),
            "profit_factor": mr.get("profit_factor", "N/A"),
            "max_drawdown": mr.get("max_drawdown", "N/A"),
            "payout_medio": mr.get("payout_medio", "N/A"),
        },
        "disclaimer": "Este plano é educacional. Não constitui recomendação de investimento.",
    }


# ═══════════════════════════════════════════
# 6. Fibonacci
# ═══════════════════════════════════════════
def fibonacci_levels(ticker: str, offline: bool = False) -> dict[str, Any]:
    """Calcula níveis de Fibonacci (retração e extensão) para um ativo."""
    ticker_clean = ticker_limpo(ticker)

    if offline:
        candles = _carregar_offline(ticker_clean)
        if candles is None:
            raise ValueError(f"Dados offline não disponíveis para {ticker_clean}")
    else:
        candles = obter_historico(ticker_clean, periodo="1y")

    fechamentos = [c["fechamento"] for c in candles]
    maximas = [c["maxima"] for c in candles]
    minimas = [c["minima"] for c in candles]

    max_preco = max(maximas)
    min_preco = min(m for m in minimas if m > 0)
    diff = max_preco - min_preco
    preco_atual = fechamentos[-1]

    # Determinar direção
    hilo = calc_hilo_activator(maximas, minimas, fechamentos, 10)
    tendencia = hilo["tendencia"][-1]

    # Retração (de cima pra baixo)
    retracao = {
        "0.0% (Topo)": round(max_preco, 2),
        "23.6%": round(max_preco - diff * 0.236, 2),
        "38.2%": round(max_preco - diff * 0.382, 2),
        "50.0%": round(max_preco - diff * 0.500, 2),
        "61.8%": round(max_preco - diff * 0.618, 2),
        "78.6%": round(max_preco - diff * 0.786, 2),
        "100.0% (Fundo)": round(min_preco, 2),
    }

    # Extensão (projeção acima do topo)
    extensao = {
        "127.2%": round(max_preco + diff * 0.272, 2),
        "161.8%": round(max_preco + diff * 0.618, 2),
        "200.0%": round(max_preco + diff * 1.000, 2),
        "261.8%": round(max_preco + diff * 1.618, 2),
    }

    # Posição atual em relação aos níveis
    posicao_fib = round((max_preco - preco_atual) / diff * 100, 1) if diff > 0 else 0

    # Níveis mais próximos
    todos_niveis = {**retracao}
    mais_proximo_acima = None
    mais_proximo_abaixo = None
    for nome, valor in sorted(todos_niveis.items(), key=lambda x: x[1]):
        if valor >= preco_atual and mais_proximo_acima is None:
            mais_proximo_acima = {"nivel": nome, "preco": formatar_brl(valor)}
        if valor <= preco_atual:
            mais_proximo_abaixo = {"nivel": nome, "preco": formatar_brl(valor)}

    return {
        "ticker": ticker_clean,
        "tendencia_hilo": tendencia,
        "preco_atual": formatar_brl(preco_atual),
        "topo_12m": formatar_brl(max_preco),
        "fundo_12m": formatar_brl(min_preco),
        "amplitude": formatar_brl(diff),
        "posicao_fibonacci": f"{posicao_fib}%",
        "retracao": {k: formatar_brl(v) for k, v in retracao.items()},
        "extensao": {k: formatar_brl(v) for k, v in extensao.items()},
        "suporte_fib_proximo": mais_proximo_abaixo,
        "resistencia_fib_proxima": mais_proximo_acima,
    }
