"""Testes das funções puras de precificação em options_sim.py.

Cobre:
- `_norm_cdf` (aproximação Abramowitz-Stegun da CDF normal padrão)
- `black_scholes_call` / `black_scholes_put` (preço de opções europeias)
- `_calcular_volatilidade_historica` (vol anualizada via log-retornos)

Escopo: apenas funções puras. A simulação end-to-end (`simular_opcoes_hilo`)
já é coberta em `test_options_sim.py` com os 14 testes de sizing da Fase 15.
"""

from __future__ import annotations

import math

import pytest

from b3_mcp.core.services.options_sim import (
    _calcular_volatilidade_historica,
    _norm_cdf,
    black_scholes_call,
    black_scholes_put,
)


class TestNormCdf:
    """Aproximação Abramowitz-Stegun da CDF normal padrão (7.1.26)."""

    def test_mediana_em_zero(self):
        # Φ(0) = 0.5 exato
        assert abs(_norm_cdf(0.0) - 0.5) < 1e-7

    def test_simetria_complementar(self):
        # Φ(-x) + Φ(x) = 1
        for x in [0.5, 1.0, 1.5, 2.0, 3.0]:
            assert abs(_norm_cdf(-x) + _norm_cdf(x) - 1.0) < 1e-6

    @pytest.mark.parametrize(
        "x,esperado",
        [
            (1.0, 0.8413447),  # Φ(1) tabelado
            (1.645, 0.95),  # 95º percentil (usado em VaR)
            (1.96, 0.975),  # 97.5º percentil
            (2.0, 0.9772499),
            (2.576, 0.995),  # 99.5º percentil
            (3.0, 0.9986501),
        ],
    )
    def test_valores_tabelados(self, x, esperado):
        """Compara com tabela normal padrão. Aproximação tem erro máx ~7.5e-8."""
        assert abs(_norm_cdf(x) - esperado) < 1e-3

    def test_monotonicidade(self):
        # CDF é estritamente crescente
        valores = [_norm_cdf(x) for x in [-3, -2, -1, 0, 1, 2, 3]]
        for i in range(1, len(valores)):
            assert valores[i] > valores[i - 1]

    def test_limites_extremos(self):
        # Φ(x) → 0 quando x → -∞, Φ(x) → 1 quando x → +∞
        assert _norm_cdf(-10.0) < 1e-6
        assert _norm_cdf(10.0) > 1 - 1e-6


class TestBlackScholesCall:
    """Preço de call europeia ATM/ITM/OTM."""

    def test_valor_intrinseco_at_expiration(self):
        """T=0 → max(S-K, 0) (sem valor tempo)."""
        assert black_scholes_call(S=100, K=100, T=0, r=0.10, sigma=0.20) == 0
        assert black_scholes_call(S=110, K=100, T=0, r=0.10, sigma=0.20) == 10
        assert black_scholes_call(S=90, K=100, T=0, r=0.10, sigma=0.20) == 0

    def test_sigma_zero_degenera_pra_intrinseco(self):
        """sigma=0 → max(S-K, 0) (sem volatilidade, sem optionality)."""
        assert black_scholes_call(S=100, K=100, T=1, r=0.10, sigma=0) == 0
        assert black_scholes_call(S=110, K=100, T=1, r=0.10, sigma=0) == 10

    def test_atm_com_vol_retorna_positivo(self):
        """ATM com T e σ > 0 sempre tem valor tempo positivo."""
        preco = black_scholes_call(S=100, K=100, T=0.25, r=0.10, sigma=0.20)
        assert preco > 0

    def test_put_call_parity(self):
        """C - P = S - K·e^(-rT). Identidade fundamental."""
        S, K, T, r, sigma = 100, 100, 0.5, 0.10, 0.25
        c = black_scholes_call(S, K, T, r, sigma)
        p = black_scholes_put(S, K, T, r, sigma)
        lhs = c - p
        rhs = S - K * math.exp(-r * T)
        assert abs(lhs - rhs) < 1e-6

    def test_call_itm_vale_mais_que_otm(self):
        """Monotonicidade em S: call(S=110) > call(S=90)."""
        c_itm = black_scholes_call(S=110, K=100, T=0.25, r=0.10, sigma=0.20)
        c_otm = black_scholes_call(S=90, K=100, T=0.25, r=0.10, sigma=0.20)
        assert c_itm > c_otm

    def test_mais_vol_vale_mais(self):
        """Vega positiva: call(σ=0.40) > call(σ=0.10) com demais constantes."""
        c_low = black_scholes_call(S=100, K=100, T=0.25, r=0.10, sigma=0.10)
        c_high = black_scholes_call(S=100, K=100, T=0.25, r=0.10, sigma=0.40)
        assert c_high > c_low

    def test_mais_tempo_vale_mais_atm(self):
        """Theta negativa (pra ATM/ITM): call(T=1) > call(T=0.25)."""
        c_curto = black_scholes_call(S=100, K=100, T=0.25, r=0.10, sigma=0.25)
        c_longo = black_scholes_call(S=100, K=100, T=1.0, r=0.10, sigma=0.25)
        assert c_longo > c_curto

    def test_valor_conhecido_atm_hull(self):
        """Valor tabelado de Hull (Options, Futures and Other Derivatives, exemplo 15.6).

        S=42, K=40, T=0.5, r=0.10, σ=0.20 → c ≈ 4.76.
        """
        c = black_scholes_call(S=42, K=40, T=0.5, r=0.10, sigma=0.20)
        assert abs(c - 4.759) < 0.01


class TestBlackScholesPut:
    """Preço de put europeia."""

    def test_valor_intrinseco_at_expiration(self):
        assert black_scholes_put(S=100, K=100, T=0, r=0.10, sigma=0.20) == 0
        assert black_scholes_put(S=90, K=100, T=0, r=0.10, sigma=0.20) == 10
        assert black_scholes_put(S=110, K=100, T=0, r=0.10, sigma=0.20) == 0

    def test_sigma_zero_degenera_pra_intrinseco(self):
        assert black_scholes_put(S=100, K=100, T=1, r=0.10, sigma=0) == 0
        assert black_scholes_put(S=90, K=100, T=1, r=0.10, sigma=0) == 10

    def test_put_itm_vale_mais_que_otm(self):
        """Monotonicidade: put(S=90) > put(S=110)."""
        p_itm = black_scholes_put(S=90, K=100, T=0.25, r=0.10, sigma=0.20)
        p_otm = black_scholes_put(S=110, K=100, T=0.25, r=0.10, sigma=0.20)
        assert p_itm > p_otm

    def test_mais_vol_vale_mais(self):
        p_low = black_scholes_put(S=100, K=100, T=0.25, r=0.10, sigma=0.10)
        p_high = black_scholes_put(S=100, K=100, T=0.25, r=0.10, sigma=0.40)
        assert p_high > p_low

    def test_valor_conhecido_atm_hull(self):
        """Mesmo exemplo de Hull 15.6 usando put-call parity:
        p = c - S + K·e^(-rT) = 4.759 - 42 + 40·e^(-0.05) ≈ 0.808.
        """
        p = black_scholes_put(S=42, K=40, T=0.5, r=0.10, sigma=0.20)
        assert abs(p - 0.808) < 0.01


class TestVolatilidadeHistorica:
    """Vol anualizada via desvio padrão dos log-retornos diários."""

    def test_dados_insuficientes_retorna_fallback(self):
        """< janela+1 fechamentos → 0.30 (30% fallback)."""
        assert _calcular_volatilidade_historica([100, 101, 102]) == 0.30
        assert _calcular_volatilidade_historica([], janela=5) == 0.30

    def test_preco_constante_retorna_zero(self):
        """Série constante → retornos = 0 → vol = 0."""
        vol = _calcular_volatilidade_historica([100] * 30)
        assert vol == 0.0

    def test_serie_com_volatilidade_retorna_positivo(self):
        """Série alternada gera retornos não-nulos → vol > 0."""
        # Alterna 100, 105, 100, 105... log-retornos alternam ±ln(1.05)
        fechamentos = [100 if i % 2 == 0 else 105 for i in range(30)]
        vol = _calcular_volatilidade_historica(fechamentos)
        assert vol > 0

    def test_anualizacao_fator_raiz_252(self):
        """Vol anual = vol diária × √252. Valida o fator de escala."""
        # Série construída com dp_log_retorno ≈ ln(1.01) ≈ 0.00995
        # Alternando +1% / -1% pra ter média ~0
        fechamentos = [100.0]
        for i in range(30):
            if i % 2 == 0:
                fechamentos.append(fechamentos[-1] * 1.01)
            else:
                fechamentos.append(fechamentos[-1] / 1.01)
        vol_anual = _calcular_volatilidade_historica(fechamentos)
        # dp diário esperado ≈ |ln(1.01)| ≈ 0.00995
        # anualizado ≈ 0.00995 × √252 ≈ 0.158
        assert 0.14 < vol_anual < 0.17

    def test_zeros_ignorados_retorna_fallback(self):
        """Fechamentos zero/negativos devem ser ignorados no cálculo dos log-retornos."""
        # Todos zeros → retornos vazios → fallback
        fechamentos = [0.0] * 30
        vol = _calcular_volatilidade_historica(fechamentos)
        assert vol == 0.30

    def test_janela_default_21(self):
        """Default janela=21 pega últimos 21 retornos."""
        # Série de 50 candles: primeiros 30 com alta vol, últimos 20 constantes
        fechamentos = list(range(100, 130))  # crescimento
        fechamentos += [130] * 20  # flat
        vol = _calcular_volatilidade_historica(fechamentos, janela=21)
        # Como os últimos 21 são quase todos flat, vol deve ser pequena
        assert vol < 0.10
