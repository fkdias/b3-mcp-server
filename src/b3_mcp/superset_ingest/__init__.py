"""
Pipeline de ingestão do B3 MCP Server para Apache Superset.

Popula um SQLite em `B3_ANALYTICS_DB` (default: C:\\b3-analytics\\b3_analytics.db)
a partir das análises existentes (Hi-Lo, backtest, opções). Consumido pelo
Superset rodando em WSL2 via /mnt/c/b3-analytics/b3_analytics.db.
"""

from .ingest import run_ingest

__all__ = ["run_ingest"]
