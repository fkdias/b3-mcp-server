"""Simulação de opções ATM (delta ~0.5) via Black-Scholes nos sinais do Hi-Lo."""

import math
from typing import Any

from ..utils.formatting import formatar_brl, formatar_percentual, ticker_limpo
from .hilo_service import _carregar_offline
from .indicators_calc import calc_hilo_activator
from .yahoo_finance import obter_historico


# ═══════════════════════════════════════════
# Black-Scholes
# ═══════════════════════════════════════════
def _norm_cdf(x: float) -> float:
    """CDF da distribuição normal padrão (aproximação)."""
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Preço de uma call europeia via Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Preço de uma put europeia via Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return max(K - S, 0)
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _calcular_volatilidade_historica(fechamentos: list[float], janela: int = 21) -> float:
    """Volatilidade anualizada (desvio padrão dos log-retornos)."""
    if len(fechamentos) < janela + 1:
        return 0.30  # fallback 30%
    retornos = []
    for i in range(1, len(fechamentos)):
        if fechamentos[i - 1] > 0 and fechamentos[i] > 0:
            retornos.append(math.log(fechamentos[i] / fechamentos[i - 1]))
    if not retornos:
        return 0.30
    recentes = retornos[-janela:]
    media = sum(recentes) / len(recentes)
    variancia = sum((r - media) ** 2 for r in recentes) / len(recentes)
    vol_diaria = math.sqrt(variancia)
    vol_anual = vol_diaria * math.sqrt(252)
    return vol_anual


# ═══════════════════════════════════════════
# Simulação de Opções nos Sinais Hi-Lo
# ═══════════════════════════════════════════
VENCIMENTO_DIAS = 21  # opções com ~1 mês para vencimento (ATM)
_SELIC_CACHE: dict[str, float] = {}


def _obter_selic() -> float:
    """Busca taxa Selic atual via API do Banco Central do Brasil. Fallback: 14.25%."""
    import time

    import requests

    cache_key = "selic"
    agora = time.time()
    if cache_key in _SELIC_CACHE and agora - _SELIC_CACHE.get("_ts", 0) < 86400:
        return _SELIC_CACHE[cache_key]

    try:
        # API BCB: série 432 = Selic Meta
        resp = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
            timeout=5,
        )
        if resp.status_code == 200:
            dados = resp.json()
            if dados:
                selic = float(dados[0]["valor"]) / 100  # ex: 14.25 -> 0.1425
                _SELIC_CACHE[cache_key] = selic
                _SELIC_CACHE["_ts"] = agora
                return selic
    except Exception:
        pass

    return 0.1425  # fallback: 14.25%


# Selic buscada dinamicamente via _obter_selic()


_SIZING_MODES_VALIDOS = (
    "agregado",
    "lote_fixo",
    "fracao_banca",
    "teto_absoluto",
    "fracao_capital",
)


def _validar_sizing(
    sizing_mode: str,
    sizing_valor: float,
    banca_inicial: float | None,
    lote_tamanho: int,
) -> None:
    """Valida os parâmetros de sizing. Levanta ValueError em inconsistências."""
    if sizing_mode not in _SIZING_MODES_VALIDOS:
        raise ValueError(f"sizing_mode inválido: {sizing_mode!r}. Modos válidos: {', '.join(_SIZING_MODES_VALIDOS)}")

    if lote_tamanho < 1:
        raise ValueError("lote_tamanho deve ser >= 1")

    if sizing_mode == "agregado":
        return  # nada mais a validar

    # Todos os modos não-agregados exigem banca_inicial > 0
    if banca_inicial is None or banca_inicial <= 0:
        raise ValueError("banca_inicial obrigatória quando sizing_mode != 'agregado'")

    if sizing_mode == "lote_fixo":
        if sizing_valor < 1:
            raise ValueError("sizing_valor (nº de lotes) deve ser >= 1 no modo 'lote_fixo'")
    elif sizing_mode in ("fracao_banca", "fracao_capital"):
        if not (0 < sizing_valor <= 1.0):
            raise ValueError(f"sizing_valor deve estar no intervalo (0, 1] no modo {sizing_mode!r}")
    elif sizing_mode == "teto_absoluto":
        if sizing_valor <= 0:
            raise ValueError("sizing_valor (teto em R$) deve ser > 0 no modo 'teto_absoluto'")


def _calcular_lotes(
    premio: float,
    sizing_mode: str,
    sizing_valor: float,
    banca_inicial: float,
    banca_atual: float,
    lote_tamanho: int,
) -> int:
    """
    Calcula quantos lotes comprar dado o sizing ativo.

    Retorna 0 quando o caixa disponível não comporta nem 1 lote — nesse caso
    o chamador deve fazer skip do sinal (quebrando o always-in-market).
    """
    if premio <= 0:
        return 0

    custo_por_lote = premio * lote_tamanho
    if custo_por_lote <= 0:
        return 0

    if sizing_mode == "lote_fixo":
        lotes_desejados = int(sizing_valor)
    elif sizing_mode == "fracao_banca":
        orcamento = max(0.0, banca_atual) * sizing_valor
        lotes_desejados = int(orcamento // custo_por_lote)
    elif sizing_mode == "teto_absoluto":
        lotes_desejados = int(sizing_valor // custo_por_lote)
    elif sizing_mode == "fracao_capital":
        teto = banca_inicial * sizing_valor
        lotes_desejados = int(teto // custo_por_lote)
    else:
        return 0

    if lotes_desejados <= 0:
        return 0

    # Caixa é o limite absoluto — nunca operar com banca negativa
    lotes_possiveis_caixa = int(max(0.0, banca_atual) // custo_por_lote)
    lotes = min(lotes_desejados, lotes_possiveis_caixa)
    return max(0, lotes)


def simular_opcoes_hilo(
    ticker: str,
    periodo_hilo: int = 10,
    vencimento_dias: int = VENCIMENTO_DIAS,
    offline: bool = False,
    banca_inicial: float | None = None,
    sizing_mode: str = "agregado",
    sizing_valor: float = 1.0,
    lote_tamanho: int = 100,
) -> dict[str, Any]:
    """
    Simula opções ATM **always-in-market** seguindo os sinais do Hi-Lo:

    - Hi-Lo COMPRA  → compra CALL ATM (long call, lucra com alta)
    - Hi-Lo VENDA   → compra PUT ATM (long put, lucra com baixa)
    - Sinal oposto  → fecha a opção atual e **abre imediatamente a do lado
      oposto** (reversão sem ficar em caixa)
    - Vencimento sem sinal oposto → fecha a opção atual e **rola pra uma
      nova opção do mesmo tipo** baseada na tendência vigente do Hi-Lo
      (`tendencia[i] == "ALTA"` → nova CALL; `"BAIXA"` → nova PUT)

    Nunca flat entre o 1º sinal e o fim do período — EXCETO quando o modo de
    sizing ativo não permite comprar nem 1 lote (skip por falta de caixa).

    Premissas:
    - Strike ATM = preço do ativo no momento do sinal/rollover (delta ~0.5)
    - Vencimento: 21 dias úteis (~1 mês)
    - Volatilidade: histórica anualizada (janela 21d)
    - Taxa livre de risco: Selic dinâmica via BCB
    - Saída: sinal oposto (reversão) OU vencimento (rollover) OU fim do período

    Parâmetros de sizing (novos):
        banca_inicial: Capital inicial em R$. Obrigatório para modos != 'agregado'.
        sizing_mode: Modelo de alocação por trade:
            - 'agregado' (default): comportamento legado, cada trade é independente
              (sem banca, sem equity curve). Ignora banca_inicial e sizing_valor.
              Retorno 100% idêntico ao contrato anterior (backward compatibility).
            - 'lote_fixo': compra int(sizing_valor) lotes por trade; skip se banca
              não cobrir.
            - 'fracao_banca': usa sizing_valor (0..1) × banca corrente como orçamento;
              lotes = int(orçamento // custo_por_lote). Dinâmico com o crescimento.
            - 'teto_absoluto': usa até sizing_valor R$ como orçamento por trade,
              independente da banca corrente (limitado pelo caixa disponível).
            - 'fracao_capital': teto = sizing_valor × banca_inicial (capital de
              referência FIXO). Equivalente ao teto_absoluto quando o valor é
              calculado a partir do capital inicial.
        sizing_valor: Parâmetro do sizing (nº de lotes, fração ou R$ conforme modo).
        lote_tamanho: Tamanho do lote padrão de opções (default 100).

    Comportamento de skip (apenas modos não-agregados):
        Quando nem 1 lote cabe na banca disponível, o sinal é pulado — não registra
        operação, não abre posição, incrementa `trades_pulados` e segue. Isso
        **quebra** o modelo always-in-market; a flag `always_in_market_quebrado`
        no retorno indica se houve skips.

    Returns:
        Dict com histórico de operações e resumo. Quando sizing_mode != 'agregado',
        o dict ganha a seção `sizing` com equity curve, pico, vale, max drawdown,
        lucro líquido, retorno % e contadores; cada entrada em `operacoes` também
        recebe `lotes`, `custo_total_rs`, `pnl_trade_rs` e `banca_pos_trade`.
    """
    _validar_sizing(sizing_mode, sizing_valor, banca_inicial, lote_tamanho)
    sizing_ativo = sizing_mode != "agregado"
    ticker_clean = ticker_limpo(ticker)

    if offline:
        candles = _carregar_offline(ticker_clean)
        if candles is None:
            raise ValueError(f"Dados offline não disponíveis para {ticker_clean}")
    else:
        candles = obter_historico(ticker_clean, periodo="1y")

    # Buscar Selic atualizada
    taxa_selic = _obter_selic()

    fechamentos = [c["fechamento"] for c in candles]
    maximas = [c["maxima"] for c in candles]
    minimas = [c["minima"] for c in candles]
    datas = [c["data"] for c in candles]

    hilo = calc_hilo_activator(maximas, minimas, fechamentos, periodo_hilo)
    sinais = hilo["sinais"]
    tendencia = hilo["tendencia"]
    T = vencimento_dias / 252  # fração do ano

    def _abrir_posicao(tipo: str, i: int, motivo_abertura: str) -> dict:
        S = fechamentos[i]
        K = S  # ATM
        sigma = _calcular_volatilidade_historica(fechamentos[: i + 1])
        if tipo == "CALL":
            premio = black_scholes_call(S, K, T, taxa_selic, sigma)
            sinal_hilo = "COMPRA"
        else:
            premio = black_scholes_put(S, K, T, taxa_selic, sigma)
            sinal_hilo = "VENDA"
        return {
            "tipo_opcao": tipo,
            "sinal_hilo": sinal_hilo,
            "strike": K,
            "premio_entrada": round(premio, 2),
            "preco_ativo_entrada": S,
            "sigma": round(sigma, 4),
            "data_entrada": datas[i],
            "idx_entrada": i,
            "vencimento_em": vencimento_dias,
            "motivo_abertura": motivo_abertura,
        }

    operacoes: list[dict] = []
    posicao: dict | None = None

    # ─── Estado do sizing (apenas quando ativo) ───
    banca_atual: float = float(banca_inicial) if sizing_ativo else 0.0
    banca_pico: float = banca_atual
    banca_vale: float = banca_atual
    max_dd_pct: float = 0.0
    equity_curve: list[tuple[str, float]] = []
    if sizing_ativo:
        equity_curve.append((datas[0], banca_atual))
    n_skips: int = 0
    total_lotes: int = 0
    always_in_market_quebrado: bool = False

    def _atualizar_metricas_banca(data_evento: str) -> None:
        """Atualiza pico, vale, max drawdown e equity curve após mudança na banca."""
        nonlocal banca_pico, banca_vale, max_dd_pct
        if banca_atual > banca_pico:
            banca_pico = banca_atual
        if banca_atual < banca_vale:
            banca_vale = banca_atual
        if banca_pico > 0:
            dd = (banca_pico - banca_atual) / banca_pico * 100
            if dd > max_dd_pct:
                max_dd_pct = dd
        equity_curve.append((data_evento, round(banca_atual, 2)))

    def _tentar_abrir(tipo: str, i: int, motivo: str) -> dict | None:
        """
        Prepara uma nova posição considerando o sizing. Retorna None se não
        couber nenhum lote (caso em que o sinal deve ser pulado).
        """
        nova = _abrir_posicao(tipo, i, motivo)
        if not sizing_ativo:
            nova["lotes"] = 1  # valor ignorado no retorno legado
            return nova
        lotes = _calcular_lotes(
            nova["premio_entrada"],
            sizing_mode,
            sizing_valor,
            float(banca_inicial),
            banca_atual,
            lote_tamanho,
        )
        if lotes <= 0:
            return None
        nova["lotes"] = lotes
        return nova

    def _aplicar_abertura(nova: dict) -> None:
        """Debita o custo da nova posição da banca (quando sizing ativo)."""
        nonlocal banca_atual, total_lotes
        if not sizing_ativo:
            return
        custo = nova["premio_entrada"] * lote_tamanho * nova["lotes"]
        banca_atual -= custo
        total_lotes += nova["lotes"]
        nova["custo_total_rs"] = round(custo, 2)

    def _aplicar_fechamento(op_registrada: dict, posicao_fechada: dict) -> None:
        """Credita pnl_trade na banca e anota campos extras na operacao."""
        nonlocal banca_atual
        if not sizing_ativo:
            return
        lotes = posicao_fechada.get("lotes", 0)
        pnl = op_registrada["resultado_opcao_rs"] * lote_tamanho * lotes
        # Prêmio de saída = custo + pnl → credita na banca
        custo = posicao_fechada.get(
            "custo_total_rs",
            posicao_fechada["premio_entrada"] * lote_tamanho * lotes,
        )
        valor_saida = custo + pnl
        banca_atual += valor_saida
        op_registrada["lotes"] = lotes
        op_registrada["custo_total_rs"] = round(custo, 2)
        op_registrada["pnl_trade_rs"] = round(pnl, 2)
        op_registrada["banca_pos_trade"] = round(banca_atual, 2)
        _atualizar_metricas_banca(op_registrada["data_saida"])

    for i in range(len(candles)):
        sinal = sinais[i]

        # Sinal do Hi-Lo: reverte a posição imediatamente
        if sinal == "COMPRA":
            if posicao is not None and posicao["tipo_opcao"] == "PUT":
                _fechar_posicao(operacoes, posicao, fechamentos[i], datas[i], i, "SINAL_OPOSTO", taxa_selic)
                _aplicar_fechamento(operacoes[-1], posicao)
                posicao = None
            if posicao is None:
                nova = _tentar_abrir("CALL", i, "SINAL_COMPRA")
                if nova is None:
                    n_skips += 1
                    always_in_market_quebrado = True
                else:
                    _aplicar_abertura(nova)
                    posicao = nova
            continue

        if sinal == "VENDA":
            if posicao is not None and posicao["tipo_opcao"] == "CALL":
                _fechar_posicao(operacoes, posicao, fechamentos[i], datas[i], i, "SINAL_OPOSTO", taxa_selic)
                _aplicar_fechamento(operacoes[-1], posicao)
                posicao = None
            if posicao is None:
                nova = _tentar_abrir("PUT", i, "SINAL_VENDA")
                if nova is None:
                    n_skips += 1
                    always_in_market_quebrado = True
                else:
                    _aplicar_abertura(nova)
                    posicao = nova
            continue

        # Sem sinal novo: checa vencimento pra decidir rollover
        if posicao is not None:
            dias_passados = i - posicao["idx_entrada"]
            if dias_passados >= vencimento_dias:
                # Fecha a opção vencida
                _fechar_posicao(operacoes, posicao, fechamentos[i], datas[i], i, "VENCIMENTO", taxa_selic)
                _aplicar_fechamento(operacoes[-1], posicao)
                posicao = None
                # Rola pra mesma direção da tendência vigente (always-in-market)
                tend = tendencia[i]
                tipo_roll: str | None = None
                if tend == "ALTA":
                    tipo_roll = "CALL"
                elif tend == "BAIXA":
                    tipo_roll = "PUT"
                if tipo_roll is not None:
                    nova = _tentar_abrir(tipo_roll, i, "ROLL_VENCIMENTO")
                    if nova is None:
                        n_skips += 1
                        always_in_market_quebrado = True
                    else:
                        _aplicar_abertura(nova)
                        posicao = nova
                # Se tendencia for None (impossível tão tarde no período), fica flat

    # Fechar posição aberta no último dia
    if posicao is not None:
        _fechar_posicao(operacoes, posicao, fechamentos[-1], datas[-1], len(candles) - 1, "FIM_PERIODO", taxa_selic)
        _aplicar_fechamento(operacoes[-1], posicao)

    # ─── Métricas ───
    if not operacoes:
        resultado_vazio: dict[str, Any] = {
            "ticker": ticker_clean,
            "total_operacoes": 0,
            "operacoes": [],
        }
        if sizing_ativo:
            resultado_vazio["always_in_market_quebrado"] = always_in_market_quebrado
            resultado_vazio["sizing"] = {
                "modo": sizing_mode,
                "valor": sizing_valor,
                "banca_inicial": float(banca_inicial),
                "banca_final": round(banca_atual, 2),
                "lucro_liquido": round(banca_atual - float(banca_inicial), 2),
                "retorno_pct": formatar_percentual((banca_atual / float(banca_inicial) - 1) * 100),
                "pico": round(banca_pico, 2),
                "vale": round(banca_vale, 2),
                "max_drawdown_pct": formatar_percentual(max_dd_pct),
                "trades_executados": 0,
                "trades_pulados": n_skips,
                "total_lotes": total_lotes,
                "lote_tamanho": lote_tamanho,
                "equity_curve": equity_curve,
            }
        return resultado_vazio

    calls = [op for op in operacoes if op["tipo_opcao"] == "CALL"]
    puts = [op for op in operacoes if op["tipo_opcao"] == "PUT"]

    lucro_total_opcoes = sum(op["resultado_opcao_rs"] for op in operacoes)
    lucro_total_acao = sum(op["resultado_acao_rs"] for op in operacoes)
    investido_opcoes = sum(op["premio_pago"] for op in operacoes)
    investido_acao = sum(op["preco_ativo_entrada"] for op in operacoes)

    wins_opcoes = [op for op in operacoes if op["resultado_opcao_rs"] > 0]

    # Quando sizing ativo, NÃO vazar o campo 'lotes' interno quando ele só
    # foi usado como marcador (modo agregado injeta lotes=1 pra reutilizar o
    # mesmo pipeline, mas o contrato legado proíbe esse campo no retorno).
    if not sizing_ativo:
        for op in operacoes:
            op.pop("lotes", None)
            op.pop("custo_total_rs", None)
            op.pop("pnl_trade_rs", None)
            op.pop("banca_pos_trade", None)

    resultado: dict[str, Any] = {
        "ticker": ticker_clean,
        "premissas": {
            "strike": "ATM (delta ~0.5)",
            "vencimento": f"{vencimento_dias} dias úteis",
            "taxa_selic": formatar_percentual(taxa_selic * 100) if taxa_selic else "N/A",
            "volatilidade": "Histórica 21d anualizada",
            "modelo": "Black-Scholes",
        },
        "resumo": {
            "total_operacoes": len(operacoes),
            "calls": len(calls),
            "puts": len(puts),
            "win_rate_opcoes": formatar_percentual(len(wins_opcoes) / len(operacoes) * 100),
            "investido_opcoes": formatar_brl(investido_opcoes),
            "lucro_opcoes": formatar_brl(lucro_total_opcoes),
            "retorno_opcoes": formatar_percentual(lucro_total_opcoes / investido_opcoes * 100)
            if investido_opcoes > 0
            else "N/A",
            "lucro_acao": formatar_brl(lucro_total_acao),
            "retorno_acao": formatar_percentual(lucro_total_acao / investido_acao * 100)
            if investido_acao > 0
            else "N/A",
            "alavancagem_media": round(investido_acao / investido_opcoes, 1) if investido_opcoes > 0 else "N/A",
        },
        "operacoes": operacoes,
        "disclaimer": (
            "SIMULACAO EDUCACIONAL — nao utiliza dados reais de opcoes da B3. "
            "Premios calculados via Black-Scholes com volatilidade historica. "
            "Resultados reais podem variar significativamente."
        ),
    }

    if sizing_ativo:
        banca_inicial_f = float(banca_inicial)
        resultado["always_in_market_quebrado"] = always_in_market_quebrado
        resultado["sizing"] = {
            "modo": sizing_mode,
            "valor": sizing_valor,
            "banca_inicial": banca_inicial_f,
            "banca_final": round(banca_atual, 2),
            "lucro_liquido": round(banca_atual - banca_inicial_f, 2),
            "retorno_pct": formatar_percentual((banca_atual / banca_inicial_f - 1) * 100),
            "pico": round(banca_pico, 2),
            "vale": round(banca_vale, 2),
            "max_drawdown_pct": formatar_percentual(max_dd_pct),
            "trades_executados": len(operacoes),
            "trades_pulados": n_skips,
            "total_lotes": total_lotes,
            "lote_tamanho": lote_tamanho,
            "equity_curve": equity_curve,
        }

    return resultado


def _fechar_posicao(
    operacoes: list,
    posicao: dict,
    preco_saida: float,
    data_saida: str,
    idx_saida: int,
    motivo: str,
    taxa_selic: float = 0.1425,
):
    """Fecha uma posição de opção e calcula resultados."""
    S = preco_saida
    K = posicao["strike"]
    dias_restantes = max(0, posicao["vencimento_em"] - (idx_saida - posicao["idx_entrada"]))
    T_restante = dias_restantes / 252
    sigma = posicao["sigma"]

    if posicao["tipo_opcao"] == "CALL":
        if T_restante > 0 and motivo != "VENCIMENTO":
            premio_saida = black_scholes_call(S, K, T_restante, taxa_selic, sigma)
        else:
            premio_saida = max(S - K, 0)
        resultado_acao = S - posicao["preco_ativo_entrada"]
    else:  # PUT
        if T_restante > 0 and motivo != "VENCIMENTO":
            premio_saida = black_scholes_put(S, K, T_restante, taxa_selic, sigma)
        else:
            premio_saida = max(K - S, 0)
        resultado_acao = posicao["preco_ativo_entrada"] - S

    resultado_opcao = premio_saida - posicao["premio_entrada"]
    retorno_opcao_pct = (resultado_opcao / posicao["premio_entrada"] * 100) if posicao["premio_entrada"] > 0 else 0

    operacoes.append(
        {
            "tipo_opcao": posicao["tipo_opcao"],
            "sinal_hilo": posicao["sinal_hilo"],
            "motivo_abertura": posicao.get("motivo_abertura", "SINAL_HILO"),
            "data_entrada": posicao["data_entrada"],
            "data_saida": data_saida,
            "dias": idx_saida - posicao["idx_entrada"],
            "motivo_saida": motivo,
            "strike": formatar_brl(K),
            "preco_ativo_entrada": posicao["preco_ativo_entrada"],
            "preco_ativo_saida": round(S, 2),
            "volatilidade": formatar_percentual(posicao["sigma"] * 100),
            "premio_pago": posicao["premio_entrada"],
            "premio_pago_fmt": formatar_brl(posicao["premio_entrada"]),
            "premio_saida": round(premio_saida, 2),
            "premio_saida_fmt": formatar_brl(premio_saida),
            "resultado_opcao_rs": round(resultado_opcao, 2),
            "resultado_opcao_fmt": formatar_brl(resultado_opcao),
            "resultado_opcao_pct": formatar_percentual(retorno_opcao_pct),
            "resultado_acao_rs": round(resultado_acao, 2),
            "resultado_acao_fmt": formatar_brl(resultado_acao),
        }
    )
