"""Smoke tests pro gerador de gráficos (chart_service.gerar_grafico_hilo).

Escopo: apenas verificar que o PNG é gerado e tem o magic-byte correto.
Não validamos aparência visual (fora do escopo automatizado).
"""

from __future__ import annotations

import os
import tempfile

import pytest

from b3_mcp.core.services.chart_service import gerar_grafico_hilo
from b3_mcp.core.services.hilo_service import _carregar_offline, analisar_hilo
from b3_mcp.core.services.indicators_calc import calc_hilo_activator

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(scope="module")
def petr4_artefatos():
    """Carrega dados offline e gera resultado Hi-Lo real pra alimentar o gráfico."""
    candles = _carregar_offline("PETR4")
    assert candles is not None and len(candles) > 100, "dataset PETR4 offline ausente"

    maximas = [c["maxima"] for c in candles]
    minimas = [c["minima"] for c in candles]
    fechamentos = [c["fechamento"] for c in candles]
    hilo_data = calc_hilo_activator(maximas, minimas, fechamentos, 10)

    # Passa pelo pipeline oficial pra ter o mesmo schema que o tool produz em runtime
    analise = analisar_hilo("PETR4", offline=True, gerar_grafico=False)
    return candles, hilo_data, analise


class TestGerarGraficoHilo:
    def test_gera_png_valido_em_path_explicito(self, petr4_artefatos, tmp_path):
        candles, hilo_data, analise = petr4_artefatos
        out = str(tmp_path / "grafico_petr4.png")

        path = gerar_grafico_hilo(
            candles=candles,
            hilo_data=hilo_data,
            ticker="PETR4",
            resultado_analise=analise,
            ultimos_dias=90,
            output_path=out,
        )

        assert path == out
        assert os.path.exists(path)
        with open(path, "rb") as fh:
            header = fh.read(8)
        assert header == PNG_MAGIC
        # Não é um PNG vazio (header + IEND no mínimo)
        assert os.path.getsize(path) > 1024

    def test_output_path_none_gera_tempfile(self, petr4_artefatos):
        candles, hilo_data, analise = petr4_artefatos

        path = gerar_grafico_hilo(
            candles=candles,
            hilo_data=hilo_data,
            ticker="PETR4",
            resultado_analise=analise,
            ultimos_dias=60,
            output_path=None,
        )

        try:
            assert path
            assert os.path.exists(path)
            # Quando output_path=None, o chart_service cria em tempdir
            assert os.path.dirname(path) == tempfile.gettempdir() or path.endswith(".png")
            with open(path, "rb") as fh:
                assert fh.read(8) == PNG_MAGIC
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_ultimos_dias_menor_nao_quebra(self, petr4_artefatos, tmp_path):
        """Gerar com janela curta (30 dias) deve funcionar."""
        candles, hilo_data, analise = petr4_artefatos
        out = str(tmp_path / "grafico_30d.png")

        path = gerar_grafico_hilo(
            candles=candles,
            hilo_data=hilo_data,
            ticker="PETR4",
            resultado_analise=analise,
            ultimos_dias=30,
            output_path=out,
        )
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1024
