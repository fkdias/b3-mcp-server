"""Testes de sizing parametrizado para `simular_opcoes_hilo`.

Cobre:
- Backward compatibility do modo 'agregado' (default)
- Os 4 modos novos de sizing (lote_fixo, fracao_banca, teto_absoluto,
  fracao_capital)
- Validação de parâmetros e erros esperados
- Consistência da equity curve e campos extras nas operações
- Anchor numérico em PETR4 offline reproduzindo resultados conhecidos
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.options_sim import simular_opcoes_hilo


# ───────────────────────── helpers ─────────────────────────
def _parse_pct(txt: str) -> float:
    """Converte '+154,60%' -> 154.60."""
    return float(txt.replace("%", "").replace(",", "."))


# ────────────────── backward compatibility ──────────────────
def test_sizing_agregado_default(candles_petr4):
    """Sem parâmetros novos, comportamento legado preservado (sem seção sizing)."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo("PETR4", offline=True)

    # Contrato legado: chaves exatas
    assert set(r.keys()) == {
        "ticker",
        "premissas",
        "resumo",
        "operacoes",
        "disclaimer",
    }
    assert "sizing" not in r
    assert "always_in_market_quebrado" not in r

    # Operacoes não devem carregar campos de sizing
    for op in r["operacoes"]:
        for campo in ("lotes", "custo_total_rs", "pnl_trade_rs", "banca_pos_trade"):
            assert campo not in op, f"Campo {campo!r} vazou no modo agregado"


def test_sizing_agregado_ignora_banca_inicial(candles_petr4):
    """Modo 'agregado' deve ignorar banca_inicial passada."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r_sem = simular_opcoes_hilo("PETR4", offline=True)
    r_com = simular_opcoes_hilo("PETR4", offline=True, banca_inicial=9999, sizing_mode="agregado")

    # Dicts idênticos
    assert r_sem["resumo"] == r_com["resumo"]
    assert len(r_sem["operacoes"]) == len(r_com["operacoes"])
    assert "sizing" not in r_com


# ───────────────────── modos de sizing ─────────────────────
def test_sizing_lote_fixo_basico(candles_petr4):
    """1 lote fixo deve gerar equity curve e métricas consistentes."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=2000,
        sizing_mode="lote_fixo",
        sizing_valor=1,
    )

    s = r["sizing"]
    assert s["modo"] == "lote_fixo"
    assert s["banca_inicial"] == 2000.0
    assert s["lote_tamanho"] == 100
    assert s["trades_executados"] > 0
    assert s["total_lotes"] == s["trades_executados"]  # 1 lote por trade
    assert len(s["equity_curve"]) >= 2


def test_sizing_fracao_banca_dinamico(candles_petr4):
    """15% da banca corrente gera volume dinâmico crescente."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=2000,
        sizing_mode="fracao_banca",
        sizing_valor=0.15,
    )
    s = r["sizing"]
    assert s["modo"] == "fracao_banca"
    # Deve fechar em território positivo com essa estratégia no PETR4
    assert s["lucro_liquido"] > 0
    # Retorno conhecido ~+154,60% (tolerância de 10 pp)
    ret = _parse_pct(s["retorno_pct"])
    assert 140.0 <= ret <= 170.0


def test_sizing_teto_absoluto(candles_petr4):
    """Teto de R$ 1000 por trade com banca de 10k."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=10000,
        sizing_mode="teto_absoluto",
        sizing_valor=1000,
    )
    s = r["sizing"]
    assert s["modo"] == "teto_absoluto"

    # Nenhum custo_total_rs deve exceder o teto
    for op in r["operacoes"]:
        assert op["custo_total_rs"] <= 1000.0 + 1e-6

    ret = _parse_pct(s["retorno_pct"])
    assert 140.0 <= ret <= 180.0


def test_sizing_fracao_capital_equivale_teto_absoluto(candles_petr4):
    """fracao_capital(0.1) com banca 10k ≡ teto_absoluto 1000."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r_teto = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=10000,
        sizing_mode="teto_absoluto",
        sizing_valor=1000,
    )
    r_frac = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=10000,
        sizing_mode="fracao_capital",
        sizing_valor=0.10,
    )

    s_teto = r_teto["sizing"]
    s_frac = r_frac["sizing"]
    assert s_teto["banca_final"] == s_frac["banca_final"]
    assert s_teto["total_lotes"] == s_frac["total_lotes"]
    assert s_teto["lucro_liquido"] == s_frac["lucro_liquido"]
    assert s_teto["retorno_pct"] == s_frac["retorno_pct"]


def test_sizing_skip_sem_caixa(candles_petr4):
    """Banca minúscula força skips sem quebrar a simulação."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    # 5 reais de banca jamais comporta 1 lote (prêmio * 100 >> 5)
    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=5,
        sizing_mode="lote_fixo",
        sizing_valor=1,
    )
    s = r["sizing"]
    assert s["trades_executados"] == 0
    assert s["trades_pulados"] > 0
    assert r["always_in_market_quebrado"] is True
    # Banca intocada
    assert s["banca_final"] == 5.0


# ───────────────────── validações ─────────────────────
def test_sizing_valida_banca_obrigatoria():
    """Modo não-agregado sem banca_inicial → ValueError."""
    with pytest.raises(ValueError, match="banca_inicial obrigatória"):
        simular_opcoes_hilo(
            "PETR4",
            offline=True,
            sizing_mode="lote_fixo",
            sizing_valor=1,
        )


def test_sizing_valida_modo_invalido():
    """sizing_mode desconhecido → ValueError listando os válidos."""
    with pytest.raises(ValueError, match="sizing_mode inválido"):
        simular_opcoes_hilo(
            "PETR4",
            offline=True,
            banca_inicial=1000,
            sizing_mode="martingale",
        )


def test_sizing_valida_fracao_fora_do_intervalo():
    """fracao_banca com valor > 1 → ValueError."""
    with pytest.raises(ValueError, match="intervalo"):
        simular_opcoes_hilo(
            "PETR4",
            offline=True,
            banca_inicial=1000,
            sizing_mode="fracao_banca",
            sizing_valor=1.5,
        )


def test_sizing_valida_lote_fixo_minimo():
    """lote_fixo com valor < 1 → ValueError."""
    with pytest.raises(ValueError, match=">= 1"):
        simular_opcoes_hilo(
            "PETR4",
            offline=True,
            banca_inicial=1000,
            sizing_mode="lote_fixo",
            sizing_valor=0,
        )


# ───────────────── consistência da equity curve ─────────────────
def test_sizing_equity_curve_consistente(candles_petr4):
    """Soma dos pnl_trade_rs das operações == banca_final - banca_inicial."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=10000,
        sizing_mode="teto_absoluto",
        sizing_valor=1000,
    )
    s = r["sizing"]
    soma_pnl = sum(op["pnl_trade_rs"] for op in r["operacoes"])
    esperado = s["banca_final"] - s["banca_inicial"]
    # Tolerância de arredondamento
    assert abs(soma_pnl - esperado) < 1.0


def test_sizing_petr4_teto_1000_reproduz_resultado_conhecido(candles_petr4):
    """Anchor numérico: PETR4 offline, banca 10k, teto R$ 1000."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=10000,
        sizing_mode="teto_absoluto",
        sizing_valor=1000,
    )
    ret = _parse_pct(r["sizing"]["retorno_pct"])
    assert 140.0 <= ret <= 180.0, f"Retorno fora do esperado: {ret}"


def test_sizing_operacoes_tem_campos_extras(candles_petr4):
    """Modo não-agregado injeta lotes, custo_total_rs, pnl_trade_rs, banca_pos_trade."""
    if candles_petr4 is None:
        pytest.skip("Dataset PETR4 offline indisponível")

    r = simular_opcoes_hilo(
        "PETR4",
        offline=True,
        banca_inicial=5000,
        sizing_mode="lote_fixo",
        sizing_valor=1,
    )
    assert r["operacoes"]
    for op in r["operacoes"]:
        assert "lotes" in op
        assert "custo_total_rs" in op
        assert "pnl_trade_rs" in op
        assert "banca_pos_trade" in op
        assert op["lotes"] == 1
        # custo = premio_pago * 100 * 1
        assert abs(op["custo_total_rs"] - op["premio_pago"] * 100) < 0.01
