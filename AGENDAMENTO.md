# Agendamento do refresh de datasets

O script `atualizar_datasets.py` re-baixa todos os 28 tickers do `TICKERS` dict
(janela de 3 anos) do Yahoo Finance e sobrescreve os JSONs em
`src/b3_mcp/core/data/samples/`. Os logs de cada execução ficam em
`relatorios/update_log_YYYY-MM-DD.txt` (modo append, um arquivo por dia).

Este documento mostra como rodar o script manualmente e como registrar ele no
**Windows Task Scheduler** pra refresh automático semanal.

---

## Execução manual

### Via linha de comando

```cmd
cd /d "C:\Users\fkdia\OneDrive\Área de Trabalho\Tio Huli\b3-mcp-server"
python atualizar_datasets.py
```

### Via duplo-clique no Explorer

Abrir a pasta do projeto e dar duplo-clique em `atualizar_datasets.bat`. O
launcher resolve o `cd` automaticamente via `%~dp0` e chama o Python.

**Tempo estimado:** ~60 segundos (28 tickers × 1,5s de rate limit + I/O).

**Exit codes:**
- `0` — todos os tickers atualizados com sucesso
- `1` — atualização parcial (alguns tickers falharam, mas >= 1 foi ok)
- `2` — falha total (nenhum ticker atualizado)

---

## Agendamento semanal (Windows Task Scheduler)

### Opção 1: Via comando `schtasks` (copy-paste)

Abrir **Command Prompt (não PowerShell)** e rodar:

```cmd
schtasks /Create /SC WEEKLY /D SAT /ST 06:00 /TN "B3_MCP_UpdateDatasets" /TR "\"C:\Users\fkdia\OneDrive\Área de Trabalho\Tio Huli\b3-mcp-server\atualizar_datasets.bat\"" /F
```

Explicação dos parâmetros:
- `/SC WEEKLY` — agendamento semanal
- `/D SAT` — executa no sábado (mercado fechado, Yahoo Finance sem carga)
- `/ST 06:00` — horário de início: 06h00
- `/TN "B3_MCP_UpdateDatasets"` — nome da tarefa
- `/TR "\"...\atualizar_datasets.bat\""` — comando a executar (aspas escapadas porque o path tem espaços e acento)
- `/F` — força sobrescrever tarefa já existente com o mesmo nome

### Opção 2: Via GUI do Task Scheduler

1. Abrir **Task Scheduler** (Agendador de Tarefas)
2. Menu direito: **Create Basic Task** (Criar Tarefa Básica)
3. Nome: `B3_MCP_UpdateDatasets`
4. Trigger: **Weekly** (Semanal) → Saturday → 06:00
5. Action: **Start a program** (Iniciar um programa)
6. Program/script: navegar até `atualizar_datasets.bat` na pasta do projeto
7. Finish (Concluir)

---

## Operações comuns

### Verificar se a tarefa está registrada

```cmd
schtasks /Query /TN "B3_MCP_UpdateDatasets" /V /FO LIST
```

Mostra o estado detalhado (próxima execução, último resultado, etc).

### Rodar a tarefa imediatamente (sem esperar sábado)

```cmd
schtasks /Run /TN "B3_MCP_UpdateDatasets"
```

Útil pra testar o registro sem esperar o próximo agendamento.

### Deletar a tarefa

```cmd
schtasks /Delete /TN "B3_MCP_UpdateDatasets" /F
```

### Ver o log da última execução

O log mais recente fica em `relatorios/update_log_YYYY-MM-DD.txt`. Pra ver o
log de hoje:

```cmd
type "relatorios\update_log_%date:~-4,4%-%date:~-10,2%-%date:~-7,2%.txt"
```

(o formato da variável `%date%` varia conforme locale do Windows — se não
funcionar, listar `relatorios\` e abrir o arquivo mais recente manualmente)

---

## Troubleshooting

**A tarefa roda mas o log não é gerado.**
Geralmente o `cd /d "%~dp0"` no `.bat` falhou. Verifique se o `.bat` está na
raiz do projeto (mesmo nível de `atualizar_datasets.py`).

**Erro de encoding no PowerShell ao rodar o `.bat`.**
Usar Command Prompt, não PowerShell. O path tem "Área de Trabalho" com acento
e o PowerShell às vezes trata a codificação errado.

**Tickers falhando com timeout ou erro 429.**
Yahoo Finance pode rate-limit. Aumentar `SLEEP_BETWEEN_REQUESTS` em
`atualizar_datasets.py` de `1.5` para `2.5` ou `3.0`.

**A tarefa não roda se o PC estiver desligado/hibernando no horário.**
Por default, o Task Scheduler não acorda a máquina. Pra mudar:
1. Task Scheduler GUI → propriedades da tarefa
2. Aba **Conditions** → marcar "Wake the computer to run this task"
3. Aba **Settings** → marcar "Run task as soon as possible after a scheduled start is missed"

---

## Interação com o MCP

O MCP server lê os JSONs de `src/b3_mcp/core/data/samples/` a cada chamada das
tools que passam `offline=True`. **Não precisa reiniciar o MCP** após o
refresh — os dados novos são lidos naturalmente na próxima chamada.

Tools afetadas (consomem datasets offline): `hilo_activator`,
`analise_tecnica_b3`, `backtest_estrategia`, `analise_multiagente_b3`,
`padroes_candle_b3`, `simular_opcoes_b3`, `refresh_dashboard_b3`.
