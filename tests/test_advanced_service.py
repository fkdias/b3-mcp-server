"""Testes de advanced_service.py.

Cobre:
- Candle pattern detectors puros: `_detectar_doji`, `_detectar_martelo`,
  `_detectar_estrela_cadente`, `_detectar_engolfo_alta`, `_detectar_engolfo_baixa`
- Helpers de notícias: `_limpar_html`, `_categorizar`
- Integração offline: `padroes_candle`, `volume_breakout_scanner`, `analise_multiagente`

Escopo: tudo exceto `noticias_b3` (HTTP/RSS — fora do escopo).
"""

from __future__ import annotations

import pytest

from b3_mcp.core.services.advanced_service import (
    _categorizar,
    _detectar_doji,
    _detectar_engolfo_alta,
    _detectar_engolfo_baixa,
    _detectar_estrela_cadente,
    _detectar_martelo,
    _limpar_html,
    analise_multiagente,
    padroes_candle,
    volume_breakout_scanner,
)


# ═══════════════════════════════════════════════
# Candle pattern detectors (puros)
# ═══════════════════════════════════════════════
class TestDetectarDoji:
    def test_doji_perfeito_abertura_igual_fechamento(self):
        # Corpo zero, range positivo → corpo/range = 0 < 0.05
        assert _detectar_doji(o=100, h=102, low=98, c=100) is True

    def test_doji_quase_sem_corpo(self):
        # Corpo = 0.1, range = 4 → 2.5% < 5%
        assert _detectar_doji(o=100, h=102, low=98, c=100.1) is True

    def test_nao_doji_corpo_grande(self):
        # Corpo = 2, range = 4 → 50% >> 5%
        assert _detectar_doji(o=100, h=102, low=98, c=102) is False

    def test_range_zero_retorna_false(self):
        # Evita div-by-zero: high == low → não é doji
        assert _detectar_doji(o=100, h=100, low=100, c=100) is False

    def test_doji_na_fronteira_5pct(self):
        # Corpo/range = exatamente 5% → False (< estrito)
        assert _detectar_doji(o=100, h=102, low=98, c=100.2) is False


class TestDetectarMartelo:
    def test_martelo_classico(self):
        """Corpo pequeno no topo, sombra inferior longa, close na metade superior."""
        # o=100, c=101 (corpo 1), h=101.5, low=95 → sombra_inf=min(100,101)-95=5
        # sombra_inf (5) >= 2x corpo (2)? sim. c (101) > (h+low)/2 (98.25)? sim.
        assert _detectar_martelo(o=100, h=101.5, low=95, c=101) is True

    def test_nao_martelo_sombra_curta(self):
        # Sombra inferior pequena
        assert _detectar_martelo(o=100, h=102, low=99.5, c=101) is False

    def test_nao_martelo_close_na_metade_inferior(self):
        # Corpo na parte de baixo → não é martelo (é estrela cadente invertida)
        # o=100, c=96, h=101, low=90 → sombra_inf=min(100,96)-90=6, corpo=4, 6>=8? não
        assert _detectar_martelo(o=100, h=101, low=90, c=96) is False

    def test_corpo_zero_retorna_false(self):
        # Corpo zero cai no early return
        assert _detectar_martelo(o=100, h=105, low=95, c=100) is False

    def test_range_zero_retorna_false(self):
        assert _detectar_martelo(o=100, h=100, low=100, c=100) is False


class TestDetectarEstrelaCadente:
    def test_estrela_cadente_classica(self):
        """Corpo pequeno na base, sombra superior longa, close na metade inferior."""
        # o=100, c=99 (corpo 1), h=106, low=98.5 → sombra_sup=106-100=6
        # 6 >= 2? sim. c(99) < (h+low)/2=102.25? sim.
        assert _detectar_estrela_cadente(o=100, h=106, low=98.5, c=99) is True

    def test_nao_estrela_sombra_superior_curta(self):
        assert _detectar_estrela_cadente(o=100, h=100.5, low=95, c=99) is False

    def test_corpo_zero_retorna_false(self):
        assert _detectar_estrela_cadente(o=100, h=110, low=95, c=100) is False


class TestDetectarEngolfoAlta:
    def test_engolfo_alta_perfeito(self):
        candles = [
            {"abertura": 105, "fechamento": 100, "volume": 1_000_000},  # vermelho
            {"abertura": 100, "fechamento": 106, "volume": 1_500_000},  # verde que engolfa
        ]
        assert _detectar_engolfo_alta(candles, 1) is True

    def test_engolfo_alta_sem_volume_confirma(self):
        # Mesmo shape mas volume menor → não confirma
        candles = [
            {"abertura": 105, "fechamento": 100, "volume": 2_000_000},
            {"abertura": 100, "fechamento": 106, "volume": 1_500_000},
        ]
        assert _detectar_engolfo_alta(candles, 1) is False

    def test_engolfo_alta_primeiro_candle_retorna_false(self):
        candles = [{"abertura": 100, "fechamento": 105, "volume": 1_000_000}]
        assert _detectar_engolfo_alta(candles, 0) is False

    def test_nao_engolfo_curr_nao_engolfa(self):
        # Corpo do atual menor que o anterior
        candles = [
            {"abertura": 110, "fechamento": 100, "volume": 1_000_000},
            {"abertura": 102, "fechamento": 105, "volume": 2_000_000},
        ]
        assert _detectar_engolfo_alta(candles, 1) is False


class TestDetectarEngolfoBaixa:
    def test_engolfo_baixa_perfeito(self):
        candles = [
            {"abertura": 100, "fechamento": 105, "volume": 1_000_000},  # verde
            {"abertura": 105, "fechamento": 99, "volume": 1_500_000},  # vermelho que engolfa
        ]
        assert _detectar_engolfo_baixa(candles, 1) is True

    def test_engolfo_baixa_sem_volume(self):
        candles = [
            {"abertura": 100, "fechamento": 105, "volume": 2_000_000},
            {"abertura": 105, "fechamento": 99, "volume": 1_500_000},
        ]
        assert _detectar_engolfo_baixa(candles, 1) is False


# ═══════════════════════════════════════════════
# Helpers de notícias (puros)
# ═══════════════════════════════════════════════
class TestLimparHtml:
    def test_remove_tags_simples(self):
        assert _limpar_html("<p>Olá <b>mundo</b></p>") == "Olá mundo"

    def test_decodifica_entidades_html(self):
        assert _limpar_html("AT&amp;T") == "AT&T"
        assert _limpar_html("&lt;tag&gt;") == "<tag>"
        assert _limpar_html("&quot;texto&quot;") == '"texto"'

    def test_remove_apostrofos_smart(self):
        assert _limpar_html("It&#8217;s") == "It's"

    def test_aspas_curly(self):
        assert _limpar_html("&#8220;citação&#8221;") == '"citação"'

    def test_strip_espacos(self):
        assert _limpar_html("  <p>teste</p>  ") == "teste"

    def test_texto_sem_html_passa_direto(self):
        assert _limpar_html("sem tags") == "sem tags"


class TestCategorizar:
    def test_mercado(self):
        cats = _categorizar("Ibovespa fecha em alta de 1%")
        assert "mercado" in cats

    def test_economia(self):
        cats = _categorizar("Banco Central mantém Selic em 14,25%")
        assert "economia" in cats

    def test_commodities(self):
        cats = _categorizar("Vale anuncia aumento na produção de minério")
        # "vale" e "minério" estão em commodities
        assert "commodities" in cats

    def test_internacional(self):
        cats = _categorizar("Fed sinaliza corte de juros nos EUA")
        assert "internacional" in cats

    def test_empresas(self):
        cats = _categorizar("Petrobras anuncia dividendo extraordinário")
        # "petrobras" → commodities; "dividendo" → empresas
        assert "empresas" in cats

    def test_politica(self):
        cats = _categorizar("Lula sanciona reforma tributária")
        assert "politica" in cats

    def test_sem_match_retorna_geral(self):
        # Texto com zero keywords de qualquer categoria.
        # Evitar "completamente", "exemplo" etc porque "pl" casa com politica
        # via substring ("pl" ∈ "completamente").
        cats = _categorizar("xyz foo bar zzz quux")
        assert cats == ["geral"]

    def test_multi_categoria(self):
        cats = _categorizar("Lula defende Selic em reunião com o BC")
        # "lula" → politica; "selic", "bc" → economia
        assert "politica" in cats
        assert "economia" in cats


# ═══════════════════════════════════════════════
# Integração offline
# ═══════════════════════════════════════════════
class TestPadroesCandle:
    def test_retorna_schema_correto(self):
        r = padroes_candle("PETR4", offline=True)
        assert r["ticker"] == "PETR4"
        assert r["periodo_analise"] == "Últimos 5 pregões"
        assert "padroes_detectados" in r
        assert isinstance(r["padroes"], list)
        assert r["padroes_detectados"] == len(r["padroes"])

    def test_ticker_invalido_offline_raises(self):
        with pytest.raises(ValueError, match="offline"):
            padroes_candle("XXXX9", offline=True)

    def test_ticker_limpo_aplicado(self):
        """ "petr4.sa" deve resolver igual a 'PETR4'."""
        r1 = padroes_candle("PETR4", offline=True)
        r2 = padroes_candle("petr4.sa", offline=True)
        assert r1["ticker"] == r2["ticker"] == "PETR4"

    def test_padroes_tem_estrutura_consistente(self):
        """Cada padrão detectado tem data, padrao, tipo, descricao."""
        r = padroes_candle("PETR4", offline=True)
        for p in r["padroes"]:
            assert "data" in p
            assert "padrao" in p
            assert p["tipo"] in ("ALTA", "BAIXA", "NEUTRO")
            assert "descricao" in p


class TestVolumeBreakoutScanner:
    def test_retorna_schema_correto(self):
        r = volume_breakout_scanner(multiplicador=2.0, offline=True)
        assert "criterio" in r
        assert "total_detectados" in r
        assert "resultados" in r
        assert isinstance(r["resultados"], list)
        assert r["total_detectados"] == len(r["resultados"])

    def test_multiplicador_alto_zera_resultados(self):
        """10x é praticamente impossível num dia normal → poucos ou zero."""
        r = volume_breakout_scanner(multiplicador=10.0, offline=True)
        # Pode ter algum caso extremo, mas deve ser <= 2
        assert r["total_detectados"] <= 2

    def test_multiplicador_baixo_detecta_mais(self):
        """1.0x (volume apenas ≥ média) detecta mais do que 2.0x."""
        r_low = volume_breakout_scanner(multiplicador=1.0, offline=True)
        r_high = volume_breakout_scanner(multiplicador=2.0, offline=True)
        assert r_low["total_detectados"] >= r_high["total_detectados"]

    def test_resultados_ordenados_por_ratio_desc(self):
        r = volume_breakout_scanner(multiplicador=1.0, offline=True)
        ratios = [x["volume_ratio"] for x in r["resultados"]]
        assert ratios == sorted(ratios, reverse=True)

    def test_resultados_tem_campos_esperados(self):
        r = volume_breakout_scanner(multiplicador=1.0, offline=True)
        if not r["resultados"]:
            pytest.skip("Nenhum breakout detectado no dataset atual")
        item = r["resultados"][0]
        for campo in [
            "ticker",
            "setor",
            "preco",
            "variacao_dia",
            "volume_atual",
            "volume_medio",
            "volume_ratio",
            "tendencia_hilo",
        ]:
            assert campo in item


class TestAnaliseMultiagente:
    def test_retorna_schema_correto(self):
        r = analise_multiagente("PETR4", offline=True)
        for chave in [
            "ticker",
            "preco",
            "veredito",
            "score_total",
            "score_normalizado",
            "confianca",
            "agentes",
            "disclaimer",
        ]:
            assert chave in r

    def test_tres_agentes_presentes(self):
        r = analise_multiagente("PETR4", offline=True)
        assert "tecnico" in r["agentes"]
        assert "momentum" in r["agentes"]
        assert "risco" in r["agentes"]

    def test_agentes_tem_score_max_e_notas(self):
        r = analise_multiagente("PETR4", offline=True)
        for nome in ("tecnico", "momentum", "risco"):
            ag = r["agentes"][nome]
            assert "score" in ag
            assert "max_score" in ag
            assert "notas" in ag
            assert isinstance(ag["notas"], list)
            assert len(ag["notas"]) > 0

    def test_veredito_em_set_valido(self):
        r = analise_multiagente("PETR4", offline=True)
        assert r["veredito"] in {"FORTE COMPRA", "COMPRA", "NEUTRO", "VENDA", "FORTE VENDA"}

    def test_confianca_em_set_valido(self):
        r = analise_multiagente("PETR4", offline=True)
        assert r["confianca"] in {"Alta", "Moderada", "Baixa"}

    def test_score_normalizado_em_range(self):
        r = analise_multiagente("PETR4", offline=True)
        assert -1.0 <= r["score_normalizado"] <= 1.0

    def test_max_scores_corretos(self):
        """Os maxes são hardcoded: tec=4, mom=3, risco=3."""
        r = analise_multiagente("PETR4", offline=True)
        assert r["agentes"]["tecnico"]["max_score"] == 4
        assert r["agentes"]["momentum"]["max_score"] == 3
        assert r["agentes"]["risco"]["max_score"] == 3

    def test_score_total_bate_com_soma_dos_agentes(self):
        r = analise_multiagente("PETR4", offline=True)
        esperado = r["agentes"]["tecnico"]["score"] + r["agentes"]["momentum"]["score"] + r["agentes"]["risco"]["score"]
        assert r["score_total"] == esperado

    def test_varios_tickers_offline(self):
        """Roda pra 3 tickers pra pegar bugs só visíveis com dados diferentes."""
        for ticker in ("VALE3", "ITUB4", "WEGE3"):
            r = analise_multiagente(ticker, offline=True)
            assert r["ticker"] == ticker
            assert r["veredito"] is not None
