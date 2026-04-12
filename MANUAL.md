# Manual de Uso — B3 MCP Server
# 19 Ferramentas para Analise do Mercado Brasileiro

---

## Como usar

Existem 2 formas de usar as ferramentas:

### Forma 1: Via Claude Code (conversa natural)
Abra o Claude Code na pasta `Tio Huli` e fale naturalmente:
- "Qual a cotacao da PETR4?"
- "Roda o Hi-Lo na VALE3"
- "Faz um backtest do Hi-Lo na ITUB4"
- "Me mostra a visao setorial da B3"
- "Compara as estrategias na COGN3"

### Forma 2: Via Terminal (Python direto)
```bash
cd b3-mcp-server
python -c "
import sys; sys.path.insert(0, 'src')
from b3_mcp.server import nome_da_ferramenta
print(nome_da_ferramenta('PETR4', offline=True))
"
```

### Modo offline vs online
- `offline=True` → usa dados salvos (26 ativos, ~3 anos / ~750 candles por ativo). Funciona sem internet.
- `offline=False` → busca dados ao vivo. Funciona com qualquer ativo da B3.

Os datasets offline sao atualizados automaticamente toda semana (ver secao
"Atualizacao automatica dos datasets" mais abaixo).

### 26 ativos disponiveis offline
BBDC4, BEEF3, BPAC11, BRAP4, BRAV3, BRKM5, CMIN3, COGN3, CSAN3, CSNA3,
CYRE3, HAPV3, ITUB4, LREN3, MGLU3, MRVE3, PETR4, PRIO3, RDOR3, RENT3,
SANB11, SAPR11, SUZB3, USIM5, VALE3, WEGE3

---

## Modelo de operacao: always-in-market long/short

O Hi-Lo Activator nesse servidor opera no modelo **"ganhos explosivos"**:
nunca fica flat (fora do mercado) entre o primeiro sinal e o ultimo candle.

**Para acoes (backtest, metricas de risco):**
- COMPRA → abre LONG (lucro = saida - entrada)
- VENDA → fecha LONG e **reverte** pra SHORT (lucro = entrada - saida)
- Ultimo candle fecha a posicao residual por FIM_PERIODO

**Para opcoes (`simular_opcoes_b3`):**
- COMPRA → compra CALL ATM (Black-Scholes, delta ~0.5)
- VENDA → compra PUT ATM
- Sinal oposto → fecha a opcao atual e abre a do outro lado (SINAL_OPOSTO)
- Vencimento sem sinal oposto → rola pra nova opcao do mesmo lado da
  tendencia vigente (ROLL_VENCIMENTO) — nunca fica em caixa

Essa abordagem ganha nas duas direcoes do mercado e e o comportamento
esperado para quem surfa tendencias explosivas com Hi-Lo. As demais
estrategias do backtest (RSI, SMA, EMA, MACD, Bollinger) continuam
long-only por design padrao.

---

## GRUPO 1: Ferramentas Core (7)

---

### [1] cotacao_b3
**O que faz:** Busca a cotacao em tempo real de qualquer acao da B3.
**Quando usar:** Quando quer saber o preco atual de um ativo.
**Requer internet:** Sim

**Como chamar:**
```
cotacao_b3("PETR4")
```

**O que retorna:**
- Preco atual (R$)
- Variacao do dia (R$ e %)
- Moeda e exchange

**Exemplo de resultado:**
```
Ticker: PETR4
Preco:  R$ 47,90
Var:    +1,12%
```

---

### [2] hilo_activator
**O que faz:** Roda o indicador Hi-Lo Activator (Gann CHiLo, periodo 10) em um ativo no modelo **always-in-market long/short reversal** — COMPRA abre LONG, VENDA reverte pra SHORT, nunca fica flat entre sinais. Gera grafico PNG + metricas de risco + historico de trades com acumulado.
**Quando usar:** Para saber a tendencia atual e os sinais de compra/venda de um ativo. E a ferramenta principal do sistema.
**Requer internet:** Nao (com offline=True)

**Como chamar:**
```
hilo_activator("PETR4", periodo=10, offline=True)
```

**Parametros:**
- `ticker` — codigo da acao (ex: PETR4, VALE3)
- `periodo` — periodo do Hi-Lo (default: 10)
- `offline` — usar dados salvos (default: False)

**O que retorna:**
- Tendencia (ALTA/BAIXA) e dias na tendencia
- Valor do activator e distancia do preco
- RSI, SMA, Bollinger
- Volume (atual vs media)
- Suporte e resistencia de 20 dias
- Cenarios (manter, sair, gatilho de reversao)
- Metricas de risco: win rate, payout, profit factor, max drawdown, expectativa
- Historico de TODOS os trades com `direcao` (LONG/SHORT), resultado acumulado progressivo e motivo de saida (reversao / fim do periodo)
- Grafico PNG salvo automaticamente

---

### [3] analise_tecnica_b3
**O que faz:** Da um score de 0 a 100 combinando 6 indicadores.
**Quando usar:** Para ter uma visao rapida se o ativo esta mais para compra ou venda.
**Requer internet:** Nao (com offline=True)

**Como chamar:**
```
analise_tecnica_b3("VALE3", offline=True)
```

**O que retorna:**
- Score 0-100 (FORTE BAIXA / BAIXA / NEUTRO / ALTA / FORTE ALTA)
- Valor de cada indicador: Hi-Lo, RSI, SMA 9/21, EMA 9/21, MACD, Bollinger
- Contagem: X sinais de alta vs Y sinais de baixa

---

### [4] panorama_mercado_b3
**O que faz:** Visao geral do mercado brasileiro.
**Quando usar:** Para abrir o dia e ver como esta o mercado.
**Requer internet:** Sim

**Como chamar:**
```
panorama_mercado_b3()
```

**O que retorna:**
- IBOVESPA: valor + variacao
- Dolar (USDBRL): valor + variacao
- Euro (EURBRL): valor + variacao
- Top 5 maiores altas do dia
- Top 5 maiores baixas do dia

---

### [5] maiores_altas_b3
**O que faz:** Lista as acoes com maior alta do dia na B3.
**Quando usar:** Para ver oportunidades de momentum.
**Requer internet:** Sim (TradingView Screener)

**Como chamar:**
```
maiores_altas_b3(limite=10)
```

---

### [6] maiores_baixas_b3
**O que faz:** Lista as acoes com maior queda do dia na B3.
**Quando usar:** Para ver quais ativos estao sob pressao.
**Requer internet:** Sim (TradingView Screener)

**Como chamar:**
```
maiores_baixas_b3(limite=10)
```

---

### [7] backtest_estrategia
**O que faz:** Testa uma estrategia no historico de 3 anos (~750 candles) e mostra os resultados.
**Quando usar:** Para comparar estrategias ou ver como o Hi-Lo teria performado.
**Requer internet:** Nao (com offline=True)

**Como chamar:**
```
backtest_estrategia("PETR4", estrategia="hilo", offline=True)
backtest_estrategia("PETR4", estrategia="todas", offline=True)  # compara todas
```

**Estrategias disponiveis:**
- `hilo` — Hi-Lo Activator (periodo 10) **always-in-market long/short**: COMPRA abre LONG, VENDA reverte pra SHORT, fecha residual no ultimo candle via FIM_PERIODO. Ganha em ambas as direcoes do mercado.
- `rsi` — RSI (14) sobrevenda/sobrecompra (long-only)
- `sma_crossover` — Cruzamento de SMA 9/21 (long-only)
- `ema_crossover` — Cruzamento de EMA 9/21 (long-only)
- `macd` — Cruzamento do histograma MACD (long-only)
- `bollinger` — Toque nas bandas de Bollinger (long-only)
- `todas` — Compara as 6 estrategias lado a lado

**O que retorna:**
- Total de trades, taxa de acerto
- Lucro total, profit factor, max drawdown
- Lista de cada trade (entrada, saida, resultado) — trades do Hi-Lo incluem campo `tipo` (LONG/SHORT) e `motivo_saida` (REVERSAO/FIM_PERIODO)

---

## GRUPO 2: Ferramentas B3-Especificas (6)

---

### [8] visao_setorial_b3
**O que faz:** Scaneia os 14 setores da B3 e mostra quais estao em alta/baixa.
**Quando usar:** Para ter uma visao macro de quais setores estao com momentum.
**Requer internet:** Nao (com offline=True)

**Como chamar:**
```
visao_setorial_b3(offline=True)
```

**O que retorna (por setor):**
- % de ativos em alta
- Classificacao de momentum: FORTE / MODERADO / FRACO
- Lista de ativos com tendencia de cada um

**14 setores:** Financeiro, Petroleo e Gas, Mineracao e Siderurgia, Energia Eletrica, Consumo, Saude, Telecomunicacoes, Tecnologia, Construcao Civil, Papel e Celulose, Alimentos, Transporte e Logistica, Seguros, Saneamento

---

### [9] scanner_setor_b3
**O que faz:** Mostra todos os ativos de um setor com analise Hi-Lo detalhada.
**Quando usar:** Para mergulhar em um setor especifico.
**Requer internet:** Nao (com offline=True)

**Como chamar:**
```
scanner_setor_b3("Financeiro", offline=True)
scanner_setor_b3("Mineracao", offline=True)
```

**O que retorna (por ativo):**
- Tendencia, preco, activator
- Dias na tendencia, RSI
- Win rate, retorno 12m, profit factor

---

### [10] analise_indice_b3
**O que faz:** Analisa os constituintes de um indice da B3 e mostra o breadth.
**Quando usar:** Para saber se o mercado esta BULL ou BEAR pela quantidade de ativos em alta.

**Como chamar:**
```
analise_indice_b3("IBOVESPA", offline=True)
analise_indice_b3("SMLL", offline=True)
analise_indice_b3("IDIV", offline=True)
```

**Indices disponiveis:** IBOVESPA, SMLL, IDIV, IBRX100

**O que retorna:**
- Breadth: BULL (>60% alta) / BEAR (<40%) / NEUTRO
- Total em alta vs em baixa
- Lista de cada ativo com tendencia e RSI

---

### [11] screener_b3
**O que faz:** Filtra ativos da B3 por tendencia, setor, profit factor, e ordena.
**Quando usar:** Para encontrar as melhores oportunidades segundo seus criterios.

**Como chamar:**
```
screener_b3(filtro_tendencia="ALTA", min_profit_factor=1.5, ordenar_por="retorno", offline=True)
screener_b3(filtro_setor="Financeiro", offline=True)
screener_b3(ordenar_por="profit_factor", offline=True)
```

**Parametros:**
- `filtro_tendencia` — "ALTA" ou "BAIXA" (ou None para todos)
- `filtro_setor` — nome do setor (ou None para todos)
- `min_profit_factor` — PF minimo (ex: 1.5)
- `ordenar_por` — "retorno", "profit_factor" ou "dias"

---

### [12] plano_trade_b3
**O que faz:** Gera um plano de trade completo com entrada, stop, alvos e risco/retorno.
**Quando usar:** Antes de abrir uma posicao.

**Como chamar:**
```
plano_trade_b3("COGN3", offline=True)
```

**O que retorna:**
- Tipo: COMPRA / AGUARDAR / NEUTRO
- Entrada sugerida, stop loss, alvo 1, alvo 2
- Risco/retorno (ex: 1:2.5)
- Historico do Hi-Lo no ativo (win rate, PF)
- Disclaimer educacional

---

### [13] fibonacci_b3
**O que faz:** Calcula niveis de Fibonacci (retracao e extensao) com base nos ultimos 3 anos.
**Quando usar:** Para encontrar suportes e resistencias chave.

**Como chamar:**
```
fibonacci_b3("VALE3", offline=True)
```

**O que retorna:**
- Topo e fundo de 3 anos
- 7 niveis de retracao: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
- 4 niveis de extensao: 127.2%, 161.8%, 200%, 261.8%
- Suporte e resistencia de Fibonacci mais proximos do preco atual
- Posicao atual em relacao aos niveis

---

## GRUPO 3: Analise Avancada (4)

---

### [14] analise_multiagente_b3
**O que faz:** 3 agentes analisam o ativo independentemente e dao um veredito conjunto.
**Quando usar:** Para ter uma analise mais robusta com multiplas perspectivas.

**Como chamar:**
```
analise_multiagente_b3("COGN3", offline=True)
```

**Os 3 agentes:**
- **Tecnico** (score 0-4): Hi-Lo, RSI, SMA crossover
- **Momentum** (score 0-3): Volume relativo, duracao da tendencia
- **Risco** (score 0-3): Profit factor, retorno, win rate

**Vereditos:** FORTE COMPRA / COMPRA / NEUTRO / VENDA / FORTE VENDA

---

### [15] volume_breakout_b3
**O que faz:** Detecta ativos com volume muito acima da media (possivel breakout).
**Quando usar:** Para encontrar ativos com movimentacao institucional anormal.

**Como chamar:**
```
volume_breakout_b3(multiplicador=2.0, offline=True)   # volume >= 2x media
volume_breakout_b3(multiplicador=1.5, offline=True)   # volume >= 1.5x media
```

**O que retorna:**
- Lista de ativos com volume acima do multiplicador
- Volume atual vs media, ratio, variacao do dia
- Tendencia Hi-Lo de cada ativo

---

### [16] noticias_b3
**O que faz:** Busca noticias financeiras brasileiras em tempo real via RSS.
**Quando usar:** Para acompanhar noticias que podem impactar o mercado.
**Requer internet:** Sim

**Como chamar:**
```
noticias_b3(limite=10)
```

**Fontes:** InfoMoney, Valor Economico

**O que retorna:**
- Titulo, link, fonte, data
- Resumo de cada noticia

---

### [17] padroes_candle_b3
**O que faz:** Detecta padroes de candle nos ultimos 5 pregoes.
**Quando usar:** Para confirmar sinais do Hi-Lo com price action.

**Como chamar:**
```
padroes_candle_b3("PETR4", offline=True)
```

**Padroes detectados:**
- **Doji** (NEUTRO) — indecisao do mercado
- **Martelo** (ALTA) — possivel reversao de alta
- **Estrela Cadente** (BAIXA) — possivel reversao de baixa
- **Engolfo de Alta** (ALTA) — padrao bullish de reversao
- **Engolfo de Baixa** (BAIXA) — padrao bearish de reversao

---

## GRUPO 4: Simulacao de Opcoes (1)

---

### [18] simular_opcoes_b3
**O que faz:** Simula compra de opcoes ATM (delta ~0.5) nos sinais do Hi-Lo no modelo **always-in-market**: nunca fica sem posicao de opcao entre o primeiro sinal e o fim do periodo.
**Quando usar:** Para entender como opcoes teriam performado nos sinais do Hi-Lo e backtest de estrategias de sizing.

**IMPORTANTE:** Simulacao educacional. Nao usa dados reais de opcoes da B3. Usa Black-Scholes com volatilidade historica e Selic dinamica via BCB.

**Como chamar:**
```python
# Modo legado (agregado): cada trade independente, sem banca
simular_opcoes_b3("PETR4", vencimento_dias=21, offline=True)

# Lote fixo: compra N lotes por trade
simular_opcoes_b3("PETR4", offline=True,
                  banca_inicial=2000, sizing_mode="lote_fixo", sizing_valor=1)

# Fracao da banca corrente (dinamico, compoe):
simular_opcoes_b3("PETR4", offline=True,
                  banca_inicial=2000, sizing_mode="fracao_banca", sizing_valor=0.15)

# Teto absoluto em R$ por trade:
simular_opcoes_b3("PETR4", offline=True,
                  banca_inicial=10000, sizing_mode="teto_absoluto", sizing_valor=1000)

# Fracao do capital inicial fixo (equivalente ao teto absoluto):
simular_opcoes_b3("PETR4", offline=True,
                  banca_inicial=10000, sizing_mode="fracao_capital", sizing_valor=0.10)
```

**Parametros:**
- `ticker` — codigo da acao
- `vencimento_dias` — dias ate vencimento (default: 21 = ~1 mes)
- `offline` — usar dados salvos
- `banca_inicial` — capital inicial em R$ (obrigatorio para `sizing_mode != "agregado"`)
- `sizing_mode` — modelo de alocacao por trade (ver abaixo)
- `sizing_valor` — parametro do sizing (lotes, fracao ou R$, conforme modo)
- `lote_tamanho` — tamanho do lote de opcoes (default 100)

**Modos de sizing:**
- `"agregado"` (default) — comportamento legado. Cada trade independente, sem banca nem equity curve. Retorno **identico** ao contrato anterior (backward compatible).
- `"lote_fixo"` — compra `int(sizing_valor)` lotes por trade. Skip se banca nao cobrir.
- `"fracao_banca"` — usa `sizing_valor * banca_corrente` como orcamento (0 < valor <= 1). Dinamico com o crescimento da banca.
- `"teto_absoluto"` — usa ate `sizing_valor` R$ por trade, independente da banca (limitado pelo caixa).
- `"fracao_capital"` — teto fixo = `sizing_valor * banca_inicial` (0 < valor <= 1). Equivalente a `teto_absoluto` quando o valor deriva do capital inicial.

**Logica (always-in-market):**
- Sinal de COMPRA do Hi-Lo → abre CALL ATM
- Sinal de VENDA do Hi-Lo → abre PUT ATM
- Sinal oposto → fecha a opcao atual (motivo SINAL_OPOSTO) e **reverte imediatamente** pra a do outro lado
- Vencimento sem sinal oposto → fecha por VENCIMENTO e **rola** pra uma nova opcao do mesmo lado da tendencia vigente (CALL se ALTA, PUT se BAIXA) — motivo ROLL_VENCIMENTO
- Ultimo candle fecha posicao residual por FIM_PERIODO
- **Skip por falta de caixa (apenas com sizing ativo):** quando nao cabe nem 1 lote, o sinal e pulado, `trades_pulados` incrementa e o always-in-market e temporariamente quebrado. A flag `always_in_market_quebrado` no retorno sinaliza isso.

**O que retorna:**
- Total de operacoes (calls + puts)
- Win rate, retorno total (opcoes vs acao)
- Alavancagem media
- Cada operacao: strike, premio pago, premio saida, resultado em R$ e %, `motivo_abertura` (SINAL_COMPRA/SINAL_VENDA/ROLL_VENCIMENTO) e `motivo_saida` (SINAL_OPOSTO/VENCIMENTO/FIM_PERIODO)
- Comparativo opcao vs acao em cada trade
- **Quando `sizing_mode != "agregado"`**: secao `sizing` adicional com `banca_inicial`, `banca_final`, `lucro_liquido`, `retorno_pct`, `pico`, `vale`, `max_drawdown_pct`, `trades_executados`, `trades_pulados`, `total_lotes`, `lote_tamanho`, `equity_curve` (lista de tuplas `(data, banca)`). E cada operacao ganha `lotes`, `custo_total_rs`, `pnl_trade_rs`, `banca_pos_trade`.

---

## FASE 12: Dashboards Superset (opcional)

### Tool 19: `refresh_dashboard_b3`

Atualiza o banco SQLite consumido por dashboards Apache Superset (ou por
consultas SQL diretas).

**Uso:**

```python
refresh_dashboard_b3()                              # todos os 26 tickers offline
refresh_dashboard_b3(tickers=["PETR4", "VALE3"])    # 2 tickers especificos
refresh_dashboard_b3(offline=False)                 # usa Yahoo Finance ao vivo
```

**O que faz:** roda `analisar_hilo`, `executar_backtest` e `simular_opcoes_hilo`
para cada ticker e grava 8 tabelas em `C:\b3-analytics\b3_analytics.db`
(caminho configuravel via variavel de ambiente `B3_ANALYTICS_DB`).

**Retorno (JSON):**

```json
{
  "status": "ok",
  "ok": 26,
  "fail": 0,
  "duration_sec": 0.9,
  "run_id": 5,
  "db_path": "C:\\b3-analytics\\b3_analytics.db"
}
```

**Pre-requisito para visualizar no Superset:** a instalacao via WSL2 esta
pausada por decisao do usuario. Enquanto isso, o banco SQLite pode ser
consultado diretamente:

```bash
sqlite3 C:\b3-analytics\b3_analytics.db "SELECT ticker, profit_factor FROM v_hilo_latest ORDER BY profit_factor DESC LIMIT 10"
```

**Tabelas disponiveis:** `ingest_runs`, `tickers`, `hilo_analysis`,
`hilo_trades`, `hilo_signals`, `backtest_results`, `backtest_trades`,
`options_sim_summary`, `options_sim_trades`.

**Views:** `v_hilo_latest`, `v_backtest_latest`, `v_options_latest` — trazem
sempre a ultima `run` com `status='ok'` por ticker.

---

## Gerar Relatorio em Lote

Para gerar o relatorio de todos os 26 ativos de uma vez:

```bash
cd b3-mcp-server
python gerar_relatorio.py
```

Isso cria:
- `relatorios/resumo_hilo_26ativos.csv` — planilha com todas as metricas
- `relatorios/relatorio_hilo_completo.json` — dados completos
- `relatorios/graficos/` — 26 imagens PNG (uma por ativo)

---

## Atualizacao automatica dos datasets

Os 26 JSONs em `src/b3_mcp/core/data/samples/` sao re-baixados do Yahoo
Finance toda semana via Windows Task Scheduler. Janela: 3 anos diarios
(~750 candles por ativo).

**Rodar manualmente:**

```bash
cd b3-mcp-server
atualizar_datasets.bat
```

Ou direto em Python:

```bash
python atualizar_datasets.py
```

**Logs:** cada execucao gera (ou appenda em) `relatorios/update_log_YYYY-MM-DD.txt`
com `[OK] TICKER: N candles, ultima data` ou `[ERRO] TICKER: mensagem`.

**Exit codes:**
- `0` — todos os 26 tickers atualizados
- `1` — atualizacao parcial (alguns tickers falharam)
- `2` — falha total (rede caiu, Yahoo fora do ar)

**Tarefa agendada:** `B3_MCP_UpdateDatasets` roda todo sabado as 06:00.
Detalhes completos (schtasks, troubleshooting, como deletar) estao em
`AGENDAMENTO.md`.

**Fonte unica da verdade:** a janela `range=3y` vive em
`gerar_datasets_v2.py:52`. Pra mudar pra 5 anos ou 1 ano, editar so essa
linha — o `atualizar_datasets.py` reutiliza a mesma funcao `baixar_historico`.

---

## Testes

Suite pytest cobrindo o nucleo do MCP. Rodar antes de qualquer
refatoracao nos modulos centrais.

```bash
cd b3-mcp-server
pip install -e ".[dev]"   # so na primeira vez
pytest tests/ -v
```

**Cobertura atual:** 350 testes em ~0.8s.

| Arquivo | Testes | Escopo |
|---|---|---|
| `tests/test_parsers.py` | 48 | `superset_ingest/parsers.py` (`_parse_num`, `_parse_trade_entrada`, `_pf_guard`) |
| `tests/test_indicators_calc.py` | 32 | `indicators_calc.py`: SMA, EMA, RSI, MACD, Bollinger, Hi-Lo (offset 1-bar) |
| `tests/test_hilo_service.py` | 36 | helpers privados + `analisar_hilo(offline=True)` end-to-end + cobertura long/short reversal |
| `tests/test_backtest_service.py` | 35 | 6 strategy runners parametrizados + `_calcular_metricas` + `executar_backtest` + cobertura Hi-Lo LONG/SHORT always-in-market |
| `tests/test_yahoo_finance.py` | ~60 | `yahoo_finance.py` + `obter_cotacao_indice` com mocks HTTP |
| `tests/test_screener_provider.py` | ~40 | `screener_provider.py` + filtros TradingView com mocks |
| `tests/test_peripheral.py` | ~100 | Módulos periféricos: formatting, b3_sectors, chart_service, options_sim, superset_ingest |

**Fixtures compartilhadas** em `tests/conftest.py`:
- `candles_sinteticos` — 30 candles em uptrend linear puro
- `candles_flat` — 30 candles com volatilidade zero
- `candles_petr4` — dataset real PETR4 (~750 candles, 3 anos)
- `fechamentos_sinteticos` — serie de fechamentos do uptrend

**Sem mocks de HTTP:** os testes usam so o modo `offline=True`, entao
rodam 100% determinsticos sem dependencia de rede.

---

## [20] Calculadora Interativa de Backtest (Streamlit)

**Camada UI** em cima do `backtest_service` e `options_sim`. Não duplica
nenhuma lógica — só coleta parâmetros via formulário, itera por ticker e
renderiza os resultados em 6 abas.

**Instalação:**
```bash
pip install -e ".[ui]"
```

**Rodar:**
```bash
streamlit run app_calculadora.py
```

Ou clique 2x em `app_calculadora.bat` no Windows.

**Formulário (sidebar):**
- **Estratégia** — dropdown com `hilo`, `rsi`, `sma_crossover`,
  `ema_crossover`, `macd`, `bollinger`, `todas` (modo comparativo roda as 6)
- **Período Hi-Lo** — slider 5-30 (default 10)
- **Ativos** — multiselect com os 26 tickers offline
- **Máx. de ativos** — slider pra limitar execução
- **Capital total** + **Capital dedicado à estratégia** — R$
- **Sizing (opções):** modo (`agregado`/`lote_fixo`/`fracao_banca`/
  `teto_absoluto`/`fracao_capital`) + valor numérico
- **Limite de risco por operação** — atalho Tio Huli (default 1%)
- **Máx. de operações** — 0 = ilimitado
- **Tamanho do lote** — default 100 contratos
- **Incluir simulação de opções** — checkbox (Black-Scholes ATM)

**Output (6 abas):**

1. **Resumo por Ativo** — tabela com trades, taxa de acerto, lucro %,
   profit factor, max DD, retorno das opções (se marcado).
2. **Totalizador Carteira** — métricas agregadas (total trades, retorno
   médio, retorno acumulado, melhor/pior ativo).
3. **Equity Curve** — `st.line_chart` multi-ticker reconstruído como
   `100 × ∏(1 + lucro_pct/100)` pra cada ativo.
4. **Trades Detalhados** — DataFrame completo com scroll interno (altura
   dinâmica, sem paginação) e seletor de ativo quando mais de 1 foi processado.
5. **Heatmap** — `DataFrame.style.background_gradient` colorindo
   lucro_pct/taxa_acerto/profit_factor/max_dd/trades.
6. **Export** — download CSV (resumo) + JSON (completo com parâmetros
   + trades + métricas + opções).

**Constraints arquiteturais:**
- **Zero modificação** dos services (`backtest_service.py`,
  `options_sim.py`, `hilo_service.py`)
- **Offline sempre** (`offline=True` hardcoded) — não faz requisição HTTP
- **Sem persistência** no MVP — tudo em memória
- **Dark theme** como default (`.streamlit/config.toml`), com suporte a
  light mode via menu hamburger → Settings → Theme (sem quebra de contraste)

**Tutorial integrado:** o expander "📖 Tutorial" no topo da página carrega
`docs/TUTORIAL_CALCULADORA.md` — inclui explicação campo a campo da seção
Capital & Sizing com exemplos numéricos, receitas prontas por perfil
(iniciante / intermediário / avançado) e tabela de erros comuns.

**Deploy no Streamlit Community Cloud:**
- URL: `b3-mcpserver.streamlit.app`
- Repo: `fkdias/b3-mcp-server`, branch `main`, main file `app_calculadora.py`
- Dependências: `requirements.txt` (streamlit, pandas, requests, matplotlib)
- Python: 3.12
- Sem secrets necessários (tudo offline)

**Stack adicional:** `streamlit>=1.30` + `pandas>=2.0` em
`[project.optional-dependencies].ui` (não entra no caminho do MCP server —
se não instalar o extra, a calculadora simplesmente não sobe).

---

## Dicas de Uso

1. **Comece pelo panorama:** Use `panorama_mercado_b3()` para ver o mercado geral
2. **Identifique setores fortes:** Use `visao_setorial_b3()` para ver quais setores estao com momentum
3. **Filtre os melhores:** Use `screener_b3(filtro_tendencia="ALTA", min_profit_factor=1.5)` para encontrar os melhores ativos
4. **Analise a fundo:** Use `hilo_activator()` para analise completa com grafico
5. **Confirme com multi-agente:** Use `analise_multiagente_b3()` para validar
6. **Monte o trade:** Use `plano_trade_b3()` para entrada, stop e alvos
7. **Suportes/resistencias:** Use `fibonacci_b3()` para niveis chave
