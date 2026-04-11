"""Testes determinísticos pros indicadores técnicos puros.

Escopo: funções de `b3_mcp.core.services.indicators_calc` — todas Python puro,
sem I/O, sem dependências externas, fácil de testar com valores hard-coded.

Cobertura:
- SMA: média móvel simples (edge: janela maior que série, série mínima)
- EMA: média móvel exponencial (edge: série constante, série curta)
- RSI: índice de força relativa (edge: só altas, só baixas, preço constante)
- MACD: linha + sinal + histograma (edge: dados insuficientes)
- Bollinger Bands: média + bandas (edge: volatilidade zero)
- Hi-Lo Activator: offset 1-bar, mudanças de tendência, sinais C/V
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.indicators_calc import (
    bollinger_bands,
    calc_hilo_activator,
    ema,
    macd,
    rsi,
    sma,
)


# ─────────────────────────────────────────────────────────────────────────────
# SMA
# ─────────────────────────────────────────────────────────────────────────────
class TestSMA:
    def test_exemplo_conhecido(self):
        """Janela 3 sobre [1,2,3,4,5] → None, None, 2, 3, 4."""
        assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]

    def test_serie_constante(self):
        """Série constante → SMA constante igual ao valor."""
        result = sma([10] * 10, 5)
        assert result[:4] == [None, None, None, None]
        assert all(v == 10.0 for v in result[4:])

    def test_periodo_maior_que_serie(self):
        """Janela 5 sobre série de 2 valores → só Nones (insuficiente)."""
        assert sma([1, 2], 5) == [None, None]

    def test_periodo_um(self):
        """Janela 1 = o próprio valor."""
        assert sma([5.0], 1) == [5.0]
        assert sma([1.0, 2.0, 3.0], 1) == [1.0, 2.0, 3.0]

    def test_mantem_tamanho_da_entrada(self):
        """Output sempre tem o mesmo length da entrada."""
        for n in [1, 5, 10, 50]:
            vals = list(range(n))
            assert len(sma(vals, 3)) == n

    def test_preserva_decimal_arredondado(self):
        """Resultado é arredondado pra 4 casas decimais."""
        result = sma([1.111, 2.222, 3.333], 3)
        assert result[-1] == round((1.111 + 2.222 + 3.333) / 3, 4)


# ─────────────────────────────────────────────────────────────────────────────
# EMA
# ─────────────────────────────────────────────────────────────────────────────
class TestEMA:
    def test_serie_constante(self):
        """EMA de série constante = a constante (com Nones iniciais)."""
        result = ema([10.0] * 10, 3)
        assert result[:2] == [None, None]
        assert all(v == 10.0 for v in result[2:])

    def test_primeiro_valor_e_sma(self):
        """Por convenção do módulo, primeiro EMA válido = SMA do período."""
        result = ema([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        assert result[2] == round((1 + 2 + 3) / 3, 4)  # SMA(1,2,3) = 2.0

    def test_formula_recursiva(self):
        """k = 2/(N+1). Próximo valor = close*k + prev*(1-k)."""
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ema(vals, 3)
        # k = 2/4 = 0.5; result[3] = 4*0.5 + 2.0*0.5 = 3.0
        assert result[3] == 3.0
        # result[4] = 5*0.5 + 3.0*0.5 = 4.0
        assert result[4] == 4.0

    def test_tamanho_output(self):
        assert len(ema([1.0] * 20, 5)) == 20


# ─────────────────────────────────────────────────────────────────────────────
# RSI
# ─────────────────────────────────────────────────────────────────────────────
class TestRSI:
    def test_so_altas(self):
        """Série estritamente crescente → RSI final = 100 (sem perdas)."""
        vals = [float(i) for i in range(1, 20)]
        result = rsi(vals, 14)
        assert result[-1] == 100.0

    def test_so_baixas(self):
        """Série estritamente decrescente → RSI próximo de 0."""
        vals = [float(i) for i in range(30, 10, -1)]
        result = rsi(vals, 14)
        assert result[-1] is not None
        assert result[-1] < 5.0

    def test_serie_constante_retorna_100(self):
        """Preço constante → avg_perda == 0 → branch retorna 100.0."""
        result = rsi([50.0] * 20, 14)
        assert result[-1] == 100.0

    def test_dados_insuficientes(self):
        """Série menor que período → lista toda de None."""
        result = rsi([1.0, 2.0, 3.0], 14)
        assert result == [None] * 3

    def test_primeiros_valores_sao_none(self):
        """Os primeiros `periodo` elementos sempre são None."""
        result = rsi([float(i) for i in range(50)], 14)
        assert all(v is None for v in result[:14])
        assert result[14] is not None

    def test_tamanho_output(self):
        vals = [float(i) for i in range(30)]
        assert len(rsi(vals, 14)) == 30


# ─────────────────────────────────────────────────────────────────────────────
# MACD
# ─────────────────────────────────────────────────────────────────────────────
class TestMACD:
    def test_estrutura_do_retorno(self):
        """MACD retorna dict com chaves linha/sinal/histograma."""
        vals = [float(i) for i in range(100)]
        result = macd(vals)
        assert set(result.keys()) == {"linha", "sinal", "histograma"}

    def test_tamanhos_consistentes(self):
        """Todas as 3 listas têm o mesmo tamanho da entrada."""
        vals = [float(i) for i in range(100)]
        result = macd(vals)
        assert len(result["linha"]) == 100
        assert len(result["sinal"]) == 100
        assert len(result["histograma"]) == 100

    def test_dados_insuficientes(self):
        """< 26 valores → linha tem Nones no início, sinal e histograma tudo None."""
        vals = [float(i) for i in range(20)]
        result = macd(vals)
        assert len(result["linha"]) == 20
        assert all(v is None for v in result["sinal"])
        assert all(v is None for v in result["histograma"])

    def test_serie_crescente_macd_positivo(self):
        """Pra série monotônica crescente, a linha MACD eventualmente é positiva."""
        vals = [float(i) for i in range(100)]
        result = macd(vals)
        linhas_validas = [v for v in result["linha"] if v is not None]
        assert linhas_validas[-1] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Bollinger Bands
# ─────────────────────────────────────────────────────────────────────────────
class TestBollingerBands:
    def test_estrutura_do_retorno(self):
        vals = [float(i) for i in range(30)]
        result = bollinger_bands(vals)
        assert set(result.keys()) == {"media", "superior", "inferior"}

    def test_volatilidade_zero(self):
        """Série constante → superior == media == inferior."""
        vals = [10.0] * 25
        result = bollinger_bands(vals, periodo=20)
        assert result["media"][-1] == 10.0
        assert result["superior"][-1] == 10.0
        assert result["inferior"][-1] == 10.0

    def test_superior_maior_que_inferior_com_variacao(self):
        """Com variação, superior > media > inferior."""
        vals = [float(i) for i in range(30)]
        result = bollinger_bands(vals, periodo=20)
        assert result["superior"][-1] > result["media"][-1]
        assert result["media"][-1] > result["inferior"][-1]

    def test_desvios_maiores_alargam_bandas(self):
        """desvios=1 produz bandas mais estreitas que desvios=2."""
        vals = [float(i) for i in range(30)]
        b1 = bollinger_bands(vals, periodo=20, desvios=1.0)
        b2 = bollinger_bands(vals, periodo=20, desvios=2.0)
        largura_1 = b1["superior"][-1] - b1["inferior"][-1]
        largura_2 = b2["superior"][-1] - b2["inferior"][-1]
        assert largura_2 > largura_1

    def test_tamanhos_consistentes(self):
        vals = [float(i) for i in range(50)]
        result = bollinger_bands(vals)
        assert len(result["media"]) == 50
        assert len(result["superior"]) == 50
        assert len(result["inferior"]) == 50


# ─────────────────────────────────────────────────────────────────────────────
# Hi-Lo Activator
# ─────────────────────────────────────────────────────────────────────────────
class TestHiLoActivator:
    def test_estrutura_do_retorno(self, candles_sinteticos):
        maximas = [c["maxima"] for c in candles_sinteticos]
        minimas = [c["minima"] for c in candles_sinteticos]
        fechamentos = [c["fechamento"] for c in candles_sinteticos]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert set(result.keys()) == {
            "activator",
            "high_ma",
            "low_ma",
            "tendencia",
            "sinais",
        }

    def test_tamanhos_consistentes(self, candles_sinteticos):
        n = len(candles_sinteticos)
        maximas = [c["maxima"] for c in candles_sinteticos]
        minimas = [c["minima"] for c in candles_sinteticos]
        fechamentos = [c["fechamento"] for c in candles_sinteticos]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert len(result["activator"]) == n
        assert len(result["high_ma"]) == n
        assert len(result["low_ma"]) == n
        assert len(result["tendencia"]) == n
        assert len(result["sinais"]) == n

    def test_uptrend_termina_em_alta(self, candles_sinteticos):
        """Uptrend linear puro → última tendência == 'ALTA'."""
        maximas = [c["maxima"] for c in candles_sinteticos]
        minimas = [c["minima"] for c in candles_sinteticos]
        fechamentos = [c["fechamento"] for c in candles_sinteticos]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert result["tendencia"][-1] == "ALTA"

    def test_uptrend_nao_gera_venda(self, candles_sinteticos):
        """Uptrend puro → não há nenhum sinal 'VENDA'."""
        maximas = [c["maxima"] for c in candles_sinteticos]
        minimas = [c["minima"] for c in candles_sinteticos]
        fechamentos = [c["fechamento"] for c in candles_sinteticos]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert "VENDA" not in result["sinais"]

    def test_offset_1_bar(self):
        """high_ma[i] deve ser igual a sma(maximas, 10)[i-1] pra i >= 1.

        Essa é a diferença chave da implementação TradingView CHiLo: a SMA
        é deslocada 1 barra pra usar o valor do candle anterior.
        """
        maximas = [float(i) for i in range(50)]
        minimas = [float(i) - 0.5 for i in range(50)]
        fechamentos = [float(i) + 0.2 for i in range(50)]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        sma_maximas = sma(maximas, 10)
        # result["high_ma"][i] == sma_maximas[i-1] pra todo i >= 1
        for i in range(1, 50):
            assert result["high_ma"][i] == sma_maximas[i - 1]

    def test_primeira_posicao_high_ma_e_none(self):
        """high_ma[0] sempre é None (offset de 1 barra)."""
        maximas = [float(i) for i in range(30)]
        minimas = [float(i) - 0.5 for i in range(30)]
        fechamentos = [float(i) + 0.2 for i in range(30)]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert result["high_ma"][0] is None
        assert result["low_ma"][0] is None

    def test_reversao_gera_venda(self):
        """Série crescente depois decrescente → pelo menos 1 sinal 'VENDA'."""
        # 30 crescentes seguidos de 30 decrescentes, diferença grande o bastante
        # pra forçar Hi-Lo cruzar pra baixo
        vals = list(range(10, 40)) + list(range(39, 9, -1))
        maximas = [float(v) + 1 for v in vals]
        minimas = [float(v) - 1 for v in vals]
        fechamentos = [float(v) for v in vals]
        result = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        assert "VENDA" in result["sinais"]
