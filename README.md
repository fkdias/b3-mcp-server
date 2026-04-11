# B3 MCP Server

[![Tests](https://github.com/fkdias/b3-mcp-server/actions/workflows/tests.yml/badge.svg)](https://github.com/fkdias/b3-mcp-server/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)

MCP Server para analise do mercado de acoes brasileiro (B3/Bovespa) com Hi-Lo Activator.

## Instalacao

```bash
pip install mcp[cli] tradingview-screener tradingview-ta feedparser requests matplotlib
```

## Uso no Claude Code

Adicione ao `.claude/settings.json`:

```json
{
  "mcpServers": {
    "b3-bovespa": {
      "command": "python",
      "args": ["-m", "b3_mcp.server"],
      "cwd": "CAMINHO/b3-mcp-server/src",
      "env": {
        "PYTHONPATH": "CAMINHO/b3-mcp-server/src"
      }
    }
  }
}
```

## 18 Ferramentas

### Core (7)
| Tool | Descricao |
|------|-----------|
| `cotacao_b3` | Cotacao em tempo real |
| `hilo_activator` | Hi-Lo Activator (periodo 10) com sinais COMPRA/VENDA, grafico PNG e metricas de risco |
| `analise_tecnica_b3` | Score tecnico com 6 indicadores |
| `panorama_mercado_b3` | IBOV, dolar, euro + maiores altas/baixas |
| `maiores_altas_b3` | Top altas do dia |
| `maiores_baixas_b3` | Top baixas do dia |
| `backtest_estrategia` | Backtest de 6 estrategias + comparativo |

### B3-Especificas (6)
| Tool | Descricao |
|------|-----------|
| `visao_setorial_b3` | Scanner de 14 setores com momentum |
| `scanner_setor_b3` | Analise detalhada de um setor |
| `analise_indice_b3` | Breadth de IBOV, SMLL, IDIV, IBrX-100 |
| `screener_b3` | Screener com filtros (tendencia, setor, PF) |
| `plano_trade_b3` | Plano de trade: entrada, stop, alvos, R:R |
| `fibonacci_b3` | Niveis de Fibonacci (retracao e extensao) |

### Analise Avancada (4)
| Tool | Descricao |
|------|-----------|
| `analise_multiagente_b3` | 3 agentes: tecnico, momentum, risco |
| `volume_breakout_b3` | Scanner de rompimento por volume |
| `noticias_b3` | Noticias financeiras (InfoMoney, Valor) |
| `padroes_candle_b3` | Detector de padroes de candle |

### Simulacao de Opcoes (1)
| Tool | Descricao |
|------|-----------|
| `simular_opcoes_b3` | Simulacao educacional de opcoes ATM (Black-Scholes) nos sinais Hi-Lo |

## Modo Offline

26 ativos disponiveis com 12 meses de dados diarios. Use `offline=True` em qualquer ferramenta.

BBDC4, BEEF3, BPAC11, BRAP4, BRAV3, BRKM5, CMIN3, COGN3, CSAN3, CSNA3,
CYRE3, HAPV3, ITUB4, LREN3, MGLU3, MRVE3, PETR4, PRIO3, RDOR3, RENT3,
SANB11, SAPR11, SUZB3, USIM5, VALE3, WEGE3

## Gerar Relatorios

```bash
python gerar_relatorio.py
```

Gera CSV + JSON + 26 graficos PNG em `relatorios/`.

## Desenvolvimento

### Rodar os testes

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Suite de 165 testes. CI roda automaticamente em cada push/PR via GitHub Actions
(matriz Python 3.10 / 3.11 / 3.12).

### Ativar o hook pre-push (uma vez por clone)

O repo traz um hook em `.githooks/pre-push` que bloqueia push direto na branch
`main` e forca o fluxo `feat branch -> pull request`. Para ativar:

```bash
git config core.hooksPath .githooks
```

Bypass de emergencia (NAO recomendado): `git push --no-verify`.

### Fluxo de contribuicao

```bash
git checkout -b feat/minha-feature
# ... mudancas ...
git commit -m "feat: descricao curta"
git push -u origin feat/minha-feature
gh pr create --base main
```

CI precisa estar verde antes do merge. PR e squash-merged e a branch apagada
automaticamente.
