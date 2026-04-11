"""Setores da B3 e seus principais ativos."""

SETORES: dict[str, list[str]] = {
    "Financeiro": [
        "ITUB4", "BBDC4", "BBAS3", "SANB11", "BPAC11", "B3SA3",
        "ITSA4", "BBDC3", "BRSR6", "ABCB4",
    ],
    "Petróleo e Gás": [
        "PETR4", "PETR3", "PRIO3", "RECV3", "RRRP3", "CSAN3",
        "UGPA3", "VBBR3",
    ],
    "Mineração e Siderurgia": [
        "VALE3", "CSNA3", "GGBR4", "USIM5", "CMIN3", "GOAU4",
    ],
    "Energia Elétrica": [
        "ELET3", "ELET6", "ENGI11", "EQTL3", "CPFE3", "CMIG4",
        "TAEE11", "ENBR3", "AURE3", "NEOE3",
    ],
    "Consumo": [
        "ABEV3", "MGLU3", "LREN3", "PETZ3", "ARZZ3", "SOMA3",
        "NTCO3", "ASAI3", "CRFB3", "PCAR3",
    ],
    "Saúde": [
        "HAPV3", "RDOR3", "FLRY3", "HYPE3", "RADL3", "ONCO3",
    ],
    "Telecomunicações": [
        "VIVT3", "TIMS3", "OIBR3",
    ],
    "Tecnologia": [
        "TOTS3", "LWSA3", "POSI3", "CASH3", "MLAS3", "BMOB3",
    ],
    "Construção Civil": [
        "CYRE3", "MRVE3", "EZTC3", "EVEN3", "DIRR3", "TEND3",
        "TRIS3", "MDNE3",
    ],
    "Papel e Celulose": [
        "SUZB3", "KLBN11", "KLBN4", "RANI3",
    ],
    "Alimentos": [
        "JBSS3", "BRFS3", "MDIA3", "MRFG3", "BEEF3", "SMTO3",
        "CAML3",
    ],
    "Transporte e Logística": [
        "RAIL3", "CCRO3", "AZUL4", "GOLL4", "EMBR3", "ECOR3",
        "STBP3",
    ],
    "Seguros": [
        "BBSE3", "IRBR3", "CXSE3", "PSSA3",
    ],
    "Saneamento": [
        "SBSP3", "SAPR11", "CSMG3",
    ],
}

TODOS_ATIVOS: list[str] = sorted(
    {ativo for ativos in SETORES.values() for ativo in ativos}
)


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
