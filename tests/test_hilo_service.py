"""Testes pros helpers privados + integração offline do `hilo_service`.

Escopo:
- Funções privadas puras: `_calcular_suporte_resistencia`, `_calcular_volatilidade`,
  `_calcular_performance_trade`, `_avaliar_volume`, `_formatar_trades_com_acumulado`,
  `_calcular_metricas_risco`.
- Integração end-to-end do `analisar_hilo(..., offline=True)` com dataset real
  PETR4 (~750 candles, refresh 3 anos).

Zero mocking de HTTP: só modo offline.
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.hilo_service import (
    _avaliar_volume,
    _calcular_metricas_risco,
    _calcular_performance_trade,
    _calcular_suporte_resistencia,
    _calcular_volatilidade,
    _carregar_offline,
    _formatar_trades_com_acumulado,
    _listar_offline_disponiveis,
    analisar_hilo,
)
from b3_mcp.core.services.indicators_calc import calc_hilo_activator


# ─────────────────────────────────────────────────────────────────────────────
# _calcular_suporte_resistencia
# ─────────────────────────────────────────────────────────────────────────────
class TestCalcularSuporteResistencia:
    def test_estrutura_do_retorno(self, candles_sinteticos):
        result = _calcular_suporte_resistencia(candles_sinteticos)
        assert set(result.keys()) == {
            "suporte_20d",
            "resistencia_20d",
            "maxima_5d",
            "minima_5d",
        }

    def test_uptrend_linear_valores_conhecidos(self, candles_sinteticos):
        """Uptrend 30 candles (máximas 11..40, mínimas 9..38).

        Janela=20 pega os últimos 20 → índices 10..29:
        - resistência_20d = max(maximas[10:30]) = 40.0
        - suporte_20d = min(minimas[10:30]) = 19.0
        Últimos 5:
        - maxima_5d = max(maximas[25:30]) = 40.0
        - minima_5d = min(minimas[25:30]) = 34.0
        """
        result = _calcular_suporte_resistencia(candles_sinteticos, janela=20)
        assert result["resistencia_20d"] == 40.0
        assert result["suporte_20d"] == 19.0
        assert result["maxima_5d"] == 40.0
        assert result["minima_5d"] == 34.0

    def test_filtra_zeros(self):
        """Valores 0 em máxima/mínima devem ser ignorados."""
        candles = [
            {"maxima": 0, "minima": 0, "fechamento": 10.0, "data": "2025-01-01"},
            {"maxima": 15.0, "minima": 12.0, "fechamento": 13.0, "data": "2025-01-02"},
            {"maxima": 14.0, "minima": 11.0, "fechamento": 13.5, "data": "2025-01-03"},
        ]
        result = _calcular_suporte_resistencia(candles, janela=20)
        assert result["resistencia_20d"] == 15.0
        assert result["suporte_20d"] == 11.0

    def test_janela_maior_que_candles(self, candles_sinteticos):
        """Janela > len(candles) → pega tudo (slicing negativo seguro)."""
        result = _calcular_suporte_resistencia(candles_sinteticos, janela=100)
        # minima global = 9.0, maxima global = 40.0
        assert result["suporte_20d"] == 9.0
        assert result["resistencia_20d"] == 40.0


# ─────────────────────────────────────────────────────────────────────────────
# _calcular_volatilidade
# ─────────────────────────────────────────────────────────────────────────────
class TestCalcularVolatilidade:
    def test_dados_insuficientes(self):
        """< janela elementos → dict com None."""
        result = _calcular_volatilidade([1.0, 2.0, 3.0], janela=20)
        assert result == {"volatilidade_20d": None}

    def test_serie_constante(self):
        """Preço constante → desvio padrão zero."""
        result = _calcular_volatilidade([10.0] * 25, janela=20)
        assert result["volatilidade_20d"] == 0.0
        assert result["desvio_padrao"] == 0.0

    def test_serie_crescente_positiva(self, fechamentos_sinteticos):
        """Série determinística → volatilidade_20d positiva conhecida."""
        # fechamentos = [10.5, 11.5, ..., 39.5] (30 valores)
        result = _calcular_volatilidade(fechamentos_sinteticos, janela=20)
        assert result["volatilidade_20d"] is not None
        assert result["volatilidade_20d"] > 0
        assert result["desvio_padrao"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# _calcular_performance_trade
# ─────────────────────────────────────────────────────────────────────────────
class TestCalcularPerformanceTrade:
    def test_menos_de_2_sinais_retorna_none(self):
        assert _calcular_performance_trade([]) is None
        assert (
            _calcular_performance_trade([{"sinal": "COMPRA", "preco": 10, "data": "X"}])
            is None
        )

    def test_par_venda_compra_retorna_dict(self):
        """Lista em ordem reversa (mais recente primeiro): VENDA seguida de COMPRA."""
        sinais = [
            {"sinal": "VENDA", "preco": 12.0, "data": "2025-01-10"},
            {"sinal": "COMPRA", "preco": 10.0, "data": "2025-01-01"},
        ]
        result = _calcular_performance_trade(sinais)
        assert result is not None
        assert result["entrada"] == "2025-01-01"
        assert result["saida"] == "2025-01-10"

    def test_so_compras_retorna_none(self):
        """Sem nenhum sinal VENDA → não há trade fechado."""
        sinais = [
            {"sinal": "COMPRA", "preco": 10.0, "data": "2025-01-01"},
            {"sinal": "COMPRA", "preco": 11.0, "data": "2025-01-02"},
        ]
        assert _calcular_performance_trade(sinais) is None

    def test_par_compra_venda_retorna_short(self):
        """COMPRA (atual) + VENDA (anterior) → fechou um SHORT (ganha caindo)."""
        # Ordem reversa (mais recente primeiro): COMPRA seguida de VENDA
        sinais = [
            {"sinal": "COMPRA", "preco": 8.0, "data": "2025-01-10"},  # mais recente
            {"sinal": "VENDA", "preco": 10.0, "data": "2025-01-01"},  # anterior
        ]
        result = _calcular_performance_trade(sinais)
        assert result is not None
        assert result["direcao"] == "SHORT"
        # SHORT: entrada (VENDA) 10 → saida (COMPRA) 8 → lucro 2 (positivo)
        assert result["entrada"] == "2025-01-01"
        assert result["saida"] == "2025-01-10"
        assert "+" in result["resultado_pct"] or "20" in result["resultado_pct"]


# ─────────────────────────────────────────────────────────────────────────────
# _avaliar_volume
# ─────────────────────────────────────────────────────────────────────────────
class TestAvaliarVolume:
    def test_volumes_insuficientes(self):
        """Menos de 21 volumes válidos → N/A."""
        candles = [
            {"volume": 100_000, "maxima": 10, "minima": 9, "fechamento": 9.5}
            for _ in range(10)
        ]
        result = _avaliar_volume(candles)
        assert result["volume_relativo"] == "N/A"
        assert result["volume_atual"] == 0

    @pytest.mark.parametrize(
        "atual,media,esperado",
        [
            (3_000_000, 1_000_000, "MUITO ACIMA da média"),  # 3.0x
            (1_500_000, 1_000_000, "ACIMA da média"),  # 1.5x
            (1_000_000, 1_000_000, "NORMAL"),  # 1.0x
            (500_000, 1_000_000, "ABAIXO da média"),  # 0.5x
            (200_000, 1_000_000, "MUITO ABAIXO da média"),  # 0.2x
        ],
    )
    def test_classificacao_por_ratio(self, atual, media, esperado):
        """5 zonas de classificação por ratio volume_atual / volume_medio."""
        # 20 candles de base com volume=media + 1 candle atual com volume=atual
        candles = [
            {"volume": media, "maxima": 10, "minima": 9, "fechamento": 9.5}
            for _ in range(20)
        ]
        candles.append({"volume": atual, "maxima": 10, "minima": 9, "fechamento": 9.5})
        result = _avaliar_volume(candles)
        assert result["volume_classificacao"] == esperado

    def test_estrutura_do_retorno_com_dados_suficientes(self):
        candles = [
            {"volume": 1_000_000, "maxima": 10, "minima": 9, "fechamento": 9.5}
            for _ in range(25)
        ]
        result = _avaliar_volume(candles)
        assert "volume_atual" in result
        assert "volume_atual_fmt" in result
        assert "volume_medio_20d" in result
        assert "volume_medio_fmt" in result
        assert "volume_relativo" in result
        assert "volume_classificacao" in result


# ─────────────────────────────────────────────────────────────────────────────
# _formatar_trades_com_acumulado
# ─────────────────────────────────────────────────────────────────────────────
class TestFormatarTradesComAcumulado:
    def test_lista_vazia(self):
        assert _formatar_trades_com_acumulado([]) == []

    def test_chaves_do_retorno(self):
        trades = [
            {
                "direcao": "LONG",
                "entrada_data": "2025-01-01",
                "saida_data": "2025-01-10",
                "entrada_preco": 10.0,
                "saida_preco": 11.0,
                "resultado_pct": 10.0,
                "dias": 9,
                "max_drawdown_trade": 2.5,
                "tipo": "WIN",
                "motivo_saida": "REVERSAO",
            }
        ]
        result = _formatar_trades_com_acumulado(trades)
        assert len(result) == 1
        assert set(result[0].keys()) == {
            "direcao",
            "entrada",
            "saida",
            "resultado",
            "acumulado",
            "dias",
            "dd_trade",
            "tipo",
            "saida_por",
        }
        assert result[0]["tipo"] == "WIN"
        assert result[0]["direcao"] == "LONG"
        # Long fechou por reversao → sinal oposto é VENDA
        assert "VENDA" in result[0]["saida_por"]
        assert "reversao" in result[0]["saida_por"].lower()

    def test_short_fim_periodo_tem_saida_por_correto(self):
        """SHORT fechado por FIM_PERIODO deve mostrar texto apropriado."""
        trades = [
            {
                "direcao": "SHORT",
                "entrada_data": "2025-01-01",
                "saida_data": "2025-01-10",
                "entrada_preco": 10.0,
                "saida_preco": 8.0,
                "resultado_pct": 20.0,
                "dias": 9,
                "max_drawdown_trade": 0,
                "tipo": "WIN",
                "motivo_saida": "FIM_PERIODO",
            }
        ]
        result = _formatar_trades_com_acumulado(trades)
        assert result[0]["direcao"] == "SHORT"
        assert "Fim do periodo" in result[0]["saida_por"]

    def test_acumulado_composto(self):
        """Equity composta: 100 * (1.10) * (1.10) = 121 → acumulado ~21%."""
        trades = [
            {
                "entrada_data": "2025-01-01",
                "saida_data": "2025-01-05",
                "entrada_preco": 10.0,
                "saida_preco": 11.0,
                "resultado_pct": 10.0,
                "dias": 4,
                "max_drawdown_trade": 0,
                "tipo": "WIN",
            },
            {
                "entrada_data": "2025-01-10",
                "saida_data": "2025-01-15",
                "entrada_preco": 11.0,
                "saida_preco": 12.1,
                "resultado_pct": 10.0,
                "dias": 5,
                "max_drawdown_trade": 0,
                "tipo": "WIN",
            },
        ]
        result = _formatar_trades_com_acumulado(trades)
        # Segundo trade: equity = 100 * 1.1 * 1.1 = 121 → acumulado = 21% (composto)
        assert "21" in result[1]["acumulado"]


# ─────────────────────────────────────────────────────────────────────────────
# _calcular_metricas_risco
# ─────────────────────────────────────────────────────────────────────────────
class TestCalcularMetricasRisco:
    def test_zero_trades_retorna_placeholders(self, candles_sinteticos):
        """Uptrend puro nunca gera VENDA → zero trades fechados."""
        maximas = [c["maxima"] for c in candles_sinteticos]
        minimas = [c["minima"] for c in candles_sinteticos]
        fechamentos = [c["fechamento"] for c in candles_sinteticos]
        hilo_data = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        result = _calcular_metricas_risco(candles_sinteticos, hilo_data)
        assert result["total_trades"] == 0
        assert result["win_rate"] == "N/A"
        assert result["profit_factor"] == "N/A"
        assert result["trades"] == []

    def test_equity_curve_existe_e_comeca_em_100(self, candles_petr4):
        """Regressão Fase 11: equity_curve é obrigatória e parte de 100."""
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        maximas = [c["maxima"] for c in candles_petr4]
        minimas = [c["minima"] for c in candles_petr4]
        fechamentos = [c["fechamento"] for c in candles_petr4]
        hilo_data = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        result = _calcular_metricas_risco(candles_petr4, hilo_data)
        assert "equity_curve" in result
        assert result["equity_curve"][0] == 100
        assert len(result["equity_curve"]) == result["total_trades"] + 1

    def test_profit_factor_infinito_quando_so_wins(self):
        """Sequência long/short always-in-market com todos os trades WIN.

        Desenho: preço sobe 10→14 (LONG wins), depois desce 14→10 (SHORT wins).
        COMPRA no idx 0, VENDA no idx 4 (reverte LONG→SHORT), último candle
        idx 8 fecha SHORT via FIM_PERIODO.
        """
        fechamentos = [10, 11, 12, 13, 14, 13, 12, 11, 10]
        candles = [
            {
                "data": f"2025-01-{i+1:02d}",
                "abertura": fechamentos[i],
                "maxima": fechamentos[i] + 0.5,
                "minima": fechamentos[i] - 0.5,
                "fechamento": fechamentos[i],
                "volume": 1_000_000,
            }
            for i in range(9)
        ]
        hilo_data = {
            "sinais": [None] * 9,
            "tendencia": ["ALTA"] * 9,
            "activator": [10.0] * 9,
            "high_ma": [11.0] * 9,
            "low_ma": [9.0] * 9,
        }
        hilo_data["sinais"][0] = "COMPRA"   # abre LONG @ 10
        hilo_data["sinais"][4] = "VENDA"    # fecha LONG @ 14 (WIN), abre SHORT @ 14
        # Último candle (idx 8, preço 10) fecha SHORT via FIM_PERIODO (WIN)
        result = _calcular_metricas_risco(candles, hilo_data)
        assert result["total_trades"] == 2
        assert result["wins"] == 2
        assert result["losses"] == 0
        assert result["profit_factor"] == float("inf")

    def test_trades_tem_direcao_long_e_short(self):
        """Sequência com 2 trades: LONG fechado por reversao + SHORT residual."""
        fechamentos = [10, 11, 12, 13, 14, 13, 12, 11, 10]
        candles = [
            {
                "data": f"2025-01-{i+1:02d}",
                "abertura": fechamentos[i],
                "maxima": fechamentos[i] + 0.5,
                "minima": fechamentos[i] - 0.5,
                "fechamento": fechamentos[i],
                "volume": 1_000_000,
            }
            for i in range(9)
        ]
        hilo_data = {
            "sinais": [None] * 9,
            "tendencia": ["ALTA"] * 9,
            "activator": [10.0] * 9,
            "high_ma": [11.0] * 9,
            "low_ma": [9.0] * 9,
        }
        hilo_data["sinais"][0] = "COMPRA"
        hilo_data["sinais"][4] = "VENDA"
        result = _calcular_metricas_risco(candles, hilo_data)
        trades_raw = result["trades"]
        assert trades_raw[0]["direcao"] == "LONG"
        assert trades_raw[1]["direcao"] == "SHORT"
        # Último trade é o residual do fim do período
        assert "Fim do periodo" in trades_raw[1]["saida_por"]
        # Primeiro trade saiu por reversao
        assert "reversao" in trades_raw[0]["saida_por"].lower()

    def test_chaves_obrigatorias_com_trades(self, candles_petr4):
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        maximas = [c["maxima"] for c in candles_petr4]
        minimas = [c["minima"] for c in candles_petr4]
        fechamentos = [c["fechamento"] for c in candles_petr4]
        hilo_data = calc_hilo_activator(maximas, minimas, fechamentos, periodo=10)
        result = _calcular_metricas_risco(candles_petr4, hilo_data)
        chaves_esperadas = {
            "total_trades",
            "win_rate",
            "wins",
            "losses",
            "payout_medio",
            "payout_medio_wins",
            "payout_medio_losses",
            "profit_factor",
            "max_drawdown",
            "expectativa",
            "dias_medio_trade",
            "maior_win",
            "maior_loss",
            "max_wins_consecutivos",
            "max_losses_consecutivos",
            "retorno_acumulado",
            "equity_final",
            "equity_curve",
            "trades",
        }
        assert chaves_esperadas.issubset(set(result.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# _carregar_offline / _listar_offline_disponiveis
# ─────────────────────────────────────────────────────────────────────────────
class TestOfflineLoader:
    def test_ticker_existente_carrega_candles(self):
        candles = _carregar_offline("PETR4")
        assert candles is not None
        assert len(candles) > 100  # refresh 3y → ~750 candles
        # cada candle tem o schema esperado
        for campo in ("data", "abertura", "maxima", "minima", "fechamento", "volume"):
            assert campo in candles[0]

    def test_ticker_inexistente_retorna_none(self):
        assert _carregar_offline("ZZZZ999") is None

    def test_listar_disponiveis_tem_petr4(self):
        disponiveis = _listar_offline_disponiveis()
        assert "PETR4" in disponiveis
        assert len(disponiveis) >= 20  # esperado: 26 tickers após limpeza EMBR3/MRFG3


# ─────────────────────────────────────────────────────────────────────────────
# analisar_hilo (end-to-end offline)
# ─────────────────────────────────────────────────────────────────────────────
class TestAnalisarHiloOffline:
    def test_estrutura_do_retorno_completa(self):
        result = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
        chaves_esperadas = {
            "ticker",
            "setor",
            "data_analise",
            "hilo",
            "preco",
            "indicadores",
            "volume",
            "suporte_resistencia",
            "volatilidade",
            "cenarios",
            "metricas_risco",
            "ultimo_sinal",
            "historico_sinais",
            "resumo",
            "total_candles",
            "grafico",
        }
        assert chaves_esperadas.issubset(set(result.keys()))

    def test_ticker_inexistente_raises(self):
        with pytest.raises(ValueError, match="Dados offline não disponíveis"):
            analisar_hilo("ZZZZ999", offline=True, gerar_grafico=False)

    def test_gerar_grafico_false_deixa_grafico_none(self):
        result = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
        assert result["grafico"] is None

    def test_ticker_limpo_normaliza_entrada(self):
        """Entrada com .SA deve ser tratada igual ao ticker limpo."""
        r1 = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
        r2 = analisar_hilo("petr4.sa", offline=True, gerar_grafico=False)
        assert r1["ticker"] == r2["ticker"] == "PETR4"
        assert r1["total_candles"] == r2["total_candles"]

    def test_metricas_risco_tem_trades_com_3_anos_de_historico(self):
        """Com dataset de 3 anos (~750 candles), esperamos > 10 trades fechados."""
        result = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
        assert result["metricas_risco"]["total_trades"] > 5
        assert isinstance(result["metricas_risco"]["equity_curve"], list)

    def test_tendencia_em_uma_das_classes_validas(self):
        result = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
        assert result["hilo"]["tendencia"] in ("ALTA", "BAIXA", None)
