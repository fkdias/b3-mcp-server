"""Formatação para o mercado brasileiro."""


def formatar_brl(valor: float) -> str:
    """Formata valor em reais: R$ 1.234,56"""
    if valor >= 0:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: float) -> str:
    """Formata percentual: +2,45% ou -1,23%"""
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{valor:.2f}%".replace(".", ",")


def formatar_volume(valor: float) -> str:
    """Formata volume: 1,2M ou 345,6K"""
    if valor >= 1_000_000_000:
        return f"{valor / 1_000_000_000:.1f}B".replace(".", ",")
    if valor >= 1_000_000:
        return f"{valor / 1_000_000:.1f}M".replace(".", ",")
    if valor >= 1_000:
        return f"{valor / 1_000:.1f}K".replace(".", ",")
    return str(int(valor))


def ticker_para_yahoo(ticker: str) -> str:
    """PETR4 -> PETR4.SA"""
    ticker = ticker.upper().strip()
    if ticker.endswith(".SA"):
        return ticker
    return f"{ticker}.SA"


def ticker_para_tv(ticker: str) -> str:
    """PETR4 -> BMFBOVESPA:PETR4"""
    ticker = ticker.upper().strip().replace(".SA", "")
    if ":" in ticker:
        return ticker
    return f"BMFBOVESPA:{ticker}"


def ticker_limpo(ticker: str) -> str:
    """BMFBOVESPA:PETR4 ou PETR4.SA -> PETR4"""
    ticker = ticker.upper().strip()
    if ":" in ticker:
        ticker = ticker.split(":")[-1]
    return ticker.replace(".SA", "")
