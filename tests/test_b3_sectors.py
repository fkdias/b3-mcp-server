"""Mapa setorial: guarda contra código morto e ticker duplicado.

Revisado em 2026-09-25 — 18 dos 92 códigos estavam deslistados ou renomeados e sumiam calados da
leitura setorial. Estes testes não consultam a rede: travam a regressão (um código velho voltar ao
mapa) e a consistência do próprio mapa.
"""

from __future__ import annotations

from b3_mcp.core.data.b3_sectors import SETORES, TODOS_ATIVOS, get_setor

# Códigos que deixaram de negociar até 2026-09-25 (renomeados ou deslistados). Se algum voltar ao
# mapa, a leitura setorial volta a perder ativos em silêncio.
CODIGOS_MORTOS = {
    "ARZZ3",
    "AZUL4",
    "BRFS3",
    "CCRO3",
    "CRFB3",
    "ELET3",
    "ELET6",
    "EMBR3",
    "ENBR3",
    "GOLL4",
    "JBSS3",
    "MRFG3",
    "NEOE3",
    "NTCO3",
    "PETZ3",
    "RRRP3",
    "SOMA3",
    "STBP3",
    "OIBR3",
}


def test_nenhum_codigo_morto_no_mapa():
    assert CODIGOS_MORTOS.isdisjoint(TODOS_ATIVOS)


def test_nenhum_ticker_em_dois_setores():
    todos = [t for ativos in SETORES.values() for t in ativos]
    assert len(todos) == len(set(todos))


def test_nenhum_setor_vazio():
    assert all(SETORES.values())


def test_codigos_renomeados_resolvem_para_o_setor_certo():
    assert get_setor("EMBJ3") == "Bens Industriais"
    assert get_setor("MBRF3") == "Alimentos"
    assert get_setor("AXIA3") == "Energia Elétrica"
    assert get_setor("BRAV3.SA") == "Petróleo e Gás"
