-- ============================================================================
-- B3 Analytics — Schema SQLite para Apache Superset
-- Fase 12 do projeto b3-mcp-server
--
-- Convenções:
--   - Valores numéricos SEMPRE em REAL/INTEGER (nada de strings formatadas)
--   - `profit_factor_is_inf` preserva semântica quando PF = float('inf')
--   - Datas armazenadas como TEXT ISO8601 (YYYY-MM-DD)
--   - FKs para `ingest_runs(id)` permitem filtrar por execução
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ingest_runs: histórico de execuções do pipeline de ingestão
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    mode            TEXT NOT NULL,      -- 'offline' | 'live'
    tickers_req     TEXT,               -- JSON array dos tickers solicitados
    tickers_ok      INTEGER DEFAULT 0,
    tickers_fail    INTEGER DEFAULT 0,
    errors_json     TEXT,               -- JSON {ticker: msg}
    duration_sec    REAL,
    status          TEXT                -- 'running' | 'ok' | 'partial' | 'error'
);

-- ----------------------------------------------------------------------------
-- tickers: catálogo dos ativos (26 offline + expandível)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickers (
    ticker          TEXT PRIMARY KEY,
    setor           TEXT,
    in_ibovespa     INTEGER DEFAULT 0,  -- 0/1
    in_smll         INTEGER DEFAULT 0,
    in_idiv         INTEGER DEFAULT 0,
    in_ibrx100      INTEGER DEFAULT 0,
    updated_at      TEXT
);

-- ----------------------------------------------------------------------------
-- hilo_analysis: snapshot completo por (ticker, data_analise)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hilo_analysis (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker                  TEXT NOT NULL,
    setor                   TEXT,
    data_analise            TEXT NOT NULL,
    periodo_hilo            INTEGER,

    -- Hi-Lo Activator
    tendencia               TEXT,        -- ALTA/BAIXA/INDEFINIDO
    activator               REAL,
    high_ma                 REAL,
    low_ma                  REAL,
    dias_na_tendencia       INTEGER,
    variacao_na_tendencia   REAL,        -- %

    -- Preço
    preco_atual             REAL,
    distancia_activator     REAL,        -- %
    bollinger_superior      REAL,
    bollinger_inferior      REAL,
    bollinger_posicao       TEXT,        -- string descritiva (não numérico)

    -- Indicadores
    rsi_14                  REAL,
    rsi_zona                TEXT,
    sma_9                   REAL,
    sma_21                  REAL,
    sma_status              TEXT,

    -- Volume
    volume_atual            INTEGER,
    volume_medio_20d        INTEGER,
    volume_relativo         REAL,
    volume_classificacao    TEXT,

    -- Suporte / Resistência
    suporte_20d             REAL,
    resistencia_20d         REAL,
    maxima_5d               REAL,
    minima_5d               REAL,

    -- Volatilidade
    volatilidade_20d        REAL,
    desvio_padrao           REAL,

    -- Métricas de risco (backtest embutido do Hi-Lo)
    total_trades            INTEGER,
    wins                    INTEGER,
    losses                  INTEGER,
    win_rate                REAL,        -- %
    payout_medio            REAL,        -- %
    payout_wins             REAL,        -- %
    payout_losses           REAL,        -- %
    profit_factor           REAL,
    profit_factor_is_inf    INTEGER DEFAULT 0,
    max_drawdown            REAL,        -- %
    expectativa             REAL,        -- %
    retorno_acumulado       REAL,        -- %
    equity_final            REAL,
    maior_win               REAL,        -- %
    maior_loss              REAL,        -- %
    max_wins_consec         INTEGER,
    max_losses_consec       INTEGER,
    dias_medio_trade        REAL,

    UNIQUE(ticker, data_analise)
);
CREATE INDEX IF NOT EXISTS idx_hilo_ticker      ON hilo_analysis(ticker);
CREATE INDEX IF NOT EXISTS idx_hilo_data        ON hilo_analysis(data_analise);
CREATE INDEX IF NOT EXISTS idx_hilo_setor       ON hilo_analysis(setor);
CREATE INDEX IF NOT EXISTS idx_hilo_tendencia   ON hilo_analysis(tendencia);

-- ----------------------------------------------------------------------------
-- hilo_trades: trades individuais do histórico de cada ticker
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hilo_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker          TEXT NOT NULL,
    trade_seq       INTEGER NOT NULL,    -- ordem no backtest
    data_entrada    TEXT,
    data_saida      TEXT,
    preco_entrada   REAL,
    preco_saida     REAL,
    resultado_pct   REAL,
    acumulado_pct   REAL,
    dias            INTEGER,
    dd_trade_pct    REAL,
    tipo            TEXT,                -- WIN/LOSS
    saida_por       TEXT
);
CREATE INDEX IF NOT EXISTS idx_hilo_trades_ticker ON hilo_trades(ticker, run_id);

-- ----------------------------------------------------------------------------
-- hilo_signals: sinais COMPRA/VENDA do histórico
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hilo_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker      TEXT NOT NULL,
    data        TEXT NOT NULL,
    sinal       TEXT NOT NULL,           -- COMPRA/VENDA
    preco       REAL
);
CREATE INDEX IF NOT EXISTS idx_hilo_signals_ticker ON hilo_signals(ticker, run_id);

-- ----------------------------------------------------------------------------
-- backtest_results: 1 linha por (ticker, estrategia, run_id)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker                  TEXT NOT NULL,
    estrategia              TEXT NOT NULL,
    periodo                 TEXT,
    total_candles           INTEGER,
    total_trades            INTEGER,
    trades_positivos        INTEGER,
    trades_negativos        INTEGER,
    taxa_acerto             REAL,        -- %
    lucro_total_rs          REAL,
    lucro_total_pct         REAL,
    maior_ganho_rs          REAL,
    maior_perda_rs          REAL,
    media_ganho_rs          REAL,
    media_perda_rs          REAL,
    profit_factor           REAL,
    profit_factor_is_inf    INTEGER DEFAULT 0,
    max_drawdown            REAL,        -- %
    UNIQUE(ticker, estrategia, run_id)
);
CREATE INDEX IF NOT EXISTS idx_bt_ticker_est ON backtest_results(ticker, estrategia);

-- ----------------------------------------------------------------------------
-- backtest_trades: trades individuais do backtest (estratégia Hi-Lo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker          TEXT NOT NULL,
    estrategia      TEXT NOT NULL,
    trade_seq       INTEGER,
    data_entrada    TEXT,
    data_saida      TEXT,
    preco_entrada   REAL,
    preco_saida     REAL,
    lucro_rs        REAL,
    lucro_pct       REAL
);
CREATE INDEX IF NOT EXISTS idx_bt_trades_ticker ON backtest_trades(ticker, estrategia, run_id);

-- ----------------------------------------------------------------------------
-- options_sim_summary: resumo da simulação de opções por ticker
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS options_sim_summary (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker                  TEXT NOT NULL,
    taxa_selic              REAL,        -- decimal (0.1425)
    vencimento_dias         INTEGER,
    total_operacoes         INTEGER,
    calls                   INTEGER,
    puts                    INTEGER,
    win_rate_opcoes         REAL,        -- %
    investido_opcoes_rs     REAL,
    lucro_opcoes_rs         REAL,
    retorno_opcoes_pct      REAL,        -- %
    lucro_acao_rs           REAL,
    retorno_acao_pct        REAL,        -- %
    alavancagem_media       REAL,
    UNIQUE(ticker, run_id)
);
CREATE INDEX IF NOT EXISTS idx_opt_sum_ticker ON options_sim_summary(ticker);

-- ----------------------------------------------------------------------------
-- options_sim_trades: operações individuais da simulação de opções
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS options_sim_trades (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES ingest_runs(id),
    ticker                  TEXT NOT NULL,
    op_seq                  INTEGER,
    tipo_opcao              TEXT,        -- CALL/PUT
    sinal_hilo              TEXT,        -- COMPRA/VENDA
    data_entrada            TEXT,
    data_saida              TEXT,
    dias                    INTEGER,
    motivo_saida            TEXT,        -- VENCIMENTO/SINAL_OPOSTO/FIM_PERIODO
    strike                  REAL,
    preco_ativo_entrada     REAL,
    preco_ativo_saida       REAL,
    volatilidade            REAL,        -- %
    premio_pago             REAL,
    premio_saida            REAL,
    resultado_opcao_rs      REAL,
    resultado_opcao_pct     REAL,        -- %
    resultado_acao_rs       REAL
);
CREATE INDEX IF NOT EXISTS idx_opt_trades_ticker ON options_sim_trades(ticker, run_id);

-- ============================================================================
-- Views auxiliares — consumidas pelos dashboards Superset
-- ============================================================================

-- Última análise Hi-Lo por ticker (run com status='ok' mais recente)
DROP VIEW IF EXISTS v_hilo_latest;
CREATE VIEW v_hilo_latest AS
SELECT h.*
FROM hilo_analysis h
INNER JOIN (
    SELECT ticker, MAX(run_id) AS max_run
    FROM hilo_analysis
    WHERE run_id IN (SELECT id FROM ingest_runs WHERE status IN ('ok', 'partial'))
    GROUP BY ticker
) m ON h.ticker = m.ticker AND h.run_id = m.max_run;

-- Último backtest por (ticker, estrategia)
DROP VIEW IF EXISTS v_backtest_latest;
CREATE VIEW v_backtest_latest AS
SELECT b.*
FROM backtest_results b
INNER JOIN (
    SELECT ticker, estrategia, MAX(run_id) AS max_run
    FROM backtest_results
    WHERE run_id IN (SELECT id FROM ingest_runs WHERE status IN ('ok', 'partial'))
    GROUP BY ticker, estrategia
) m ON b.ticker = m.ticker AND b.estrategia = m.estrategia AND b.run_id = m.max_run;

-- Último resumo de opções por ticker
DROP VIEW IF EXISTS v_options_latest;
CREATE VIEW v_options_latest AS
SELECT o.*
FROM options_sim_summary o
INNER JOIN (
    SELECT ticker, MAX(run_id) AS max_run
    FROM options_sim_summary
    WHERE run_id IN (SELECT id FROM ingest_runs WHERE status IN ('ok', 'partial'))
    GROUP BY ticker
) m ON o.ticker = m.ticker AND o.run_id = m.max_run;
