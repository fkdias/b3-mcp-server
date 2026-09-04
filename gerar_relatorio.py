"""Gera relatório completo Hi-Lo Activator de todos os 26 ativos offline."""

import csv
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from b3_mcp.core.services.chart_service import gerar_grafico_hilo
from b3_mcp.core.services.hilo_service import _listar_offline_disponiveis, analisar_hilo

RELATORIO_DIR = os.path.join(os.path.dirname(__file__), "relatorios")
GRAFICOS_DIR = os.path.join(RELATORIO_DIR, "graficos")
os.makedirs(GRAFICOS_DIR, exist_ok=True)


def gerar():
    tickers = _listar_offline_disponiveis()
    print(f"Gerando relatório para {len(tickers)} ativos...\n")

    resultados = []
    erros = []

    for ticker in sorted(tickers):
        try:
            # Gerar análise
            result = analisar_hilo(ticker, periodo=13, offline=True)

            # Salvar gráfico na pasta correta
            grafico_path = os.path.join(GRAFICOS_DIR, f"hilo_{ticker.lower()}.png")
            from b3_mcp.core.services.hilo_service import _carregar_offline
            from b3_mcp.core.services.indicators_calc import calc_hilo_activator as calc_hilo

            candles = _carregar_offline(ticker)
            maximas = [c["maxima"] for c in candles]
            minimas = [c["minima"] for c in candles]
            fechamentos = [c["fechamento"] for c in candles]
            hilo_data = calc_hilo(maximas, minimas, fechamentos, 10)

            gerar_grafico_hilo(candles, hilo_data, ticker, result, output_path=grafico_path)
            result["grafico"] = grafico_path

            resultados.append(result)

            mr = result.get("metricas_risco", {})
            hilo = result.get("hilo", {})
            print(
                f"  {ticker:8s} | {hilo.get('tendencia', 'N/A'):5s} | "
                f"{result['preco']['formatado']:>12s} | "
                f"Activator: {hilo.get('activator_formatado', 'N/A'):>12s} | "
                f"WR: {mr.get('win_rate', 'N/A'):>8s} | "
                f"PF: {str(mr.get('profit_factor', 'N/A')):>6s} | "
                f"DD: {mr.get('max_drawdown', 'N/A'):>8s} | "
                f"Ret: {mr.get('retorno_acumulado', 'N/A'):>10s} | "
                f"PNG OK"
            )
        except Exception as e:
            print(f"  {ticker:8s} | ERRO: {e}")
            erros.append((ticker, str(e)))

    # ─── Salvar JSON completo ───
    json_path = os.path.join(RELATORIO_DIR, "relatorio_hilo_completo.json")
    # Remover campo grafico do JSON (não serializável como path)
    resultados_json = []
    for r in resultados:
        r_copy = dict(r)
        r_copy["grafico"] = os.path.basename(r.get("grafico", "")) if r.get("grafico") else None
        resultados_json.append(r_copy)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_ativos": len(resultados),
                "ativos": resultados_json,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ─── Salvar CSV resumo ───
    csv_path = os.path.join(RELATORIO_DIR, "resumo_hilo_26ativos.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "Ticker",
                "Setor",
                "Tendencia",
                "Preco",
                "Activator",
                "Dist Activator",
                "Dias Tendencia",
                "Var Tendencia",
                "RSI",
                "RSI Zona",
                "SMA Status",
                "Vol Relativo",
                "Vol Class",
                "Trades",
                "Win Rate",
                "Payout Medio",
                "Payout Wins",
                "Payout Losses",
                "Profit Factor",
                "Max Drawdown",
                "Retorno Acum",
                "Maior Win",
                "Maior Loss",
                "Max Wins Consec",
                "Max Losses Consec",
                "Dias Medio Trade",
                "Expectativa",
                "Suporte 20d",
                "Resistencia 20d",
                "Volatilidade 20d",
                "Ultimo Sinal",
                "Data Ultimo Sinal",
                "Grafico",
            ]
        )

        for r in resultados:
            hilo = r.get("hilo", {})
            preco = r.get("preco", {})
            ind = r.get("indicadores", {})
            vol = r.get("volume", {})
            mr = r.get("metricas_risco", {})
            sr = r.get("suporte_resistencia", {})
            volat = r.get("volatilidade", {})
            us = r.get("ultimo_sinal", {})

            writer.writerow(
                [
                    r.get("ticker", ""),
                    r.get("setor", ""),
                    hilo.get("tendencia", ""),
                    preco.get("formatado", ""),
                    hilo.get("activator_formatado", ""),
                    preco.get("distancia_activator", ""),
                    hilo.get("dias_na_tendencia", ""),
                    hilo.get("variacao_na_tendencia", ""),
                    ind.get("rsi_14", ""),
                    ind.get("rsi_zona", ""),
                    ind.get("sma_status", ""),
                    vol.get("volume_relativo", ""),
                    vol.get("volume_classificacao", ""),
                    mr.get("total_trades", ""),
                    mr.get("win_rate", ""),
                    mr.get("payout_medio", ""),
                    mr.get("payout_medio_wins", ""),
                    mr.get("payout_medio_losses", ""),
                    mr.get("profit_factor", ""),
                    mr.get("max_drawdown", ""),
                    mr.get("retorno_acumulado", ""),
                    mr.get("maior_win", ""),
                    mr.get("maior_loss", ""),
                    mr.get("max_wins_consecutivos", ""),
                    mr.get("max_losses_consecutivos", ""),
                    mr.get("dias_medio_trade", ""),
                    mr.get("expectativa", ""),
                    sr.get("suporte_20d", ""),
                    sr.get("resistencia_20d", ""),
                    volat.get("volatilidade_20d", ""),
                    us.get("sinal", "") if us else "",
                    us.get("data", "") if us else "",
                    f"graficos/hilo_{r.get('ticker', '').lower()}.png",
                ]
            )

    print(f"\n{'=' * 60}")
    print("RELATORIO GERADO COM SUCESSO")
    print(f"{'=' * 60}")
    print(f"  Ativos analisados: {len(resultados)}")
    print(f"  Erros: {len(erros)} {erros if erros else ''}")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  Graficos: {GRAFICOS_DIR}/ ({len(resultados)} PNGs)")

    # Resumo por tendência
    altas = [r for r in resultados if r.get("hilo", {}).get("tendencia") == "ALTA"]
    baixas = [r for r in resultados if r.get("hilo", {}).get("tendencia") == "BAIXA"]
    print(f"\n  TENDENCIA ALTA:  {len(altas)} ativos")
    for r in sorted(altas, key=lambda x: x.get("hilo", {}).get("dias_na_tendencia", 0), reverse=True):
        print(f"    {r['ticker']:8s} ha {r['hilo']['dias_na_tendencia']} dias | {r['preco']['formatado']}")
    print(f"\n  TENDENCIA BAIXA: {len(baixas)} ativos")
    for r in sorted(baixas, key=lambda x: x.get("hilo", {}).get("dias_na_tendencia", 0), reverse=True):
        print(f"    {r['ticker']:8s} ha {r['hilo']['dias_na_tendencia']} dias | {r['preco']['formatado']}")


if __name__ == "__main__":
    gerar()
