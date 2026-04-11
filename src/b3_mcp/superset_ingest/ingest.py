"""
Pipeline de ingestão B3 → SQLite (Apache Superset).

Fluxo:
    1. Abre/cria SQLite em $B3_ANALYTICS_DB (default: C:\\b3-analytics\\b3_analytics.db)
    2. Executa schema.sql (CREATE TABLE IF NOT EXISTS)
    3. Ativa WAL mode para concorrência leitor/escritor
    4. Cria 1 linha em ingest_runs (status='running')
    5. Seeds catálogo `tickers` a partir de b3_sectors + b3_indices
    6. Para cada ticker: roda analisar_hilo, executar_backtest(hilo) e
       simular_opcoes_hilo (este último com try/except — BCB pode falhar offline),
       convertendo strings pt-BR → números via parsers.py antes de inserir.
    7. Atualiza ingest_runs com status final (ok | partial | error) e métricas.

CLI:
    python -m b3_mcp.superset_ingest.ingest --all --offline
    python -m b3_mcp.superset_ingest.ingest --ticker PETR4 --offline
    python -m b3_mcp.superset_ingest.ingest --tickers PETR4,VALE3 --live
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .parsers import _parse_num, _parse_trade_entrada, _pf_guard

# ═════════════════════════════════════════════════════════════
# Configuração
# ═════════════════════════════════════════════════════════════
DEFAULT_DB_PATH = r"C:\b3-analytics\b3_analytics.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def _get_db_path() -> str:
    """Resolve o caminho do SQLite a partir de B3_ANALYTICS_DB ou default."""
    return os.environ.get("B3_ANALYTICS_DB", DEFAULT_DB_PATH)


def _now_iso() -> str:
    """Timestamp ISO8601 com timezone local."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ═════════════════════════════════════════════════════════════
# Conexão SQLite + Schema
# ═════════════════════════════════════════════════════════════
def _connect(db_path: str) -> sqlite3.Connection:
    """Abre conexão SQLite com WAL mode e busy_timeout."""
    # Garantir que o diretório existe
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Executa schema.sql (idempotente)."""
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


# ═════════════════════════════════════════════════════════════
# Seed: tickers (setor + flags de índices)
# ═════════════════════════════════════════════════════════════
def _seed_tickers(conn: sqlite3.Connection) -> None:
    """
    Popula/atualiza tabela `tickers` a partir de SETORES + INDICES.

    Merge de todos os tickers presentes em qualquer setor OU em qualquer
    índice. Cada linha traz setor (pode ser None) e 4 flags binárias.
    """
    from ..core.data.b3_indices import INDICES
    from ..core.data.b3_sectors import SETORES, get_setor

    # Universo: união dos tickers vistos em setores + índices
    universo: set[str] = set()
    for ativos in SETORES.values():
        universo.update(ativos)
    for idx in INDICES.values():
        universo.update(idx.get("constituintes", []))

    ibov = set(INDICES.get("IBOVESPA", {}).get("constituintes", []))
    smll = set(INDICES.get("SMLL", {}).get("constituintes", []))
    idiv = set(INDICES.get("IDIV", {}).get("constituintes", []))
    ibrx = set(INDICES.get("IBRX100", {}).get("constituintes", []))

    now = _now_iso()
    rows = []
    for ticker in sorted(universo):
        rows.append(
            (
                ticker,
                get_setor(ticker),
                1 if ticker in ibov else 0,
                1 if ticker in smll else 0,
                1 if ticker in idiv else 0,
                1 if ticker in ibrx else 0,
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO tickers (ticker, setor, in_ibovespa, in_smll, in_idiv, in_ibrx100, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            setor=excluded.setor,
            in_ibovespa=excluded.in_ibovespa,
            in_smll=excluded.in_smll,
            in_idiv=excluded.in_idiv,
            in_ibrx100=excluded.in_ibrx100,
            updated_at=excluded.updated_at
        """,
        rows,
    )
    conn.commit()


# ═════════════════════════════════════════════════════════════
# ingest_runs helpers
# ═════════════════════════════════════════════════════════════
def _create_run(conn: sqlite3.Connection, mode: str, tickers_req: list[str]) -> int:
    """Cria linha em ingest_runs com status='running' e retorna o id."""
    cursor = conn.execute(
        """
        INSERT INTO ingest_runs (started_at, mode, tickers_req, status)
        VALUES (?, ?, ?, 'running')
        """,
        (_now_iso(), mode, json.dumps(tickers_req)),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def _finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    tickers_ok: int,
    tickers_fail: int,
    errors: dict[str, str],
    duration_sec: float,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE ingest_runs
        SET finished_at=?, tickers_ok=?, tickers_fail=?,
            errors_json=?, duration_sec=?, status=?
        WHERE id=?
        """,
        (_now_iso(), tickers_ok, tickers_fail, json.dumps(errors), round(duration_sec, 2), status, run_id),
    )
    conn.commit()


# ═════════════════════════════════════════════════════════════
# Inserts por análise
# ═════════════════════════════════════════════════════════════
def _insert_hilo(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    analise: dict[str, Any],
) -> None:
    """Insere 1 linha em hilo_analysis + N em hilo_trades + N em hilo_signals."""
    hilo = analise.get("hilo", {}) or {}
    preco = analise.get("preco", {}) or {}
    indic = analise.get("indicadores", {}) or {}
    vol = analise.get("volume", {}) or {}
    sr = analise.get("suporte_resistencia", {}) or {}
    volat = analise.get("volatilidade", {}) or {}
    mr = analise.get("metricas_risco", {}) or {}

    pf_val, pf_is_inf = _pf_guard(mr.get("profit_factor"))

    # volume_relativo pode vir numérico ou string "N/A"
    vol_rel = vol.get("volume_relativo")
    if isinstance(vol_rel, str):
        vol_rel = _parse_num(vol_rel)

    conn.execute(
        """
        INSERT OR REPLACE INTO hilo_analysis (
            run_id, ticker, setor, data_analise, periodo_hilo,
            tendencia, activator, high_ma, low_ma,
            dias_na_tendencia, variacao_na_tendencia,
            preco_atual, distancia_activator,
            bollinger_superior, bollinger_inferior, bollinger_posicao,
            rsi_14, rsi_zona, sma_9, sma_21, sma_status,
            volume_atual, volume_medio_20d, volume_relativo, volume_classificacao,
            suporte_20d, resistencia_20d, maxima_5d, minima_5d,
            volatilidade_20d, desvio_padrao,
            total_trades, wins, losses,
            win_rate, payout_medio, payout_wins, payout_losses,
            profit_factor, profit_factor_is_inf,
            max_drawdown, expectativa, retorno_acumulado, equity_final,
            maior_win, maior_loss,
            max_wins_consec, max_losses_consec, dias_medio_trade
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            ticker,
            analise.get("setor"),
            analise.get("data_analise"),
            hilo.get("periodo"),
            hilo.get("tendencia"),
            _parse_num(hilo.get("activator")),
            _parse_num(hilo.get("high_ma")),
            _parse_num(hilo.get("low_ma")),
            hilo.get("dias_na_tendencia"),
            _parse_num(hilo.get("variacao_na_tendencia")),
            _parse_num(preco.get("atual")),
            _parse_num(preco.get("distancia_activator")),
            _parse_num(preco.get("bollinger_superior")),
            _parse_num(preco.get("bollinger_inferior")),
            preco.get("posicao_bollinger"),
            _parse_num(indic.get("rsi_14")),
            indic.get("rsi_zona"),
            _parse_num(indic.get("sma_9")),
            _parse_num(indic.get("sma_21")),
            indic.get("sma_status"),
            vol.get("volume_atual")
            if isinstance(vol.get("volume_atual"), (int, float))
            else _parse_num(vol.get("volume_atual")),
            vol.get("volume_medio_20d")
            if isinstance(vol.get("volume_medio_20d"), (int, float))
            else _parse_num(vol.get("volume_medio_20d")),
            vol_rel,
            vol.get("volume_classificacao"),
            _parse_num(sr.get("suporte_20d")),
            _parse_num(sr.get("resistencia_20d")),
            _parse_num(sr.get("maxima_5d")),
            _parse_num(sr.get("minima_5d")),
            _parse_num(volat.get("volatilidade_20d")),
            _parse_num(volat.get("desvio_padrao")),
            mr.get("total_trades"),
            mr.get("wins"),
            mr.get("losses"),
            _parse_num(mr.get("win_rate")),
            _parse_num(mr.get("payout_medio")),
            _parse_num(mr.get("payout_medio_wins")),
            _parse_num(mr.get("payout_medio_losses")),
            pf_val,
            1 if pf_is_inf else 0,
            _parse_num(mr.get("max_drawdown")),
            _parse_num(mr.get("expectativa")),
            _parse_num(mr.get("retorno_acumulado")),
            _parse_num(mr.get("equity_final")),
            _parse_num(mr.get("maior_win")),
            _parse_num(mr.get("maior_loss")),
            mr.get("max_wins_consecutivos"),
            mr.get("max_losses_consecutivos"),
            _parse_num(mr.get("dias_medio_trade")),
        ),
    )

    # ── hilo_trades ──
    trades = mr.get("trades") or []
    trade_rows = []
    for seq, t in enumerate(trades, start=1):
        data_ent, preco_ent = _parse_trade_entrada(t.get("entrada"))
        data_sai, preco_sai = _parse_trade_entrada(t.get("saida"))
        trade_rows.append(
            (
                run_id,
                ticker,
                seq,
                data_ent,
                data_sai,
                preco_ent,
                preco_sai,
                _parse_num(t.get("resultado")),
                _parse_num(t.get("acumulado")),
                t.get("dias"),
                _parse_num(t.get("dd_trade")),
                t.get("tipo"),
                t.get("saida_por"),
            )
        )
    if trade_rows:
        conn.executemany(
            """
            INSERT INTO hilo_trades (
                run_id, ticker, trade_seq, data_entrada, data_saida,
                preco_entrada, preco_saida, resultado_pct, acumulado_pct,
                dias, dd_trade_pct, tipo, saida_por
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trade_rows,
        )

    # ── hilo_signals ──
    signals = analise.get("historico_sinais") or []
    sig_rows = []
    for s in signals:
        sig_rows.append(
            (
                run_id,
                ticker,
                s.get("data"),
                s.get("sinal"),
                _parse_num(s.get("preco")),
            )
        )
    if sig_rows:
        conn.executemany(
            """
            INSERT INTO hilo_signals (run_id, ticker, data, sinal, preco)
            VALUES (?, ?, ?, ?, ?)
            """,
            sig_rows,
        )


def _insert_backtest(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    bt: dict[str, Any],
) -> None:
    """Insere 1 linha em backtest_results + N em backtest_trades."""
    metricas = bt.get("metricas", {}) or {}
    estrategia = bt.get("estrategia", "hilo")

    pf_val, pf_is_inf = _pf_guard(metricas.get("profit_factor"))

    conn.execute(
        """
        INSERT OR REPLACE INTO backtest_results (
            run_id, ticker, estrategia, periodo, total_candles,
            total_trades, trades_positivos, trades_negativos,
            taxa_acerto, lucro_total_rs, lucro_total_pct,
            maior_ganho_rs, maior_perda_rs,
            media_ganho_rs, media_perda_rs,
            profit_factor, profit_factor_is_inf, max_drawdown
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            ticker,
            estrategia,
            bt.get("periodo"),
            bt.get("total_candles"),
            metricas.get("total_trades"),
            metricas.get("trades_positivos"),
            metricas.get("trades_negativos"),
            _parse_num(metricas.get("taxa_acerto")),
            _parse_num(metricas.get("lucro_total")),
            _parse_num(metricas.get("lucro_total_pct")),
            _parse_num(metricas.get("maior_ganho")),
            _parse_num(metricas.get("maior_perda")),
            _parse_num(metricas.get("media_ganho")),
            _parse_num(metricas.get("media_perda")),
            pf_val,
            1 if pf_is_inf else 0,
            _parse_num(metricas.get("max_drawdown")),
        ),
    )

    # ── backtest_trades ──
    trades = bt.get("todos_trades") or bt.get("ultimos_trades") or []
    trade_rows = []
    for seq, t in enumerate(trades, start=1):
        trade_rows.append(
            (
                run_id,
                ticker,
                estrategia,
                seq,
                t.get("data_entrada"),
                t.get("data_saida"),
                _parse_num(t.get("preco_entrada")),
                _parse_num(t.get("preco_saida")),
                _parse_num(t.get("lucro")),
                _parse_num(t.get("lucro_pct")),
            )
        )
    if trade_rows:
        conn.executemany(
            """
            INSERT INTO backtest_trades (
                run_id, ticker, estrategia, trade_seq,
                data_entrada, data_saida,
                preco_entrada, preco_saida, lucro_rs, lucro_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trade_rows,
        )


def _insert_options(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    opcoes: dict[str, Any],
) -> None:
    """Insere 1 linha em options_sim_summary + N em options_sim_trades."""
    resumo = opcoes.get("resumo") or {}
    premissas = opcoes.get("premissas") or {}
    operacoes = opcoes.get("operacoes") or []

    # Se a simulação retornou vazio (sem sinais), grava resumo minimalista
    total_ops = resumo.get("total_operacoes", opcoes.get("total_operacoes", 0))

    conn.execute(
        """
        INSERT OR REPLACE INTO options_sim_summary (
            run_id, ticker, taxa_selic, vencimento_dias,
            total_operacoes, calls, puts,
            win_rate_opcoes, investido_opcoes_rs, lucro_opcoes_rs,
            retorno_opcoes_pct, lucro_acao_rs, retorno_acao_pct,
            alavancagem_media
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            ticker,
            # taxa_selic vem como "14,25%"; guardamos em decimal (0.1425)
            (_parse_num(premissas.get("taxa_selic")) / 100.0)
            if _parse_num(premissas.get("taxa_selic")) is not None
            else None,
            21,  # VENCIMENTO_DIAS default
            total_ops,
            resumo.get("calls"),
            resumo.get("puts"),
            _parse_num(resumo.get("win_rate_opcoes")),
            _parse_num(resumo.get("investido_opcoes")),
            _parse_num(resumo.get("lucro_opcoes")),
            _parse_num(resumo.get("retorno_opcoes")),
            _parse_num(resumo.get("lucro_acao")),
            _parse_num(resumo.get("retorno_acao")),
            _parse_num(resumo.get("alavancagem_media")),
        ),
    )

    op_rows = []
    for seq, op in enumerate(operacoes, start=1):
        op_rows.append(
            (
                run_id,
                ticker,
                seq,
                op.get("tipo_opcao"),
                op.get("sinal_hilo"),
                op.get("data_entrada"),
                op.get("data_saida"),
                op.get("dias"),
                op.get("motivo_saida"),
                _parse_num(op.get("strike")),
                _parse_num(op.get("preco_ativo_entrada")),
                _parse_num(op.get("preco_ativo_saida")),
                _parse_num(op.get("volatilidade")),
                _parse_num(op.get("premio_pago")),
                _parse_num(op.get("premio_saida")),
                _parse_num(op.get("resultado_opcao_rs")),
                _parse_num(op.get("resultado_opcao_pct")),
                _parse_num(op.get("resultado_acao_rs")),
            )
        )
    if op_rows:
        conn.executemany(
            """
            INSERT INTO options_sim_trades (
                run_id, ticker, op_seq, tipo_opcao, sinal_hilo,
                data_entrada, data_saida, dias, motivo_saida,
                strike, preco_ativo_entrada, preco_ativo_saida,
                volatilidade, premio_pago, premio_saida,
                resultado_opcao_rs, resultado_opcao_pct, resultado_acao_rs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            op_rows,
        )


def _clear_run_ticker(conn: sqlite3.Connection, run_id: int, ticker: str) -> None:
    """Limpa dados de filhas para este (run_id, ticker) antes de reinsert."""
    for tbl in ("hilo_trades", "hilo_signals", "backtest_trades", "options_sim_trades"):
        conn.execute(f"DELETE FROM {tbl} WHERE run_id=? AND ticker=?", (run_id, ticker))


# ═════════════════════════════════════════════════════════════
# Orquestrador
# ═════════════════════════════════════════════════════════════
def _processar_ticker(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    offline: bool,
) -> None:
    """Roda Hi-Lo + backtest + opções para um ticker e grava tudo no DB."""
    # Imports lazy para não pagar custo no startup do módulo
    from ..core.services.backtest_service import executar_backtest
    from ..core.services.hilo_service import analisar_hilo
    from ..core.services.options_sim import simular_opcoes_hilo

    _clear_run_ticker(conn, run_id, ticker)

    # ─── Hi-Lo (gerar_grafico=False é crítico para performance) ───
    analise = analisar_hilo(ticker, periodo=10, offline=offline, gerar_grafico=False)
    _insert_hilo(conn, run_id, ticker, analise)

    # ─── Backtest Hi-Lo ───
    bt = executar_backtest(ticker, estrategia="hilo", offline=offline)
    _insert_backtest(conn, run_id, ticker, bt)

    # ─── Simulação de opções (try/except: BCB pode falhar offline) ───
    try:
        opcoes = simular_opcoes_hilo(ticker, periodo_hilo=10, offline=offline)
        _insert_options(conn, run_id, ticker, opcoes)
    except Exception as e:
        # Não falha o ticker inteiro por causa das opções
        print(f"  [WARN] options_sim falhou para {ticker}: {e}", file=sys.stderr)

    conn.commit()


def run_ingest(
    tickers: list[str] | None = None,
    offline: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Executa a ingestão completa.

    Args:
        tickers: Lista de tickers a processar. None = todos os disponíveis offline.
        offline: True = usa JSONs em core/data/samples; False = Yahoo Finance.
        db_path: Override do caminho do SQLite (default: $B3_ANALYTICS_DB).

    Returns:
        dict com status, ok, fail, errors, duration_sec, db_path, run_id.
    """
    from ..core.services.hilo_service import _listar_offline_disponiveis

    if tickers is None:
        tickers = _listar_offline_disponiveis()

    tickers = [t.upper().strip() for t in tickers if t]

    db_path = db_path or _get_db_path()
    mode = "offline" if offline else "live"

    t0 = time.time()
    conn = _connect(db_path)
    try:
        _apply_schema(conn)
        _seed_tickers(conn)
        run_id = _create_run(conn, mode, tickers)

        ok = 0
        fail = 0
        errors: dict[str, str] = {}

        for ticker in tickers:
            try:
                _processar_ticker(conn, run_id, ticker, offline)
                ok += 1
                print(f"  [OK]  {ticker}")
            except Exception as e:
                fail += 1
                errors[ticker] = f"{type(e).__name__}: {e}"
                print(f"  [ERR] {ticker}: {e}", file=sys.stderr)

        duration = time.time() - t0

        if fail == 0 and ok > 0:
            status = "ok"
        elif ok > 0:
            status = "partial"
        else:
            status = "error"

        _finish_run(conn, run_id, ok, fail, errors, duration, status)

        return {
            "status": status,
            "ok": ok,
            "fail": fail,
            "errors": errors,
            "duration_sec": round(duration, 2),
            "db_path": db_path,
            "run_id": run_id,
            "mode": mode,
        }
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="b3_mcp.superset_ingest.ingest",
        description="Pipeline de ingestão B3 → SQLite (Apache Superset)",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Processar todos os tickers offline disponíveis")
    group.add_argument("--ticker", type=str, help="Processar 1 ticker específico")
    group.add_argument("--tickers", type=str, help="Lista de tickers separados por vírgula")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Usar datasets offline (default)")
    mode.add_argument("--live", action="store_true", help="Usar Yahoo Finance ao vivo")

    p.add_argument("--db", type=str, default=None, help="Caminho do SQLite (override de $B3_ANALYTICS_DB)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.all:
        tickers: list[str] | None = None
    elif args.ticker:
        tickers = [args.ticker]
    else:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    offline = not args.live  # default offline

    print(f"[ingest] db_path={args.db or _get_db_path()}")
    print(f"[ingest] mode={'offline' if offline else 'live'}")
    print(f"[ingest] tickers={tickers or 'ALL (offline disponíveis)'}")

    try:
        result = run_ingest(tickers=tickers, offline=offline, db_path=args.db)
    except Exception as e:
        print(f"[ingest] FATAL: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
