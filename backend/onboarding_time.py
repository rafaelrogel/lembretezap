"""
Parse da hora local a partir da mensagem do utilizador («que horas são aí?»).
Retorna (hora, minuto) em 0-23, 0-59 ou None.
"""

import re
from typing import Tuple


def parse_local_time_from_message(text: str | None) -> Tuple[int, int] | None:
    """
    Extrai hora e minuto da mensagem (ex.: «14:30», «14h30», «2 da tarde», «3pm»).
    Retorna (h, m) ou None.
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    # 24h: 14:30, 14.30, 14h30, 14h 30
    m = re.search(r"\b(\d{1,2})[h:\.\s]+(\d{2})\b", t, re.I)
    if m:
        h, m_val = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= m_val <= 59:
            return (h, m_val)
        if 0 <= h <= 12 and 0 <= m_val <= 59:  # pode ser 12h
            return (h, m_val)
    # 24h só hora: 14h, 14
    m = re.search(r"\b(\d{1,2})\s*h(?:oras?)?\s*(?:e\s*(\d{1,2}))?\b", t, re.I)
    if m:
        h = int(m.group(1))
        m_val = int(m.group(2)) if m.group(2) else 0
        if 0 <= h <= 23 and 0 <= m_val <= 59:
            return (h, m_val)
    # 12h: 2 pm, 2 da tarde, 3am, 10 da manhã
    tarde_noite = re.compile(
        r"\b(\d{1,2})\s*(?:h(?:oras?)?)?\s*"
        r"(?:da\s*(?:tarde|noite)|pm|p\.m\.|depois\s*do\s*meio[- ]?dia)",
        re.I
    )
    manha = re.compile(
        r"\b(\d{1,2})\s*(?:h(?:oras?)?)?\s*"
        r"(?:da\s*manhã|da\s*manha|am|a\.m\.)",
        re.I
    )
    for pattern, add_12 in [(tarde_noite, True), (manha, False)]:
        m = pattern.search(t)
        if m:
            h = int(m.group(1))
            if 1 <= h <= 12:
                if add_12 and h != 12:
                    h += 12
                elif not add_12 and h == 12:
                    h = 0
                return (h, 0)
    # Número isolado 0-23 (hora sem minuto)
    m = re.search(r"\b(0?[0-9]|1[0-9]|2[0-3])\s*(?:h|horas?)?\s*$", t, re.I)
    if m:
        return (int(m.group(1)), 0)
    return None
