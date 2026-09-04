"""Serviço do indicador Hi-Lo Activator para B3."""

import json
import os
from typing import Any

from ..data.b3_sectors import get_setor
from ..utils.formatting import formatar_brl, formatar_percentual, formatar_volume, ticker_limpo
from .chart_service import gerar_grafico_hilo
from .indicators_calc import bollinger_bands, calc_hilo_activator, rsi, sma
from .yahoo_finance import obter_historico

# Dados offline. Os testes redirecionam para uma cópia congelada via B3_SAMPLES_DIR
# (o pipeline diário sobrescreve o diretório de produção — ver tests/fixtures/README.md).
SAMPLES_DIR = os.environ.get("B3_SAMPLES_DIR") or os.path.join(os.path.dirname(__file__), "..", "data", "samples")


def _carregar_offline(ticker: str) -> list[dict] | None:
    """Tenta carregar dados offline para o ticker."""
    nome = ticker_limpo(ticker).lower()
    caminho = os.path.join(SAMPLES_DIR, f"{nome}_diario.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return None


def _listar_offline_disponiveis() -> list[str]:
    """Lista tickers disponíveis offline."""
    disponiveis = []
    if os.path.exists(SAMPLES_DIR):
        for f in os.listdir(SAMPLES_DIR):
            if f.endswith("_diario.json"):
                disponiveis.append(f.replace("_diario.json", "").upper())
    return sorted(disponiveis)


def _calcular_suporte_resistencia(candles: list[dict], janela: int = 20) -> dict:
    """Calcula suporte e resistência recentes."""
    recentes = candles[-janela:]
    maximas = [c["maxima"] for c in recentes if c["maxima"] > 0]
    minimas = [c["minima"] for c in recentes if c["minima"] > 0]

    resistencia = max(maximas) if maximas else 0
    suporte = min(minimas) if minimas else 0

    # Máxima e mínima dos últimos 5 dias (filtrar zeros)
    ultimos_5 = candles[-5:]
    maximas_5d = [c["maxima"] for c in ultimos_5 if c["maxima"] > 0]
    minimas_5d = [c["minima"] for c in ultimos_5 if c["minima"] > 0]
    max_5d = max(maximas_5d) if maximas_5d else resistencia
    min_5d = min(minimas_5d) if minimas_5d else suporte

    return {
        "suporte_20d": round(suporte, 2),
        "resistencia_20d": round(resistencia, 2),
        "maxima_5d": round(max_5d, 2),
        "minima_5d": round(min_5d, 2),
    }


def _calcular_volatilidade(fechamentos: list[float], janela: int = 20) -> dict:
    """Calcula volatilidade e ATR simplificado."""
    if len(fechamentos) < janela:
        return {"volatilidade_20d": None}

    recentes = fechamentos[-janela:]
    media = sum(recentes) / len(recentes)
    variancia = sum((x - media) ** 2 for x in recentes) / len(recentes)
    dp = variancia**0.5
    volatilidade_pct = (dp / media) * 100

    return {
        "volatilidade_20d": round(volatilidade_pct, 2),
        "desvio_padrao": round(dp, 2),
    }


def _calcular_performance_trade(sinais_hist: list[dict]) -> dict | None:
    """Calcula performance do último trade fechado no modelo always-in-market.

    `sinais_hist` vem em ordem reversa (mais recente primeiro). O último trade
    fechado é o par formado pelos 2 sinais mais recentes — pode ser:
    - COMPRA → VENDA (fechou LONG, reverte pra SHORT)
    - VENDA → COMPRA (fechou SHORT, reverte pra LONG)

    Retorna `direcao` indicando qual foi o tipo do trade que acabou de fechar.
    """
    if len(sinais_hist) < 2:
        return None

    mais_recente = sinais_hist[0]
    anterior = sinais_hist[1]

    # Par VENDA (atual) + COMPRA (anterior) → fechou um LONG
    if mais_recente["sinal"] == "VENDA" and anterior["sinal"] == "COMPRA":
        direcao = "LONG"
        entrada = anterior["preco"]
        saida = mais_recente["preco"]
        lucro = saida - entrada
    # Par COMPRA (atual) + VENDA (anterior) → fechou um SHORT
    elif mais_recente["sinal"] == "COMPRA" and anterior["sinal"] == "VENDA":
        direcao = "SHORT"
        entrada = anterior["preco"]
        saida = mais_recente["preco"]
        lucro = entrada - saida
    else:
        return None

    lucro_pct = (lucro / entrada) * 100 if entrada else 0
    return {
        "direcao": direcao,
        "entrada": anterior["data"],
        "entrada_preco": formatar_brl(entrada),
        "saida": mais_recente["data"],
        "saida_preco": formatar_brl(saida),
        "resultado": formatar_brl(lucro),
        "resultado_pct": formatar_percentual(lucro_pct),
        "dias": None,
    }


def _avaliar_volume(candles: list[dict]) -> dict:
    """Avalia volume atual vs média."""
    volumes = [c["volume"] for c in candles if c["volume"] > 0]
    if len(volumes) < 21:
        return {"volume_atual": 0, "volume_medio_20d": 0, "volume_relativo": "N/A"}

    vol_atual = volumes[-1]
    vol_medio = sum(volumes[-21:-1]) / 20

    if vol_medio > 0:
        ratio = vol_atual / vol_medio
        if ratio >= 2.0:
            classificacao = "MUITO ACIMA da média"
        elif ratio >= 1.3:
            classificacao = "ACIMA da média"
        elif ratio >= 0.7:
            classificacao = "NORMAL"
        elif ratio >= 0.4:
            classificacao = "ABAIXO da média"
        else:
            classificacao = "MUITO ABAIXO da média"
    else:
        ratio = 0
        classificacao = "N/A"

    return {
        "volume_atual": vol_atual,
        "volume_atual_fmt": formatar_volume(vol_atual),
        "volume_medio_20d": int(vol_medio),
        "volume_medio_fmt": formatar_volume(vol_medio),
        "volume_relativo": round(ratio, 2),
        "volume_classificacao": classificacao,
    }


def _formatar_trades_com_acumulado(trades: list[dict]) -> list[dict]:
    """Formata trades (LONG/SHORT) adicionando acumulado composto progressivo."""
    resultado = []
    equity = 100

    for t in trades:
        equity *= 1 + t["resultado_pct"] / 100
        direcao = t.get("direcao", "LONG")
        motivo = t.get("motivo_saida", "REVERSAO")
        # Texto da saída: descreve o que fechou o trade
        if motivo == "REVERSAO":
            sinal_oposto = "VENDA" if direcao == "LONG" else "COMPRA"
            saida_por = f"Sinal {sinal_oposto} do Hi-Lo (reversao)"
        elif motivo == "FIM_PERIODO":
            saida_por = "Fim do periodo (posicao residual)"
        else:
            saida_por = motivo
        resultado.append(
            {
                "direcao": direcao,
                "entrada": f"{t['entrada_data']} @ {formatar_brl(t['entrada_preco'])}",
                "saida": f"{t['saida_data']} @ {formatar_brl(t['saida_preco'])}",
                "resultado": formatar_percentual(t["resultado_pct"]),
                "acumulado": formatar_percentual(equity - 100),
                "dias": t["dias"],
                "dd_trade": formatar_percentual(-t["max_drawdown_trade"]),
                "tipo": t["tipo"],  # WIN ou LOSS
                "saida_por": saida_por,
            }
        )

    return resultado


def _calcular_metricas_risco(candles: list[dict], hilo_data: dict) -> dict:
    """
    Calcula métricas de risco completas do Hi-Lo Activator com modelo
    **always-in-market** (long/short reversal):

    - COMPRA → LONG (ou reverte SHORT→LONG)
    - VENDA  → SHORT (ou reverte LONG→SHORT)
    - Fim do período fecha posição residual com motivo FIM_PERIODO
    - Cada trade tem `direcao ∈ {LONG, SHORT}` e `tipo ∈ {WIN, LOSS}`
    - Drawdown/runup intra-trade calculado via curva de P&L genérica
      (funciona uniforme pra long e short)

    Retorna: win rate, payout médio, profit factor, max drawdown da equity,
    sequências de wins/losses, histórico completo dos trades.
    """
    fechamentos = [c["fechamento"] for c in candles]
    datas = [c["data"] for c in candles]
    sinais_list = hilo_data["sinais"]

    def _fechar_trade(pos: dict, idx_saida: int, motivo: str) -> dict:
        entrada_preco = pos["entrada_preco"]
        saida_preco = fechamentos[idx_saida]
        if pos["direcao"] == "LONG":
            lucro = saida_preco - entrada_preco
        else:  # SHORT
            lucro = entrada_preco - saida_preco
        lucro_pct = (lucro / entrada_preco) * 100
        dias = idx_saida - pos["entrada_idx"]

        # Curva de P&L intra-trade em % (uniforme long/short)
        precos_trade = fechamentos[pos["entrada_idx"] : idx_saida + 1]
        if pos["direcao"] == "LONG":
            pnl_curve = [(p - entrada_preco) / entrada_preco * 100 for p in precos_trade]
        else:
            pnl_curve = [(entrada_preco - p) / entrada_preco * 100 for p in precos_trade]

        peak_pnl = 0.0
        max_dd_trade = 0.0
        max_runup_trade = 0.0
        for pnl in pnl_curve:
            if pnl > peak_pnl:
                peak_pnl = pnl
            dd = peak_pnl - pnl
            if dd > max_dd_trade:
                max_dd_trade = dd
            if pnl > max_runup_trade:
                max_runup_trade = pnl

        return {
            "direcao": pos["direcao"],
            "entrada_data": pos["entrada_data"],
            "saida_data": datas[idx_saida],
            "entrada_preco": round(entrada_preco, 2),
            "saida_preco": round(saida_preco, 2),
            "resultado_rs": round(lucro, 2),
            "resultado_pct": round(lucro_pct, 2),
            "dias": dias,
            "max_drawdown_trade": round(max_dd_trade, 2),
            "max_runup_trade": round(max_runup_trade, 2),
            "motivo_saida": motivo,
            "tipo": "WIN" if lucro > 0 else "LOSS",
        }

    # Reconstruir trades com always-in-market reversal
    trades: list[dict] = []
    posicao: dict | None = None

    for i in range(len(candles)):
        sinal = sinais_list[i]
        if sinal == "COMPRA":
            if posicao is not None and posicao["direcao"] == "SHORT":
                trades.append(_fechar_trade(posicao, i, "REVERSAO"))
            posicao = {
                "direcao": "LONG",
                "entrada_idx": i,
                "entrada_preco": fechamentos[i],
                "entrada_data": datas[i],
            }
        elif sinal == "VENDA":
            if posicao is not None and posicao["direcao"] == "LONG":
                trades.append(_fechar_trade(posicao, i, "REVERSAO"))
            posicao = {
                "direcao": "SHORT",
                "entrada_idx": i,
                "entrada_preco": fechamentos[i],
                "entrada_data": datas[i],
            }

    # Fecha posição residual no último candle
    if posicao is not None:
        trades.append(_fechar_trade(posicao, len(candles) - 1, "FIM_PERIODO"))

    if not trades:
        return {
            "total_trades": 0,
            "win_rate": "N/A",
            "payout_medio": "N/A",
            "profit_factor": "N/A",
            "max_drawdown": "N/A",
            "trades": [],
        }

    # Métricas gerais
    wins = [t for t in trades if t["resultado_pct"] > 0]
    losses = [t for t in trades if t["resultado_pct"] <= 0]
    win_rate = len(wins) / len(trades) * 100

    # Payouts
    payout_medio = sum(t["resultado_pct"] for t in trades) / len(trades)
    payout_wins = sum(t["resultado_pct"] for t in wins) / len(wins) if wins else 0
    payout_losses = sum(t["resultado_pct"] for t in losses) / len(losses) if losses else 0

    # Profit factor
    ganho_total = sum(t["resultado_pct"] for t in wins) if wins else 0
    perda_total = abs(sum(t["resultado_pct"] for t in losses)) if losses else 0
    profit_factor = round(ganho_total / perda_total, 2) if perda_total > 0 else float("inf")

    # Max drawdown da equity curve
    equity = 100  # base 100
    peak_equity = 100
    max_dd_total = 0
    equity_curve = [100]
    for t in trades:
        equity *= 1 + t["resultado_pct"] / 100
        equity_curve.append(round(equity, 2))
        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd_total:
            max_dd_total = dd

    # Maior sequência de wins e losses
    max_wins_seq = 0
    max_losses_seq = 0
    current_wins = 0
    current_losses = 0
    for t in trades:
        if t["tipo"] == "WIN":
            current_wins += 1
            current_losses = 0
            max_wins_seq = max(max_wins_seq, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_losses_seq = max(max_losses_seq, current_losses)

    # Dias médio por trade
    dias_medio = sum(t["dias"] for t in trades) / len(trades)

    # Expectativa matemática (edge)
    expectativa = (win_rate / 100 * payout_wins) + ((1 - win_rate / 100) * payout_losses)

    return {
        "total_trades": len(trades),
        "win_rate": formatar_percentual(win_rate),
        "wins": len(wins),
        "losses": len(losses),
        "payout_medio": formatar_percentual(payout_medio),
        "payout_medio_wins": formatar_percentual(payout_wins),
        "payout_medio_losses": formatar_percentual(payout_losses),
        "profit_factor": profit_factor,
        "max_drawdown": formatar_percentual(-max_dd_total),
        "expectativa": formatar_percentual(expectativa),
        "dias_medio_trade": round(dias_medio, 1),
        "maior_win": formatar_percentual(max(t["resultado_pct"] for t in trades)),
        "maior_loss": formatar_percentual(min(t["resultado_pct"] for t in trades)),
        "max_wins_consecutivos": max_wins_seq,
        "max_losses_consecutivos": max_losses_seq,
        "retorno_acumulado": formatar_percentual(equity_curve[-1] - 100),
        "equity_final": round(equity_curve[-1], 2),
        "equity_curve": equity_curve,
        "trades": _formatar_trades_com_acumulado(trades),
    }


def _gerar_cenarios(
    ticker: str,
    tendencia: str,
    preco: float,
    activator: float,
    suporte: float,
    resistencia: float,
    rsi_val: float | None,
    volatilidade: float | None,
) -> dict:
    """Gera cenários de alta, baixa e neutro com alvos."""
    dist_suporte = abs(preco - suporte)
    dist_resistencia = abs(resistencia - preco)

    if tendencia == "ALTA":
        alvo_1 = round(preco + dist_resistencia * 0.5, 2)
        alvo_2 = round(resistencia, 2)
        alvo_3 = round(resistencia * 1.03, 2)
        stop = round(activator * 0.98, 2)
        risco = abs(preco - stop)
        retorno_1 = abs(alvo_1 - preco)
        rr_1 = round(retorno_1 / risco, 2) if risco > 0 else 0

        cenario_base = {
            "direcao": "COMPRADO / manter posição",
            "alvo_1": {"preco": formatar_brl(alvo_1), "descricao": "Alvo parcial (50% do caminho à resistência)"},
            "alvo_2": {"preco": formatar_brl(alvo_2), "descricao": "Resistência de 20 dias"},
            "alvo_3": {"preco": formatar_brl(alvo_3), "descricao": "Rompimento da resistência (+3%)"},
            "stop_loss": {"preco": formatar_brl(stop), "descricao": "2% abaixo do activator"},
            "risco_retorno": f"1:{rr_1}",
        }
        cenario_reverso = {
            "gatilho": f"Fechamento abaixo de {formatar_brl(activator)} (activator)",
            "acao": "VENDER / sair da posição",
            "proximo_suporte": formatar_brl(suporte),
        }
    elif tendencia == "BAIXA":
        alvo_1 = round(preco - dist_suporte * 0.5, 2)
        alvo_2 = round(suporte, 2)
        stop = round(activator * 1.02, 2)
        risco = abs(stop - preco)
        retorno_1 = abs(preco - alvo_1)
        rr_1 = round(retorno_1 / risco, 2) if risco > 0 else 0

        cenario_base = {
            "direcao": "FORA / aguardar sinal de COMPRA",
            "proximo_suporte": {"preco": formatar_brl(suporte), "descricao": "Suporte de 20 dias"},
            "zona_compra": {
                "preco": f"{formatar_brl(suporte)} - {formatar_brl(round(suporte * 1.02, 2))}",
                "descricao": "Região de suporte com margem de 2%",
            },
            "observacao": "Aguardar Hi-Lo virar COMPRA antes de entrar",
        }
        cenario_reverso = {
            "gatilho": f"Fechamento acima de {formatar_brl(activator)} (activator)",
            "acao": "COMPRAR / iniciar posição",
            "proximo_alvo": formatar_brl(resistencia),
        }
    else:
        cenario_base = {"direcao": "INDEFINIDO / aguardar definição de tendência"}
        cenario_reverso = {"gatilho": "Aguardar rompimento do activator"}

    return {
        "cenario_base": cenario_base,
        "cenario_reversao": cenario_reverso,
    }


def analisar_hilo(
    ticker: str,
    periodo: int = 13,
    offline: bool = False,
    gerar_grafico: bool = True,
) -> dict[str, Any]:
    """
    Analisa um ativo com o Hi-Lo Activator — entrega completa.

    Args:
        ticker: Código do ativo (ex: PETR4)
        periodo: Período do Hi-Lo Activator (default: 10)
        offline: Usar dados offline (dataset de exemplo)

    Returns:
        Análise completa com tendência, sinais, volume, cenários e alvos.
    """
    ticker_clean = ticker_limpo(ticker)

    # Obter dados
    if offline:
        candles = _carregar_offline(ticker_clean)
        if candles is None:
            disponiveis = _listar_offline_disponiveis()
            raise ValueError(
                f"Dados offline não disponíveis para {ticker_clean}. "
                f"Disponíveis ({len(disponiveis)}): {', '.join(disponiveis)}"
            )
    else:
        candles = obter_historico(ticker_clean, periodo="1y")

    if len(candles) < periodo + 5:
        raise ValueError(f"Dados insuficientes para {ticker_clean} (mínimo: {periodo + 5} candles)")

    # Extrair séries
    maximas = [c["maxima"] for c in candles]
    minimas = [c["minima"] for c in candles]
    fechamentos = [c["fechamento"] for c in candles]
    datas = [c["data"] for c in candles]

    # ─── Hi-Lo Activator ───
    hilo = calc_hilo_activator(maximas, minimas, fechamentos, periodo)

    # ─── Indicadores complementares ───
    rsi_vals = rsi(fechamentos, 14)
    sma_9 = sma(fechamentos, 9)
    sma_21 = sma(fechamentos, 21)
    bb = bollinger_bands(fechamentos)

    # ─── Último candle ───
    ultimo_idx = len(candles) - 1
    preco_atual = fechamentos[ultimo_idx]
    activator_atual = hilo["activator"][ultimo_idx]
    tendencia_atual = hilo["tendencia"][ultimo_idx]

    # ─── Últimos sinais (até 10) ───
    ultimos_sinais = []
    for i in range(len(candles) - 1, -1, -1):
        if hilo["sinais"][i] is not None:
            ultimos_sinais.append(
                {
                    "data": datas[i],
                    "sinal": hilo["sinais"][i],
                    "preco": fechamentos[i],
                    "preco_formatado": formatar_brl(fechamentos[i]),
                }
            )
            if len(ultimos_sinais) >= 10:
                break

    # ─── Distância preço vs activator ───
    distancia = preco_atual - activator_atual if activator_atual else 0
    distancia_pct = (distancia / activator_atual * 100) if activator_atual else 0

    # ─── RSI ───
    rsi_atual = rsi_vals[ultimo_idx] if ultimo_idx < len(rsi_vals) and rsi_vals[ultimo_idx] is not None else None
    if rsi_atual:
        if rsi_atual >= 70:
            rsi_zona = "SOBRECOMPRA"
        elif rsi_atual >= 60:
            rsi_zona = "FORTE"
        elif rsi_atual >= 40:
            rsi_zona = "NEUTRO"
        elif rsi_atual >= 30:
            rsi_zona = "FRACO"
        else:
            rsi_zona = "SOBREVENDA"
    else:
        rsi_zona = "N/A"

    # ─── Dias na tendência ───
    dias_tendencia = 0
    for i in range(ultimo_idx, -1, -1):
        if hilo["tendencia"][i] == tendencia_atual:
            dias_tendencia += 1
        else:
            break

    # ─── Variação no período da tendência ───
    inicio_tendencia_idx = ultimo_idx - dias_tendencia + 1
    preco_inicio_tendencia = fechamentos[inicio_tendencia_idx] if inicio_tendencia_idx >= 0 else preco_atual
    variacao_tendencia = (
        ((preco_atual - preco_inicio_tendencia) / preco_inicio_tendencia * 100) if preco_inicio_tendencia else 0
    )

    # ─── Suporte e Resistência ───
    sr = _calcular_suporte_resistencia(candles)

    # ─── Volume ───
    volume = _avaliar_volume(candles)

    # ─── Volatilidade ───
    volat = _calcular_volatilidade(fechamentos)

    # ─── Bollinger position ───
    bb_sup = bb["superior"][ultimo_idx]
    bb_inf = bb["inferior"][ultimo_idx]
    if bb_sup and bb_inf and bb_sup != bb_inf:
        bb_posicao = round((preco_atual - bb_inf) / (bb_sup - bb_inf) * 100, 1)
    else:
        bb_posicao = None

    # ─── SMA trend ───
    sma9_val = sma_9[ultimo_idx]
    sma21_val = sma_21[ultimo_idx]
    if sma9_val and sma21_val:
        if sma9_val > sma21_val:
            sma_status = "ALTA (SMA9 > SMA21)"
        else:
            sma_status = "BAIXA (SMA9 < SMA21)"
    else:
        sma_status = "N/A"

    # ─── Cenários e alvos ───
    cenarios = _gerar_cenarios(
        ticker_clean,
        tendencia_atual,
        preco_atual,
        activator_atual,
        sr["suporte_20d"],
        sr["resistencia_20d"],
        rsi_atual,
        volat.get("volatilidade_20d"),
    )

    # ─── Métricas de risco ───
    metricas_risco = _calcular_metricas_risco(candles, hilo)

    # ─── Setor ───
    setor = get_setor(ticker_clean)

    # ─── Resumo enriquecido ───
    if tendencia_atual == "ALTA":
        resumo = (
            f"{ticker_clean} em TENDENCIA DE ALTA pelo Hi-Lo Activator (periodo {periodo}). "
            f"Preco {formatar_brl(preco_atual)} esta {formatar_percentual(distancia_pct)} acima do activator ({formatar_brl(activator_atual)}). "
            f"Tendencia de alta ha {dias_tendencia} pregoes com variacao de {formatar_percentual(variacao_tendencia)} no periodo. "
            f"RSI em {round(rsi_atual, 1) if rsi_atual else 'N/A'} ({rsi_zona}). "
            f"Volume {volume['volume_classificacao'].lower()}. "
            f"Manter posicao enquanto preco ficar acima do activator. "
            f"Stop sugerido: {formatar_brl(activator_atual * 0.98)}."
        )
    elif tendencia_atual == "BAIXA":
        resumo = (
            f"{ticker_clean} em TENDENCIA DE BAIXA pelo Hi-Lo Activator (periodo {periodo}). "
            f"Preco {formatar_brl(preco_atual)} esta {formatar_percentual(abs(distancia_pct))} abaixo do activator ({formatar_brl(activator_atual)}). "
            f"Tendencia de baixa ha {dias_tendencia} pregoes com variacao de {formatar_percentual(variacao_tendencia)} no periodo. "
            f"RSI em {round(rsi_atual, 1) if rsi_atual else 'N/A'} ({rsi_zona}). "
            f"Volume {volume['volume_classificacao'].lower()}. "
            f"Aguardar sinal de COMPRA (fechamento acima do activator) antes de entrar. "
            f"Suporte proximo: {formatar_brl(sr['suporte_20d'])}."
        )
    else:
        resumo = f"{ticker_clean}: tendencia indefinida pelo Hi-Lo Activator."

    result = {
        "ticker": ticker_clean,
        "setor": setor,
        "data_analise": datas[ultimo_idx],
        # ─── Hi-Lo Activator ───
        "hilo": {
            "periodo": periodo,
            "tendencia": tendencia_atual,
            "activator": round(activator_atual, 2) if activator_atual else None,
            "activator_formatado": formatar_brl(activator_atual) if activator_atual else "N/A",
            "high_ma": round(hilo["high_ma"][ultimo_idx], 2) if hilo["high_ma"][ultimo_idx] else None,
            "low_ma": round(hilo["low_ma"][ultimo_idx], 2) if hilo["low_ma"][ultimo_idx] else None,
            "dias_na_tendencia": dias_tendencia,
            "variacao_na_tendencia": formatar_percentual(variacao_tendencia),
        },
        # ─── Preço ───
        "preco": {
            "atual": preco_atual,
            "formatado": formatar_brl(preco_atual),
            "distancia_activator": formatar_percentual(distancia_pct),
            "posicao_bollinger": f"{bb_posicao}%" if bb_posicao is not None else "N/A",
            "bollinger_superior": formatar_brl(bb_sup) if bb_sup else "N/A",
            "bollinger_inferior": formatar_brl(bb_inf) if bb_inf else "N/A",
        },
        # ─── Indicadores ───
        "indicadores": {
            "rsi_14": round(rsi_atual, 2) if rsi_atual else None,
            "rsi_zona": rsi_zona,
            "sma_9": round(sma9_val, 2) if sma9_val else None,
            "sma_21": round(sma21_val, 2) if sma21_val else None,
            "sma_status": sma_status,
        },
        # ─── Volume ───
        "volume": volume,
        # ─── Suporte e Resistência ───
        "suporte_resistencia": sr,
        # ─── Volatilidade ───
        "volatilidade": volat,
        # ─── Cenários e operação ───
        "cenarios": cenarios,
        # ─── Métricas de risco ───
        "metricas_risco": metricas_risco,
        # ─── Histórico de sinais ───
        "ultimo_sinal": ultimos_sinais[0] if ultimos_sinais else None,
        "historico_sinais": ultimos_sinais,
        # ─── Resumo ───
        "resumo": resumo,
        "total_candles": len(candles),
        # ─── Gráfico ───
        "grafico": None,
    }

    # ─── Gerar gráfico PNG (só quando solicitado) ───
    if gerar_grafico:
        try:
            grafico_path = gerar_grafico_hilo(candles, hilo, ticker_clean, result)
            result["grafico"] = grafico_path
        except Exception:
            pass

    return result
