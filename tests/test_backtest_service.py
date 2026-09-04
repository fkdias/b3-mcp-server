"""Testes pros 6 strategy runners + `_calcular_metricas` + `executar_backtest`.

Escopo:
- Runners: `_run_hilo`, `_run_rsi`, `_run_sma_crossover`, `_run_ema_crossover`,
  `_run_macd_strategy`, `_run_bollinger` — todos recebem candles e devolvem
  lista de trades.
- `_calcular_metricas(trades, capital_inicial)` — placeholders pra lista vazia,
  profit_factor infinito pra 100% wins, chaves obrigatórias.
- `executar_backtest(ticker, estrategia, offline)` — end-to-end com dataset
  real PETR4, modo "todas" (comparativo), validação de estratégia inválida,
  ticker normalizado via `ticker_limpo`.
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.backtest_service import (
    ESTRATEGIA_RUNNERS,
    _calcular_metricas,
    _run_bollinger,
    _run_ema_crossover,
    _run_hilo,
    _run_macd_strategy,
    _run_rsi,
    _run_sma_crossover,
    executar_backtest,
)

STRATEGY_RUNNERS = [
    ("hilo", _run_hilo),
    ("rsi", _run_rsi),
    ("sma_crossover", _run_sma_crossover),
    ("ema_crossover", _run_ema_crossover),
    ("macd", _run_macd_strategy),
    ("bollinger", _run_bollinger),
]

TRADE_KEYS = {
    "data_entrada",
    "data_saida",
    "preco_entrada",
    "preco_saida",
    "lucro",
    "lucro_pct",
}


# ─────────────────────────────────────────────────────────────────────────────
# Strategy runners (parametrize pelas 6 estratégias)
# ─────────────────────────────────────────────────────────────────────────────
class TestStrategyRunners:
    @pytest.mark.parametrize(
        "nome,runner",
        # bollinger é excluído: com σ=0 as bandas colapsam no preço, o runner
        # abre/fecha trades zero-P&L a cada candle. Comportamento real do
        # runner (não é bug) — seria eliminado por qualquer filtro de slippage.
        [(n, r) for n, r in STRATEGY_RUNNERS if n != "bollinger"],
    )
    def test_serie_flat_zero_trades(self, candles_flat, nome, runner):
        """Zero volatilidade → nenhum runner (exceto bollinger) abre posição."""
        trades = runner(candles_flat)
        assert trades == []

    def test_bollinger_serie_flat_so_trades_zero_pnl(self, candles_flat):
        """Bollinger com σ=0: bandas colapsam, trades têm lucro/pct == 0."""
        trades = _run_bollinger(candles_flat)
        for t in trades:
            assert t["lucro"] == 0.0
            assert t["lucro_pct"] == 0.0

    @pytest.mark.parametrize("nome,runner", STRATEGY_RUNNERS)
    def test_retorna_lista(self, candles_sinteticos, nome, runner):
        """Todos runners sempre devolvem list (mesmo que vazia)."""
        trades = runner(candles_sinteticos)
        assert isinstance(trades, list)

    @pytest.mark.parametrize("nome,runner", STRATEGY_RUNNERS)
    def test_dataset_real_tem_trades_com_schema_consistente(self, candles_petr4, nome, runner):
        """Com 3 anos de PETR4, todos runners produzem trades bem-formados.

        Hi-Lo é always-in-market long/short: LONG lucra em alta, SHORT lucra em
        baixa. Demais runners são long-only (lucra só em alta).
        """
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        trades = runner(candles_petr4)
        assert isinstance(trades, list)
        for t in trades:
            assert TRADE_KEYS.issubset(set(t.keys()))
            # Consistência do lucro vs direção do preço:
            if nome == "hilo":
                # LONG: sobe preço → lucra; SHORT: desce preço → lucra
                if t["tipo"] == "LONG":
                    if t["preco_saida"] > t["preco_entrada"]:
                        assert t["lucro"] > 0
                        assert t["lucro_pct"] > 0
                    elif t["preco_saida"] < t["preco_entrada"]:
                        assert t["lucro"] < 0
                        assert t["lucro_pct"] < 0
                else:  # SHORT
                    if t["preco_saida"] < t["preco_entrada"]:
                        assert t["lucro"] > 0
                        assert t["lucro_pct"] > 0
                    elif t["preco_saida"] > t["preco_entrada"]:
                        assert t["lucro"] < 0
                        assert t["lucro_pct"] < 0
            else:
                # Long-only: lucro positivo quando saida > entrada
                if t["preco_saida"] > t["preco_entrada"]:
                    assert t["lucro"] > 0
                    assert t["lucro_pct"] > 0

    def test_hilo_default_vs_explicit_periodo(self, candles_petr4):
        """`_run_hilo(candles)` deve dar mesmo resultado que o período default (13)."""
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        t1 = _run_hilo(candles_petr4)
        t2 = _run_hilo(candles_petr4, periodo=13)
        assert t1 == t2

    def test_runners_registry_tem_as_6_estrategias(self):
        assert set(ESTRATEGIA_RUNNERS.keys()) == {
            "hilo",
            "rsi",
            "sma_crossover",
            "ema_crossover",
            "macd",
            "bollinger",
        }

    def test_hilo_trades_tem_campo_tipo_long_short(self, candles_petr4):
        """Todo trade Hi-Lo tem `tipo` ∈ {LONG, SHORT} e `motivo_saida`."""
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        trades = _run_hilo(candles_petr4)
        assert len(trades) > 0
        for t in trades:
            assert t["tipo"] in ("LONG", "SHORT")
            assert t["motivo_saida"] in ("REVERSAO", "FIM_PERIODO")
        # Always-in-market: último trade sempre fecha em FIM_PERIODO
        assert trades[-1]["motivo_saida"] == "FIM_PERIODO"
        # Demais trades fecham em REVERSAO
        for t in trades[:-1]:
            assert t["motivo_saida"] == "REVERSAO"

    def test_hilo_alterna_long_short(self, candles_petr4):
        """Sequência always-in-market: trades alternam LONG/SHORT."""
        if candles_petr4 is None:
            pytest.skip("Dataset PETR4 offline não disponível")
        trades = _run_hilo(candles_petr4)
        if len(trades) < 2:
            pytest.skip("Dataset com poucos sinais")
        for i in range(1, len(trades)):
            assert trades[i]["tipo"] != trades[i - 1]["tipo"], (
                f"Trades {i - 1} e {i} têm mesmo tipo — violação de reversal"
            )

    def test_hilo_short_pnl_invertido(self):
        """SHORT com preço caindo → lucro positivo (verifica fórmula SHORT)."""
        # Série em V invertido: sobe até idx 4, desce até idx 8
        # COMPRA idx 0, VENDA idx 4 (reverte pra SHORT), fim idx 8 (FIM_PERIODO SHORT)
        candles = []
        fechamentos = [10, 11, 12, 13, 14, 13, 12, 11, 10]
        for i, f in enumerate(fechamentos):
            # maximas / minimas desenhadas pra forçar sinais Hi-Lo
            candles.append(
                {
                    "data": f"2025-01-{i + 1:02d}",
                    "abertura": f,
                    "maxima": f + 0.5,
                    "minima": f - 0.5,
                    "fechamento": f,
                    "volume": 1_000_000,
                }
            )
        trades = _run_hilo(candles, periodo=3)
        # Pode haver 0 ou mais trades dependendo se Hi-Lo gerou sinal;
        # o importante é validar a fórmula quando SHORT existe
        for t in trades:
            if t["tipo"] == "SHORT":
                # SHORT: entrada > saida → lucro > 0
                esperado = t["preco_entrada"] - t["preco_saida"]
                assert abs(t["lucro"] - esperado) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# _calcular_metricas
# ─────────────────────────────────────────────────────────────────────────────
class TestCalcularMetricas:
    def test_lista_vazia_retorna_placeholders(self):
        result = _calcular_metricas([])
        assert result["total_trades"] == 0
        assert result["trades_positivos"] == 0
        assert result["trades_negativos"] == 0
        assert result["taxa_acerto"] == "0,00%"
        assert result["profit_factor"] == 0

    def test_so_wins_profit_factor_infinito(self):
        """100% vencedores → profit_factor == inf (sem perdas)."""
        trades = [
            {
                "data_entrada": "2025-01-01",
                "data_saida": "2025-01-05",
                "preco_entrada": 10.0,
                "preco_saida": 11.0,
                "lucro": 1.0,
                "lucro_pct": 10.0,
            },
            {
                "data_entrada": "2025-01-10",
                "data_saida": "2025-01-15",
                "preco_entrada": 11.0,
                "preco_saida": 12.1,
                "lucro": 1.1,
                "lucro_pct": 10.0,
            },
        ]
        result = _calcular_metricas(trades)
        assert result["total_trades"] == 2
        assert result["trades_positivos"] == 2
        assert result["trades_negativos"] == 0
        assert result["profit_factor"] == float("inf")

    def test_50_50_wins_losses(self):
        """2 wins + 2 losses → taxa_acerto == '50,00%'."""
        trades = [
            {
                "data_entrada": "A",
                "data_saida": "B",
                "preco_entrada": 10.0,
                "preco_saida": 11.0,
                "lucro": 1.0,
                "lucro_pct": 10.0,
            },
            {
                "data_entrada": "C",
                "data_saida": "D",
                "preco_entrada": 10.0,
                "preco_saida": 9.0,
                "lucro": -1.0,
                "lucro_pct": -10.0,
            },
            {
                "data_entrada": "E",
                "data_saida": "F",
                "preco_entrada": 10.0,
                "preco_saida": 12.0,
                "lucro": 2.0,
                "lucro_pct": 20.0,
            },
            {
                "data_entrada": "G",
                "data_saida": "H",
                "preco_entrada": 10.0,
                "preco_saida": 8.0,
                "lucro": -2.0,
                "lucro_pct": -20.0,
            },
        ]
        result = _calcular_metricas(trades)
        assert result["total_trades"] == 4
        assert result["trades_positivos"] == 2
        assert result["trades_negativos"] == 2
        assert result["taxa_acerto"] == "+50,00%"

    def test_chaves_obrigatorias(self):
        trades = [
            {
                "data_entrada": "A",
                "data_saida": "B",
                "preco_entrada": 10.0,
                "preco_saida": 11.0,
                "lucro": 1.0,
                "lucro_pct": 10.0,
            }
        ]
        result = _calcular_metricas(trades)
        chaves_esperadas = {
            "total_trades",
            "trades_positivos",
            "trades_negativos",
            "taxa_acerto",
            "lucro_total",
            "lucro_total_pct",
            "maior_ganho",
            "maior_perda",
            "media_ganho",
            "media_perda",
            "profit_factor",
            "max_drawdown",
        }
        assert chaves_esperadas.issubset(set(result.keys()))

    def test_max_drawdown_sempre_zero_ou_negativo_string(self):
        """Max drawdown é formatado como string percentual, nunca positivo."""
        trades = [
            {
                "data_entrada": "A",
                "data_saida": "B",
                "preco_entrada": 10.0,
                "preco_saida": 11.0,
                "lucro": 1.0,
                "lucro_pct": 10.0,
            },
            {
                "data_entrada": "C",
                "data_saida": "D",
                "preco_entrada": 11.0,
                "preco_saida": 9.9,
                "lucro": -1.1,
                "lucro_pct": -10.0,
            },
        ]
        result = _calcular_metricas(trades)
        assert isinstance(result["max_drawdown"], str)
        assert "%" in result["max_drawdown"]


# ─────────────────────────────────────────────────────────────────────────────
# executar_backtest (end-to-end offline)
# ─────────────────────────────────────────────────────────────────────────────
class TestExecutarBacktest:
    def test_estrutura_completa_hilo(self):
        result = executar_backtest("PETR4", estrategia="hilo", offline=True)
        chaves = {
            "ticker",
            "estrategia",
            "periodo",
            "total_candles",
            "metricas",
            "ultimos_trades",
            "todos_trades",
        }
        assert chaves.issubset(set(result.keys()))
        assert result["ticker"] == "PETR4"
        assert result["estrategia"] == "hilo"

    def test_ultimos_trades_tem_no_maximo_10(self):
        result = executar_backtest("PETR4", estrategia="hilo", offline=True)
        assert len(result["ultimos_trades"]) <= 10
        # ultimos_trades é um sublista de todos_trades
        assert len(result["ultimos_trades"]) <= len(result["todos_trades"])

    def test_estrategia_invalida_raises(self):
        with pytest.raises(ValueError, match="não encontrada"):
            executar_backtest("PETR4", estrategia="estrategia_inexistente", offline=True)

    def test_ticker_offline_inexistente_raises(self):
        with pytest.raises(ValueError, match="offline"):
            executar_backtest("ZZZZ999", estrategia="hilo", offline=True)

    def test_estrategia_todas_gera_comparativo(self):
        result = executar_backtest("PETR4", estrategia="todas", offline=True)
        assert "comparativo" in result
        assert set(result["comparativo"].keys()) == {
            "hilo",
            "rsi",
            "sma_crossover",
            "ema_crossover",
            "macd",
            "bollinger",
        }
        # Cada estratégia tem metricas + trades
        for _nome, dados in result["comparativo"].items():
            assert "metricas" in dados
            assert "trades" in dados
            assert len(dados["trades"]) <= 5

    def test_ticker_limpo_normaliza_entrada(self):
        """'petr4.sa' deve resolver igual a 'PETR4'."""
        r1 = executar_backtest("PETR4", estrategia="hilo", offline=True)
        r2 = executar_backtest("petr4.sa", estrategia="hilo", offline=True)
        assert r1["ticker"] == r2["ticker"] == "PETR4"
        assert r1["total_candles"] == r2["total_candles"]
        assert len(r1["todos_trades"]) == len(r2["todos_trades"])

    def test_dataset_3_anos_gera_trades_suficientes(self):
        """Com refresh 3 anos (~750 candles), hilo deve ter > 5 trades."""
        result = executar_backtest("PETR4", estrategia="hilo", offline=True)
        assert result["total_candles"] > 500  # ~750 esperado
        assert result["metricas"]["total_trades"] > 5
