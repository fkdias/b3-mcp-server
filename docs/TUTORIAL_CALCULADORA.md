# 📖 Tutorial — Calculadora Interativa de Backtest

Este tutorial explica **cada campo da barra lateral** da calculadora. A barra
lateral é dividida em **4 seções** (Estratégia, Ativos, Capital & Sizing e o
botão final). Leia antes de rodar a primeira simulação — entender os campos
evita interpretar resultados errados.

> 💡 **Regra de ouro:** todos os cálculos são feitos contra dados **offline**
> (JSONs em `src/b3_mcp/core/data/samples/`, ~3 anos de candles diários por
> ativo). Nenhuma requisição HTTP é feita — rode quantas vezes quiser.

---

## 1. Seção "Estratégia"

### 🧠 Estratégia de backtest

**Dropdown com 7 opções.** Define a lógica de compra/venda que será aplicada em
cada ativo selecionado.

| Valor | O que faz | Quando usar |
|---|---|---|
| `hilo` | **Hi-Lo Activator** — estratégia principal do projeto. Always-in-market: sempre LONG ou SHORT, inverte a posição quando o sinal vira. | Default — é a estratégia oficial do Tio Huli. |
| `rsi` | Compra quando RSI < 30 (sobrevendido), vende quando RSI > 70 (sobrecomprado). | Ativos lateralizados com oscilação clara. |
| `sma_crossover` | Cruzamento de médias simples (SMA 9 vs SMA 21). Golden cross → compra, death cross → vende. | Tendências longas e suaves. |
| `ema_crossover` | Igual acima, mas com média exponencial (mais reativa que SMA). | Tendências com mais ruído. |
| `macd` | Cruzamento da linha MACD com sua linha de sinal. | Confirmar momentum. |
| `bollinger` | Compra quando preço toca banda inferior, vende quando toca superior. | Reversão à média. |
| `todas` | **Roda todas as 6 estratégias em paralelo** pra o mesmo ativo. A calculadora mostra a melhor no resumo. | Quando você não sabe qual usar — use `todas` primeiro como exploração, depois fixe numa específica. |

**Exemplo prático:** escolha `hilo` se quer validar o setup Tio Huli. Escolha
`todas` se quer comparar qual estratégia funciona melhor num ativo específico
antes de decidir operar.

### 🎚️ Período Hi-Lo (slider 5–30)

Controla o **período do Hi-Lo Activator** (quantos candles olhar pra trás ao
calcular a média móvel das máximas e mínimas).

- **5** = muito reativo, muitos sinais falsos, bom pra day trade agressivo.
- **10** = **default recomendado** — equilíbrio entre sinais e ruído.
- **20** = suave, poucos sinais, bom pra swing de semanas.
- **30** = extremamente conservador, só pega tendências muito longas.

**Impacto:** só afeta as estratégias `hilo` e a simulação de opções (que
também usa Hi-Lo como gatilho). Nas outras estratégias (`rsi`, `sma_crossover`,
etc.) este slider é ignorado.

---

## 2. Seção "Ativos"

### 📋 Selecione os tickers

**Multiselect com os 26 datasets offline** disponíveis. Lista inclui PETR4,
VALE3, ITUB4, WEGE3, BBDC4, etc. Você pode:

- **Adicionar** clicando em qualquer ticker disponível no dropdown.
- **Remover** clicando no `×` ao lado de cada tag selecionada.
- **Limpar tudo** clicando no `×` grande à direita do campo.

Por default, os **3 primeiros** da lista já vêm selecionados — é só clicar
Rodar pra ver um resultado imediato.

### 🔢 Máx. de ativos a processar

Slider que **limita quantos dos selecionados acima serão efetivamente
processados**. Útil quando você seleciona 15 ativos mas quer testar só com 5
primeiro pra verificar se os parâmetros fazem sentido antes de rodar tudo.

**Por que existe:** porque rodar 26 ativos × estratégia `todas` × opções
marcadas é ~1-2 minutos de CPU. Começa com 3-5 pra iterar rápido, depois
expande.

---

## 3. Seção "Capital & Sizing"

Esta é a seção **mais importante e mais confusa** — leia com atenção. Os
campos de sizing só afetam a simulação de **opções** (quando o checkbox
`Incluir opções` estiver marcado). O backtest de ações em si ignora o sizing
(sempre opera 1 unidade por sinal).

### 💰 Capital total da banca (R$)

**Quanto dinheiro total você tem na conta da corretora**, considerando todas
as estratégias somadas. Default R$ 10.000.

**Exemplo:** Se você tem R$ 50.000 na XP, preenche `50000`. Este valor NÃO é
usado pelos runners de backtest — é só um contexto pra calcular percentuais
na aba "Totalizador Carteira". Pense nele como "o denominador" dos retornos
que você vai comparar depois.

### 🎯 Capital dedicado à estratégia (R$)

**Quanto do seu capital total você quer alocar pra ESTA simulação específica**.
Default R$ 5.000.

**Exemplo:** Se você tem R$ 50.000 total mas só quer arriscar R$ 5.000 na
estratégia Hi-Lo com opções, preenche `5000` aqui. Este é o valor que a
simulação de opções usa como **banca inicial** — é sobre ele que o retorno
final é calculado.

**Relação prática:** `capital estratégia / capital total = % do patrimônio
arriscado`. Se deu 10%, você está numa postura conservadora (metodologia Tio
Huli recomenda ≤ 10% por estratégia).

### ⚙️ Modo de sizing (opções)

**Dropdown com 5 modos** que definem **como a quantidade de contratos de
opção é calculada** a cada trade. Este é o coração do risk management do
simulador.

| Modo | O que significa | Campo "Valor do sizing" é interpretado como |
|---|---|---|
| `agregado` | **Default.** Compra 1 lote fixo por trade, ignora a banca. Modo mais simples — usa quando só quer ver sinais funcionando. | Irrelevante (o valor é ignorado internamente). |
| `lote_fixo` | Compra **N lotes fixos** por trade, sempre a mesma quantidade. | Número de lotes (ex: `3` = 3 lotes × 100 contratos = 300 contratos por trade). |
| `fracao_banca` | Arrisca **X% da banca atual** em cada trade. Banca cresce → trade maior (martingale). Banca cai → trade menor (defensivo). | Fração decimal (ex: `0.02` = 2% da banca). |
| `teto_absoluto` | **Nunca arrisca mais de R$ X num trade.** Se o prêmio ATM custa R$ 200, compra `X / 200` lotes. | Teto em reais (ex: `100` = máx R$ 100 por trade — atalho Tio Huli 1% de R$ 10.000). |
| `fracao_capital` | Arrisca **X% do capital INICIAL** (não da banca atual — igual a lote_fixo proporcional). | Fração decimal (ex: `0.01` = 1% do capital fixo). |

**Recomendação Tio Huli:** comece com `teto_absoluto` + valor = **1% do
capital dedicado à estratégia**. É a postura mais defensiva e a que a
metodologia documentada usa.

### 🔢 Valor do sizing

Número que o campo acima interpreta. **O significado muda conforme o modo**
(ver tabela acima). Leia o tooltip `(?)` ao lado do campo em caso de dúvida.

**Armadilha comum:** se você escolheu `fracao_banca` e preencheu `1.0`, está
dizendo "arrisca 100% da banca por trade" — vai explodir no primeiro loss.
Fração é decimal (0.01 = 1%, 0.1 = 10%).

### 🛡️ Limite de risco por operação — atalho Tio Huli

Slider **informativo**, de 0.5% a 10% (default 1%). **Este slider NÃO é
aplicado automaticamente** — serve apenas como referência visual do que a
metodologia Tio Huli recomenda.

**O que fazer com ele:** use como lembrete. Se você escolheu `teto_absoluto`
com valor R$ 500 numa banca de R$ 10.000 (= 5%), mas o slider mostra 1%, você
está fora da metodologia. Ajuste o valor do sizing pra R$ 100.

> 🚨 Este slider existe pra você **não esquecer** qual é o limite recomendado.
> Ele NÃO sobrepõe os valores do sizing — esses são a fonte de verdade real.

### 🔢 Máx. de operações (0 = ilimitado)

**Trava o número máximo de trades** que a simulação executará antes de parar.
Default `0` = sem limite (roda tudo o que a estratégia gerar no período
histórico).

**Quando usar:** se você está testando "e se eu parasse depois de 50 trades?"
ou "qual a performance nos primeiros 20 sinais?". Para análise normal, deixe
em `0`.

### 📦 Tamanho do lote (opções)

Quantos contratos tem 1 lote de opção. **Default = 100** (padrão da B3 pra
opções de ações brasileiras).

**Quando mexer:** você praticamente nunca precisa mexer nisso. Só muda se
estiver simulando outro mercado (opções de índice, futuros, etc.).

### ☑️ Incluir simulação de opções (Black-Scholes ATM)

**Checkbox principal** que ativa/desativa a simulação de opções na execução.

- **Desmarcado (default):** só roda o backtest da **ação à vista** usando a
  estratégia selecionada. Rápido (1-2 segundos por ativo), métricas simples.
- **Marcado:** além do backtest da ação, roda a simulação de **opções ATM**
  via Black-Scholes, aplicando o sizing mode escolhido. Mostra uma coluna
  extra "Opções Retorno" no resumo e um resultado de banca final na simulação
  de sizing.

**Quando marcar:** quando você quer validar a **metodologia completa Tio
Huli** (Hi-Lo gerando sinais → opções ATM sendo abertas/fechadas → banca
evoluindo com sizing). Sem marcar, a calculadora é só um backtest de ação
convencional.

⚠️ **Aviso metodológico importante:** a simulação de opções é **teto teórico**,
não retorno executável. Ver `memory/project_b3_mcp_plugin.md` seção
"Auditoria metodológica" pra entender os 6 vícios do modelo (bid-ask = 0,
liquidez infinita, IV = HV, zero custos, survivorship, fill no close).

---

## 4. Botão 🚀 Rodar Backtest

Submete o formulário e dispara a execução. **Nada acontece até você clicar
aqui** — pode mexer nos campos à vontade sem medo de consumir CPU.

Após clicar, a área principal mostra:
1. Barra de progresso por ativo
2. Erros (se houver) num expander
3. As 6 abas de output: **Resumo por Ativo**, **Totalizador Carteira**,
   **Equity Curve**, **Trades Detalhados**, **Heatmap**, **Export**

---

## Workflow recomendado pro primeiro uso

1. Deixa a estratégia em `hilo` e período em `10` (defaults).
2. Selecione **3 ativos** que você conhece (ex: PETR4, VALE3, ITUB4).
3. Deixa capital total em R$ 10.000 e capital dedicado em R$ 5.000.
4. **Não marque** o checkbox de opções (começa com ação pura).
5. Clica **Rodar Backtest**.
6. Lê as abas **Resumo** e **Totalizador** pra ver se os ativos têm
   performance positiva na estratégia escolhida.
7. **Depois** marca o checkbox de opções, escolhe `teto_absoluto` com valor
   `50` (1% de R$ 5.000), e roda de novo. Compare o retorno da ação com o
   retorno da opção.
8. Repete com `estrategia=todas` pra ver qual runner produz melhor resultado
   em cada ativo.

---

## FAQ rápido

**P: Posso usar ticker que não está na lista?**
R: Não. A calculadora é offline-only. Pra adicionar novo ticker, rode o
script `atualizar_datasets.py` com o ticker incluso em `gerar_datasets_v2.py`
primeiro.

**P: Os resultados são reais ou simulação?**
R: **Simulação.** Backtest histórico sobre ~3 anos de candles. Opções usam
Black-Scholes, não dados reais da B3. Ver aviso metodológico acima.

**P: Posso rodar várias simulações sem reiniciar?**
R: Sim. Basta mudar os campos e clicar **Rodar Backtest** de novo — o estado
anterior é substituído.

**P: Onde ficam salvos os resultados?**
R: **Em lugar nenhum** por padrão (MVP sem persistência). Use a aba **Export**
pra baixar CSV/JSON antes de fechar a aba do navegador.

**P: Posso rodar no celular?**
R: Não. O Streamlit sobe em `localhost:8501` — precisa estar no mesmo
computador onde o processo Python está rodando.
