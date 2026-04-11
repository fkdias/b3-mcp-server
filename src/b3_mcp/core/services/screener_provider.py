"""Provider para TradingView Screener — B3/BMFBOVESPA."""

from typing import Any

try:
    from tradingview_screener import Query, Column
    TV_DISPONIVEL = True
except ImportError:
    TV_DISPONIVEL = False


EXCHANGE = "BMFBOVESPA"
MARKET = "brazil"


def _check_tv():
    if not TV_DISPONIVEL:
        raise RuntimeError(
            "tradingview-screener não instalado. "
            "Execute: pip install tradingview-screener"
        )


def maiores_altas(limite: int = 10) -> list[dict[str, Any]]:
    """Retorna as maiores altas do dia na B3."""
    _check_tv()
    q = (
        Query()
        .set_markets(MARKET)
        .where(Column("exchange") == EXCHANGE)
        .where(Column("change") > 0)
        .order_by("change", ascending=False)
        .limit(limite * 3)
        .select(
            "name", "close", "change", "change_abs",
            "volume", "market_cap_basic", "description"
        )
    )
    count, rows = q.get_scanner_data()
    return _formatar_resultados(rows)[:limite]


def maiores_baixas(limite: int = 10) -> list[dict[str, Any]]:
    """Retorna as maiores baixas do dia na B3."""
    _check_tv()
    q = (
        Query()
        .set_markets(MARKET)
        .where(Column("exchange") == EXCHANGE)
        .where(Column("change") < 0)
        .order_by("change", ascending=True)
        .limit(limite * 3)
        .select(
            "name", "close", "change", "change_abs",
            "volume", "market_cap_basic", "description"
        )
    )
    count, rows = q.get_scanner_data()
    return _formatar_resultados(rows)[:limite]


def maiores_volumes(limite: int = 10) -> list[dict[str, Any]]:
    """Retorna os ativos com maior volume do dia na B3."""
    _check_tv()
    q = (
        Query()
        .set_markets(MARKET)
        .where(Column("exchange") == EXCHANGE)
        .order_by("volume", ascending=False)
        .limit(limite * 3)
        .select(
            "name", "close", "change", "change_abs",
            "volume", "market_cap_basic", "description"
        )
    )
    count, rows = q.get_scanner_data()
    return _formatar_resultados(rows)[:limite]


def _formatar_resultados(rows) -> list[dict[str, Any]]:
    """Converte DataFrame do screener para lista de dicts."""
    resultados = []
    if hasattr(rows, "to_dict"):
        # pandas DataFrame
        for _, row in rows.iterrows():
            ticker_raw = row.get("name", "")
            if ":" in str(ticker_raw):
                ticker_raw = str(ticker_raw).split(":")[-1]
            # Ignorar tickers fracionários (terminam com F)
            if str(ticker_raw).endswith("F"):
                continue
            resultados.append({
                "ticker": ticker_raw,
                "preco": round(float(row.get("close", 0)), 2),
                "variacao_pct": round(float(row.get("change", 0)), 2),
                "variacao_abs": round(float(row.get("change_abs", 0)), 2),
                "volume": int(row.get("volume", 0)),
                "market_cap": float(row.get("market_cap_basic", 0)),
                "nome": str(row.get("description", "")),
            })
    return resultados
