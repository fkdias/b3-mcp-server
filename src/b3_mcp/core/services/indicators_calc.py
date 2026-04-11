"""Cálculos de indicadores técnicos — Python puro."""

from typing import Any


def sma(valores: list[float], periodo: int) -> list[float | None]:
    """Simple Moving Average."""
    resultado = []
    for i in range(len(valores)):
        if i < periodo - 1:
            resultado.append(None)
        else:
            media = sum(valores[i - periodo + 1 : i + 1]) / periodo
            resultado.append(round(media, 4))
    return resultado


def ema(valores: list[float], periodo: int) -> list[float | None]:
    """Exponential Moving Average."""
    resultado: list[float | None] = [None] * (periodo - 1)
    k = 2 / (periodo + 1)
    # Primeiro valor = SMA
    primeiro = sum(valores[:periodo]) / periodo
    resultado.append(round(primeiro, 4))
    for i in range(periodo, len(valores)):
        prev = resultado[-1]
        valor = valores[i] * k + prev * (1 - k)
        resultado.append(round(valor, 4))
    return resultado


def rsi(closes: list[float], periodo: int = 14) -> list[float | None]:
    """Relative Strength Index."""
    resultado: list[float | None] = [None] * periodo
    ganhos = []
    perdas = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        ganhos.append(max(diff, 0))
        perdas.append(max(-diff, 0))

    if len(ganhos) < periodo:
        return [None] * len(closes)

    avg_ganho = sum(ganhos[:periodo]) / periodo
    avg_perda = sum(perdas[:periodo]) / periodo

    if avg_perda == 0:
        resultado.append(100.0)
    else:
        rs = avg_ganho / avg_perda
        resultado.append(round(100 - (100 / (1 + rs)), 2))

    for i in range(periodo, len(ganhos)):
        avg_ganho = (avg_ganho * (periodo - 1) + ganhos[i]) / periodo
        avg_perda = (avg_perda * (periodo - 1) + perdas[i]) / periodo
        if avg_perda == 0:
            resultado.append(100.0)
        else:
            rs = avg_ganho / avg_perda
            resultado.append(round(100 - (100 / (1 + rs)), 2))

    return resultado


def macd(
    closes: list[float],
    rapido: int = 12,
    lento: int = 26,
    sinal_periodo: int = 9,
) -> dict[str, list[float | None]]:
    """MACD — retorna linha, sinal e histograma."""
    ema_rapida = ema(closes, rapido)
    ema_lenta = ema(closes, lento)

    linha = []
    for r, lento_v in zip(ema_rapida, ema_lenta, strict=False):
        if r is None or lento_v is None:
            linha.append(None)
        else:
            linha.append(round(r - lento_v, 4))

    # Sinal = EMA da linha MACD
    valores_validos = [v for v in linha if v is not None]
    if len(valores_validos) < sinal_periodo:
        return {"linha": linha, "sinal": [None] * len(closes), "histograma": [None] * len(closes)}

    ema_sinal = ema(valores_validos, sinal_periodo)

    # Reconstrói com Nones no início
    sinal_completo: list[float | None] = []
    idx_valido = 0
    for v in linha:
        if v is None:
            sinal_completo.append(None)
        else:
            if idx_valido < len(ema_sinal):
                sinal_completo.append(ema_sinal[idx_valido])
            else:
                sinal_completo.append(None)
            idx_valido += 1

    histograma = []
    for l_val, s_val in zip(linha, sinal_completo, strict=False):
        if l_val is None or s_val is None:
            histograma.append(None)
        else:
            histograma.append(round(l_val - s_val, 4))

    return {"linha": linha, "sinal": sinal_completo, "histograma": histograma}


def bollinger_bands(closes: list[float], periodo: int = 20, desvios: float = 2.0) -> dict[str, list[float | None]]:
    """Bandas de Bollinger."""
    media = sma(closes, periodo)
    superior = []
    inferior = []

    for i in range(len(closes)):
        if media[i] is None:
            superior.append(None)
            inferior.append(None)
        else:
            janela = closes[max(0, i - periodo + 1) : i + 1]
            m = media[i]
            n = len(janela)
            variancia = sum((x - m) ** 2 for x in janela) / n if n > 0 else 0
            dp = variancia**0.5
            superior.append(round(m + desvios * dp, 4))
            inferior.append(round(m - desvios * dp, 4))

    return {"media": media, "superior": superior, "inferior": inferior}


def calc_hilo_activator(
    maximas: list[float],
    minimas: list[float],
    fechamentos: list[float],
    periodo: int = 10,
) -> dict[str, Any]:
    """
    Gann Hi-Lo Activator (Custom Hi-Lo / CHiLo) — período 10.

    Implementação compatível com TradingView CHiLo:
    - high_ma = SMA(máximas, 10) deslocado 1 barra (candle anterior)
    - low_ma = SMA(mínimas, 10) deslocado 1 barra (candle anterior)
    - Se close > high_ma[anterior]: tendência = ALTA, activator = low_ma[anterior]
    - Se close < low_ma[anterior]: tendência = BAIXA, activator = high_ma[anterior]
    - COMPRA quando muda de BAIXA → ALTA
    - VENDA quando muda de ALTA → BAIXA

    O offset de 1 barra é a diferença chave vs implementações simplificadas.
    """
    n = len(fechamentos)
    high_ma_raw = sma(maximas, periodo)
    low_ma_raw = sma(minimas, periodo)

    # Deslocar SMAs em 1 barra (usar valor do candle anterior)
    high_ma: list[float | None] = [None] + high_ma_raw[:-1]
    low_ma: list[float | None] = [None] + low_ma_raw[:-1]

    activator: list[float | None] = [None] * n
    tendencia: list[str | None] = [None] * n
    sinais: list[str | None] = [None] * n

    trend_atual = None

    for i in range(n):
        if high_ma[i] is None or low_ma[i] is None:
            continue

        close = fechamentos[i]
        h_ma = high_ma[i]
        l_ma = low_ma[i]

        if close > h_ma:
            novo_trend = "ALTA"
            activator[i] = l_ma
        elif close < l_ma:
            novo_trend = "BAIXA"
            activator[i] = h_ma
        else:
            novo_trend = trend_atual
            if trend_atual == "ALTA":
                activator[i] = l_ma
            elif trend_atual == "BAIXA":
                activator[i] = h_ma
            else:
                activator[i] = l_ma

        tendencia[i] = novo_trend

        # Detectar mudança de tendência
        if trend_atual is not None and novo_trend != trend_atual:
            if novo_trend == "ALTA":
                sinais[i] = "COMPRA"
            elif novo_trend == "BAIXA":
                sinais[i] = "VENDA"

        trend_atual = novo_trend

    return {
        "activator": activator,
        "high_ma": high_ma,
        "low_ma": low_ma,
        "tendencia": tendencia,
        "sinais": sinais,
    }
