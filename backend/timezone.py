"""Timezone por utilizador: inferência por prefixo telefónico e /tz Cidade (IANA)."""

from zoneinfo import ZoneInfo

from backend.locale import _digits_from_chat_id

# Brasil: DDD (2 dígitos, após 55) → IANA da capital do estado (fusos: Rio Branco, Manaus, Cuiabá, São Paulo)
# Ver: https://www.anatel.gov.br/legislacao/resolucoes/2023/1482-resolucao-745
BR_DDD_TO_IANA = {
    68: "America/Rio_Branco",       # Acre - Rio Branco
    82: "America/Maceio",           # Alagoas - Maceió (Maceio em IANA)
    96: "America/Belem",            # Amapá - Macapá (usa Belém)
    92: "America/Manaus",           # Amazonas - Manaus
    71: "America/Bahia",            # Bahia - Salvador
    85: "America/Fortaleza",        # Ceará - Fortaleza
    61: "America/Sao_Paulo",        # DF - Brasília
    27: "America/Sao_Paulo",        # ES - Vitória
    62: "America/Sao_Paulo",        # Goiás - Goiânia
    98: "America/Sao_Paulo",        # Maranhão - São Luís
    65: "America/Cuiaba",           # Mato Grosso - Cuiabá
    67: "America/Campo_Grande",      # Mato Grosso do Sul - Campo Grande
    31: "America/Sao_Paulo",        # MG - Belo Horizonte
    91: "America/Belem",             # Pará - Belém
    83: "America/Sao_Paulo",         # Paraíba - João Pessoa
    41: "America/Sao_Paulo",         # Paraná - Curitiba
    81: "America/Recife",            # Pernambuco - Recife
    86: "America/Sao_Paulo",         # Piauí - Teresina
    21: "America/Sao_Paulo",         # RJ - Rio de Janeiro
    84: "America/Sao_Paulo",         # RN - Natal
    51: "America/Sao_Paulo",         # RS - Porto Alegre
    69: "America/Porto_Velho",      # Rondônia - Porto Velho
    95: "America/Boa_Vista",        # Roraima - Boa Vista
    48: "America/Sao_Paulo",         # SC - Florianópolis
    11: "America/Sao_Paulo",         # SP - São Paulo
    79: "America/Sao_Paulo",         # Sergipe - Aracaju
    63: "America/Sao_Paulo",         # Tocantins - Palmas
}

# Prefixo país (dígitos) → IANA timezone por defeito (Brasil 55 tratado à parte com DDD)
_DEFAULT_TZ_BY_PREFIX = {
    "351": "Europe/Lisbon",         # Portugal
    "34": "Europe/Madrid",          # Espanha
    "52": "America/Mexico_City",    # México
    "54": "America/Argentina/Buenos_Aires",
    "57": "America/Bogota",
    "58": "America/Caracas",
    "51": "America/Lima",
    "56": "America/Santiago",
    "593": "America/Guayaquil",
    "598": "America/Montevideo",
    "591": "America/La_Paz",
    "503": "America/El_Salvador",
    "502": "America/Guatemala",
    "505": "America/Managua",
    "506": "America/Costa_Rica",
    "507": "America/Panama",
    "53": "America/Havana",
    "44": "Europe/London",          # UK
    "33": "Europe/Paris",
    "49": "Europe/Berlin",
    "39": "Europe/Rome",
    "1": "America/New_York",        # EUA (default; não cobre todos)
}
# Ordenar por comprimento decrescente para match correto (351 antes de 35)
_PREFIXES_SORTED = sorted(_DEFAULT_TZ_BY_PREFIX.keys(), key=len, reverse=True)

# Fuso padrão por idioma (quando chat_id não tem dígitos e devolveria UTC).
# Garante que o cliente, onde quer que esteja, tem o horário considerado.
DEFAULT_TZ_BY_LANG: dict[str, str] = {
    "pt-BR": "America/Sao_Paulo",
    "pt-PT": "Europe/Lisbon",
    "es": "Europe/Madrid",
    "en": "America/New_York",
}

# Cidades comuns → IANA (para /tz Cidade)
CITY_TO_IANA = {
    "lisboa": "Europe/Lisbon",
    "lisbon": "Europe/Lisbon",
    "porto": "Europe/Lisbon",
    "portugal": "Europe/Lisbon",
    "são paulo": "America/Sao_Paulo",
    "sao paulo": "America/Sao_Paulo",
    "brasília": "America/Sao_Paulo",
    "brasilia": "America/Sao_Paulo",
    "rio": "America/Sao_Paulo",
    "rio de janeiro": "America/Sao_Paulo",
    "salvador": "America/Bahia",
    "bahia": "America/Bahia",
    "maceió": "America/Maceio",
    "maceio": "America/Maceio",
    "manaus": "America/Manaus",
    "belém": "America/Belem",
    "belem": "America/Belem",
    "fortaleza": "America/Fortaleza",
    "recife": "America/Recife",
    "goiânia": "America/Sao_Paulo",
    "goiania": "America/Sao_Paulo",
    "cuiabá": "America/Cuiaba",
    "cuiaba": "America/Cuiaba",
    "campo grande": "America/Campo_Grande",
    "rio branco": "America/Rio_Branco",
    "porto velho": "America/Porto_Velho",
    "boa vista": "America/Boa_Vista",
    "curitiba": "America/Sao_Paulo",
    "belo horizonte": "America/Sao_Paulo",
    "porto alegre": "America/Sao_Paulo",
    "florianópolis": "America/Sao_Paulo",
    "florianopolis": "America/Sao_Paulo",
    "natal": "America/Sao_Paulo",
    "joão pessoa": "America/Sao_Paulo",
    "joao pessoa": "America/Sao_Paulo",
    "teresina": "America/Sao_Paulo",
    "são luís": "America/Sao_Paulo",
    "sao luis": "America/Sao_Paulo",
    "macapá": "America/Belem",
    "macapa": "America/Belem",
    "aracaju": "America/Sao_Paulo",
    "palmas": "America/Sao_Paulo",
    "vitória": "America/Sao_Paulo",
    "vitoria": "America/Sao_Paulo",
    "brasil": "America/Sao_Paulo",
    "brazil": "America/Sao_Paulo",
    "madrid": "Europe/Madrid",
    "barcelona": "Europe/Madrid",
    "espanha": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "london": "Europe/London",
    "londres": "Europe/London",
    "uk": "Europe/London",
    "nova york": "America/New_York",
    "new york": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "mexico": "America/Mexico_City",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "bogotá": "America/Bogota",
    "bogota": "America/Bogota",
    "lima": "America/Lima",
    "santiago": "America/Santiago",
    # Mais cidades do mundo (onboarding aceita qualquer cidade; reconhecidas aqui ajustam o fuso)
    "paris": "Europe/Paris",
    "berlim": "Europe/Berlin",
    "berlin": "Europe/Berlin",
    "roma": "Europe/Rome",
    "rome": "Europe/Rome",
    "tóquio": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "dubai": "Asia/Dubai",
    "dubái": "Asia/Dubai",
    "sydney": "Australia/Sydney",
    "sidney": "Australia/Sydney",
    "toronto": "America/Toronto",
    "vancouver": "America/Vancouver",
    "chicago": "America/Chicago",
    "miami": "America/New_York",
    "amsterdam": "Europe/Amsterdam",
    "bruxelas": "Europe/Brussels",
    "brussels": "Europe/Brussels",
    "viena": "Europe/Vienna",
    "vienna": "Europe/Vienna",
    "moscou": "Europe/Moscow",
    "moscow": "Europe/Moscow",
    "pequim": "Asia/Shanghai",
    "beijing": "Asia/Shanghai",
    "xangai": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "singapura": "Asia/Singapore",
    "singapore": "Asia/Singapore",
    "bombaim": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata",
    "cidade do cabo": "Africa/Johannesburg",
    "cape town": "Africa/Johannesburg",
    "joanesburgo": "Africa/Johannesburg",
    "johannesburg": "Africa/Johannesburg",
    "nairobi": "Africa/Nairobi",
    "lagos": "Africa/Lagos",
    "cairo": "Africa/Cairo",
}


def phone_to_default_timezone(chat_id: str) -> str:
    """Infere timezone por defeito: Brasil (55) pelo DDD da capital do estado; outros pelo prefixo do país."""
    digits = _digits_from_chat_id(chat_id)
    if not digits:
        return "UTC"
    # Brasil: 55 + DDD (2 dígitos) → fuso da capital do estado
    if digits.startswith("55") and len(digits) >= 4:
        try:
            ddd = int(digits[2:4])
            if ddd in BR_DDD_TO_IANA:
                return BR_DDD_TO_IANA[ddd]
        except (ValueError, IndexError):
            pass
        return "America/Sao_Paulo"  # fallback Brasil
    for prefix in _PREFIXES_SORTED:
        if digits.startswith(prefix):
            return _DEFAULT_TZ_BY_PREFIX[prefix]
    return "UTC"


def format_utc_timestamp_for_user(utc_timestamp_seconds: int, tz_name: str, show_seconds: bool = False) -> str:
    """Formata timestamp UTC como HH:MM (ou HH:MM:SS) no timezone do utilizador.
    Horário de verão (DST): tratado automaticamente pela base IANA (zoneinfo).
    Portugal (Europe/Lisbon): UTC+0 inverno, UTC+1 verão. Brasil: sem DST desde 2019.
    show_seconds=True: inclui segundos (para lembretes curtos 'daqui a X min').
    """
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    from datetime import datetime
    dt = datetime.fromtimestamp(utc_timestamp_seconds, tz=tz)
    fmt = "%H:%M:%S" if show_seconds else "%H:%M"
    return dt.strftime(fmt)


def is_valid_iana(tz_name: str) -> bool:
    """True se tz_name é um timezone IANA válido."""
    try:
        ZoneInfo(tz_name)
        return True
    except Exception:
        return False


def city_to_iana(city: str) -> str | None:
    """Converte nome de cidade (normalizado) para IANA. Retorna None se não reconhecido."""
    key = (city or "").strip().lower()
    if not key:
        return None
    key = key.replace("-", " ").replace("_", " ")
    return CITY_TO_IANA.get(key)


def iana_from_offset_minutes(offset_minutes: int) -> str:
    """
    Converte offset UTC em minutos (positivo = à frente de UTC) para IANA.
    Usado quando o utilizador diz «são 14h30» e sabemos a hora UTC do servidor.
    Retorna Etc/GMT±N (válido em zoneinfo).
    """
    if offset_minutes >= 0:
        hours = min(14, offset_minutes // 60)
        return f"Etc/GMT-{hours}"  # Etc/GMT-2 = UTC+2
    hours = min(12, (-offset_minutes) // 60)
    return f"Etc/GMT+{hours}"  # Etc/GMT+3 = UTC-3
