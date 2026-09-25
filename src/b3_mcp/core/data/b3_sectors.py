"""Setores da B3 e seus principais ativos."""

SETORES: dict[str, list[str]] = {
    # Mapa revisado em 2026-09-25: 9 códigos renomeados trocados pelo atual (conferido na lista de
    # renomeações da Brapi e com cotação no Yahoo), 8 sem cotação em nenhuma fonte removidos, e os
    # ativos da watchlist da Sala Nitro incluídos. Código deslistado aqui não dá erro — some calado
    # da leitura setorial —, então revisar quando uma empresa mudar de ticker.
    "Financeiro": [
        "ITUB4",
        "BBDC4",
        "BBAS3",
        "SANB11",
        "BPAC11",
        "B3SA3",
        "ITSA4",
        "BBDC3",
        "BRSR6",
        "ABCB4",
    ],
    "Petróleo e Gás": [
        "PETR4",
        "PETR3",
        "PRIO3",
        "RECV3",
        "BRAV3",  # ex-RRRP3 (3R + Enauta), desde 09/2024
        "CSAN3",
        "UGPA3",
        "VBBR3",
    ],
    "Mineração e Siderurgia": [
        "VALE3",
        "CSNA3",
        "GGBR4",
        "USIM5",
        "CMIN3",
        "GOAU4",
        "BRAP4",
    ],
    "Energia Elétrica": [
        "AXIA3",  # ex-ELET3 (Eletrobras → Axia), desde 11/2025
        "ENGI11",
        "EQTL3",
        "CPFE3",
        "CMIG4",
        "TAEE11",
        "AURE3",
    ],
    "Consumo": [
        "ABEV3",
        "MGLU3",
        "LREN3",
        "AUAU3",  # ex-PETZ3 (Petz + Cobasi), desde 01/2026
        "AZZA3",  # ex-ARZZ3 e SOMA3 (Arezzo + Soma), desde 08/2024
        "NATU3",  # ex-NTCO3, desde 07/2025
        "ASAI3",
        "PCAR3",
    ],
    "Saúde": [
        "HAPV3",
        "RDOR3",
        "FLRY3",
        "HYPE3",
        "RADL3",
        "ONCO3",
    ],
    "Telecomunicações": [
        "VIVT3",
        "TIMS3",
    ],
    "Tecnologia": [
        "TOTS3",
        "LWSA3",
        "POSI3",
        "CASH3",
        "MLAS3",
        "BMOB3",
    ],
    "Construção Civil": [
        "CYRE3",
        "MRVE3",
        "EZTC3",
        "EVEN3",
        "DIRR3",
        "TEND3",
        "TRIS3",
        "MDNE3",
    ],
    "Papel e Celulose": [
        "SUZB3",
        "KLBN11",
        "KLBN4",
        "RANI3",
    ],
    "Alimentos": [
        "JBSS32",  # ex-JBSS3: JBS migrou para a NYSE; na B3 negocia como BDR, desde 2025
        "MBRF3",  # ex-BRFS3 e MRFG3 (BRF + Marfrig), desde 09/2025
        "MDIA3",
        "BEEF3",
        "SMTO3",
        "CAML3",
    ],
    "Transporte e Logística": [
        "RAIL3",
        "MOTV3",  # ex-CCRO3 (CCR → Motiva), desde 05/2025
        "ECOR3",
        "RENT3",
    ],
    "Seguros": [
        "BBSE3",
        "IRBR3",
        "CXSE3",
        "PSSA3",
    ],
    "Saneamento": [
        "SBSP3",
        "SAPR11",
        "CSMG3",
    ],
    "Bens Industriais": [
        "WEGE3",
        "EMBJ3",  # ex-EMBR3 (Embraer), desde 11/2025; antes ficava em Transporte e Logística
    ],
    "Educação": [
        "COGN3",
    ],
    "Química": [
        "BRKM5",
    ],
}

TODOS_ATIVOS: list[str] = sorted({ativo for ativos in SETORES.values() for ativo in ativos})


def get_setor(ticker: str) -> str | None:
    """Retorna o setor de um ticker, ou None se não encontrado."""
    ticker = ticker.upper().replace(".SA", "")
    for setor, ativos in SETORES.items():
        if ticker in ativos:
            return setor
    return None


def get_ativos_setor(setor: str) -> list[str]:
    """Retorna os ativos de um setor (busca parcial, case-insensitive)."""
    setor_lower = setor.lower()
    for nome, ativos in SETORES.items():
        if setor_lower in nome.lower():
            return ativos
    return []
