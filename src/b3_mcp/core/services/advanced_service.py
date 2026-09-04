"""Serviços avançados: volume breakout, candle patterns, notícias, multi-agente."""

import os
from typing import Any

import feedparser

from ..data.b3_sectors import get_setor
from ..utils.formatting import formatar_brl, formatar_percentual, formatar_volume, ticker_limpo
from .hilo_service import _carregar_offline, _listar_offline_disponiveis, analisar_hilo
from .indicators_calc import calc_hilo_activator
from .yahoo_finance import obter_historico

# Dados offline. Os testes redirecionam para uma cópia congelada via B3_SAMPLES_DIR
# (o pipeline diário sobrescreve o diretório de produção — ver tests/fixtures/README.md).
SAMPLES_DIR = os.environ.get("B3_SAMPLES_DIR") or os.path.join(os.path.dirname(__file__), "..", "data", "samples")


def _tem_offline(ticker: str) -> bool:
    nome = ticker_limpo(ticker).lower()
    return os.path.exists(os.path.join(SAMPLES_DIR, f"{nome}_diario.json"))


# ═══════════════════════════════════════════
# 1. Volume Breakout Scanner
# ═══════════════════════════════════════════
def volume_breakout_scanner(
    multiplicador: float = 2.0,
    offline: bool = False,
) -> dict[str, Any]:
    """Detecta ativos com volume muito acima da média (breakout de volume)."""
    tickers = _listar_offline_disponiveis() if offline else []
    resultados = []

    for ticker in tickers:
        try:
            if offline:
                candles = _carregar_offline(ticker)
            else:
                candles = obter_historico(ticker, periodo="1y")
            if not candles or len(candles) < 22:
                continue

            volumes = [c["volume"] for c in candles if c["volume"] > 0]
            if len(volumes) < 22:
                continue

            vol_atual = volumes[-1]
            vol_medio = sum(volumes[-21:-1]) / 20
            ratio = vol_atual / vol_medio if vol_medio > 0 else 0

            if ratio >= multiplicador:
                fechamentos = [c["fechamento"] for c in candles]
                maximas = [c["maxima"] for c in candles]
                minimas = [c["minima"] for c in candles]
                hilo = calc_hilo_activator(maximas, minimas, fechamentos, 10)

                preco = fechamentos[-1]
                var_dia = ((preco - fechamentos[-2]) / fechamentos[-2] * 100) if len(fechamentos) > 1 else 0

                resultados.append(
                    {
                        "ticker": ticker,
                        "setor": get_setor(ticker),
                        "preco": formatar_brl(preco),
                        "variacao_dia": formatar_percentual(var_dia),
                        "volume_atual": formatar_volume(vol_atual),
                        "volume_medio": formatar_volume(vol_medio),
                        "volume_ratio": round(ratio, 2),
                        "tendencia_hilo": hilo["tendencia"][-1],
                    }
                )
        except Exception:
            continue

    resultados.sort(key=lambda x: x.get("volume_ratio", 0), reverse=True)

    return {
        "criterio": f"Volume >= {multiplicador}x da média 20d",
        "total_detectados": len(resultados),
        "resultados": resultados,
    }


# ═══════════════════════════════════════════
# 2. Padrões de Candle
# ═══════════════════════════════════════════
def _detectar_doji(o, h, low, c):
    corpo = abs(c - o)
    range_total = h - low
    if range_total == 0:
        return False
    return corpo / range_total < 0.05  # 5% threshold (mais preciso)


def _detectar_martelo(o, h, low, c):
    corpo = abs(c - o)
    range_total = h - low
    if range_total == 0 or corpo == 0:
        return False
    sombra_inf = min(o, c) - low
    # Martelo: sombra inferior >= 2x corpo E close na metade superior
    if sombra_inf >= corpo * 2 and c > (h + low) / 2:
        return True
    return False


def _detectar_engolfo_alta(candles, i):
    if i < 1:
        return False
    prev = candles[i - 1]
    curr = candles[i]
    # Engolfo de alta: candle anterior vermelho, atual verde engolfa, volume maior
    vol_confirma = curr.get("volume", 0) > prev.get("volume", 0)
    padrao = (
        prev["fechamento"] < prev["abertura"]
        and curr["fechamento"] > curr["abertura"]
        and curr["abertura"] <= prev["fechamento"]
        and curr["fechamento"] >= prev["abertura"]
    )
    return padrao and vol_confirma


def _detectar_engolfo_baixa(candles, i):
    if i < 1:
        return False
    prev = candles[i - 1]
    curr = candles[i]
    # Engolfo de baixa: candle anterior verde, atual vermelho engolfa, volume maior
    vol_confirma = curr.get("volume", 0) > prev.get("volume", 0)
    padrao = (
        prev["fechamento"] > prev["abertura"]
        and curr["fechamento"] < curr["abertura"]
        and curr["abertura"] >= prev["fechamento"]
        and curr["fechamento"] <= prev["abertura"]
    )
    return padrao and vol_confirma


def _detectar_estrela_cadente(o, h, low, c):
    corpo = abs(c - o)
    range_total = h - low
    if range_total == 0 or corpo == 0:
        return False
    sombra_sup = h - max(o, c)
    # Estrela cadente: sombra superior >= 2x corpo E close na metade inferior
    if sombra_sup >= corpo * 2 and c < (h + low) / 2:
        return True
    return False


def padroes_candle(ticker: str, offline: bool = False) -> dict[str, Any]:
    """Detecta padrões de candle nos últimos 5 dias de um ativo."""
    ticker_clean = ticker_limpo(ticker)

    if offline:
        candles = _carregar_offline(ticker_clean)
        if candles is None:
            raise ValueError(f"Dados offline não disponíveis para {ticker_clean}")
    else:
        candles = obter_historico(ticker_clean, periodo="1y")

    padroes_detectados = []

    for i in range(max(0, len(candles) - 5), len(candles)):
        c = candles[i]
        o, h, low, cl = c["abertura"], c["maxima"], c["minima"], c["fechamento"]
        data = c["data"]

        if _detectar_doji(o, h, low, cl):
            padroes_detectados.append(
                {"data": data, "padrao": "Doji", "tipo": "NEUTRO", "descricao": "Indecisão do mercado"}
            )
        if _detectar_martelo(o, h, low, cl):
            padroes_detectados.append(
                {"data": data, "padrao": "Martelo", "tipo": "ALTA", "descricao": "Possível reversão de alta"}
            )
        if _detectar_estrela_cadente(o, h, low, cl):
            padroes_detectados.append(
                {"data": data, "padrao": "Estrela Cadente", "tipo": "BAIXA", "descricao": "Possível reversão de baixa"}
            )
        if _detectar_engolfo_alta(candles, i):
            padroes_detectados.append(
                {"data": data, "padrao": "Engolfo de Alta", "tipo": "ALTA", "descricao": "Padrão bullish de reversão"}
            )
        if _detectar_engolfo_baixa(candles, i):
            padroes_detectados.append(
                {"data": data, "padrao": "Engolfo de Baixa", "tipo": "BAIXA", "descricao": "Padrão bearish de reversão"}
            )

    return {
        "ticker": ticker_clean,
        "periodo_analise": "Últimos 5 pregões",
        "padroes_detectados": len(padroes_detectados),
        "padroes": padroes_detectados,
    }


# ═══════════════════════════════════════════
# 3. Notícias B3
# ═══════════════════════════════════════════
RSS_FEEDS = {
    "InfoMoney": "https://www.infomoney.com.br/feed/",
    "InfoMoney Mercados": "https://www.infomoney.com.br/mercados/feed/",
    "InfoMoney Economia": "https://www.infomoney.com.br/economia/feed/",
    "Valor Econômico": "https://valor.globo.com/rss/valor.xml",
}

# Categorias por palavras-chave no título
_CATEGORIAS = {
    "mercado": ["ibovespa", "b3", "bolsa", "ação", "ações", "mercado", "investidor", "fundo"],
    "economia": ["pib", "inflação", "selic", "juros", "câmbio", "dólar", "fiscal", "governo", "reforma", "bc"],
    "commodities": ["petróleo", "minério", "soja", "commodity", "vale", "petrobras", "opep"],
    "internacional": ["eua", "trump", "china", "fed", "europa", "guerra", "irã", "rússia", "ucrânia", "ormuz"],
    "empresas": ["lucro", "resultado", "dividendo", "fusão", "aquisição", "ipo", "oferta"],
    "politica": ["lula", "congresso", "câmara", "senado", "stf", "eleição", "partido", "pt", "pl"],
}


def _limpar_html(texto: str) -> str:
    """Remove tags HTML de um texto."""
    import re

    limpo = re.sub(r"<[^>]+>", "", texto)
    limpo = limpo.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    limpo = limpo.replace("&quot;", '"').replace("&#8217;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    return limpo.strip()


def _categorizar(titulo: str) -> list[str]:
    """Categoriza uma notícia por palavras-chave no título."""
    titulo_lower = titulo.lower()
    categorias = []
    for cat, palavras in _CATEGORIAS.items():
        for palavra in palavras:
            if palavra in titulo_lower:
                categorias.append(cat)
                break
    return categorias if categorias else ["geral"]


def noticias_b3(limite: int = 10) -> dict[str, Any]:
    """Busca notícias financeiras brasileiras via RSS com links e categorias."""
    todas_noticias = []

    for fonte, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limite]:
                titulo = entry.get("title", "")
                resumo_raw = entry.get("summary", entry.get("description", ""))
                resumo = _limpar_html(str(resumo_raw))[:300] if resumo_raw else ""

                todas_noticias.append(
                    {
                        "titulo": titulo,
                        "link": entry.get("link", ""),
                        "fonte": fonte.split(" ")[0],  # "InfoMoney Mercados" -> "InfoMoney"
                        "data": entry.get("published", entry.get("updated", "")),
                        "categorias": _categorizar(titulo),
                        "resumo": resumo,
                    }
                )
        except Exception:
            continue

    # Remover duplicatas por título
    vistos = set()
    unicas = []
    for n in todas_noticias:
        if n["titulo"] not in vistos:
            vistos.add(n["titulo"])
            unicas.append(n)

    unicas = unicas[:limite]

    # Contagem por categoria
    contagem = {}
    for n in unicas:
        for cat in n["categorias"]:
            contagem[cat] = contagem.get(cat, 0) + 1

    return {
        "total": len(unicas),
        "fontes": ["InfoMoney", "Valor Econômico"],
        "categorias": contagem,
        "noticias": unicas,
    }


# ═══════════════════════════════════════════
# 4. Análise Multi-Agente
# ═══════════════════════════════════════════
def analise_multiagente(ticker: str, offline: bool = False) -> dict[str, Any]:
    """
    Framework com 3 agentes analisando o ativo:
    - Agente Técnico: Hi-Lo, RSI, SMA, Bollinger
    - Agente Momentum: volume, velocidade da tendência
    - Agente Risco: drawdown, profit factor, expectativa
    """
    analise = analisar_hilo(ticker, periodo=13, offline=offline, gerar_grafico=False)
    hilo = analise.get("hilo", {})
    ind = analise.get("indicadores", {})
    vol = analise.get("volume", {})
    mr = analise.get("metricas_risco", {})

    # ─── Agente Técnico (max ±4) ───
    score_tecnico = 0
    notas_tecnico = []
    tendencia = hilo["tendencia"]

    if tendencia == "ALTA":
        score_tecnico += 2
        notas_tecnico.append("Hi-Lo Activator em ALTA")
    elif tendencia == "BAIXA":
        score_tecnico -= 2
        notas_tecnico.append("Hi-Lo Activator em BAIXA")

    rsi_val = ind.get("rsi_14")
    if rsi_val:
        # RSI contextuado com a tendência Hi-Lo
        if rsi_val < 30 and tendencia == "ALTA":
            score_tecnico += 1
            notas_tecnico.append(f"RSI sobrevenda em tendência de alta — possível bounce ({rsi_val})")
        elif rsi_val < 30 and tendencia == "BAIXA":
            score_tecnico -= 1
            notas_tecnico.append(f"RSI sobrevenda confirmando queda ({rsi_val})")
        elif rsi_val > 70 and tendencia == "ALTA":
            score_tecnico -= 1
            notas_tecnico.append(f"RSI sobrecompra — esticado, risco de correção ({rsi_val})")
        elif rsi_val > 70 and tendencia == "BAIXA":
            score_tecnico += 1
            notas_tecnico.append(f"RSI sobrecompra em tendência de baixa — divergência altista ({rsi_val})")
        else:
            notas_tecnico.append(f"RSI neutro ({rsi_val})")

    if "ALTA" in ind.get("sma_status", ""):
        score_tecnico += 1
        notas_tecnico.append("SMA 9 > SMA 21 (bullish)")
    elif "BAIXA" in ind.get("sma_status", ""):
        score_tecnico -= 1
        notas_tecnico.append("SMA 9 < SMA 21 (bearish)")

    # ─── Agente Momentum (max ±3) ───
    score_momentum = 0
    notas_momentum = []

    vol_rel = vol.get("volume_relativo", 1)
    if isinstance(vol_rel, (int, float)):
        if vol_rel >= 1.5:
            score_momentum += 2
            notas_momentum.append(f"Volume {vol_rel}x acima da média (forte momentum)")
        elif vol_rel >= 1.0:
            score_momentum += 1
            notas_momentum.append(f"Volume normal ({vol_rel}x)")
        else:
            score_momentum -= 1
            notas_momentum.append(f"Volume abaixo da média ({vol_rel}x)")

    dias = hilo.get("dias_na_tendencia", 0)
    if dias >= 10:
        score_momentum += 1
        notas_momentum.append(f"Tendência sustentada há {dias} pregões")
    elif dias >= 5:
        notas_momentum.append(f"Tendência recente ({dias} pregões)")
    else:
        score_momentum -= 1
        notas_momentum.append(f"Tendência muito recente ({dias} pregões)")

    # ─── Agente Risco (max ±3) ───
    score_risco = 0
    notas_risco = []

    pf = mr.get("profit_factor", 0)
    if isinstance(pf, (int, float)) and pf != float("inf"):
        if pf >= 2:
            score_risco += 2
            notas_risco.append(f"Profit factor excelente ({pf})")
        elif pf >= 1:
            score_risco += 1
            notas_risco.append(f"Profit factor positivo ({pf})")
        else:
            score_risco -= 2
            notas_risco.append(f"Profit factor negativo ({pf}) — Hi-Lo perde dinheiro neste ativo")
    elif pf == float("inf"):
        score_risco += 2
        notas_risco.append("Profit factor infinito (0 losses)")

    equity = mr.get("equity_final", 100)
    if isinstance(equity, (int, float)):
        retorno = equity - 100
        if retorno > 20:
            score_risco += 1
            notas_risco.append(f"Retorno forte no período ({formatar_percentual(retorno)})")
        elif retorno < -10:
            score_risco -= 1
            notas_risco.append(f"Retorno negativo ({formatar_percentual(retorno)})")

    wr = mr.get("win_rate", "N/A")
    notas_risco.append(f"Win rate: {wr}")
    notas_risco.append(f"Max drawdown: {mr.get('max_drawdown', 'N/A')}")

    # ─── Veredito final (normalizado) ───
    # Normalizar cada agente para -1 a +1
    norm_tec = score_tecnico / 4
    norm_mom = score_momentum / 3
    norm_risco = score_risco / 3
    score_normalizado = round((norm_tec + norm_mom + norm_risco) / 3, 2)  # -1 a +1

    # Score bruto para display
    score_total = score_tecnico + score_momentum + score_risco

    if score_normalizado >= 0.55:
        veredito = "FORTE COMPRA"
        confianca = "Alta"
    elif score_normalizado >= 0.25:
        veredito = "COMPRA"
        confianca = "Moderada"
    elif score_normalizado >= -0.15:
        veredito = "NEUTRO"
        confianca = "Baixa"
    elif score_normalizado >= -0.45:
        veredito = "VENDA"
        confianca = "Moderada"
    else:
        veredito = "FORTE VENDA"
        confianca = "Alta"

    return {
        "ticker": ticker_limpo(ticker),
        "preco": analise["preco"]["formatado"],
        "veredito": veredito,
        "score_total": score_total,
        "score_normalizado": score_normalizado,
        "confianca": confianca,
        "agentes": {
            "tecnico": {
                "score": score_tecnico,
                "max_score": 4,
                "notas": notas_tecnico,
            },
            "momentum": {
                "score": score_momentum,
                "max_score": 3,
                "notas": notas_momentum,
            },
            "risco": {
                "score": score_risco,
                "max_score": 3,
                "notas": notas_risco,
            },
        },
        "disclaimer": "Análise educacional. Não constitui recomendação de investimento.",
    }
