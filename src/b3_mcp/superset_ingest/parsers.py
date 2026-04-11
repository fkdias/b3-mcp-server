"""
Parsers para converter strings formatadas pt-BR dos serviços B3 em numéricos puros.

Os serviços `hilo_service`, `backtest_service` e `options_sim` retornam várias
métricas já formatadas para humanos (ex: "55,50%", "R$ 1.234,56"). Apache Superset
precisa de REAL/INTEGER para agregar, ordenar e plotar. Este módulo faz o caminho
inverso.

Edge cases tratados:
- `None` e "N/A" → None
- `float('inf')` no profit_factor → (None, True) via _pf_guard
- Separador de milhares "." e decimal ","
- Sinal negativo
- Prefixo "R$ " (com ou sem espaço)
- Sufixo "%"
- Strings compostas "YYYY-MM-DD @ R$ 30,50" (trades)
"""

from __future__ import annotations

import math
import re
from typing import Any

_NUM_RE = re.compile(r"[+-]?[\d.,]+")


def _parse_num(valor: Any) -> float | None:
    """
    Converte string formatada pt-BR em float puro.

    Exemplos:
        "55,50%"          -> 55.5
        "R$ 1.234,56"     -> 1234.56
        "-12,30%"         -> -12.3
        "N/A"             -> None
        None              -> None
        float('inf')      -> None
        42.5              -> 42.5
        "2.5"             -> 2.5  (formato US, sem vírgula)
    """
    if valor is None:
        return None

    # Já é numérico
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and (math.isinf(valor) or math.isnan(valor)):
            return None
        return float(valor)

    if not isinstance(valor, str):
        return None

    s = valor.strip()
    if not s or s.upper() in {"N/A", "NA", "NONE", "NULL", "-", "—"}:
        return None

    # Remover R$, %, espaços (inclusive internos, ex: "-R$ 1,49" -> "-1,49")
    s = s.replace("R$", "").replace("%", "")
    s = "".join(s.split())  # remove TODO whitespace (inclusive interno)

    if not s or s in {"+", "-"}:
        return None

    # Detectar formato pt-BR (tem vírgula como decimal) vs US (só ponto)
    if "," in s:
        # pt-BR: "1.234,56" → "1234.56"
        s = s.replace(".", "").replace(",", ".")
    # else: formato US-like "2.5" ou "2500", deixa como está

    try:
        num = float(s)
        if math.isinf(num) or math.isnan(num):
            return None
        return num
    except (ValueError, TypeError):
        return None


def _parse_trade_entrada(valor: Any) -> tuple[str | None, float | None]:
    """
    Converte string composta de trade em (data, preço).

    Formato esperado: "YYYY-MM-DD @ R$ 30,50"

    Exemplos:
        "2024-03-15 @ R$ 30,50"   -> ("2024-03-15", 30.50)
        "2024-03-15@R$30,50"       -> ("2024-03-15", 30.50)
        "2024-03-15"               -> ("2024-03-15", None)
        None                       -> (None, None)
        ""                         -> (None, None)
    """
    if valor is None or not isinstance(valor, str):
        return (None, None)

    s = valor.strip()
    if not s:
        return (None, None)

    if "@" in s:
        partes = s.split("@", 1)
        data_raw = partes[0].strip()
        preco_raw = partes[1].strip() if len(partes) > 1 else ""
        data = data_raw or None
        preco = _parse_num(preco_raw)
        return (data, preco)

    # Sem @ — assumir que é só a data
    return (s or None, None)


def _pf_guard(pf: Any) -> tuple[float | None, bool]:
    """
    Guard para profit_factor que pode ser float('inf') quando não há losses.

    Retorna (valor_numerico_ou_None, is_inf_flag).

    Exemplos:
        float('inf')  -> (None, True)
        2.5           -> (2.5, False)
        "2.5"         -> (2.5, False)
        "N/A"         -> (None, False)
        None          -> (None, False)
        0             -> (0.0, False)
    """
    if pf is None:
        return (None, False)

    # Detecção direta de inf (float ou string)
    if isinstance(pf, float):
        if math.isinf(pf):
            return (None, True)
        if math.isnan(pf):
            return (None, False)
        return (float(pf), False)

    if isinstance(pf, int):
        return (float(pf), False)

    if isinstance(pf, str):
        s = pf.strip().lower()
        if s in {"inf", "infinity", "infinito", "+inf", "∞"}:
            return (None, True)
        num = _parse_num(pf)
        return (num, False)

    return (None, False)
