"""Teste Tio Huli 10x escalado - capital R$ 1M, banca R$ 100k, teto R$ 10k."""
import sys
sys.path.insert(0, 'src')
from b3_mcp.core.services.options_sim import simular_opcoes_hilo

TICKERS = [
    'BBDC4','BEEF3','BPAC11','BRAP4','BRAV3','BRKM5','CMIN3','COGN3',
    'CSAN3','CSNA3','CYRE3','HAPV3','ITUB4','LREN3','MGLU3','MRVE3',
    'PETR4','PRIO3','RDOR3','RENT3','SANB11','SAPR11','SUZB3','USIM5',
    'VALE3','WEGE3',
]

CAPITAL_TOTAL = 1_000_000      # R$ 1.000.000
BANCA_EST     = 100_000        # 10% do capital total
TETO          = 10_000         # 1% do capital total
LOTE          = 100            # contratos por lote minimo

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def fmt_brl(v, casas=2):
    """Formato brasileiro: ponto de milhar, virgula decimal."""
    neg = v < 0
    v = abs(v)
    s = f"{v:,.{casas}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" + s) if neg else s

def fmt_pct(v, casas=2):
    sinal = "+" if v >= 0 else "-"
    return sinal + f"{abs(v):.{casas}f}".replace(".", ",") + "%"

def max_drawdown(curva):
    if not curva:
        return 0.0
    peak = curva[0]
    dd = 0.0
    for v in curva:
        peak = max(peak, v)
        if peak > 0:
            dd = min(dd, (v - peak) / peak * 100)
    return dd

def vale_curva(curva):
    return min(curva) if curva else 0.0

# ---------------------------------------------------------------
# 1) Teste isolado por ativo (banca R$ 100k cada, teto R$ 10k)
# ---------------------------------------------------------------
def simular_isolado(ops):
    banca = BANCA_EST
    peak = banca
    vale = banca
    curva = [banca]
    trades = 0
    skips = 0
    total_lotes = 0
    investido = 0.0
    for op in ops:
        premio_lote = op['premio_pago'] * LOTE
        orcamento = min(TETO, banca)
        if premio_lote <= 0:
            skips += 1
            continue
        lotes = int(orcamento // premio_lote)
        if lotes < 1:
            skips += 1
            continue
        custo = lotes * premio_lote
        if custo > banca:
            skips += 1
            continue
        pnl = lotes * op['resultado_opcao_rs'] * LOTE
        banca += pnl
        investido += custo
        peak = max(peak, banca)
        vale = min(vale, banca)
        curva.append(banca)
        trades += 1
        total_lotes += lotes
    lotes_med = (total_lotes / trades) if trades else 0.0
    return {
        'banca_final': banca,
        'lucro': banca - BANCA_EST,
        'retorno_banca': (banca - BANCA_EST) / BANCA_EST * 100,
        'retorno_capital': (banca - BANCA_EST) / CAPITAL_TOTAL * 100,
        'peak': peak,
        'vale': vale,
        'dd_banca': max_drawdown(curva),
        'trades': trades,
        'skips': skips,
        'total_lotes': total_lotes,
        'lotes_medios': lotes_med,
        'investido': investido,
    }

resultados = []
erros = []
trades_por_ticker = {}
for ticker in TICKERS:
    try:
        r = simular_opcoes_hilo(ticker, offline=True)
        ops = r['operacoes']
        trades_por_ticker[ticker] = ops
        if not ops:
            erros.append((ticker, 'sem operacoes'))
            continue
        custos = [op['premio_pago'] * LOTE for op in ops]
        prm_med = sum(custos) / len(custos)
        iso = simular_isolado(ops)
        resultados.append({
            'ticker': ticker,
            'n_sinais': len(ops),
            'premio_medio_lote': prm_med,
            'iso': iso,
        })
    except Exception as e:
        erros.append((ticker, str(e)))

# ---------------------------------------------------------------
# 2) Cenario PARALELO - banca unica R$ 100k
# ---------------------------------------------------------------
todos = []
for ticker, ops in trades_por_ticker.items():
    for op in ops:
        todos.append({
            'ticker': ticker,
            'data_entrada': op['data_entrada'],
            'premio_pago': op['premio_pago'],
            'resultado_opcao_rs': op['resultado_opcao_rs'],
            'tipo': op.get('tipo_opcao', ''),
        })
todos.sort(key=lambda t: t['data_entrada'])

def sim_paralelo(trades):
    banca = BANCA_EST
    peak = banca
    vale = banca
    curva = [banca]
    tr = 0
    sk = 0
    total_lotes = 0
    investido = 0.0
    log = []  # trades executados detalhados
    skips_motivo = {'lotes_zero': 0, 'caixa_insuf': 0, 'premio_invalido': 0}
    for t in trades:
        premio_lote = t['premio_pago'] * LOTE
        if premio_lote <= 0:
            sk += 1
            skips_motivo['premio_invalido'] += 1
            log.append({**t, 'exec': False, 'motivo': 'premio invalido', 'banca': banca})
            continue
        orcamento = min(TETO, banca)
        lotes = int(orcamento // premio_lote)
        if lotes < 1:
            sk += 1
            skips_motivo['lotes_zero'] += 1
            log.append({**t, 'exec': False, 'motivo': 'lotes<1', 'banca': banca})
            continue
        custo = lotes * premio_lote
        if custo > banca:
            sk += 1
            skips_motivo['caixa_insuf'] += 1
            log.append({**t, 'exec': False, 'motivo': 'caixa insuf', 'banca': banca})
            continue
        pnl = lotes * t['resultado_opcao_rs'] * LOTE
        banca_antes = banca
        banca += pnl
        investido += custo
        peak = max(peak, banca)
        vale = min(vale, banca)
        curva.append(banca)
        tr += 1
        total_lotes += lotes
        log.append({
            **t,
            'exec': True,
            'lotes': lotes,
            'custo': custo,
            'pnl': pnl,
            'banca_antes': banca_antes,
            'banca_depois': banca,
        })
    return {
        'banca_final': banca,
        'peak': peak,
        'vale': vale,
        'curva': curva,
        'trades': tr,
        'skips': sk,
        'total_lotes': total_lotes,
        'investido': investido,
        'log': log,
        'skips_motivo': skips_motivo,
    }

par = sim_paralelo(todos)
par['lucro'] = par['banca_final'] - BANCA_EST
par['retorno_banca'] = par['lucro'] / BANCA_EST * 100
par['retorno_capital'] = par['lucro'] / CAPITAL_TOTAL * 100
par['dd_banca'] = max_drawdown(par['curva'])
par['dd_capital'] = par['dd_banca'] * (BANCA_EST / CAPITAL_TOTAL)
par['lotes_medios'] = (par['total_lotes'] / par['trades']) if par['trades'] else 0.0

# ---------------------------------------------------------------
# Impressao
# ---------------------------------------------------------------
print("=" * 110)
print("TESTE TIO HULI 10x ESCALADO  -  Capital R$ 1.000.000 | Banca R$ 100.000 | Teto R$ 10.000")
print("=" * 110)

print()
print("PARTE 1 - Resultados isolados (cada ativo com R$ 100k e teto R$ 10k)")
print("-" * 110)
print(f"{'Ticker':<8}{'Sinais':>8}{'PrmMedLote':>14}{'LotMed/Tr':>12}"
      f"{'BancaFinal':>18}{'RetBanca':>12}{'RetCap':>11}{'MaxDD':>11}")
print("-" * 110)
resultados_sorted = sorted(resultados, key=lambda r: r['iso']['retorno_banca'], reverse=True)
soma_lucro_iso = 0.0
for r in resultados_sorted:
    iso = r['iso']
    soma_lucro_iso += iso['lucro']
    print(f"{r['ticker']:<8}{r['n_sinais']:>8}"
          f"  R$ {fmt_brl(r['premio_medio_lote'],0):>8}"
          f"{iso['lotes_medios']:>12.2f}"
          f"  R$ {fmt_brl(iso['banca_final'],0):>13}"
          f"{fmt_pct(iso['retorno_banca']):>12}"
          f"{fmt_pct(iso['retorno_capital']):>11}"
          f"{fmt_pct(iso['dd_banca']):>11}")
print("-" * 110)
med_ret = sum(r['iso']['retorno_banca'] for r in resultados) / len(resultados)
wins = sum(1 for r in resultados if r['iso']['lucro'] > 0)
print(f"Media retorno banca: {fmt_pct(med_ret)}   (win rate: {wins}/{len(resultados)})")
print(f"Lucro agregado 26 ativos (isolados): R$ {fmt_brl(soma_lucro_iso)}")

# ---------------------------------------------------------------
# Parte 2 - Cenario paralelo
# ---------------------------------------------------------------
print()
print("=" * 110)
print("PARTE 2 - Cenario PARALELO (banca unica R$ 100.000 compartilhada)")
print("=" * 110)
print(f"  Trades consolidados (universo):   {len(todos)}")
print(f"  Banca inicial:                    R$ {fmt_brl(BANCA_EST)}")
print(f"  Banca final:                      R$ {fmt_brl(par['banca_final'])}")
print(f"  Lucro:                            R$ {fmt_brl(par['lucro'])}")
print(f"  Retorno banca:                    {fmt_pct(par['retorno_banca'])}")
print(f"  Retorno capital total (R$ 1M):    {fmt_pct(par['retorno_capital'])}")
print(f"  Pico da banca:                    R$ {fmt_brl(par['peak'])}")
print(f"  Vale da banca:                    R$ {fmt_brl(par['vale'])}")
print(f"  Max DD banca:                     {fmt_pct(par['dd_banca'])}")
print(f"  Max DD capital total:             {fmt_pct(par['dd_capital'])}")
print(f"  Trades executados:                {par['trades']}/{len(todos)}")
print(f"  Skips:                            {par['skips']}  {par['skips_motivo']}")
print(f"  Lotes totais:                     {par['total_lotes']:,}".replace(",", "."))
print(f"  Lotes medios por trade:           {par['lotes_medios']:.2f}".replace(".", ","))
print(f"  Investido agregado:               R$ {fmt_brl(par['investido'])}")
print(f"  Multiplos de banca usados:        {par['investido']/BANCA_EST:.2f}x".replace(".", ","))

# ---------------------------------------------------------------
# Parte 3 - Primeiros 15 trades do paralelo
# ---------------------------------------------------------------
print()
print("=" * 110)
print("PARTE 3 - Primeiros 15 trades EXECUTADOS do cenario paralelo")
print("=" * 110)
print(f"{'#':>3}  {'Data':<12}{'Tkr':<7}{'Tipo':<6}{'Premio':>10}{'Lotes':>7}"
      f"{'Custo':>13}{'PnL':>14}{'Banca apos':>18}")
print("-" * 110)
execs = [l for l in par['log'] if l.get('exec')]
for i, l in enumerate(execs[:15], 1):
    print(f"{i:>3}  {str(l['data_entrada'])[:10]:<12}{l['ticker']:<7}{str(l['tipo'])[:5]:<6}"
          f"  R$ {fmt_brl(l['premio_pago'],2):>5}"
          f"{l['lotes']:>7}"
          f"  R$ {fmt_brl(l['custo'],0):>8}"
          f"  R$ {fmt_brl(l['pnl'],0):>9}"
          f"  R$ {fmt_brl(l['banca_depois'],0):>12}")

# ---------------------------------------------------------------
# Parte extra - contexto/debug
# ---------------------------------------------------------------
print()
print("=" * 110)
print("DEBUG - Relacao premio medio lote vs teto R$ 10.000")
print("=" * 110)
premio_min = min(r['premio_medio_lote'] for r in resultados)
premio_max = max(r['premio_medio_lote'] for r in resultados)
print(f"  Premio medio lote minimo:  R$ {fmt_brl(premio_min)}")
print(f"  Premio medio lote maximo:  R$ {fmt_brl(premio_max)}")
print(f"  Teto por trade:            R$ {fmt_brl(TETO)}")
print(f"  Razao teto/premio_max:     {TETO/premio_max:.2f}x".replace(".", ","))
print(f"  Razao teto/premio_min:     {TETO/premio_min:.2f}x".replace(".", ","))

if erros:
    print()
    print("ERROS:")
    for t, e in erros:
        print(f"  {t}: {e}")
