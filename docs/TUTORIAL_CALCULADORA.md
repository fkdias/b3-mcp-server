# 👋 Tutorial para Iniciantes — Calculadora de Backtest

> **Primeira vez mexendo com backtest de ações?** Este guia é pra você.
> Nada de jargão de trader — vamos do zero.

---

## O que essa calculadora faz, em 1 parágrafo

Imagine que você tivesse uma máquina do tempo e pudesse voltar **3 anos**,
comprar e vender ações seguindo uma regra fixa, e depois ver quanto você
ganhou ou perdeu. Essa calculadora é essa máquina do tempo. Você escolhe
a regra ("estratégia"), escolhe os ativos, aperta o botão, e ela simula
o que teria acontecido se você tivesse operado de verdade. O resultado
final mostra quantas operações foram feitas, quantas deram lucro e
quanto dinheiro você teria ganhado (ou perdido).

**Importante:** é uma **simulação**, não a realidade. Serve pra **testar
ideias** antes de arriscar dinheiro de verdade. Resultado bom no passado
**não garante** que vai repetir no futuro.

---

## Conceitos básicos (leia antes de mexer)

### O que é "backtest"?

Backtest = **teste para trás**. É quando você aplica uma regra de compra
e venda em dados do passado para ver o que teria acontecido. Por exemplo:
"Se eu tivesse comprado PETR4 toda vez que o RSI ficou abaixo de 30 e
vendido quando passou de 70, quanto eu teria ganhado nos últimos 3 anos?"

A calculadora responde essa pergunta automaticamente, pra várias regras
e vários ativos ao mesmo tempo.

### O que é "estratégia"?

Estratégia = **a regra de compra e venda** que você quer testar. Tipo
uma receita de bolo. Exemplos:

- **"Compre quando o preço cruzar pra cima da média de 9 dias e venda
  quando cruzar pra baixo"** → estratégia SMA crossover
- **"Compre quando o Hi-Lo virar pra cima e venda quando virar pra
  baixo"** → estratégia Hi-Lo (a principal do projeto)
- **"Compre quando o RSI ficar < 30 e venda quando > 70"** → estratégia RSI

Você NÃO precisa entender cada estratégia por dentro pra usar a
calculadora. Basta saber que cada uma é uma "receita" diferente.

### O que é "ativo" ou "ticker"?

Ativo = **uma ação da bolsa**. Cada ação tem um código de 4-6 letras:
PETR4 é Petrobras, VALE3 é Vale, ITUB4 é Itaú. Esses códigos são
chamados de **tickers**.

A calculadora vem com **26 ativos** prontos pra usar (os mais
negociados da B3). Não dá pra adicionar ativo novo pela interface.

### O que é "candle"?

Candle = **uma barra no gráfico de preços**, geralmente representando
**1 dia** de negociação. Cada candle tem 4 números:

- **Abertura** — o preço no começo do dia
- **Máxima** — o preço mais alto do dia
- **Mínima** — o preço mais baixo do dia
- **Fechamento** — o preço no final do dia

A calculadora tem cerca de **750 candles** por ativo (3 anos de
negociação). Ela usa isso como "histórico" pra simular os trades.

### O que é "trade"?

Trade = **uma operação completa**. Comprou hoje, vendeu daqui 5 dias
com lucro? Isso foi 1 trade. A calculadora conta quantos trades a
estratégia teria feito nos 3 anos de histórico.

---

## Passo a passo — Como fazer sua primeira simulação

> 👉 **Se você está com pressa, faça só os passos 1-5 e ignore o resto.**

### Passo 1 — Escolha a estratégia (primeiro campo da barra lateral)

O dropdown mostra 7 opções. **Para começar, escolha `hilo`.** É a
estratégia principal do projeto e a que foi mais testada.

> 💡 Se você quiser comparar várias estratégias ao mesmo tempo, escolha
> `todas`. A calculadora vai rodar as 6 e mostrar qual foi a melhor.

### Passo 2 — Deixe o período Hi-Lo em 10

Não mexa nesse slider. **10 é o valor recomendado** e funciona bem pra
maioria dos casos. Só mexa depois que você entender o que ele faz
(explicado lá embaixo na seção "Conceitos avançados").

### Passo 3 — Escolha os ativos

No campo "Selecione os tickers", **clique 3 ações que você conhece**.
Por exemplo: **PETR4, VALE3, ITUB4**. Essas 3 são as mais famosas do
Brasil.

> 💡 Comece com poucos ativos (2-3). Depois que entender o resultado,
> você pode testar com 10 ou 20 de uma vez.

### Passo 4 — Capital: deixe os valores padrão

- **Capital total da banca:** deixe em **R$ 10.000**
- **Capital dedicado à estratégia:** deixe em **R$ 5.000**

Esses números servem pra calcular o retorno percentual depois. Você
não está arriscando dinheiro de verdade.

> 👉 Quer entender **o que cada campo da seção Capital & Sizing faz
> em detalhe**? Pula pra seção **"Capital & Sizing — entendendo cada
> campo"** mais abaixo. Tem explicação campo por campo com exemplos
> numéricos concretos.

### Passo 5 — **NÃO marque** o checkbox de opções (ainda)

Lá embaixo tem um checkbox "Incluir simulação de opções". **Deixe
desmarcado na primeira vez.** Opções é um instrumento mais avançado e
vamos deixar pra depois.

### Passo 6 — Clique **🚀 Rodar Backtest**

O botão azul grande no final da barra lateral. Leva 2-5 segundos.

### Passo 7 — Leia o resultado

Vão aparecer várias abas no meio da tela. **Comece pela aba "Resumo
por Ativo"**. Nela você vê, pra cada ação que você escolheu:

- **Trades** = quantas operações a estratégia fez (ex: 59)
- **Taxa de acerto** = de cada 10 trades, quantos deram lucro (ex: "45%"
  = 4,5 em cada 10)
- **Lucro %** = quanto a estratégia teria rendido ao longo dos 3 anos
- **Profit Factor** = quanto você ganhou dividido por quanto perdeu.
  **Acima de 1,5 é bom. Acima de 2 é ótimo.** Abaixo de 1 significa que
  você perdeu mais do que ganhou.
- **Max Drawdown** = qual foi a **maior queda** na sua banca ao longo
  do tempo. Quanto mais perto de 0%, melhor. -30% significa que em algum
  momento você perdeu 30% do seu dinheiro antes de se recuperar.

### Passo 8 — Explore as outras abas

- **Totalizador Carteira** → visão geral do conjunto de ações
- **Equity Curve** → um gráfico que mostra como seu "dinheiro" teria
  crescido ao longo do tempo (curva subindo = bom)
- **Trades Detalhados** → todas as operações listadas (data de compra,
  data de venda, lucro/prejuízo de cada uma)
- **Heatmap** → tabela colorida comparando os ativos (verde = bom,
  vermelho = ruim)
- **Export** → botões pra baixar o resultado em CSV ou JSON

---

## E quando eu marco o checkbox de opções?

Quando você marca "Incluir simulação de opções", a calculadora simula
também **operações com opções de compra e venda** (chamadas **calls** e
**puts**) baseadas nos mesmos sinais da estratégia.

**O que são calls e puts?** Simplificando:

- **Call** = um bilhete que dá direito de **comprar** uma ação por um
  preço fixo no futuro. Se a ação sobe, o bilhete vale mais.
- **Put** = o contrário. Um bilhete que dá direito de **vender** por um
  preço fixo. Se a ação cai, o bilhete vale mais.

Opções são **mais arriscadas** que ações (podem zerar) mas têm potencial
de lucro maior. A calculadora simula o preço delas usando um modelo
matemático (Black-Scholes) — NÃO é o preço real de mercado.

Quando você marca o checkbox, aparece uma aba nova **🎯 Opções** com
os detalhes: quantas calls, quantas puts, quanto foi o retorno, etc.

> ⚠️ **Aviso:** a simulação de opções é **simplificada demais pra ser
> realista**. Os números que aparecem são um "teto teórico" — na
> prática, custos de corretagem, spreads e falta de liquidez em muitos
> ativos destruiriam boa parte do lucro. Use como comparação entre
> estratégias, não como previsão de quanto você ganharia de verdade.

---

## Capital & Sizing — entendendo cada campo

Esta é a seção **mais confusa** da calculadora. São 8 campos empilhados
e a maioria parece repetida. Vou destrinchar um por um, com exemplos
numéricos, pra você entender exatamente o que cada botão faz.

> 🎯 **Regra geral:** a maioria dos campos desta seção **só importa se
> você marcou o checkbox de opções no final**. Se você só quer testar
> ações à vista, só os 2 primeiros campos (capital) importam pra
> aparecer certinho na aba Totalizador — o resto pode ficar no padrão.

---

### Campo 1 — "Capital total da banca (R$)"

**Padrão:** R$ 10.000

**O que é:** o **total** de dinheiro que você tem na corretora
(teórico). A calculadora usa esse número **apenas como denominador
dos percentuais** que aparecem na aba "Totalizador Carteira".

**Analogia:** se você disser "tenho R$ 10.000 na corretora" e a
estratégia render R$ 500, a calculadora mostra "5% de retorno sobre a
banca total" (500 ÷ 10.000 = 5%).

**Importante:** mudar esse valor **NÃO muda os trades simulados**.
Não muda o número de operações, não muda os sinais, não muda o lucro
absoluto. Só muda os percentuais **informativos** na aba Totalizador.

**Na prática:** deixa em R$ 10.000 e esquece. Só mexe se quiser ver os
percentuais referenciados a uma banca diferente (ex: "e se eu tivesse
R$ 50.000?").

---

### Campo 2 — "Capital dedicado à estratégia (R$)"

**Padrão:** R$ 5.000

**O que é:** quanto, do seu capital total, você quer **separar
especificamente** pra rodar esta estratégia. Serve como **"banca
inicial"** da simulação de opções.

**Por que separar?** Boa prática de gerenciamento de risco — você não
coloca tudo numa estratégia só. Dos seus R$ 10.000 totais, talvez você
queira usar só R$ 5.000 na Hi-Lo e os outros R$ 5.000 em renda fixa,
FIIs ou outras estratégias.

**Quando esse campo importa de verdade?** Só quando você marca o
checkbox de opções **E** escolhe um modo de sizing diferente de
`agregado`. Nos outros casos, é só informativo.

**Regras práticas:**
- Capital dedicado nunca deve ser **maior** que o capital total
- Pode ser qualquer fração (20%, 30%, 50%) — o padrão de 50% é só um
  exemplo
- Esse é o valor que vira a **banca inicial** da equity curve na aba
  Opções

---

### Campo 3 — "Modo de sizing (opções)"

**Padrão:** `agregado`

**O que é "sizing"?** É a resposta pra pergunta:

> *"Quando a estratégia disser 'COMPRE', quantos contratos de opção
> eu devo comprar?"*

A calculadora tem **5 modos diferentes** de responder essa pergunta.
Cada um é uma estratégia de gerenciamento de risco diferente. Vou
explicar os 5 com **o mesmo cenário** pra ficar fácil comparar.

**Cenário base pros exemplos abaixo:**
- Banca dedicada: R$ 5.000
- Custo de 1 lote de opção no momento do sinal: R$ 300
  (prêmio R$ 3,00 × 100 contratos)

---

#### 🥇 Modo 1 — `agregado` (o padrão, mais simples)

**O que faz:** compra **1 lote em todo trade**, sempre. Não simula
banca real, não pula trade nenhum. Cada operação é contada
independentemente, como se você tivesse dinheiro infinito.

**Exemplo:** estratégia gerou 68 sinais → 68 lotes comprados, sem
exceção, total investido R$ 300 × 68 = R$ 20.400 (maior que a banca,
mas o modo `agregado` ignora isso).

**Quando usar:** **primeira vez mexendo na calculadora.** É o mais
simples e mostra o potencial "bruto" da estratégia, sem se preocupar
com realismo de banca.

**Limitação:** não simula risco de ruína. É uma visão otimista.

---

#### 🥈 Modo 2 — `lote_fixo` (você escolhe quantos lotes)

**O que faz:** compra exatamente **N lotes** em todo trade, onde N é
o número que você digita em "Valor do sizing".

**Exemplo:** sizing_valor = 3 → a cada sinal, tenta comprar 3 lotes
(3 × R$ 300 = R$ 900 por trade). Se a banca atual tiver ≥ R$ 900,
compra. Se não tiver, **pula o trade**.

**Quando usar:** quando você já entendeu o comportamento bruto e quer
testar escalas específicas — "e se eu fizesse 2 lotes em vez de 1?".

**Cuidado:** se você escolher número muito grande (ex: 10 lotes =
R$ 3.000/trade numa banca de R$ 5.000), vários trades serão pulados
por falta de caixa e sua equity curve vai ter buracos.

---

#### 🥉 Modo 3 — `fracao_banca` (arrisca X% do que tem NAQUELE momento)

**O que faz:** a cada trade, arrisca **X% da banca ATUAL** — e "atual"
significa o valor **depois** de todos os lucros e perdas anteriores.
É um modo **dinâmico** que cresce quando você ganha e encolhe quando
você perde.

**Exemplo:** sizing_valor = 0.1 (= 10%), banca atual = R$ 5.000 →
orçamento do trade = R$ 500 → compra `int(500 ÷ 300) = 1 lote`.

- Se a banca sobe pra R$ 9.000 → orçamento vira R$ 900 → **3 lotes**
- Se a banca cai pra R$ 2.000 → orçamento vira R$ 200 → **0 lotes**,
  trade pulado

**Quando usar:** **avançado.** Aproveita o efeito bola-de-neve (juros
compostos): quanto mais você ganha, mais você compra; quanto mais
perde, menos arrisca. Mas exige disciplina psicológica.

**⚠️ PERIGO MÁXIMO:** se você colocar `sizing_valor = 1.0`, significa
**100% da banca por trade**. Basta UM trade perder pra sua banca zerar.
**NUNCA use valores maiores que 0.1 (10%) aqui.** O recomendado é
**0.01 a 0.05** (1% a 5%).

---

#### 🏅 Modo 4 — `teto_absoluto` (nunca arrisca mais que R$ X por trade)

**O que faz:** a cada trade, nunca arrisca mais que **R$ X em reais**
(valor fixo). X é o que você digita em "Valor do sizing".

**Exemplo:** sizing_valor = 500 (= R$ 500 por trade), custo do lote =
R$ 300 → compra `int(500 ÷ 300) = 1 lote` (sobra R$ 200 sem usar).

- Se o lote subir pra R$ 600 → teto só cobre 0 lotes → trade pulado
- Se o lote cair pra R$ 200 → teto cobre 2 lotes → compra 2

**Quando usar:** **modo mais conservador**, recomendado pra quem tá
começando a mexer com opções. Você sabe de antemão **o prejuízo
máximo** de cada trade, então nunca toma susto.

**💡 Dica Tio Huli:** use um valor que seja ~1% da sua banca dedicada:
- Banca R$ 5.000 → teto R$ 50
- Banca R$ 10.000 → teto R$ 100
- Banca R$ 50.000 → teto R$ 500

Isso implementa de verdade a regra de "nunca arrisque mais de 1% por
trade" que o slider só menciona visualmente.

---

#### 🎖️ Modo 5 — `fracao_capital` (fração fixa do capital inicial)

**O que faz:** parecido com `fracao_banca`, mas usa o **capital
INICIAL** como base, não a banca atual. Ou seja: o orçamento por trade
fica **fixo** ao longo da simulação, mesmo se a banca subir ou cair.

**Exemplo:** banca_inicial = R$ 5.000, sizing_valor = 0.1 (10%) →
orçamento por trade = R$ 500 **sempre** (5.000 × 0.1 = 500, fixo).

- Mesmo se a banca crescer pra R$ 8.000, o orçamento continua R$ 500
- Mesmo se a banca cair pra R$ 2.000, ainda tenta orçar R$ 500
  (mas vai pular se não tiver caixa real)

**Quando usar:** quando você quer **um teto fixo proporcional** ao
tamanho inicial da banca. Mais intuitivo que o `teto_absoluto` (que
é em reais) porque você pensa em porcentagem.

**Diferença prática pro `teto_absoluto`:** zero — matematicamente são
equivalentes. A diferença é só o formato de entrada:
- `teto_absoluto` → `500` (reais)
- `fracao_capital` → `0.1` (fração do capital inicial)

Use o que for mais intuitivo pra você.

---

### Campo 4 — "Valor do sizing"

**Padrão:** 1.0

**O que é:** o número que acompanha o modo escolhido acima. O
significado **depende do modo**:

| Modo | O que digitar | Exemplo | Significa |
|---|---|---|---|
| `agregado` | Qualquer coisa | `1.0` | Ignorado, deixe 1.0 |
| `lote_fixo` | **Nº inteiro** de lotes | `3` | 3 lotes por trade |
| `fracao_banca` | **Decimal** entre 0 e 1 | `0.05` | 5% da banca atual |
| `teto_absoluto` | **Reais** por trade | `500` | R$ 500 máx/trade |
| `fracao_capital` | **Decimal** entre 0 e 1 | `0.1` | 10% do capital inicial |

**⚠️ Cuidados importantes:**

1. **Use ponto, não vírgula.** O campo aceita `0.1`, não `0,1`.

2. **O maior erro do iniciante:** digitar `1.0` no modo `fracao_banca`
   achando que é "1 lote" — mas no `fracao_banca` isso significa
   **100% da banca por trade**, e você explode no primeiro prejuízo.

3. **Pensa no zero absoluto:** colocar `0.0` em qualquer modo (exceto
   `agregado`) resulta em **zero lotes sempre** → zero trades → simulação
   vazia.

---

### Campo 5 — "Limite de risco por operação (% da banca) — atalho Tio Huli"

**Padrão:** 1% (slider)

**⚠️ ATENÇÃO:** este slider **NÃO aplica nenhum limite automaticamente**.
É só um **lembrete visual** da regra de gerenciamento de risco do
Tio Huli:

> *"Nunca arrisque mais de 1% da sua banca em uma única operação."*

O slider existe pra você ver esse número na tela e lembrar da regra.
Mas se você quiser que ela seja **respeitada de verdade**, você
precisa ajustar o **Campo 4 ("Valor do sizing")** manualmente pra bater:

- Banca R$ 5.000, regra 1% = R$ 50/trade → use `teto_absoluto` com
  valor `50`
- Banca R$ 10.000, regra 1% = R$ 100/trade → use `teto_absoluto` com
  valor `100`
- Banca R$ 5.000, regra 2% = R$ 100/trade → mesmo modo, valor `100`

**Por que o slider não aplica automaticamente?** Porque as 5 regras
de sizing são todas diferentes e forçar 1% quebraria a lógica de cada
modo. A calculadora prefere dar controle ao usuário e ser explícita
sobre o que está fazendo.

**O valor do slider aparece** na aba "Totalizador Carteira" como
informativo, pra você comparar com o que foi efetivamente configurado.

---

### Campo 6 — "Máx. de operações (0 = ilimitado)"

**Padrão:** 0 (ilimitado)

**O que faz hoje:** **nada funcional, por enquanto.** O valor só é
exibido no rodapé da aba Totalizador como informativo. O backend
não usa esse campo pra truncar trades ainda.

**Por que o campo existe:** é um placeholder pra uma feature futura
(limitar o número total de operações da simulação — ex: "quero ver o
que acontece se eu só fizer as 10 primeiras e parar").

**Como usar agora:** deixa em **0** (ilimitado). Qualquer outro valor
aparece no info box mas **não afeta nenhuma operação do backtest**.

---

### Campo 7 — "Tamanho do lote (opções)"

**Padrão:** 100

**O que é:** na B3, opções são negociadas em **lotes padrão de 100
contratos**. Quando você compra "1 lote", você está comprando 100
contratos de opção de uma só vez.

**O que digitar:** **deixa em 100, não mexe.** Esse é o padrão oficial
da B3 pra praticamente todas as opções.

**Por que o campo existe:** pra dar flexibilidade em simulações
teóricas (ex: "e se eu pudesse comprar apenas 10 contratos em vez de
100?") ou caso no futuro a B3 mude a convenção.

---

### Campo 8 — "Incluir simulação de opções (Black-Scholes ATM)"

**Padrão:** desmarcado

**O que faz quando MARCADO:** além do backtest de ações à vista, roda
também uma simulação de **opções ATM** (At-The-Money) para cada sinal
do Hi-Lo, usando o modelo Black-Scholes pra precificar as opções.
Ativa a aba 🎯 **Opções** com todas as métricas de sizing,
alavancagem e operações detalhadas.

**O que faz quando DESMARCADO:** ignora os campos 3 a 7 (sizing,
lote, etc.) e só roda backtest de ações simples. Fica mais rápido e
mais simples.

**Quando usar cada um:**
- **Primeira vez usando a calculadora** → deixa **desmarcado**. Foca
  em entender o backtest de ações primeiro.
- **Já entendi o backtest, quero explorar opções** → marca.
- **Só quero comparar estratégias sem me preocupar com derivativos**
  → deixa **desmarcado**.

---

### 🎯 Receitas prontas (pra não ter que pensar)

Se você não quer montar tudo do zero, use uma dessas combinações
testadas:

#### 🟢 Perfil Iniciante — só ações, zero risco

```
Capital total:       R$ 10.000
Capital estratégia:  R$ 5.000
Modo sizing:         agregado      (ignorado, mas deixa assim)
Valor sizing:        1.0           (ignorado)
Slider risco:        1%            (ignorado, só visual)
Máx. operações:      0             (ilimitado)
Tamanho lote:        100           (padrão B3)
☐ Incluir opções               ← DESMARCADO
```
→ Roda só backtest de ações à vista. Simples, rápido, didático.

#### 🟡 Perfil Intermediário — ações + opções conservador

```
Capital total:       R$ 10.000
Capital estratégia:  R$ 5.000
Modo sizing:         teto_absoluto ← muda aqui
Valor sizing:        50            ← R$ 50 máx por trade (= 1% da banca)
Slider risco:        1%
Máx. operações:      0
Tamanho lote:        100
☑ Incluir opções               ← MARCADO
```
→ Aplica a regra "1% por trade" de verdade. Você sabe o prejuízo
máximo de cada operação (R$ 50). Vários trades podem ser pulados se
o prêmio ficar caro, mas nenhum vai te explodir.

#### 🔴 Perfil Avançado — dinâmico com juros compostos

```
Capital total:       R$ 10.000
Capital estratégia:  R$ 5.000
Modo sizing:         fracao_banca  ← dinâmico
Valor sizing:        0.02          ← 2% da banca atual por trade
Slider risco:        2%
Máx. operações:      0
Tamanho lote:        100
☑ Incluir opções
```
→ Quando a banca cresce, você compra mais lotes; quando cai, arrisca
menos. Maximiza o potencial de juros compostos, mas exige disciplina
psicológica.

#### ☠️ NUNCA FAÇA ISSO

| Erro | Resultado |
|---|---|
| `fracao_banca` com valor `1.0` | 100% da banca por trade → zera no primeiro loss |
| `lote_fixo` com valor `100` e banca R$ 5.000 | Todo trade pulado (sem caixa) |
| `teto_absoluto` com valor `50000` e banca R$ 5.000 | Compra tudo no primeiro trade, zera no primeiro loss |
| Ignorar Max Drawdown na aba Resumo | Pode estar celebrando backtest que passou por -60% |
| Confundir `0.1` com `10` no modo `fracao_banca` | `0.1` = 10%, `10` = 1000% (ou seja, 0 lotes porque nunca cabe) |

---

## Os 4 "ajustes de risco" (resumo rápido — se você pulou a seção acima)

> 💡 Se você leu a seção "Capital & Sizing — entendendo cada campo"
> logo acima, pode pular este resumo. Ele é só um TL;DR.

Estes campos **só importam se você marcou o checkbox de opções**. Se
está só testando ações à vista, pode ignorar todos.

| Campo | Função | Valor recomendado pra iniciante |
|---|---|---|
| **Modo de sizing** | Como calcular quantos lotes comprar | `teto_absoluto` |
| **Valor do sizing** | Parâmetro do modo | `50` (R$ 50/trade) |
| **Limite de risco** | Lembrete visual da regra 1% (não aplica) | `1.0` |
| **Tamanho do lote** | Contratos por lote (padrão B3) | `100` |

**Regra de ouro:** se não sabe o que fazer, `teto_absoluto` com valor
= 1% da sua banca dedicada. Ponto final.

---

## Perguntas frequentes

### "Por que o resultado mudou quando eu apertei Rodar de novo?"
Não muda. O backtest é **determinístico** (mesmo input → mesmo output).
Se mudou, é porque você alterou algum campo sem perceber.

### "Posso usar um ticker que não está na lista?"
Não, infelizmente. A calculadora usa dados offline e só tem os 26
ativos pré-baixados. Adicionar novo ativo requer rodar um script Python.

### "Os resultados são reais?"
**Não.** É simulação histórica. O passado não garante o futuro.

### "Por que não tem dados de hoje?"
Os datasets são atualizados **uma vez por semana** (todo sábado às 6h)
por uma tarefa automática. Então tem sempre dados até o sábado mais
recente.

### "Posso acessar do celular?"
Não. A calculadora roda no seu computador (`localhost:8501`) e só é
acessível pelo navegador da mesma máquina.

### "Como salvo um resultado pra ver depois?"
Aba **Export** → clica no botão "Baixar JSON completo". Guarda o
arquivo. Não tem "salvar simulação" dentro da calculadora.

### "Qual estratégia é a melhor?"
**Depende do ativo e do período.** É pra isso que a calculadora existe
— pra você testar e descobrir. Use a opção `todas` no dropdown pra
rodar as 6 ao mesmo tempo e comparar.

### "Fiquei com lucro de 300%. Quer dizer que vou ficar rico?"
**Não.** Por 3 motivos:
1. Performance passada não se repete no futuro
2. A simulação ignora custos reais (corretagem, spread, IR, slippage)
3. Mercado real tem estresse emocional que o backtest não tem

Use os resultados como **comparação entre estratégias**, não como
previsão de retorno.

---

## Conceitos avançados (opcional)

Se você quer entender os parâmetros mais a fundo, leia as seções abaixo.
Se não, pode ignorar — o padrão funciona bem.

### "Período Hi-Lo" detalhado

Esse número controla quantos candles pra trás a estratégia Hi-Lo
olha pra decidir comprar ou vender.

- **Número baixo (5)** = a estratégia fica mais **nervosa**. Abre e
  fecha trades rapidamente. Muitos trades, muito ruído.
- **Número médio (10)** = equilíbrio. **Padrão recomendado.**
- **Número alto (30)** = a estratégia fica **sonolenta**. Poucos trades,
  só pega tendências longas.

**Analogia:** pense num motorista. Período 5 = motorista ansioso que
troca de faixa toda hora. Período 30 = motorista zen que fica 20 minutos
na mesma faixa sem mudar.

### "Profit Factor" detalhado

Profit Factor = **(soma dos ganhos) ÷ (soma das perdas)**.

- **1,0** = empatou (ganhou o mesmo que perdeu)
- **1,5** = ganhou 1,5× mais do que perdeu → **aceitável**
- **2,0** = ganhou 2× mais → **bom**
- **3,0+** = ganhou 3× ou mais → **excelente** (mas desconfie, pode ser
  curva otimizada demais)
- **Menor que 1** = perdeu mais do que ganhou → **estratégia ruim**

### "Max Drawdown" detalhado

Imagine que sua banca subiu pra R$ 15.000, depois caiu pra R$ 10.500,
depois voltou. O drawdown foi `(15000 - 10500) / 15000 = 30%`.

- **Acima de -30%** = saudável
- **-30% a -50%** = desconfortável mas tolerável
- **Pior que -50%** = você provavelmente desistiria no meio do caminho
  na vida real (psicologia humana não aguenta)

### Por que começar com `hilo`?

Porque é a estratégia que o projeto **B3 MCP Server** foi construído em
volta. Tem mais teste, mais análise, e mais documentação. As outras 5
estratégias estão aqui como comparação, mas o Hi-Lo é o "produto
principal".

---

## Resumo de 30 segundos

1. Escolhe `hilo` no primeiro dropdown
2. Escolhe 3 ações (PETR4, VALE3, ITUB4)
3. **Não marca** opções
4. Clica **🚀 Rodar Backtest**
5. Olha a aba **Resumo por Ativo**
6. Se Profit Factor > 1,5 e Lucro % positivo → a estratégia foi boa no
   passado pra esse ativo
7. Se Profit Factor < 1 → a estratégia foi ruim, não use

Pronto. Agora você sabe o essencial. Pode começar a experimentar com
outros ativos, outras estratégias, e depois (quando estiver confortável)
com o checkbox de opções marcado.

**Boa sorte! 🚀**
