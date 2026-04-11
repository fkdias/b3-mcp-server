"""Testes do pipeline de ingestão `superset_ingest/ingest.py`.

Cobre:
- Helpers puros: `_get_db_path`, `_now_iso`, `_parse_args`
- Infra SQLite: `_connect`, `_apply_schema`, `_seed_tickers`, `_create_run`, `_finish_run`, `_clear_run_ticker`
- Integração end-to-end: `run_ingest(offline=True)` em SQLite temporário

Os testes de insert (`_insert_hilo`, `_insert_backtest`, `_insert_options`) são exercitados
implicitamente via `run_ingest`, que valida o pipeline inteiro contra um ticker real.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

import pytest

from b3_mcp.superset_ingest.ingest import (
    DEFAULT_DB_PATH,
    _apply_schema,
    _clear_run_ticker,
    _connect,
    _create_run,
    _finish_run,
    _get_db_path,
    _now_iso,
    _parse_args,
    _seed_tickers,
    run_ingest,
)


@pytest.fixture
def tmp_db(tmp_path):
    """SQLite temporário em disco (não :memory: porque _connect chama mkdir)."""
    return str(tmp_path / "subdir" / "test.db")


@pytest.fixture
def conn_with_schema(tmp_db):
    """Conexão já com schema aplicado."""
    conn = _connect(tmp_db)
    _apply_schema(conn)
    yield conn
    conn.close()


# ═══════════════════════════════════════════════
# Helpers puros
# ═══════════════════════════════════════════════
class TestGetDbPath:
    def test_default_sem_env(self, monkeypatch):
        monkeypatch.delenv("B3_ANALYTICS_DB", raising=False)
        assert _get_db_path() == DEFAULT_DB_PATH

    def test_override_via_env(self, monkeypatch):
        monkeypatch.setenv("B3_ANALYTICS_DB", "/tmp/custom.db")
        assert _get_db_path() == "/tmp/custom.db"


class TestNowIso:
    def test_formato_parseavel(self):
        s = _now_iso()
        # Deve ser parsable por datetime.fromisoformat
        dt = datetime.fromisoformat(s)
        assert dt is not None

    def test_tem_timezone(self):
        s = _now_iso()
        # Deve conter '+' ou '-' no offset (não ser naive)
        assert "+" in s or s.count("-") >= 3  # 2 no date + 1 no offset


# ═══════════════════════════════════════════════
# Infra SQLite
# ═══════════════════════════════════════════════
class TestConnectApplySchema:
    def test_connect_cria_diretorio_parent(self, tmp_path):
        db_path = str(tmp_path / "nao_existe_ainda" / "test.db")
        conn = _connect(db_path)
        try:
            assert os.path.exists(os.path.dirname(db_path))
            # WAL mode ativado
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
            # Row factory configurado
            assert conn.row_factory is sqlite3.Row
        finally:
            conn.close()

    def test_apply_schema_cria_tabelas(self, conn_with_schema):
        cursor = conn_with_schema.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tabelas = {row[0] for row in cursor.fetchall()}
        # Tabelas core esperadas
        for nome in (
            "tickers",
            "ingest_runs",
            "hilo_analysis",
            "hilo_trades",
            "hilo_signals",
            "backtest_results",
            "backtest_trades",
            "options_sim_summary",
            "options_sim_trades",
        ):
            assert nome in tabelas, f"tabela {nome} não encontrada; existem: {tabelas}"

    def test_apply_schema_idempotente(self, conn_with_schema):
        """Rodar 2x não levanta erro."""
        _apply_schema(conn_with_schema)
        _apply_schema(conn_with_schema)  # duplo exec não deve quebrar


class TestSeedTickers:
    def test_popula_tabela_tickers(self, conn_with_schema):
        _seed_tickers(conn_with_schema)
        count = conn_with_schema.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        assert count > 0

    def test_flags_bitwise(self, conn_with_schema):
        """Flags in_ibovespa etc devem ser 0 ou 1."""
        _seed_tickers(conn_with_schema)
        rows = conn_with_schema.execute("SELECT in_ibovespa, in_smll, in_idiv, in_ibrx100 FROM tickers").fetchall()
        for r in rows:
            for flag in r:
                assert flag in (0, 1)

    def test_seed_idempotente(self, conn_with_schema):
        """Seed 2x → mesma contagem (upsert via ON CONFLICT)."""
        _seed_tickers(conn_with_schema)
        c1 = conn_with_schema.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        _seed_tickers(conn_with_schema)
        c2 = conn_with_schema.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        assert c1 == c2

    def test_petr4_esta_no_ibov(self, conn_with_schema):
        _seed_tickers(conn_with_schema)
        row = conn_with_schema.execute("SELECT in_ibovespa FROM tickers WHERE ticker=?", ("PETR4",)).fetchone()
        assert row is not None
        assert row[0] == 1


# ═══════════════════════════════════════════════
# ingest_runs
# ═══════════════════════════════════════════════
class TestIngestRuns:
    def test_create_run_retorna_id_valido(self, conn_with_schema):
        run_id = _create_run(conn_with_schema, mode="offline", tickers_req=["PETR4", "VALE3"])
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_create_run_grava_status_running(self, conn_with_schema):
        run_id = _create_run(conn_with_schema, mode="offline", tickers_req=["PETR4"])
        row = conn_with_schema.execute("SELECT status, mode FROM ingest_runs WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "running"
        assert row["mode"] == "offline"

    def test_finish_run_atualiza_status(self, conn_with_schema):
        run_id = _create_run(conn_with_schema, mode="offline", tickers_req=["PETR4"])
        _finish_run(
            conn_with_schema,
            run_id=run_id,
            tickers_ok=1,
            tickers_fail=0,
            errors={},
            duration_sec=3.14,
            status="ok",
        )
        row = conn_with_schema.execute(
            "SELECT status, tickers_ok, duration_sec FROM ingest_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row["status"] == "ok"
        assert row["tickers_ok"] == 1
        assert row["duration_sec"] == 3.14


class TestClearRunTicker:
    def test_limpa_apenas_linhas_daquele_ticker(self, conn_with_schema):
        # Precisa criar linha-pai em ingest_runs (FK constraint ativa)
        run_id = _create_run(conn_with_schema, mode="offline", tickers_req=["PETR4", "VALE3"])
        # Idem pra tickers (pode ter FK por ticker)
        _seed_tickers(conn_with_schema)

        # Insere registros fake em 2 tabelas filhas
        conn_with_schema.execute(
            "INSERT INTO hilo_trades (run_id, ticker, trade_seq, data_entrada, data_saida, "
            "preco_entrada, preco_saida, resultado_pct, acumulado_pct, dias, dd_trade_pct, "
            "tipo, saida_por) VALUES (?, 'PETR4', 1, '2025-01-01', '2025-01-05', 10, 11, 10, 10, 4, 0, 'C', 'target')",
            (run_id,),
        )
        conn_with_schema.execute(
            "INSERT INTO hilo_trades (run_id, ticker, trade_seq, data_entrada, data_saida, "
            "preco_entrada, preco_saida, resultado_pct, acumulado_pct, dias, dd_trade_pct, "
            "tipo, saida_por) VALUES (?, 'VALE3', 1, '2025-01-01', '2025-01-05', 10, 11, 10, 10, 4, 0, 'C', 'target')",
            (run_id,),
        )
        conn_with_schema.commit()

        _clear_run_ticker(conn_with_schema, run_id=run_id, ticker="PETR4")

        rows = conn_with_schema.execute("SELECT ticker FROM hilo_trades WHERE run_id=?", (run_id,)).fetchall()
        tickers = [r["ticker"] for r in rows]
        assert "PETR4" not in tickers
        assert "VALE3" in tickers


# ═══════════════════════════════════════════════
# CLI parser
# ═══════════════════════════════════════════════
class TestParseArgs:
    def test_flag_all(self):
        ns = _parse_args(["--all"])
        assert ns.all is True
        assert ns.ticker is None

    def test_flag_ticker_unico(self):
        ns = _parse_args(["--ticker", "PETR4"])
        assert ns.ticker == "PETR4"
        assert ns.all is False

    def test_flag_tickers_lista(self):
        ns = _parse_args(["--tickers", "PETR4,VALE3,ITUB4"])
        assert ns.tickers == "PETR4,VALE3,ITUB4"

    def test_mutex_all_e_ticker(self):
        with pytest.raises(SystemExit):
            _parse_args(["--all", "--ticker", "PETR4"])

    def test_mutex_offline_e_live(self):
        with pytest.raises(SystemExit):
            _parse_args(["--all", "--offline", "--live"])

    def test_offline_default_quando_nao_passado(self):
        ns = _parse_args(["--all"])
        assert ns.live is False


# ═══════════════════════════════════════════════
# End-to-end
# ═══════════════════════════════════════════════
class TestRunIngestEndToEnd:
    def test_single_ticker_offline(self, tmp_db):
        result = run_ingest(tickers=["PETR4"], offline=True, db_path=tmp_db)

        assert result["status"] in ("ok", "partial")  # partial pode rolar se options_sim falhar
        assert result["ok"] == 1
        assert result["fail"] == 0
        assert result["mode"] == "offline"
        assert result["db_path"] == tmp_db
        assert isinstance(result["run_id"], int)

    def test_grava_hilo_analysis(self, tmp_db):
        run_ingest(tickers=["PETR4"], offline=True, db_path=tmp_db)
        conn = _connect(tmp_db)
        try:
            row = conn.execute(
                "SELECT ticker, tendencia, preco_atual FROM hilo_analysis WHERE ticker='PETR4'"
            ).fetchone()
            assert row is not None
            assert row["ticker"] == "PETR4"
            assert row["tendencia"] in ("ALTA", "BAIXA")
            assert row["preco_atual"] is not None and row["preco_atual"] > 0
        finally:
            conn.close()

    def test_grava_backtest_results(self, tmp_db):
        run_ingest(tickers=["PETR4"], offline=True, db_path=tmp_db)
        conn = _connect(tmp_db)
        try:
            row = conn.execute(
                "SELECT ticker, estrategia, total_trades FROM backtest_results WHERE ticker='PETR4'"
            ).fetchone()
            assert row is not None
            assert row["estrategia"] == "hilo"
            assert row["total_trades"] is not None
        finally:
            conn.close()

    def test_ingest_run_fica_com_status_terminal(self, tmp_db):
        result = run_ingest(tickers=["PETR4"], offline=True, db_path=tmp_db)
        conn = _connect(tmp_db)
        try:
            row = conn.execute("SELECT status, finished_at FROM ingest_runs WHERE id=?", (result["run_id"],)).fetchone()
            assert row["status"] in ("ok", "partial", "error")
            assert row["status"] != "running"
            assert row["finished_at"] is not None
        finally:
            conn.close()

    def test_ticker_invalido_vai_pra_errors(self, tmp_db):
        result = run_ingest(tickers=["ZZZZ9"], offline=True, db_path=tmp_db)
        assert result["fail"] == 1
        assert "ZZZZ9" in result["errors"]
        assert result["status"] == "error"

    def test_mix_ok_e_fail_vira_partial(self, tmp_db):
        result = run_ingest(tickers=["PETR4", "ZZZZ9"], offline=True, db_path=tmp_db)
        assert result["ok"] == 1
        assert result["fail"] == 1
        assert result["status"] == "partial"
