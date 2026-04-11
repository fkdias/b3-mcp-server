"""Teste Tio Huli 1% do capital total (R$ 1.000 teto) nos 26 ativos offline.

Sizing variavel: lotes = int(min(R$ 1.000, banca_atual) // (premio_pago * 100)).
Banca estrategia R$ 10k, capital total R$ 100k, teto por trade R$ 1.000.
"""
import sys
sys.path.insert(0, 'src')
from b3_mcp.core.services.options_sim import simular_opcoes_hilo

TICKERS = [
    'BBDC4','BEEF3','BPAC11','BRAP4','BRAV3','BRKM5','CMIN3','COGN3',
    'CSAN3','CSNA3','CYRE3','HAPV3','ITUB4','LREN3','MGLU3','MRVE3',
    'PETR4','PRIO3','RDOR3','RENT3','SANB11','SAPR11','SUZB3','USIM5',
    'VALE3','WEGE3',
]

CAPITAL_TOTAL = 100_000.0
BANCA_EST = CAPITAL_TOTAL * 0.10   # R$ 10.000
TETO = CAPITAL_TOTAL * 0.01         # R$ 1.000 = 1% do capital total
LOTE = 100                          # contratos por lote minimo


def fmt_brl(valor):
    """Formata numero no padrao brasileiro R$ 1.234,56."""
    sinal = '-' if valor < 0 else ''
    v = abs(valor)
    inteiro = int(v)
    dec = int(round((v - inteiro) * 100))
    if dec == 100:
        inteiro += 1
        dec = 0
    s = f"{inteiro:,}".replace(',', '.')
    return f"{sinal}R$ {s},{dec:02d}"


def fmt_pct(valor, casas=2):
    s = f"{valor:+.{casas}f}".replace('.', ',')
    return f"{s}%"


def fmt_num(valor, casas=2):
    s = f"{valor:,.{casas}f}"
    # swap: comma->temp, dot->comma, temp->dot
    s = s.replace(',', '_').replace('.', ',').replace('_', '.')
    return s


def max_drawdown_pct(curva):
    if not curva:
        return 0.0
    peak = curva[0]
    dd = 0.0
    for v in curva:
        peak = max(peak, v)
        if peak > 0:
            dd = min(dd, (v - peak) / peak * 100)
    return dd


def max_drawdown_abs(curva):
    """Drawdown maximo em valor absoluto (R$)."""
    if not curva:
        return 0.0
    peak = curva[0]
    dd = 0.0
    for v in curva:
        peak = max(peak, v)
        dd = min(dd, v - peak)
    return dd


def simular_sizing_variavel(ops, banca_inicial):
    """Simula lista de ops com sizing variavel (teto R$ 1.000 por trade)."""
    banca = banca_inicial
    peak = banca
    curva = [banca]
    trades = 0
    skips = 0
    total_lotes = 0
    investido_agregado = 0.0
    for op in ops:
        orcamento = min(TETO, banca)
        custo_lote = op['premio_pago'] * LOTE
        if custo_lote <= 0:
            skips += 1
            continue
        lotes = int(orcamento // custo_lote)
        if lotes < 1:
            skips += 1
            continue
        custo_total = lotes * custo_lote
        pnl = op['resultado_opcao_rs'] * LOTE * lotes
        banca += pnl
        peak = max(peak, banca)
        curva.append(banca)
        trades += 1
        total_lotes += lotes
        investido_agregado += custo_total
    return {
        'banca_final': banca,
        'lucro': banca - banca_inicial,
        'retorno_banca': (banca - banca_inicial) / banca_inicial * 100,
        'peak': peak,
        'vale': min(curva) if curva else banca_inicial,
        'dd_banca_pct': max_drawdown_pct(curva),
        'dd_abs': max_drawdown_abs(curva),
        'trades': trades,
        'skips': skips,
        'total_lotes': total_lotes,
        'investido_agregado': investido_agregado,
        'curva': curva,
    }


# ============================================================
# COLETA - roda sim por ticker e guarda operacoes
# ============================================================
resultados = []
erros = []
operacoes_por_ticker = {}

for ticker in TICKERS:
    try:
        r = simular_opcoes_hilo(ticker, offline=True)
        ops = r['operacoes']
        if not ops:
            erros.append((ticker, 'sem operacoes'))
            continue
        operacoes_por_ticker[ticker] = ops
        custos = [op['premio_pago'] * LOTE for op in ops]
        prm_med = sum(custos) / len(custos)
        sim = simular_sizing_variavel(ops, BANCA_EST)
        lotes_medios = sim['total_lotes'] / sim['trades'] if sim['trades'] > 0 else 0
        resultados.append({
            'ticker': ticker,
            'n_sinais': len(ops),
            'premio_medio_lote': prm_med,
            'sim': sim,
            'lotes_medios': lotes_medios,
        })
    except Exception as e:
        erros.append((ticker, str(e)))

# ============================================================
# PARTE 1 - RESULTADOS ISOLADOS POR ATIVO
# ============================================================
print("=" * 120)
print("PARTE 1 - TESTE ISOLADO POR ATIVO (banca R$ 10k propria, teto R$ 1.000/trade)")
print("=" * 120)
print(f"{'Ticker':<8}{'Sinais':>8}{'PrmMedLote':>14}{'LotesMed':>11}"
      f"{'BancaFinal':>17}{'RetBanca':>12}{'RetCap':>11}{'MaxDD':>11}")
print("-" * 120)

resultados_sorted = sorted(
    resultados, key=lambda r: r['sim']['retorno_banca'], reverse=True
)

soma_lucro_iso = 0.0
for r in resultados_sorted:
    s = r['sim']
    soma_lucro_iso += s['lucro']
    ret_cap = s['lucro'] / CAPITAL_TOTAL * 100
    print(
        f"{r['ticker']:<8}"
        f"{r['n_sinais']:>8}"
        f"{fmt_brl(r['premio_medio_lote']):>14}"
        f"{r['lotes_medios']:>11.2f}"
        f"{fmt_brl(s['banca_final']):>17}"
        f"{fmt_pct(s['retorno_banca']):>12}"
        f"{fmt_pct(ret_cap):>11}"
        f"{fmt_pct(s['dd_banca_pct']):>11}"
    )

print("-" * 120)
wins_iso = sum(1 for r in resultados if r['sim']['lucro'] > 0)
med_ret_iso = sum(r['sim']['retorno_banca'] for r in resultados) / len(resultados)
print(f"Media retorno banca (isolado): {fmt_pct(med_ret_iso)}")
print(f"Win rate cross-ticker: {wins_iso}/{len(resultados)} "
      f"({wins_iso/len(resultados)*100:.1f}%)")
print(f"Lucro agregado 26 isolados (26 bancas separadas): {fmt_brl(soma_lucro_iso)}")

# ============================================================
# PARTE 2 - CENARIO PARALELO
# ============================================================
print()
print("=" * 120)
print("PARTE 2 - CENARIO PARALELO (banca unica R$ 10.000 compartilhada entre 26 ativos)")
print("=" * 120)

todos_trades = []
for ticker, ops in operacoes_por_ticker.items():
    for op in ops:
        todos_trades.append({
            'ticker': ticker,
            'data_entrada': op['data_entrada'],
            'premio_pago': op['premio_pago'],
            'resultado_opcao_rs': op['resultado_opcao_rs'],
            'tipo': op['tipo_opcao'],
        })

todos_trades.sort(key=lambda t: t['data_entrada'])
total_sinais = len(todos_trades)
print(f"Total de sinais consolidados: {total_sinais}")

# Simulacao paralela detalhada (com log dos trades)
banca = BANCA_EST
peak = banca
vale = banca
curva = [banca]
trades_exec = 0
skips = 0
total_lotes = 0
investido_agregado = 0.0
log_trades = []

for t in todos_trades:
    orcamento = min(TETO, banca)
    custo_lote = t['premio_pago'] * LOTE
    if custo_lote <= 0:
        skips += 1
        continue
    lotes = int(orcamento // custo_lote)
    if lotes < 1:
        skips += 1
        continue
    custo_total = lotes * custo_lote
    pnl = t['resultado_opcao_rs'] * LOTE * lotes
    banca += pnl
    peak = max(peak, banca)
    vale = min(vale, banca)
    curva.append(banca)
    trades_exec += 1
    total_lotes += lotes
    investido_agregado += custo_total
    log_trades.append({
        'n': trades_exec,
        'data': t['data_entrada'],
        'ticker': t['ticker'],
        'tipo': t['tipo'],
        'lotes': lotes,
        'custo': custo_total,
        'pnl': pnl,
        'banca_pos': banca,
    })

dd_banca_pct = max_drawdown_pct(curva)
dd_abs = max_drawdown_abs(curva)
dd_cap_pct = dd_abs / CAPITAL_TOTAL * 100
lucro = banca - BANCA_EST
lotes_medios_par = total_lotes / trades_exec if trades_exec > 0 else 0

print(f"  Banca inicial:        {fmt_brl(BANCA_EST)}")
print(f"  Banca final:          {fmt_brl(banca)}")
print(f"  Lucro:                {fmt_brl(lucro)}")
print(f"  Retorno banca:        {fmt_pct(lucro/BANCA_EST*100)}")
print(f"  Retorno capital 100k: {fmt_pct(lucro/CAPITAL_TOTAL*100)}")
print(f"  Pico:                 {fmt_brl(peak)}")
print(f"  Vale:                 {fmt_brl(vale)}")
print(f"  Max DD banca:         {fmt_pct(dd_banca_pct)}")
print(f"  Max DD R$:            {fmt_brl(dd_abs)}")
print(f"  Max DD capital 100k:  {fmt_pct(dd_cap_pct)}")
print(f"  Trades executados:    {trades_exec}/{total_sinais}")
print(f"  Skips:                {skips}")
print(f"  Lotes totais:         {total_lotes}")
print(f"  Lotes medios/trade:   {lotes_medios_par:.2f}")
print(f"  Investido agregado:   {fmt_brl(investido_agregado)}")

# ============================================================
# PARTE 3 - PRIMEIROS 15 TRADES DETALHADOS
# ============================================================
print()
print("=" * 120)
print("PARTE 3 - PRIMEIROS 15 TRADES DO PARALELO")
print("=" * 120)
print(f"{'#':>4}{'Data':>13}{'Ticker':>9}{'Tipo':>6}{'Lotes':>8}"
      f"{'Custo':>15}{'P&L':>16}{'BancaPos':>17}")
print("-" * 120)
for lt in log_trades[:15]:
    print(
        f"{lt['n']:>4}"
        f"{str(lt['data']):>13}"
        f"{lt['ticker']:>9}"
        f"{lt['tipo']:>6}"
        f"{lt['lotes']:>8}"
        f"{fmt_brl(lt['custo']):>15}"
        f"{fmt_brl(lt['pnl']):>16}"
        f"{fmt_brl(lt['banca_pos']):>17}"
    )

# Top 5 maiores lucros e maiores perdas
print()
print("TOP 5 maiores GANHOS (paralelo):")
top_ganhos = sorted(log_trades, key=lambda x: x['pnl'], reverse=True)[:5]
for lt in top_ganhos:
    print(
        f"  #{lt['n']:<4} {lt['data']} {lt['ticker']:<8} {lt['tipo']:<5} "
        f"{lt['lotes']} lotes  PnL {fmt_brl(lt['pnl']):>15}  "
        f"banca {fmt_brl(lt['banca_pos'])}"
    )

print()
print("TOP 5 maiores PERDAS (paralelo):")
top_perdas = sorted(log_trades, key=lambda x: x['pnl'])[:5]
for lt in top_perdas:
    print(
        f"  #{lt['n']:<4} {lt['data']} {lt['ticker']:<8} {lt['tipo']:<5} "
        f"{lt['lotes']} lotes  PnL {fmt_brl(lt['pnl']):>15}  "
        f"banca {fmt_brl(lt['banca_pos'])}"
    )

# ============================================================
# PARTE 4 - COMPARATIVO COM TESTES ANTERIORES
# ============================================================
print()
print("=" * 120)
print("PARTE 4 - COMPARATIVO COM TESTES ANTERIORES")
print("=" * 120)
print(f"{'Teto':<22}{'RetBanca':>14}{'DDBanca':>12}"
      f"{'DDCapital':>13}{'TradesExec':>16}")
print("-" * 120)
print(f"{'R$ 100 estrito':<22}{'+120,90%':>14}{'-6,82%':>12}"
      f"{'-0,68%':>13}{'1176/1794':>16}")
print(f"{'R$ 100 flex':<22}{'+162,19%':>14}{'-17,78%':>12}"
      f"{'-1,78%':>13}{'1794/1794':>16}")
print(
    f"{'R$ 1.000 (este teste)':<22}"
    f"{fmt_pct(lucro/BANCA_EST*100):>14}"
    f"{fmt_pct(dd_banca_pct):>12}"
    f"{fmt_pct(dd_cap_pct):>13}"
    f"{str(trades_exec) + '/' + str(total_sinais):>16}"
)

if erros:
    print()
    print("ERROS:")
    for t, e in erros:
        print(f"  {t}: {e}")
