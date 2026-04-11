"""Testes de b3_service.py no modo offline.

Cobre as 6 funções públicas:
- `visao_setorial`, `scanner_setor`, `analise_indice`
- `screener_b3`, `plano_trade`, `fibonacci_levels`

Todos os testes rodam com `offline=True` para não depender de HTTP.
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.b3_service import (
    analise_indice,
    fibonacci_levels,
    plano_trade,
    scanner_setor,
    screener_b3,
    visao_setorial,
)


# ═══════════════════════════════════════════════
# visao_setorial
# ═══════════════════════════════════════════════
class TestVisaoSetorial:
    def test_retorna_dict_nao_vazio(self):
        r = visao_setorial(offline=True)
        assert isinstance(r, dict)
        assert len(r) > 0

    def test_cada_setor_tem_schema_consistente(self):
        r = visao_setorial(offline=True)
        for _setor, dados in r.items():
            for chave in ("ativos_alta", "ativos_baixa", "ativos", "total", "pct_alta", "momentum"):
                assert chave in dados
            assert dados["momentum"] in ("FORTE", "MODERADO", "FRACO")
            assert isinstance(dados["ativos"], list)
            assert dados["ativos_alta"] + dados["ativos_baixa"] <= dados["total"]

    def test_ordenacao_por_pct_alta_desc(self):
        r = visao_setorial(offline=True)
        pcts = [dados["pct_alta"] for dados in r.values()]
        assert pcts == sorted(pcts, reverse=True)

    def test_cada_ativo_tem_campos(self):
        r = visao_setorial(offline=True)
        for _setor, dados in r.items():
            for a in dados["ativos"]:
                assert "ticker" in a
                assert "tendencia" in a
                assert "preco" in a


# ═══════════════════════════════════════════════
# scanner_setor
# ═══════════════════════════════════════════════
class TestScannerSetor:
    def test_setor_valido_retorna_resultados(self):
        r = scanner_setor("Financeiro", offline=True)
        assert r["setor"] == "Financeiro"
        assert "total_ativos" in r
        assert isinstance(r["ativos"], list)
        assert r["total_ativos"] == len(r["ativos"])

    def test_setor_invalido_raises(self):
        with pytest.raises(ValueError, match="não encontrado"):
            scanner_setor("SetorInexistente", offline=True)

    def test_ativos_ordenados_por_dias_tendencia_desc(self):
        r = scanner_setor("Financeiro", offline=True)
        dias = [a.get("dias_tendencia", 0) for a in r["ativos"]]
        assert dias == sorted(dias, reverse=True)

    def test_ativos_tem_campos_esperados(self):
        r = scanner_setor("Financeiro", offline=True)
        if not r["ativos"]:
            pytest.skip("Sem ativos offline pro setor Financeiro")
        item = r["ativos"][0]
        for campo in ("ticker", "tendencia", "preco", "activator", "dias_tendencia", "rsi"):
            assert campo in item


# ═══════════════════════════════════════════════
# analise_indice
# ═══════════════════════════════════════════════
class TestAnaliseIndice:
    def test_ibovespa_offline(self):
        r = analise_indice("IBOVESPA", offline=True)
        assert r["indice"] == "IBOVESPA"
        for chave in ("total_analisados", "em_alta", "em_baixa", "pct_alta", "breadth", "ativos"):
            assert chave in r
        assert r["em_alta"] + r["em_baixa"] <= r["total_analisados"]

    def test_indice_invalido_raises(self):
        with pytest.raises(ValueError, match="não encontrado"):
            analise_indice("XPTO123", offline=True)

    def test_breadth_em_set_valido(self):
        r = analise_indice("IBOVESPA", offline=True)
        assert r["breadth"] in ("BULL", "BEAR", "NEUTRO", "N/A")

    def test_ativos_ordenados_por_dias_tendencia(self):
        r = analise_indice("IBOVESPA", offline=True)
        dias = [a.get("dias_tendencia", 0) for a in r["ativos"]]
        assert dias == sorted(dias, reverse=True)


# ═══════════════════════════════════════════════
# screener_b3
# ═══════════════════════════════════════════════
class TestScreenerB3:
    def test_sem_filtros_retorna_lista(self):
        r = screener_b3(offline=True)
        assert "filtros" in r
        assert "total" in r
        assert "resultados" in r
        assert r["total"] == len(r["resultados"])

    def test_filtro_tendencia_alta(self):
        r = screener_b3(filtro_tendencia="ALTA", offline=True)
        for item in r["resultados"]:
            assert item["tendencia"] == "ALTA"

    def test_filtro_tendencia_baixa(self):
        r = screener_b3(filtro_tendencia="BAIXA", offline=True)
        for item in r["resultados"]:
            assert item["tendencia"] == "BAIXA"

    def test_campos_internos_removidos(self):
        r = screener_b3(offline=True)
        for item in r["resultados"]:
            assert "_retorno_num" not in item
            assert "_pf_num" not in item

    def test_ordenacao_por_dias(self):
        r = screener_b3(ordenar_por="dias", offline=True)
        dias = [x.get("dias_tendencia", 0) for x in r["resultados"]]
        assert dias == sorted(dias, reverse=True)

    def test_min_profit_factor_zero_nao_filtra(self):
        """min_profit_factor=0 → todos passam no filtro PF."""
        r_all = screener_b3(offline=True)
        r_zero = screener_b3(min_profit_factor=0, offline=True)
        assert r_all["total"] == r_zero["total"]

    def test_filtros_ecoados_no_retorno(self):
        r = screener_b3(
            filtro_tendencia="ALTA",
            filtro_setor="Financeiro",
            min_profit_factor=1.5,
            ordenar_por="profit_factor",
            offline=True,
        )
        f = r["filtros"]
        assert f["tendencia"] == "ALTA"
        assert f["setor"] == "Financeiro"
        assert f["min_profit_factor"] == 1.5
        assert f["ordenar_por"] == "profit_factor"


# ═══════════════════════════════════════════════
# plano_trade
# ═══════════════════════════════════════════════
class TestPlanoTrade:
    def test_retorna_schema_completo(self):
        r = plano_trade("PETR4", offline=True)
        for chave in (
            "ticker",
            "tipo_operacao",
            "motivo",
            "tendencia",
            "preco_atual",
            "entrada_sugerida",
            "stop_loss",
            "alvo_1",
            "alvo_2",
            "risco_retorno_alvo1",
            "risco_retorno_alvo2",
            "activator",
            "rsi",
            "volume",
            "historico_hilo",
            "disclaimer",
        ):
            assert chave in r

    def test_tipo_operacao_valido(self):
        r = plano_trade("PETR4", offline=True)
        assert r["tipo_operacao"] in ("COMPRA", "AGUARDAR", "NEUTRO")

    def test_historico_hilo_tem_metricas(self):
        r = plano_trade("PETR4", offline=True)
        h = r["historico_hilo"]
        for chave in ("win_rate", "profit_factor", "max_drawdown", "payout_medio"):
            assert chave in h

    def test_ticker_limpo_aplicado(self):
        r1 = plano_trade("PETR4", offline=True)
        r2 = plano_trade("petr4.sa", offline=True)
        assert r1["ticker"] == r2["ticker"] == "PETR4"

    def test_disclaimer_presente(self):
        r = plano_trade("PETR4", offline=True)
        assert "educacional" in r["disclaimer"].lower()

    def test_multi_tickers_offline(self):
        for ticker in ("VALE3", "ITUB4", "WEGE3"):
            r = plano_trade(ticker, offline=True)
            assert r["tipo_operacao"] in ("COMPRA", "AGUARDAR", "NEUTRO")


# ═══════════════════════════════════════════════
# fibonacci_levels
# ═══════════════════════════════════════════════
class TestFibonacciLevels:
    def test_retorna_schema_completo(self):
        r = fibonacci_levels("PETR4", offline=True)
        for chave in (
            "ticker",
            "tendencia_hilo",
            "preco_atual",
            "topo_12m",
            "fundo_12m",
            "amplitude",
            "posicao_fibonacci",
            "retracao",
            "extensao",
            "suporte_fib_proximo",
            "resistencia_fib_proxima",
        ):
            assert chave in r

    def test_retracao_tem_7_niveis(self):
        r = fibonacci_levels("PETR4", offline=True)
        niveis_esperados = [
            "0.0% (Topo)",
            "23.6%",
            "38.2%",
            "50.0%",
            "61.8%",
            "78.6%",
            "100.0% (Fundo)",
        ]
        for n in niveis_esperados:
            assert n in r["retracao"]

    def test_extensao_tem_4_niveis(self):
        r = fibonacci_levels("PETR4", offline=True)
        for n in ("127.2%", "161.8%", "200.0%", "261.8%"):
            assert n in r["extensao"]

    def test_ticker_invalido_offline_raises(self):
        with pytest.raises(ValueError, match="offline"):
            fibonacci_levels("XXXX9", offline=True)

    def test_ticker_limpo_aplicado(self):
        r1 = fibonacci_levels("PETR4", offline=True)
        r2 = fibonacci_levels("petr4.sa", offline=True)
        assert r1["ticker"] == r2["ticker"] == "PETR4"

    def test_posicao_fibonacci_string_com_pct(self):
        r = fibonacci_levels("PETR4", offline=True)
        assert r["posicao_fibonacci"].endswith("%")
