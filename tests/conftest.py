"""Fixtures compartilhadas entre os testes do b3-mcp-server.

Fornece:
- `candles_sinteticos`: 30 candles OHLC em uptrend linear puro (determinístico).
- `candles_flat`: 30 candles com preço constante (volatilidade zero).
- `candles_petr4`: dataset real de PETR4 (750 candles) vindo da cópia
  congelada em `tests/fixtures/samples/` — anchor de integração estável.
- `fechamentos_sinteticos`: série de fechamentos derivada do fixture sintético.
"""

from __future__ import annotations

import os
from pathlib import Path

# Aponta os dados offline para a cópia CONGELADA antes de importar o pacote — o
# pipeline diário reescreve o diretório de produção. Ver tests/fixtures/README.md.
os.environ.setdefault(
    "B3_SAMPLES_DIR", str(Path(__file__).parent / "fixtures" / "samples")
)

import pytest  # noqa: E402

from b3_mcp.core.services.hilo_service import _carregar_offline  # noqa: E402


@pytest.fixture
def candles_sinteticos() -> list[dict]:
    """30 candles OHLC determinísticos em uptrend linear.

    Cada candle sobe exatamente 1 unidade em todas as pontas (abertura/
    máxima/mínima/fechamento), com volumes também crescentes. Útil pra
    validar comportamento de indicadores em cenário extremo de só-alta.
    """
    return [
        {
            "data": f"2025-01-{i + 1:02d}",
            "abertura": 10.0 + i,
            "maxima": 11.0 + i,
            "minima": 9.0 + i,
            "fechamento": 10.5 + i,
            "volume": 1_000_000 + i * 10_000,
        }
        for i in range(30)
    ]


@pytest.fixture
def candles_flat() -> list[dict]:
    """30 candles com OHLC constante em 20.0 e volume estável.

    Zero volatilidade. Qualquer indicador baseado em variação (RSI, Hi-Lo,
    Bollinger) deve degenerar em casos-borda bem definidos.
    """
    out = []
    for i in range(30):
        if i < 28:
            data = f"2025-02-{i + 1:02d}"
        else:
            data = f"2025-03-{i - 27:02d}"
        out.append(
            {
                "data": data,
                "abertura": 20.0,
                "maxima": 20.0,
                "minima": 20.0,
                "fechamento": 20.0,
                "volume": 500_000,
            }
        )
    return out


@pytest.fixture
def candles_petr4() -> list[dict]:
    """Dataset real PETR4 (750 candles) — cópia congelada em tests/fixtures.

    Gabarito fixo: não é afetado pelo `atualizar_datasets.py`, que reescreve o
    diretório de produção todo dia útil. Os testes que o consomem ainda tratam
    `None` por segurança, mas o arquivo é versionado e deve sempre existir.
    """
    return _carregar_offline("PETR4")


@pytest.fixture
def fechamentos_sinteticos(candles_sinteticos: list[dict]) -> list[float]:
    """Série de fechamentos extraída do uptrend linear (30 valores)."""
    return [c["fechamento"] for c in candles_sinteticos]
