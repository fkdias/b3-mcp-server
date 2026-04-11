"""
Calculadora Interativa de Backtest — B3 MCP Server (camada UI / Streamlit).

MVP — Fase 21 do projeto.

Esta calculadora é **apenas uma camada de apresentação** em cima de:
- `b3_mcp.core.services.backtest_service.executar_backtest`
- `b3_mcp.core.services.options_sim.simular_opcoes_hilo`
- `b3_mcp.core.services.hilo_service._listar_offline_disponiveis`

Zero lógica de estratégia/sizing é duplicada aqui — apenas coleta de inputs,
iteração por ticker e formatação do resultado.

Rodar:
    pip install -e ".[ui]"
    streamlit run app_calculadora.py

Ou via launcher:
    app_calculadora.bat
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

# Garante que "src/" esteja no path quando rodando via `streamlit run app_calculadora.py`
# (mesmo sem `pip install -e .`)
_ROOT = Path(__file__).parent
_SRC = _ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
import streamlit as st

from b3_mcp.core.services.backtest_service import executar_backtest
from b3_mcp.core.services.hilo_service import _listar_offline_disponiveis
from b3_mcp.core.services.options_sim import simular_opcoes_hilo

# ════════════════════════════════════════════════════════════════════════════
# Config da página + dark theme
# ════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="B3 Calculadora de Backtest",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme custom — alinhado com chart_service.py (fundo #0E1117)
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stDataFrame, .stTable {
        background-color: #1E2128;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
    h1, h2, h3 { color: #00D4FF; }
    </style>
    """,
    unsafe_allow_html=True,
)

ESTRATEGIAS = ["hilo", "rsi", "sma_crossover", "ema_crossover", "macd", "bollinger", "todas"]
SIZING_MODES = ["agregado", "lote_fixo", "fracao_banca", "teto_absoluto", "fracao_capital"]


# ════════════════════════════════════════════════════════════════════════════
# Helpers de parsing (lidam com números formatados R$/%)
# ════════════════════════════════════════════════════════════════════════════
def _parse_pct(valor: Any) -> float:
    """Converte '12,34%' / '-5,67%' / 'N/A' em float. Retorna 0.0 em fallback."""
    if valor is None or valor == "N/A":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).replace("%", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_brl(valor: Any) -> float:
    """Converte 'R$ 1.234,56' / 'R$ -789,00' em float."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


# ════════════════════════════════════════════════════════════════════════════
# Execução por ticker (wrapper fino sobre os backends)
# ════════════════════════════════════════════════════════════════════════════
def _rodar_ticker(
    ticker: str,
    estrategia: str,
    incluir_opcoes: bool,
    opcoes_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Roda backtest + (opcional) simulação de opções para UM ticker, modo offline."""
    resultado: dict[str, Any] = {"ticker": ticker}
    try:
        bt = executar_backtest(ticker, estrategia=estrategia, offline=True)
        resultado["backtest"] = bt
        resultado["erro"] = None
    except Exception as exc:
        resultado["backtest"] = None
        resultado["erro"] = f"backtest: {exc}"
        return resultado

    if incluir_opcoes:
        try:
            resultado["opcoes"] = simular_opcoes_hilo(
                ticker,
                offline=True,
                **opcoes_kwargs,
            )
        except Exception as exc:
            resultado["opcoes"] = None
            resultado["erro_opcoes"] = f"opcoes: {exc}"
    return resultado


# ════════════════════════════════════════════════════════════════════════════
# Tutorial — carregado do markdown em docs/TUTORIAL_CALCULADORA.md
# ════════════════════════════════════════════════════════════════════════════
_TUTORIAL_PATH = _ROOT / "docs" / "TUTORIAL_CALCULADORA.md"


@st.cache_data
def _carregar_tutorial() -> str:
    """Lê o markdown do tutorial. Cacheado pra não reler a cada rerun."""
    try:
        return _TUTORIAL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "⚠️ Arquivo `docs/TUTORIAL_CALCULADORA.md` não encontrado. Verifique se o projeto está completo."


# ════════════════════════════════════════════════════════════════════════════
# Sidebar — Formulário principal
# ════════════════════════════════════════════════════════════════════════════
st.title("📈 Calculadora de Backtest — B3 MCP")
st.caption(
    "Camada UI sobre o `backtest_service` e `options_sim` do B3 MCP Server. "
    "Dados em modo **offline** (datasets ~3 anos de candles diários)."
)

# Tutorial expansível — sempre visível no topo pra primeira vez
with st.expander("📖 **Tutorial — O que cada campo da barra lateral faz** (clique pra abrir)", expanded=False):
    st.markdown(_carregar_tutorial())

with st.sidebar:
    st.header("⚙️ Parâmetros")

    # Link rápido pro tutorial (redundância útil pro usuário novo)
    st.caption("📖 [Abra o tutorial completo](#tutorial) no topo da página principal ↗️")

    tickers_offline = _listar_offline_disponiveis()

    with st.form("form_calculadora"):
        st.subheader("Estratégia")
        estrategia = st.selectbox(
            "Estratégia de backtest",
            options=ESTRATEGIAS,
            index=0,
            help="`todas` roda todas as 6 estratégias em paralelo pra comparativo.",
        )

        periodo_hilo = st.slider(
            "Período Hi-Lo (apenas relevante pra hilo/opcoes)",
            min_value=5,
            max_value=30,
            value=10,
            step=1,
            help=(
                "Quantos candles olhar pra trás ao calcular a média do Hi-Lo. "
                "5 = reativo (day trade). 10 = default. 30 = conservador (swing longo)."
            ),
        )

        st.subheader("Ativos")
        ativos = st.multiselect(
            "Selecione os tickers (datasets offline)",
            options=tickers_offline,
            default=tickers_offline[:3] if len(tickers_offline) >= 3 else tickers_offline,
            help="Lista dos 26 datasets offline (~3 anos de candles cada). Pode escolher quantos quiser.",
        )

        limite_ativos = st.slider(
            "Máx. de ativos a processar",
            min_value=1,
            max_value=max(len(tickers_offline), 1),
            value=min(5, len(tickers_offline) or 1),
            help="Trava quantos dos ativos selecionados acima serão efetivamente processados.",
        )

        st.subheader("Capital & Sizing")
        capital_total = st.number_input(
            "Capital total da banca (R$)",
            min_value=100.0,
            value=10_000.0,
            step=500.0,
            help="Quanto você tem total na corretora. Serve só como denominador pros % na aba Totalizador.",
        )
        capital_estrategia = st.number_input(
            "Capital dedicado à estratégia (R$)",
            min_value=100.0,
            value=5_000.0,
            step=500.0,
            help="Usado como banca inicial na simulação de opções.",
        )

        sizing_mode = st.selectbox(
            "Modo de sizing (opções)",
            options=SIZING_MODES,
            index=0,
            help="Modos do options_sim — só aplicáveis se 'Incluir opções' estiver ativo.",
        )
        sizing_valor = st.number_input(
            "Valor do sizing",
            min_value=0.0,
            value=1.0,
            step=0.1,
            help="Interpretação depende do modo: lote_fixo=nº lotes, fracao_banca/fracao_capital=pct (0-1), teto_absoluto=R$ máx/trade.",
        )

        limite_por_op_pct = st.slider(
            "Limite de risco por operação (% da banca) — atalho Tio Huli",
            min_value=0.5,
            max_value=10.0,
            value=1.0,
            step=0.5,
            help="Aviso informativo — não é aplicado automaticamente (o sizing acima é a fonte de verdade).",
        )

        max_operacoes = st.number_input(
            "Máx. de operações (0 = ilimitado)",
            min_value=0,
            value=0,
            step=10,
        )

        lote_tamanho = st.number_input(
            "Tamanho do lote (opções)",
            min_value=1,
            value=100,
            step=1,
        )

        incluir_opcoes = st.checkbox(
            "Incluir simulação de opções (Black-Scholes ATM)",
            value=False,
        )

        submit = st.form_submit_button("🚀 Rodar Backtest", use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# Execução + renderização
# ════════════════════════════════════════════════════════════════════════════
if not submit:
    st.info(
        "👈 Configure os parâmetros na barra lateral e clique **Rodar Backtest**. "
        "Nenhum cálculo é feito até você submeter o formulário."
    )
    st.stop()

if not ativos:
    st.error("Selecione ao menos 1 ativo antes de rodar.")
    st.stop()

ativos_a_rodar = ativos[:limite_ativos]

opcoes_kwargs: dict[str, Any] = {
    "periodo_hilo": periodo_hilo,
    "banca_inicial": capital_estrategia,
    "sizing_mode": sizing_mode,
    "sizing_valor": sizing_valor,
    "lote_tamanho": int(lote_tamanho),
}

with st.spinner(f"Rodando {len(ativos_a_rodar)} ativo(s)…"):
    resultados: list[dict[str, Any]] = []
    progresso = st.progress(0.0)
    for i, tk in enumerate(ativos_a_rodar, start=1):
        resultados.append(_rodar_ticker(tk, estrategia, incluir_opcoes, opcoes_kwargs))
        progresso.progress(i / len(ativos_a_rodar))
    progresso.empty()

erros = [r for r in resultados if r.get("erro")]
if erros:
    with st.expander(f"⚠️ {len(erros)} erro(s) durante execução"):
        for e in erros:
            st.warning(f"**{e['ticker']}**: {e['erro']}")

# Filtra só os que rodaram o backtest com sucesso
ok = [r for r in resultados if r.get("backtest") is not None]
if not ok:
    st.error("Nenhum ativo produziu resultado válido. Confira os erros acima.")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# Monta o resumo agregado (por ativo)
# ════════════════════════════════════════════════════════════════════════════
def _resumo_ativo(r: dict[str, Any]) -> dict[str, Any]:
    """Extrai métricas-chave de um resultado bruto do executar_backtest."""
    bt = r["backtest"]
    linha: dict[str, Any] = {"ticker": r["ticker"], "periodo": bt.get("periodo", "N/A")}

    if "comparativo" in bt:
        # Modo "todas" — aplaina: pega só o hilo pro resumo + flag
        comp = bt["comparativo"]
        melhor = max(
            comp.items(),
            key=lambda kv: _parse_pct(kv[1]["metricas"].get("lucro_total_pct", 0)),
        )
        linha["estrategia"] = f"[comparativo] melhor={melhor[0]}"
        m = melhor[1]["metricas"]
    else:
        linha["estrategia"] = bt.get("estrategia", "?")
        m = bt.get("metricas", {})

    linha["trades"] = m.get("total_trades", 0)
    linha["taxa_acerto"] = m.get("taxa_acerto", "0,00%")
    linha["lucro_pct"] = m.get("lucro_total_pct", "0,00%")
    linha["lucro_total"] = m.get("lucro_total", "R$ 0,00")
    linha["profit_factor"] = m.get("profit_factor", 0)
    linha["max_drawdown"] = m.get("max_drawdown", "0,00%")

    # Flag de opções
    if r.get("opcoes"):
        opc = r["opcoes"]
        if "sizing" in opc:
            linha["opcoes_retorno"] = opc["sizing"].get("retorno_pct", "N/A")
        elif "resumo" in opc:
            linha["opcoes_retorno"] = opc["resumo"].get("retorno_opcoes", "N/A")
        else:
            linha["opcoes_retorno"] = "N/A"
    else:
        linha["opcoes_retorno"] = "-"

    return linha


resumo_df = pd.DataFrame([_resumo_ativo(r) for r in ok])

# ════════════════════════════════════════════════════════════════════════════
# Totalizadores da carteira
# ════════════════════════════════════════════════════════════════════════════
total_trades = sum(
    (r["backtest"].get("metricas", {}) if "metricas" in r["backtest"] else {}).get("total_trades", 0) for r in ok
)
soma_lucro_pct = sum(_parse_pct(row["lucro_pct"]) for _, row in resumo_df.iterrows())
media_lucro_pct = soma_lucro_pct / len(resumo_df) if len(resumo_df) > 0 else 0
melhor_ativo = (
    resumo_df.loc[resumo_df["lucro_pct"].apply(_parse_pct).idxmax(), "ticker"] if len(resumo_df) > 0 else "N/A"
)
pior_ativo = resumo_df.loc[resumo_df["lucro_pct"].apply(_parse_pct).idxmin(), "ticker"] if len(resumo_df) > 0 else "N/A"

# ════════════════════════════════════════════════════════════════════════════
# Tabs de output
# ════════════════════════════════════════════════════════════════════════════
st.success(f"✅ Backtest concluído em {len(ok)} ativo(s). Estratégia: **{estrategia}**.")

# Lista de tabs: a aba de Opções só aparece quando o checkbox foi marcado E
# pelo menos 1 ativo produziu simulação válida.
ativos_com_opcoes = [r for r in ok if r.get("opcoes") is not None]
tem_opcoes = incluir_opcoes and len(ativos_com_opcoes) > 0

tab_labels = [
    "📊 Resumo por Ativo",
    "💼 Totalizador Carteira",
    "📉 Equity Curve",
    "📋 Trades Detalhados",
    "🔥 Heatmap",
]
if tem_opcoes:
    tab_labels.append("🎯 Opções")
tab_labels.append("💾 Export")

tabs = st.tabs(tab_labels)

# Indices dinâmicos — quando "Opções" existe, shifta o Export
IDX_RESUMO = 0
IDX_TOTAL = 1
IDX_EQUITY = 2
IDX_TRADES = 3
IDX_HEATMAP = 4
IDX_OPCOES = 5 if tem_opcoes else None
IDX_EXPORT = 6 if tem_opcoes else 5

# ──────────────────────────────────────────────
# TAB 1 — Resumo por Ativo
# ──────────────────────────────────────────────
with tabs[IDX_RESUMO]:
    st.subheader("Resumo por Ativo")
    st.dataframe(resumo_df, use_container_width=True, hide_index=True)
    if incluir_opcoes and not tem_opcoes:
        st.warning(
            "⚠️ Checkbox de opções estava marcado, mas nenhum ativo gerou operações de opção válidas. "
            "Verifique os erros no expander de execução."
        )
    elif tem_opcoes:
        st.info(
            f"🎯 Simulação de opções ativa — veja a aba **Opções** pra detalhes "
            f"de cada um dos {len(ativos_com_opcoes)} ativo(s)."
        )

# ──────────────────────────────────────────────
# TAB 2 — Totalizador
# ──────────────────────────────────────────────
with tabs[IDX_TOTAL]:
    st.subheader("Totalizador da Carteira")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ativos processados", len(ok))
    c2.metric("Total de trades", total_trades)
    c3.metric("Retorno médio (ativo)", f"{media_lucro_pct:.2f}%")
    c4.metric("Retorno acumulado (soma)", f"{soma_lucro_pct:.2f}%")

    c5, c6 = st.columns(2)
    c5.metric("Melhor ativo", melhor_ativo)
    c6.metric("Pior ativo", pior_ativo)

    st.info(
        f"💰 Capital total declarado: R$ {capital_total:,.2f} — "
        f"dedicado à estratégia: R$ {capital_estrategia:,.2f} — "
        f"limite/op: {limite_por_op_pct:.1f}% — "
        f"máx. ops: {max_operacoes if max_operacoes else '∞'}"
    )
    st.caption(
        "Retorno médio = média simples do retorno % de cada ativo. "
        "Retorno acumulado = soma dos retornos (não composto, pra comparar ativos)."
    )

# ──────────────────────────────────────────────
# TAB 3 — Equity Curve
# ──────────────────────────────────────────────
with tabs[IDX_EQUITY]:
    st.subheader("Equity Curve Multi-Ticker")
    st.caption("Curva composta capital = 100 × ∏(1 + lucro_pct/100) reconstruída por ativo.")

    equity_por_ativo: dict[str, list[float]] = {}
    for r in ok:
        bt = r["backtest"]
        trades = bt.get("todos_trades") or []
        if not trades and "comparativo" in bt:
            # fallback para modo "todas" — pega os últimos trades do hilo
            trades = bt["comparativo"].get("hilo", {}).get("trades", [])
        curva = [100.0]
        for t in trades:
            pct = t.get("lucro_pct", 0)
            curva.append(curva[-1] * (1 + pct / 100))
        if len(curva) > 1:
            equity_por_ativo[r["ticker"]] = curva

    if not equity_por_ativo:
        st.warning("Nenhum ativo produziu trades — sem equity curve a desenhar.")
    else:
        # Normaliza pro mesmo comprimento máx pra plotar num DataFrame
        max_len = max(len(v) for v in equity_por_ativo.values())
        dados = {
            tk: curva + [None] * (max_len - len(curva))  # pad com None
            for tk, curva in equity_por_ativo.items()
        }
        df_eq = pd.DataFrame(dados)
        st.line_chart(df_eq, height=400)
        st.caption(f"Eixo X = nº de trades sequenciais por ativo. Pico comum = {max_len - 1} trades.")

# ──────────────────────────────────────────────
# TAB 4 — Trades Detalhados (paginados)
# ──────────────────────────────────────────────
with tabs[IDX_TRADES]:
    st.subheader("Trades Detalhados")
    if len(ok) > 1:
        ticker_focus = st.selectbox("Ativo:", [r["ticker"] for r in ok], key="focus_trades")
    else:
        ticker_focus = ok[0]["ticker"]
    focus = next(r for r in ok if r["ticker"] == ticker_focus)
    trades = focus["backtest"].get("todos_trades") or []
    if not trades and "comparativo" in focus["backtest"]:
        st.info("Modo `todas` — mostrando apenas os últimos trades da estratégia Hi-Lo.")
        trades = focus["backtest"]["comparativo"].get("hilo", {}).get("trades", [])

    if not trades:
        st.warning(f"Sem trades pra {ticker_focus}.")
    else:
        df_tr = pd.DataFrame(trades)
        page_size = 20
        total_paginas = (len(df_tr) - 1) // page_size + 1
        pagina = st.number_input("Página", min_value=1, max_value=total_paginas, value=1, step=1)
        ini = (pagina - 1) * page_size
        fim = ini + page_size
        st.dataframe(df_tr.iloc[ini:fim], use_container_width=True, hide_index=True)
        st.caption(f"Mostrando trades {ini + 1}–{min(fim, len(df_tr))} de {len(df_tr)} ({total_paginas} página(s)).")

# ──────────────────────────────────────────────
# TAB 5 — Heatmap
# ──────────────────────────────────────────────
with tabs[IDX_HEATMAP]:
    st.subheader("Heatmap — Ativo × Métrica")
    st.caption("Valores numéricos extraídos dos campos formatados pra comparação visual.")

    heat = pd.DataFrame(
        {
            "ticker": [r["ticker"] for r in ok],
            "lucro_pct": [_parse_pct(_resumo_ativo(r)["lucro_pct"]) for r in ok],
            "taxa_acerto": [_parse_pct(_resumo_ativo(r)["taxa_acerto"]) for r in ok],
            "profit_factor": [
                float(_resumo_ativo(r)["profit_factor"]) if _resumo_ativo(r)["profit_factor"] != float("inf") else 99.0
                for r in ok
            ],
            "max_dd_abs": [abs(_parse_pct(_resumo_ativo(r)["max_drawdown"])) for r in ok],
            "trades": [_resumo_ativo(r)["trades"] for r in ok],
        }
    ).set_index("ticker")

    st.dataframe(
        heat.style.background_gradient(
            cmap="RdYlGn", subset=["lucro_pct", "taxa_acerto", "profit_factor"]
        ).background_gradient(cmap="RdYlGn_r", subset=["max_dd_abs"]),
        use_container_width=True,
    )

# ──────────────────────────────────────────────
# TAB 6 (condicional) — Opções
# ──────────────────────────────────────────────
if tem_opcoes:
    with tabs[IDX_OPCOES]:
        st.subheader("🎯 Simulação de Opções (Black-Scholes ATM)")
        st.caption(
            "Opções sintéticas precificadas via Black-Scholes. "
            "Aplicação do sizing escolhido: "
            f"**{sizing_mode}** (valor = {sizing_valor})."
        )

        # Picker de ativo — só um por vez pra não poluir
        if len(ativos_com_opcoes) > 1:
            ticker_opc = st.selectbox(
                "Ativo (opções):",
                [r["ticker"] for r in ativos_com_opcoes],
                key="focus_opcoes",
            )
        else:
            ticker_opc = ativos_com_opcoes[0]["ticker"]

        focus_opc = next(r for r in ativos_com_opcoes if r["ticker"] == ticker_opc)
        opc_data = focus_opc["opcoes"]

        # ─── Cards de métricas-resumo (do bloco "resumo" do options_sim) ───
        resumo_opc = opc_data.get("resumo", {})
        if resumo_opc:
            st.markdown("##### Resumo agregado")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total operações", resumo_opc.get("total_operacoes", 0))
            c2.metric("Calls / Puts", f"{resumo_opc.get('calls', 0)} / {resumo_opc.get('puts', 0)}")
            c3.metric("Win rate opções", resumo_opc.get("win_rate_opcoes", "N/A"))
            c4.metric("Retorno opções", resumo_opc.get("retorno_opcoes", "N/A"))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Investido opções", resumo_opc.get("investido_opcoes", "N/A"))
            c6.metric("Lucro opções", resumo_opc.get("lucro_opcoes", "N/A"))
            c7.metric("Lucro ação equivalente", resumo_opc.get("lucro_acao", "N/A"))
            alav = resumo_opc.get("alavancagem_media", "N/A")
            c8.metric("Alavancagem média", f"{alav}x" if isinstance(alav, (int, float)) else alav)

        # ─── Bloco sizing (se ativo) ───
        sizing_info = opc_data.get("sizing")
        if sizing_info:
            st.markdown("##### Sizing (banca dedicada)")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Banca inicial", f"R$ {sizing_info.get('banca_inicial', 0):,.2f}")
            s2.metric("Banca final", f"R$ {sizing_info.get('banca_final', 0):,.2f}")
            s3.metric("Retorno", sizing_info.get("retorno_pct", "N/A"))
            s4.metric("Max drawdown", sizing_info.get("max_drawdown_pct", "N/A"))

            s5, s6, s7, s8 = st.columns(4)
            s5.metric("Trades executados", sizing_info.get("trades_executados", 0))
            s6.metric("Trades pulados", sizing_info.get("trades_pulados", 0))
            s7.metric("Total de lotes", sizing_info.get("total_lotes", 0))
            s8.metric("Pico da banca", f"R$ {sizing_info.get('pico', 0):,.2f}")
        else:
            st.info(
                "ℹ️ Sizing não aplicado neste modo (`agregado` usa 1 lote fixo por trade). "
                "Troque pra `lote_fixo`, `fracao_banca`, `teto_absoluto` ou `fracao_capital` "
                "pra ver banca evoluindo."
            )

        # ─── Tabela paginada das operações ───
        operacoes = opc_data.get("operacoes", [])
        if not operacoes:
            st.warning(f"Nenhuma operação de opção foi aberta pra {ticker_opc}.")
        else:
            st.markdown(f"##### Operações ({len(operacoes)} total)")
            df_opc = pd.DataFrame(operacoes)

            page_size_opc = 20
            total_paginas_opc = max((len(df_opc) - 1) // page_size_opc + 1, 1)
            pagina_opc = st.number_input(
                "Página (opções)",
                min_value=1,
                max_value=total_paginas_opc,
                value=1,
                step=1,
                key="pag_opcoes",
            )
            ini_opc = (pagina_opc - 1) * page_size_opc
            fim_opc = ini_opc + page_size_opc
            st.dataframe(df_opc.iloc[ini_opc:fim_opc], use_container_width=True, hide_index=True)
            st.caption(
                f"Mostrando operações {ini_opc + 1}–{min(fim_opc, len(df_opc))} de {len(df_opc)} "
                f"({total_paginas_opc} página(s))."
            )

        # ─── Premissas + disclaimer ───
        with st.expander("🔎 Premissas do modelo"):
            premissas = opc_data.get("premissas", {})
            for k, v in premissas.items():
                st.write(f"- **{k}:** {v}")
        st.caption(opc_data.get("disclaimer", ""))


# ──────────────────────────────────────────────
# TAB 7 — Export
# ──────────────────────────────────────────────
with tabs[IDX_EXPORT]:
    st.subheader("Exportar Resultados")

    col1, col2 = st.columns(2)

    with col1:
        csv_buffer = io.StringIO()
        resumo_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📄 Baixar resumo (CSV)",
            data=csv_buffer.getvalue(),
            file_name="calculadora_resumo.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        # JSON completo (com trades + metricas + opcoes se aplicável)
        export_json = json.dumps(
            {
                "parametros": {
                    "estrategia": estrategia,
                    "ativos": ativos_a_rodar,
                    "capital_total": capital_total,
                    "capital_estrategia": capital_estrategia,
                    "sizing_mode": sizing_mode,
                    "sizing_valor": sizing_valor,
                    "lote_tamanho": int(lote_tamanho),
                    "incluir_opcoes": incluir_opcoes,
                },
                "resultados": ok,
            },
            default=str,
            indent=2,
            ensure_ascii=False,
        )
        st.download_button(
            label="🧾 Baixar JSON completo",
            data=export_json,
            file_name="calculadora_completo.json",
            mime="application/json",
            use_container_width=True,
        )

    st.caption(
        "💡 Para exportar o gráfico como PNG, use o botão de câmera no canto superior direito "
        "de qualquer st.line_chart (feature nativa do Streamlit)."
    )

# ════════════════════════════════════════════════════════════════════════════
# Rodapé
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.caption(
    "⚠️ SIMULAÇÃO EDUCACIONAL — não utiliza dados reais de opções da B3. "
    "Backtest com datasets offline (~3 anos de histórico). Resultados passados "
    "não garantem retornos futuros."
)
