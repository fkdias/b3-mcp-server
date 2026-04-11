"""
B3 MCP Server — Análise do mercado de ações brasileiro (B3/Bovespa).

19 ferramentas:
 1. cotacao_b3            2. hilo_activator         3. analise_tecnica_b3
 4. panorama_mercado_b3   5. maiores_altas_b3       6. maiores_baixas_b3
 7. backtest_estrategia   8. visao_setorial_b3      9. scanner_setor_b3
10. analise_indice_b3    11. screener_b3           12. plano_trade_b3
13. fibonacci_b3         14. analise_multiagente   15. volume_breakout_b3
16. noticias_b3          17. padroes_candle_b3     18. simular_opcoes_b3
19. refresh_dashboard_b3  (Fase 12 — ingest → SQLite → Apache Superset)
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .core.services.yahoo_finance import obter_cotacao, obter_cotacao_indice, obter_historico
from .core.services.hilo_service import analisar_hilo
from .core.services.screener_provider import maiores_altas, maiores_baixas, maiores_volumes
from .core.services.backtest_service import executar_backtest, ESTRATEGIAS_DISPONIVEIS
from .core.services.indicators_calc import (
    calc_hilo_activator, rsi, sma, ema, macd, bollinger_bands,
)
from .core.services.b3_service import (
    visao_setorial, scanner_setor, analise_indice, screener_b3 as _screener_b3,
    plano_trade, fibonacci_levels,
)
from .core.services.advanced_service import (
    volume_breakout_scanner, padroes_candle, noticias_b3 as _noticias_b3,
    analise_multiagente,
)
from .core.services.options_sim import simular_opcoes_hilo
from .core.data.b3_sectors import SETORES, get_setor, get_ativos_setor
from .core.data.b3_indices import INDICES, get_constituintes
from .core.utils.formatting import formatar_brl, formatar_percentual, formatar_volume

mcp = FastMCP("B3 Bovespa")


# ═══════════════════════════════════════════════════════════════
# Tool 1: Cotação B3
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def cotacao_b3(ticker: str) -> str:
    """
    Cotação em tempo real de uma ação da B3.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3, ITUB4)

    Retorna preço atual, variação, e informações básicas.
    """
    try:
        dados = obter_cotacao(ticker)
        return json.dumps(dados, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 2: Hi-Lo Activator
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def hilo_activator(ticker: str, periodo: int = 10, offline: bool = False) -> str:
    """
    Indicador Hi-Lo Activator para ações da B3.

    Calcula a tendência (ALTA/BAIXA), valor do activator, sinais de
    COMPRA/VENDA, e histórico dos últimos 5 sinais.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3, ITUB4)
        periodo: Período do Hi-Lo Activator (default: 10)
        offline: Usar dados offline para demonstração (default: False)

    Sinais:
    - COMPRA: quando tendência muda de BAIXA para ALTA
    - VENDA: quando tendência muda de ALTA para BAIXA
    """
    try:
        resultado = analisar_hilo(ticker, periodo, offline)
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 3: Análise Técnica B3
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def analise_tecnica_b3(ticker: str, offline: bool = False) -> str:
    """
    Análise técnica completa de uma ação da B3.

    Inclui: Hi-Lo Activator, RSI, SMA (9/21), EMA (9/21),
    MACD, Bandas de Bollinger, e resumo da análise.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3, ITUB4)
        offline: Usar dados offline para demonstração (default: False)
    """
    try:
        from .core.services.hilo_service import _carregar_offline
        from .core.utils.formatting import ticker_limpo

        ticker_clean = ticker_limpo(ticker)

        if offline:
            candles = _carregar_offline(ticker_clean)
            if candles is None:
                return json.dumps({"erro": f"Dados offline não disponíveis para {ticker_clean}"})
        else:
            candles = obter_historico(ticker_clean, periodo="1y")

        fechamentos = [c["fechamento"] for c in candles]
        maximas = [c["maxima"] for c in candles]
        minimas = [c["minima"] for c in candles]
        ultimo = len(candles) - 1

        # Hi-Lo Activator
        hilo = calc_hilo_activator(maximas, minimas, fechamentos, 10)

        # RSI
        rsi_vals = rsi(fechamentos, 14)
        rsi_atual = rsi_vals[ultimo] if rsi_vals[ultimo] is not None else None

        # SMAs
        sma_9 = sma(fechamentos, 9)
        sma_21 = sma(fechamentos, 21)

        # EMAs
        ema_9 = ema(fechamentos, 9)
        ema_21 = ema(fechamentos, 21)

        # MACD
        macd_data = macd(fechamentos)

        # Bollinger
        bb = bollinger_bands(fechamentos)

        preco = fechamentos[ultimo]

        # Contagem de sinais
        sinais_alta = 0
        sinais_baixa = 0

        # Hi-Lo
        if hilo["tendencia"][ultimo] == "ALTA":
            sinais_alta += 1
        elif hilo["tendencia"][ultimo] == "BAIXA":
            sinais_baixa += 1

        # RSI
        if rsi_atual:
            if rsi_atual < 30:
                sinais_alta += 1  # sobrevenda = oportunidade
            elif rsi_atual > 70:
                sinais_baixa += 1  # sobrecompra = risco

        # SMA crossover
        if sma_9[ultimo] and sma_21[ultimo]:
            if sma_9[ultimo] > sma_21[ultimo]:
                sinais_alta += 1
            else:
                sinais_baixa += 1

        # EMA crossover
        if ema_9[ultimo] and ema_21[ultimo]:
            if ema_9[ultimo] > ema_21[ultimo]:
                sinais_alta += 1
            else:
                sinais_baixa += 1

        # MACD
        if macd_data["histograma"][ultimo] is not None:
            if macd_data["histograma"][ultimo] > 0:
                sinais_alta += 1
            else:
                sinais_baixa += 1

        # Bollinger
        if bb["inferior"][ultimo] and bb["superior"][ultimo]:
            if preco <= bb["inferior"][ultimo]:
                sinais_alta += 1
            elif preco >= bb["superior"][ultimo]:
                sinais_baixa += 1

        total_sinais = sinais_alta + sinais_baixa
        if total_sinais > 0:
            score = round((sinais_alta / total_sinais) * 100)
        else:
            score = 50

        if score >= 70:
            veredicto = "FORTE ALTA"
        elif score >= 55:
            veredicto = "ALTA"
        elif score >= 45:
            veredicto = "NEUTRO"
        elif score >= 30:
            veredicto = "BAIXA"
        else:
            veredicto = "FORTE BAIXA"

        resultado = {
            "ticker": ticker_clean,
            "preco": preco,
            "preco_formatado": formatar_brl(preco),
            "data": candles[ultimo]["data"],
            "indicadores": {
                "hilo_activator": {
                    "tendencia": hilo["tendencia"][ultimo],
                    "activator": round(hilo["activator"][ultimo], 2) if hilo["activator"][ultimo] else None,
                    "periodo": 10,
                },
                "rsi_14": round(rsi_atual, 2) if rsi_atual else None,
                "sma_9": round(sma_9[ultimo], 2) if sma_9[ultimo] else None,
                "sma_21": round(sma_21[ultimo], 2) if sma_21[ultimo] else None,
                "ema_9": round(ema_9[ultimo], 2) if ema_9[ultimo] else None,
                "ema_21": round(ema_21[ultimo], 2) if ema_21[ultimo] else None,
                "macd": {
                    "linha": round(macd_data["linha"][ultimo], 4) if macd_data["linha"][ultimo] else None,
                    "sinal": round(macd_data["sinal"][ultimo], 4) if macd_data["sinal"][ultimo] else None,
                    "histograma": round(macd_data["histograma"][ultimo], 4) if macd_data["histograma"][ultimo] else None,
                },
                "bollinger": {
                    "superior": round(bb["superior"][ultimo], 2) if bb["superior"][ultimo] else None,
                    "media": round(bb["media"][ultimo], 2) if bb["media"][ultimo] else None,
                    "inferior": round(bb["inferior"][ultimo], 2) if bb["inferior"][ultimo] else None,
                },
            },
            "score_tecnico": score,
            "veredicto": veredicto,
            "sinais_alta": sinais_alta,
            "sinais_baixa": sinais_baixa,
            "resumo": (
                f"{ticker_clean} a {formatar_brl(preco)} — Score técnico: {score}/100 ({veredicto}). "
                f"Hi-Lo: {hilo['tendencia'][ultimo]}, RSI: {round(rsi_atual, 1) if rsi_atual else 'N/A'}. "
                f"{sinais_alta} sinais de alta vs {sinais_baixa} sinais de baixa."
            ),
        }

        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 4: Panorama do Mercado B3
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def panorama_mercado_b3() -> str:
    """
    Visão geral do mercado brasileiro.

    Retorna: IBOVESPA, Dólar (USDBRL), Euro (EURBRL),
    e as maiores altas e baixas do dia via TradingView Screener.
    """
    try:
        resultado: dict[str, Any] = {"indices": {}, "cambio": {}}

        # Índices e câmbio
        for nome, simbolo in [("IBOVESPA", "^BVSP"), ("Dólar", "USDBRL=X"), ("Euro", "EURBRL=X")]:
            try:
                dados = obter_cotacao_indice(simbolo)
                chave = "indices" if nome == "IBOVESPA" else "cambio"
                resultado[chave][nome] = {
                    "valor": dados["preco"],
                    "valor_formatado": formatar_brl(dados["preco"]),
                    "variacao_pct": formatar_percentual(dados["variacao_pct"]),
                }
            except Exception:
                pass

        # Maiores altas e baixas
        try:
            resultado["maiores_altas"] = maiores_altas(5)
        except Exception:
            resultado["maiores_altas"] = []

        try:
            resultado["maiores_baixas"] = maiores_baixas(5)
        except Exception:
            resultado["maiores_baixas"] = []

        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 5: Maiores Altas B3
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def maiores_altas_b3(limite: int = 10) -> str:
    """
    Maiores altas do dia na B3.

    Args:
        limite: Quantidade de resultados (default: 10)

    Retorna lista de ações com maior valorização do dia.
    """
    try:
        resultado = maiores_altas(limite)
        return json.dumps({
            "titulo": f"Top {limite} Maiores Altas — B3",
            "resultados": resultado,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 6: Maiores Baixas B3
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def maiores_baixas_b3(limite: int = 10) -> str:
    """
    Maiores baixas do dia na B3.

    Args:
        limite: Quantidade de resultados (default: 10)

    Retorna lista de ações com maior desvalorização do dia.
    """
    try:
        resultado = maiores_baixas(limite)
        return json.dumps({
            "titulo": f"Top {limite} Maiores Baixas — B3",
            "resultados": resultado,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Tool 7: Backtest de Estratégia
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def backtest_estrategia(
    ticker: str,
    estrategia: str = "hilo",
    offline: bool = False,
) -> str:
    """
    Backtest de estratégia em uma ação da B3 (timeframe diário, 12 meses).

    Args:
        ticker: Código da ação (ex: PETR4, VALE3, ITUB4)
        estrategia: Nome da estratégia. Opções:
            - hilo: Hi-Lo Activator (período 10)
            - rsi: RSI (14) com sobrevenda/sobrecompra
            - sma_crossover: Cruzamento de SMA 9/21
            - ema_crossover: Cruzamento de EMA 9/21
            - macd: Cruzamento do histograma MACD
            - bollinger: Bandas de Bollinger (toque inferior/superior)
            - todas: Compara todas as estratégias
        offline: Usar dados offline para demonstração (default: False)

    Retorna: métricas de performance (taxa de acerto, profit factor,
    max drawdown, lucro total) e lista de trades.
    """
    try:
        resultado = executar_backtest(ticker, estrategia, offline)
        # Remover lista completa de trades para resposta mais limpa
        if "todos_trades" in resultado:
            del resultado["todos_trades"]
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# FASE 8: Tools B3-Específicas
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def visao_setorial_b3(offline: bool = True) -> str:
    """
    Scanner de todos os 14 setores da B3 com tendência Hi-Lo e momentum.

    Mostra quantos ativos de cada setor estão em alta/baixa e classifica
    o momentum setorial (FORTE/MODERADO/FRACO).

    Args:
        offline: Usar dados offline (default: True)
    """
    try:
        return json.dumps(visao_setorial(offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def scanner_setor_b3(setor: str, offline: bool = True) -> str:
    """
    Análise detalhada de todos os ativos de um setor da B3.

    Args:
        setor: Nome do setor (ex: Financeiro, Petróleo, Mineração, Energia,
               Consumo, Saúde, Telecom, Tecnologia, Construção, Papel,
               Alimentos, Transporte, Seguros, Saneamento)
        offline: Usar dados offline (default: True)
    """
    try:
        return json.dumps(scanner_setor(setor, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def analise_indice_b3(indice: str = "IBOVESPA", offline: bool = True) -> str:
    """
    Análise Hi-Lo dos constituintes de um índice da B3.

    Mostra breadth (% em alta) e lista cada ativo com tendência.

    Args:
        indice: Nome do índice (IBOVESPA, SMLL, IDIV, IBRX100)
        offline: Usar dados offline (default: True)
    """
    try:
        return json.dumps(analise_indice(indice, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def screener_b3(
    filtro_tendencia: str | None = None,
    filtro_setor: str | None = None,
    min_profit_factor: float = 0,
    ordenar_por: str = "retorno",
    offline: bool = True,
) -> str:
    """
    Screener de ações da B3 com filtros.

    Args:
        filtro_tendencia: Filtrar por tendência Hi-Lo (ALTA ou BAIXA)
        filtro_setor: Filtrar por setor (ex: Financeiro, Petróleo)
        min_profit_factor: Profit factor mínimo do Hi-Lo (ex: 1.5)
        ordenar_por: Ordenar por: retorno, profit_factor, dias
        offline: Usar dados offline (default: True)
    """
    try:
        return json.dumps(
            _screener_b3(filtro_tendencia, filtro_setor, min_profit_factor, ordenar_por, offline),
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def plano_trade_b3(ticker: str, offline: bool = False) -> str:
    """
    Plano de trade completo: entrada, stop, alvos e risco/retorno.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)
        offline: Usar dados offline (default: False)
    """
    try:
        return json.dumps(plano_trade(ticker, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def fibonacci_b3(ticker: str, offline: bool = False) -> str:
    """
    Níveis de Fibonacci (retração e extensão) para um ativo da B3.

    Calcula com base no topo e fundo dos últimos 12 meses.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)
        offline: Usar dados offline (default: False)
    """
    try:
        return json.dumps(fibonacci_levels(ticker, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# FASE 9: Análise Avançada
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def analise_multiagente_b3(ticker: str, offline: bool = False) -> str:
    """
    Análise com 3 agentes: Técnico, Momentum e Risco.

    Cada agente dá um score e notas. O veredicto final combina os 3.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)
        offline: Usar dados offline (default: False)
    """
    try:
        return json.dumps(analise_multiagente(ticker, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def volume_breakout_b3(multiplicador: float = 2.0, offline: bool = True) -> str:
    """
    Scanner de rompimento por volume na B3.

    Detecta ativos com volume muito acima da média de 20 dias.

    Args:
        multiplicador: Múltiplo do volume médio (default: 2.0x)
        offline: Usar dados offline (default: True)
    """
    try:
        return json.dumps(
            volume_breakout_scanner(multiplicador, offline),
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def noticias_b3(limite: int = 10) -> str:
    """
    Notícias financeiras brasileiras (InfoMoney, Valor Econômico).

    Args:
        limite: Quantidade de notícias (default: 10)
    """
    try:
        return json.dumps(_noticias_b3(limite), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


@mcp.tool()
def padroes_candle_b3(ticker: str, offline: bool = False) -> str:
    """
    Detector de padrões de candle nos últimos 5 pregões.

    Detecta: Doji, Martelo, Estrela Cadente, Engolfo de Alta/Baixa.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)
        offline: Usar dados offline (default: False)
    """
    try:
        return json.dumps(padroes_candle(ticker, offline), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# FASE 10: Simulação de Opções
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def simular_opcoes_b3(
    ticker: str,
    vencimento_dias: int = 21,
    offline: bool = False,
    banca_inicial: float | None = None,
    sizing_mode: str = "agregado",
    sizing_valor: float = 1.0,
    lote_tamanho: int = 100,
) -> str:
    """
    Simulação educacional de opções ATM (delta ~0.5) nos sinais do Hi-Lo.

    Compra CALL ATM nos sinais de COMPRA e PUT ATM nos sinais de VENDA.
    Usa Black-Scholes com volatilidade histórica e taxa Selic.

    IMPORTANTE: Simulação educacional, não usa dados reais de opções da B3.

    Args:
        ticker: Código da ação (ex: PETR4, VALE3)
        vencimento_dias: Dias até vencimento da opção (default: 21)
        offline: Usar dados offline (default: False)
        banca_inicial: Capital inicial em R$ (obrigatório se sizing_mode != 'agregado')
        sizing_mode: Modelo de alocação por trade. Valores: 'agregado' (default,
            comportamento legado), 'lote_fixo', 'fracao_banca', 'teto_absoluto',
            'fracao_capital'
        sizing_valor: Parâmetro do sizing (nº de lotes, fração 0..1 ou teto em R$)
        lote_tamanho: Tamanho do lote padrão de opções (default 100)
    """
    try:
        resultado = simular_opcoes_hilo(
            ticker,
            10,
            vencimento_dias,
            offline,
            banca_inicial=banca_inicial,
            sizing_mode=sizing_mode,
            sizing_valor=sizing_valor,
            lote_tamanho=lote_tamanho,
        )
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# FASE 12: Apache Superset — Ingest SQLite
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def refresh_dashboard_b3(
    tickers: list[str] | None = None,
    offline: bool = True,
) -> str:
    """
    Atualiza o banco SQLite consumido pelos dashboards Apache Superset.

    Roda o pipeline de ingestão (Hi-Lo + backtest + simulação de opções)
    para cada ticker e grava em `$B3_ANALYTICS_DB` (default:
    C:\\b3-analytics\\b3_analytics.db). O Superset no WSL2 lê este mesmo
    arquivo via `/mnt/c/b3-analytics/b3_analytics.db`.

    Args:
        tickers: Lista de tickers. None = todos os 26 offline disponíveis.
        offline: True = usa datasets offline; False = Yahoo Finance ao vivo.

    Returns:
        JSON com status, ok, fail, errors, duration_sec, db_path, run_id.
    """
    try:
        # Lazy import — evita custo no startup do server
        from .superset_ingest.ingest import run_ingest
        resultado = run_ingest(tickers=tickers, offline=offline)
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════════════════
def main():
    """Inicia o servidor MCP."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
