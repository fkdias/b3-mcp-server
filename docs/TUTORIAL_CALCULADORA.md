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

- **Capital total da banca:** deixe em **R$ 10.000** (pode ser
  qualquer número — é só referência)
- **Capital dedicado à estratégia:** deixe em **R$ 5.000**

Esses números servem pra calcular o retorno percentual depois. Você
não está arriscando dinheiro de verdade.

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

## Os 4 "ajustes de risco" (só se interessar por opções)

Estes campos **só importam se você marcou o checkbox de opções**. Se
está só testando ações à vista, pode ignorar.

### Modo de sizing

"Sizing" significa **"quanto comprar de cada vez"**. Tem 5 opções:

| Modo | O que faz | Quando usar |
|---|---|---|
| `agregado` | Compra 1 lote fixo sempre | **Começa por esse** — é o mais simples |
| `lote_fixo` | Compra N lotes sempre iguais | Quando você quer escalar |
| `fracao_banca` | Arrisca X% do dinheiro que você tem naquele momento | Avançado |
| `teto_absoluto` | Nunca arrisca mais que R$ X por operação | **Recomendado pra ser conservador** |
| `fracao_capital` | Arrisca X% do capital inicial | Similar ao `lote_fixo` |

**Se você é iniciante:** use `agregado` ou `teto_absoluto` com valor
pequeno (tipo R$ 50).

### Valor do sizing

Depende do modo acima. Leia o texto de ajuda `(?)` ao lado do campo
quando tiver dúvida. **Cuidado com `fracao_banca`**: `1.0` ali significa
**100% da banca por trade** — você explode no primeiro prejuízo.
Fração é número decimal (`0.01` = 1%).

### Limite de risco por operação (slider)

Esse slider é só um **lembrete visual**. A metodologia que este projeto
segue recomenda **nunca arriscar mais de 1% da banca em uma única
operação**. O slider NÃO aplica isso automaticamente — você precisa
ajustar o "Valor do sizing" pra bater com essa regra.

### Tamanho do lote

Na B3, opções são negociadas em lotes de **100 contratos**. Deixa
em 100, não mexe.

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
