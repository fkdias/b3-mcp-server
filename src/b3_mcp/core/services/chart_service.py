"""Gerador de gráficos PNG para o Hi-Lo Activator — layout limpo."""

import os
import tempfile

import matplotlib

matplotlib.use("Agg")
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

# ─── Paleta dark profissional ───
C = {
    "bg": "#0f1318",
    "panel": "#161b22",
    "grid": "#21262d",
    "border": "#30363d",
    "text": "#e6edf3",
    "text2": "#8b949e",
    "blue": "#58a6ff",
    "green": "#3fb950",
    "red": "#f85149",
    "yellow": "#d29922",
    "purple": "#bc8cff",
}


def gerar_grafico_hilo(
    candles: list[dict],
    hilo_data: dict,
    ticker: str,
    resultado_analise: dict,
    ultimos_dias: int = 90,
    output_path: str | None = None,
) -> str:
    """
    Gera gráfico PNG com layout separado:
    - Esquerda: gráfico de preço + Hi-Lo + volume
    - Direita: painel de métricas (sem sobreposição)
    """
    # ─── Dados ───
    candles_plot = candles[-ultimos_dias:]
    offset = len(candles) - ultimos_dias

    datas = [datetime.strptime(c["data"], "%Y-%m-%d") for c in candles_plot]
    fechamentos = [c["fechamento"] for c in candles_plot]
    maximas = [c["maxima"] for c in candles_plot]
    minimas = [c["minima"] for c in candles_plot]
    aberturas = [c["abertura"] for c in candles_plot]
    volumes = [c["volume"] for c in candles_plot]

    activator_vals = hilo_data["activator"][offset:]
    tendencias = hilo_data["tendencia"][offset:]
    sinais_list = hilo_data["sinais"][offset:]

    # ─── Extrair info ───
    hilo_info = resultado_analise.get("hilo", {})
    preco_info = resultado_analise.get("preco", {})
    ind = resultado_analise.get("indicadores", {})
    mr = resultado_analise.get("metricas_risco", {})
    vol_info = resultado_analise.get("volume", {})
    sr = resultado_analise.get("suporte_resistencia", {})
    tendencia = hilo_info.get("tendencia", "N/A")
    cor_tend = C["green"] if tendencia == "ALTA" else C["red"]

    # ═══════════════════════════════════════════════
    # LAYOUT: gráfico (75%) | painel métricas (25%)
    # ═══════════════════════════════════════════════
    fig = plt.figure(figsize=(20, 11), facecolor=C["bg"])

    gs_main = gridspec.GridSpec(1, 2, width_ratios=[3, 1], wspace=0.02, figure=fig)

    # Sub-grid esquerda: preço (60%) + volume (20%) + equity curve (20%)
    gs_chart = gridspec.GridSpecFromSubplotSpec(
        3,
        1,
        subplot_spec=gs_main[0],
        height_ratios=[3, 1, 1],
        hspace=0.18,
    )
    ax_preco = fig.add_subplot(gs_chart[0])
    ax_vol = fig.add_subplot(gs_chart[1], sharex=ax_preco)
    ax_equity = fig.add_subplot(gs_chart[2])  # x-axis próprio (trade_seq)

    # Painel direito: área de texto (sem eixos)
    ax_info = fig.add_subplot(gs_main[1])
    ax_info.axis("off")

    # ─── Estilo dos eixos ───
    for ax in [ax_preco, ax_vol, ax_equity]:
        ax.set_facecolor(C["bg"])
        ax.tick_params(colors=C["text2"], labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(C["border"])
        ax.grid(True, alpha=0.12, color=C["grid"], linestyle="--")

    # ═══════════════════════════════════════════════
    # GRÁFICO DE PREÇO
    # ═══════════════════════════════════════════════

    # ─── Candles OHLC reais (Rectangle bodies + wicks) ───
    body_width = 0.6  # largura do corpo em dias (unidade matplotlib)
    for i in range(len(datas)):
        op = aberturas[i]
        cl = fechamentos[i]
        hi = maximas[i]
        lo = minimas[i]
        cor = C["green"] if cl >= op else C["red"]

        data_num = mdates.date2num(datas[i])

        # Wick (sombra superior+inferior)
        ax_preco.vlines(data_num, lo, hi, color=cor, linewidth=0.9, alpha=0.9, zorder=3)

        # Body (retângulo open→close)
        body_low = min(op, cl)
        body_height = max(abs(cl - op), 1e-6)  # evita altura zero
        rect = Rectangle(
            (data_num - body_width / 2, body_low),
            body_width,
            body_height,
            facecolor=cor,
            edgecolor=cor,
            linewidth=0.6,
            alpha=0.95,
            zorder=4,
        )
        ax_preco.add_patch(rect)

    # Hi-Lo Activator (cor dinâmica, segmentos desconectados em viradas)
    # Quando a tendência muda (ALTA ↔ BAIXA), NÃO desenhamos o segmento entre
    # o último candle da tendência antiga e o primeiro da nova. Isso evita que
    # a linha verde "conecte" na vermelha e vice-versa, deixando cada trecho
    # de tendência visualmente isolado.
    for i in range(1, len(datas)):
        if activator_vals[i] is None or activator_vals[i - 1] is None:
            continue
        if tendencias[i] != tendencias[i - 1]:
            # Virada de tendência: pula o segmento de conexão
            continue
        cor = C["green"] if tendencias[i] == "ALTA" else C["red"]
        ax_preco.plot(
            [datas[i - 1], datas[i]],
            [activator_vals[i - 1], activator_vals[i]],
            color=cor,
            linewidth=2.2,
            alpha=0.8,
            zorder=4,
        )

    # Sinais COMPRA / VENDA — posicionados fora do candle, relativos ao activator:
    # - COMPRA: ▲ verde ABAIXO da linha verde do activator (não sobrepõe o candle)
    # - VENDA:  ▼ vermelho ACIMA da linha vermelha do activator (não sobrepõe o candle)
    # Offset proporcional ao range visível, garante que o marcador fique dentro
    # dos limites do eixo (y_pad de 6% é maior que o marker_offset de 2%).
    activator_finitos_pre = [v for v in activator_vals if v is not None]
    _y_range = (
        max(maximas + activator_finitos_pre) - min(minimas + activator_finitos_pre)
        if activator_finitos_pre
        else (max(maximas) - min(minimas))
    )
    marker_offset = _y_range * 0.02 if _y_range > 0 else 0.5

    for i in range(len(datas)):
        if activator_vals[i] is None:
            continue
        if sinais_list[i] == "COMPRA":
            ax_preco.scatter(
                datas[i],
                activator_vals[i] - marker_offset,
                color=C["green"],
                marker="^",
                s=140,
                zorder=5,
                edgecolors="white",
                linewidths=0.8,
            )
        elif sinais_list[i] == "VENDA":
            ax_preco.scatter(
                datas[i],
                activator_vals[i] + marker_offset,
                color=C["red"],
                marker="v",
                s=140,
                zorder=5,
                edgecolors="white",
                linewidths=0.8,
            )

    # Suporte e resistência (linhas horizontais pontilhadas)
    sup = sr.get("suporte_20d", 0)
    res = sr.get("resistencia_20d", 0)
    if sup > 0:
        ax_preco.axhline(sup, color=C["green"], linewidth=0.8, linestyle=":", alpha=0.4)
    if res > 0:
        ax_preco.axhline(res, color=C["red"], linewidth=0.8, linestyle=":", alpha=0.4)

    # Ylim explícito: Rectangle patches não atualizam datalim, e o Hi-Lo activator
    # pode puxar o eixo pra valores fora da faixa real dos preços. Força limites
    # com base em candles + activator (ignorando None).
    activator_finitos = [v for v in activator_vals if v is not None]
    y_min = min(minimas + activator_finitos)
    y_max = max(maximas + activator_finitos)
    y_pad = (y_max - y_min) * 0.06 if y_max > y_min else 1.0
    ax_preco.set_ylim(y_min - y_pad, y_max + y_pad)

    # Xlim explícito: garante que os candles nas bordas não fiquem cortados.
    x_min = mdates.date2num(datas[0]) - 1
    x_max = mdates.date2num(datas[-1]) + 1
    ax_preco.set_xlim(x_min, x_max)

    ax_preco.set_ylabel("Preço (R$)", color=C["text2"], fontsize=10)
    plt.setp(ax_preco.get_xticklabels(), visible=False)

    # Legenda compacta
    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor=C["green"],
            markersize=9,
            label="Candle alta",
            linestyle="None",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor=C["red"],
            markersize=9,
            label="Candle baixa",
            linestyle="None",
        ),
        Line2D([0], [0], color=C["green"], linewidth=2.2, label="Hi-Lo Alta"),
        Line2D([0], [0], color=C["red"], linewidth=2.2, label="Hi-Lo Baixa"),
        Line2D(
            [0], [0], marker="^", color="w", markerfacecolor=C["green"], markersize=8, label="Compra", linestyle="None"
        ),
        Line2D(
            [0], [0], marker="v", color="w", markerfacecolor=C["red"], markersize=8, label="Venda", linestyle="None"
        ),
    ]
    ax_preco.legend(
        handles=legend_elements,
        loc="lower left",
        ncol=6,
        fontsize=7.5,
        facecolor=C["panel"],
        edgecolor=C["border"],
        labelcolor=C["text2"],
    )

    # ═══════════════════════════════════════════════
    # VOLUME
    # ═══════════════════════════════════════════════
    cores_vol = [C["green"] if fechamentos[i] >= aberturas[i] else C["red"] for i in range(len(datas))]
    ax_vol.bar(datas, volumes, color=cores_vol, alpha=0.45, width=0.8)
    ax_vol.set_ylabel("Vol", color=C["text2"], fontsize=9)
    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax_vol.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    plt.setp(ax_vol.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

    # ═══════════════════════════════════════════════
    # EQUITY CURVE (base 100, eixo X = trade_seq)
    # ═══════════════════════════════════════════════
    equity_curve = (mr or {}).get("equity_curve") or [100]
    trade_idx = list(range(len(equity_curve)))

    # Cor: verde se terminou acima de 100, vermelho se abaixo
    cor_equity = C["green"] if equity_curve[-1] >= 100 else C["red"]

    ax_equity.plot(trade_idx, equity_curve, color=cor_equity, linewidth=1.6, zorder=3)
    ax_equity.fill_between(trade_idx, 100, equity_curve, color=cor_equity, alpha=0.15, zorder=2)
    ax_equity.axhline(100, color=C["text2"], linewidth=0.6, linestyle=":", alpha=0.6, zorder=1)

    ax_equity.set_ylabel("Equity", color=C["text2"], fontsize=9)
    ax_equity.set_xlabel("Trade nº (base 100)", color=C["text2"], fontsize=8)
    ax_equity.tick_params(colors=C["text2"], labelsize=8)
    ax_equity.margins(x=0.01)

    # ═══════════════════════════════════════════════
    # PAINEL DE MÉTRICAS (lado direito, sem sobreposição)
    # ═══════════════════════════════════════════════

    # Título
    ax_info.text(
        0.05,
        0.98,
        ticker,
        fontsize=22,
        fontweight="bold",
        color=C["text"],
        va="top",
        fontfamily="monospace",
        transform=ax_info.transAxes,
    )
    ax_info.text(
        0.05,
        0.93,
        f"Hi-Lo Activator  |  Período {hilo_info.get('periodo', 10)}",
        fontsize=9,
        color=C["text2"],
        va="top",
        transform=ax_info.transAxes,
    )

    # Badge de tendência
    badge_x, badge_y = 0.05, 0.88
    ax_info.text(
        badge_x,
        badge_y,
        f"  {tendencia}  ",
        fontsize=14,
        fontweight="bold",
        color="white",
        va="top",
        transform=ax_info.transAxes,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=cor_tend, alpha=0.9),
    )

    # Seção: Preço e Activator
    y = 0.80
    sections = []

    # --- Preço ---
    sections.append(
        (
            "PRECO",
            [
                ("Preco atual", preco_info.get("formatado", "N/A")),
                ("Activator", hilo_info.get("activator_formatado", "N/A")),
                ("Distancia", preco_info.get("distancia_activator", "N/A")),
                ("Dias tendencia", str(hilo_info.get("dias_na_tendencia", "N/A"))),
                ("Var. tendencia", hilo_info.get("variacao_na_tendencia", "N/A")),
            ],
        )
    )

    # --- Indicadores ---
    sections.append(
        (
            "INDICADORES",
            [
                ("RSI (14)", f"{ind.get('rsi_14', 'N/A')}  {ind.get('rsi_zona', '')}"),
                ("SMA 9/21", ind.get("sma_status", "N/A")),
                ("Bollinger", preco_info.get("posicao_bollinger", "N/A")),
            ],
        )
    )

    # --- Risco ---
    if mr and mr.get("total_trades", 0) > 0:
        sections.append(
            (
                "RISCO (LONG/SHORT)",
                [
                    ("Trades", str(mr.get("total_trades", 0))),
                    ("Win Rate", mr.get("win_rate", "N/A")),
                    ("Payout medio", mr.get("payout_medio", "N/A")),
                    ("Payout wins", mr.get("payout_medio_wins", "N/A")),
                    ("Payout losses", mr.get("payout_medio_losses", "N/A")),
                    ("Profit Factor", str(mr.get("profit_factor", "N/A"))),
                    ("Max Drawdown", mr.get("max_drawdown", "N/A")),
                    ("Expectativa", mr.get("expectativa", "N/A")),
                    ("Retorno acum.", mr.get("retorno_acumulado", "N/A")),
                ],
            )
        )

    # --- Volume ---
    sections.append(
        (
            "VOLUME",
            [
                ("Vol atual", vol_info.get("volume_atual_fmt", "N/A")),
                ("Vol medio 20d", vol_info.get("volume_medio_fmt", "N/A")),
                ("Classificacao", vol_info.get("volume_classificacao", "N/A")),
            ],
        )
    )

    # Renderizar seções
    for section_title, items in sections:
        # Linha separadora
        ax_info.plot([0.05, 0.95], [y, y], color=C["border"], linewidth=0.5, transform=ax_info.transAxes, clip_on=False)
        y -= 0.015

        # Título da seção
        ax_info.text(
            0.05,
            y,
            section_title,
            fontsize=8,
            fontweight="bold",
            color=C["yellow"],
            va="top",
            transform=ax_info.transAxes,
        )
        y -= 0.025

        # Itens
        for label, value in items:
            ax_info.text(0.07, y, label, fontsize=8, color=C["text2"], va="top", transform=ax_info.transAxes)
            ax_info.text(
                0.95,
                y,
                str(value),
                fontsize=8,
                color=C["text"],
                va="top",
                ha="right",
                fontweight="bold",
                transform=ax_info.transAxes,
            )
            y -= 0.023

        y -= 0.01  # gap entre seções

    # Rodapé
    ax_info.text(
        0.05,
        0.02,
        f"Dados: {candles_plot[0]['data']}  a  {candles_plot[-1]['data']}",
        fontsize=7,
        color=C["text2"],
        va="bottom",
        transform=ax_info.transAxes,
    )

    # Título global
    fig.suptitle("", fontsize=1)  # espaço reservado

    # ─── Salvar ───
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), f"hilo_{ticker.lower()}.png")

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=C["bg"], edgecolor="none")
    plt.close(fig)

    return output_path
