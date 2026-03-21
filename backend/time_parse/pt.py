"""Portuguese language constants for time parsing."""

DIAS_SEMANA = {
    "segunda-feira": 1, "terça-feira": 2, "terca-feira": 2, "quarta-feira": 3, "quinta-feira": 4, "sexta-feira": 5,
    "domingo": 0, "segunda": 1, "terça": 2, "terca": 2, "quarta": 3, "quinta": 4, "sexta": 5,
    "sábado": 6, "sabado": 6,
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

MONTH_NAMES = [
    "janeiro", "fevereiro", r"mar[cç]o", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
]

RE_DAQUI = r"daqui\s+a\s+(\d+)\s*(minutos?|minuto?|min|horas?|hora?|dias?|dia?)\b"
RE_EM = r"em\s+(\d+)\s*(minutos?|minuto?|min|horas?|hora?|dias?|dia?)\b"

AM_PM_MODIFIERS = [
    r"(?:da|de|na|[àa]s?)\s+(?:manh[ãa]|tarde|noite)"
]
