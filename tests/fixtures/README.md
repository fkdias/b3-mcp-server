# Fixtures congeladas

Cópia **imutável** dos datasets que a suíte usa como gabarito.

## Por que existe

`src/b3_mcp/core/data/samples/` é o diretório de dados offline **de produção** — e
o pipeline `atualizar_datasets.py` (cron diário) o reescreve com dados novos de
mercado.

Enquanto os testes liam de lá, o gabarito mudava sozinho todo dia útil. Isso
produz dois problemas, o segundo pior que o primeiro:

1. um teste passa hoje e falha amanhã sem ninguém tocar em código;
2. um teste **passa quando deveria falhar**, porque os dados se moveram junto
   com o comportamento — e a suíte deixa de proteger de verdade.

## Como funciona

`SAMPLES_DIR` (nos quatro serviços que leem dados offline) respeita a variável
de ambiente `B3_SAMPLES_DIR`. O `conftest.py` a aponta para cá antes de importar
qualquer módulo do pacote. Produção não muda: sem a variável, lê de
`core/data/samples/` como sempre.

Isso cobre os dois caminhos — o fixture `candles_petr4` e qualquer chamada de
serviço com `offline=True`.

## Atualizar (raramente)

Só quando um teste precisar de um período de mercado que estes 750 candles não
contêm. Nesse caso, copie o arquivo novo para cá **em um commit separado**, para
que a mudança de gabarito fique explícita na revisão:

    cp src/b3_mcp/core/data/samples/petr4_diario.json tests/fixtures/samples/

Não aponte os testes de volta para `core/data/samples/`.
