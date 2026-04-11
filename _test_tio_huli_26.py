"""Teste Tio Huli 1% da banca estratégia (R$ 100 teto) nos 26 ativos offline."""
import sys
sys.path.insert(0, 'src')
from b3_mcp.core.services.options_sim import simular_opcoes_hilo

TICKERS = [
    'BBDC4','BEEF3','BPAC11','BRAP4','BRAV3','BRKM5','CMIN3','COGN3',
    'CSAN3','CSNA3','CYRE3','HAPV3','ITUB4','LREN3','MGLU3','MRVE3',
    'PETR4','PRIO3','RDOR3','RENT3','SANB11','SAPR11','SUZB3','USIM5',
    'VALE3','WEGE3',
]

CAPITAL_TOTAL = 100_000
BANCA_EST = CAPITAL_TOTAL * 0.10
TETO = BANCA_EST * 0.01
LOTE = 100

def max_drawdown(curva):
    peak = curva[0]
    dd = 0.0
    for v in curva:
        peak = max(peak, v)
        dd = min(dd, (v - peak) / peak * 100)
    return dd

def simular(ops, modo):
    banca = BANCA_EST
    peak = banca
    curva = [banca]
    trades = 0
    skips = 0
    total_lotes = 0
    for op in ops:
        custo_lote = op['premio_pago'] * LOTE
        if modo == 'estrito':
            if custo_lote > TETO:
                skips += 1
                continue
            lotes = 1
        else:
            if custo_lote > banca:
                skips += 1
                continue
            lotes = 1
        pnl = op['resultado_opcao_rs'] * LOTE * lotes
        banca += pnl
        peak = max(peak, banca)
        curva.append(banca)
        trades += 1
        total_lotes += lotes
    return {
        'banca_final': banca,
        'lucro': banca - BANCA_EST,
        'retorno_banca': (banca - BANCA_EST) / BANCA_EST * 100,
        'peak': peak,
        'dd_banca': max_drawdown(curva),
        'trades': trades,
        'skips': skips,
        'total_lotes': total_lotes,
    }

resultados = []
erros = []
for ticker in TICKERS:
    try:
        r = simular_opcoes_hilo(ticker, offline=True)
        ops = r['operacoes']
        if not ops:
            erros.append((ticker, 'sem operacoes'))
            continue
        custos = [op['premio_pago'] * LOTE for op in ops]
        prm_med = sum(custos)/len(custos)
        caveis = sum(1 for c in custos if c <= TETO)
        resultados.append({
            'ticker': ticker,
            'n_sinais': len(ops),
            'premio_medio_lote': prm_med,
            'caveis_teto': caveis,
            'estrito': simular(ops, 'estrito'),
            'flex': simular(ops, 'flex'),
        })
    except Exception as e:
        erros.append((ticker, str(e)))

print("=" * 100)
print("VARIANTE ESTRITA - 1% da banca (R$ 100 teto rigoroso)")
print("=" * 100)
print(f"{'Ticker':<8}{'Sinais':>8}{'PrmMed':>10}{'Caveis':>9}{'Exec':>7}"
      f"{'BancaFinal':>13}{'RetBanca':>11}{'RetCap':>10}{'MaxDD':>10}")
print("-" * 100)
resultados_est = sorted(resultados, key=lambda r: r['estrito']['retorno_banca'], reverse=True)
soma_lucro_est = 0.0
for r in resultados_est:
    e = r['estrito']
    soma_lucro_est += e['lucro']
    print(f"{r['ticker']:<8}{r['n_sinais']:>8}  R${r['premio_medio_lote']:>6.0f}"
          f"{r['caveis_teto']:>8}/{r['n_sinais']:<2}{e['trades']:>5}"
          f"  R${e['banca_final']:>9,.0f}"
          f"{e['retorno_banca']:>+10.2f}%"
          f"{e['retorno_banca']/10:>+9.2f}%"
          f"{e['dd_banca']:>+9.2f}%")
print("-" * 100)
med_ret_est = sum(r['estrito']['retorno_banca'] for r in resultados) / len(resultados)
wins_est = sum(1 for r in resultados if r['estrito']['lucro'] > 0)
print(f"MEDIA retorno banca: {med_ret_est:+.2f}%   (win rate: {wins_est}/{len(resultados)})")
print(f"Lucro agregado 26 ativos (cada um com R$ 10k isolados): R$ {soma_lucro_est:+,.2f}")

print()
print("=" * 100)
print("VARIANTE FLEX - 1 lote sempre (ignora teto R$ 100, usa so limite de caixa)")
print("=" * 100)
print(f"{'Ticker':<8}{'Sinais':>8}{'PrmMed':>10}{'Exec':>7}{'Skip':>6}"
      f"{'BancaFinal':>13}{'RetBanca':>11}{'RetCap':>10}{'MaxDD':>10}")
print("-" * 100)
resultados_flex = sorted(resultados, key=lambda r: r['flex']['retorno_banca'], reverse=True)
soma_lucro_flex = 0.0
for r in resultados_flex:
    f = r['flex']
    soma_lucro_flex += f['lucro']
    print(f"{r['ticker']:<8}{r['n_sinais']:>8}  R${r['premio_medio_lote']:>6.0f}"
          f"{f['trades']:>7}{f['skips']:>6}"
          f"  R${f['banca_final']:>9,.0f}"
          f"{f['retorno_banca']:>+10.2f}%"
          f"{f['retorno_banca']/10:>+9.2f}%"
          f"{f['dd_banca']:>+9.2f}%")
print("-" * 100)
med_ret_flex = sum(r['flex']['retorno_banca'] for r in resultados) / len(resultados)
wins_flex = sum(1 for r in resultados if r['flex']['lucro'] > 0)
print(f"MEDIA retorno banca: {med_ret_flex:+.2f}%   (win rate: {wins_flex}/{len(resultados)})")
print(f"Lucro agregado 26 ativos (cada um com R$ 10k isolados): R$ {soma_lucro_flex:+,.2f}")

# ============================================================
# PARALELO — banca unica R$ 10k compartilhada entre os 26 ativos
# ============================================================
print()
print("=" * 100)
print("CENARIO PARALELO — banca unica R$ 10.000 compartilhada entre os 26 ativos")
print("=" * 100)
todos = []
for r in resultados:
    ops = simular_opcoes_hilo(r['ticker'], offline=True)['operacoes']
    for op in ops:
        todos.append({
            'ticker': r['ticker'],
            'data_entrada': op['data_entrada'],
            'premio_pago': op['premio_pago'],
            'resultado_opcao_rs': op['resultado_opcao_rs'],
            'tipo': op['tipo_opcao'],
        })
todos.sort(key=lambda t: t['data_entrada'])
print(f"Total de trades (todos os ativos): {len(todos)}")

def sim_paralelo(trades, modo):
    banca = BANCA_EST
    peak = banca
    curva = [banca]
    tr = 0
    sk = 0
    for t in trades:
        custo_lote = t['premio_pago'] * LOTE
        if modo == 'estrito' and custo_lote > TETO:
            sk += 1
            continue
        if custo_lote > banca:
            sk += 1
            continue
        pnl = t['resultado_opcao_rs'] * LOTE
        banca += pnl
        peak = max(peak, banca)
        curva.append(banca)
        tr += 1
    return banca, peak, curva, tr, sk

for modo in ['estrito', 'flex']:
    banca_p, peak_p, curva_p, tr_p, sk_p = sim_paralelo(todos, modo)
    dd_p = max_drawdown(curva_p)
    lucro_p = banca_p - BANCA_EST
    print(f"\n[{modo.upper()}]")
    print(f"  Banca final:  R$ {banca_p:,.2f}")
    print(f"  Lucro:        R$ {lucro_p:+,.2f}")
    print(f"  Ret. banca:   {lucro_p/BANCA_EST*100:+.2f}%")
    print(f"  Ret. capital: {lucro_p/CAPITAL_TOTAL*100:+.2f}%")
    print(f"  Pico:         R$ {peak_p:,.2f}")
    print(f"  Max DD banca: {dd_p:+.2f}%")
    print(f"  Trades:       {tr_p}/{len(todos)}")
    print(f"  Skips:        {sk_p}")

if erros:
    print()
    print("ERROS:")
    for t, e in erros:
        print(f"  {t}: {e}")
