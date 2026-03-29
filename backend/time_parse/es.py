"""Spanish language constants for time parsing."""

DIAS_SEMANA = {
    "lunes": 1, "martes": 2, "miércoles": 3, "miercoles": 3, "jueves": 4, "viernes": 5,
    "sábado": 6, "sabado": 6, "domingo": 0,
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

MONTH_NAMES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

RE_EM = r"em\s+(\d+)\s*(minutos?|horas?|d[íi]as?)\b"
RE_EN = r"en\s+(\d+)\s*(minutos?|horas?|d[íi]as?)\b"

AM_PM_MODIFIERS = [
    r"(?:de|por)\s+la\s+(?:ma[ñn]ana|tarde|noche)"
]
