"""
IDs de 2-3 letras que podem confundir o utilizador quando usados como ID de lembrete.
Ex.: "depois de PIX" no Brasil = pagamento instantâneo, não um lembrete.
Usar para evitar sugestões ou avisar o utilizador.

Cada lista: frozenset de strings (2-3 letras maiúsculas).
"""

# --- PT-BR (Brasil) ---
CONFUSING_IDS_PT_BR: frozenset[str] = frozenset({
    # Estados brasileiros (27)
    "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    # Pagamento / Documentos / Governo
    "PIX", "CPF", "CNH", "PIS", "DRE", "ANV", "ANS",
    "ANP", "BAC", "BND", "CVM", "TCU", "STF", "STJ", "TST", "TSE", "MPF",
    # Bancos / Marcas
    "BB", "IT", "BT", "NU", "XP", "CEF", "BAN", "ITA", "SAN", "BRA",
    # Unidades / Medidas
    "KG", "KM", "ML", "LT", "MT", "CM", "MM", "HA", "M2", "M3",
    # Comum / Internet
    "OK", "ID", "API", "URL", "PDF", "JPG", "PNG", "MP3", "MP4", "ZIP",
    "RAR", "EXE", "TXT", "DOC", "XLS", "PPT", "CSV", "XML",
    "CSS", "JS", "PHP", "SQL", "VPN", "DNS", "IP", "PC", "TV", "HD",
    "SSD", "USB", "RAM", "CPU", "GPU", "LED", "LCD", "BT",
    # Códigos país / Moeda
    "BR", "US", "EU", "PT", "AR", "MX", "CO", "CL", "PE", "UY",
    "BRL", "USD", "EUR", "GBP", "ARS", "MXN",
    # Educação / Profissional
    "EN", "EM", "ET", "IF", "UF", "USP", "UFR", "UNB", "UER", "UFF",
    "MBA", "PHD", "MEC", "CAP", "FAP", "CNP", "CRE", "OAB", "CRM", "CFO",
    # Saúde / Medicamentos
    "HIV", "HPV", "DNA", "RNA", "PCR", "IGG", "IGM", "UBS", "UPA",
    "SUS", "ANS", "ANV", "FDA",
    # Transporte / Logística
    "ANT", "DNI", "PLU", "SKU", "EAN", "NFC",
    # Outros
    "RE", "NA", "DA", "DE", "DO", "NO", "AO", "EM", "OU", "SE",
    "EU", "VO", "TE", "LO", "LA", "LE", "LI", "LU", "AS", "OS",
    "UM", "NOV", "DEZ", "JAN", "FEV", "MAR",
    "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
    "SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM",
    # Partidos / Política
    "PT", "PS", "PP", "PL", "PD", "PM", "PC", "PV", "PSL", "PSD",
    # Empresas / Operadoras
    "OI", "TIM", "VIV", "CLR", "NET", "SKY", "GLO", "REC", "AZU",
    # Cidades / Aeroportos
    "BH", "BS", "CV", "FL", "MC", "PV", "SL", "VD",
    # Esportes / Times
    "CR", "FL", "SC", "SP", "PA", "BA", "RS", "MG",
    # Apps / Serviços
    "UB", "IF", "RA", "IE", "NU", "XP", "BT",
    # Outras siglas comuns
    "AC", "AD", "AE", "AG", "AI", "AM", "AN", "AO", "AP", "AQ", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
    "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BQ", "BS", "BV", "BW", "BX", "BY", "BZ",
    "CC", "CD", "CF", "CG", "CI", "CK", "CN", "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ",
    "DC", "DD", "DG", "DI", "DK", "DL", "DM", "DN", "DP", "DQ", "DR", "DS", "DT", "DU", "DV", "DW", "DX", "DY", "DZ",
    "EA", "EB", "EC", "ED", "EE", "EF", "EG", "EH", "EI", "EK", "EL", "EP", "EQ", "EV", "EW", "EX", "EY", "EZ",
    "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH", "FI", "FJ", "FK", "FL", "FM", "FN", "FO", "FP", "FQ", "FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ",
})

# --- PT-PT (Portugal) ---
CONFUSING_IDS_PT_PT: frozenset[str] = frozenset({
    # Distritos / Regiões Portugal
    "AV", "BE", "BR", "CO", "EV", "FA", "GU", "LE", "LI", "PA",
    "PO", "SA", "SE", "SE", "VI", "VR", "AC", "AL", "AM", "AR",
    "BA", "CA", "CE", "ES", "GU", "MA", "PO", "SA", "SE", "VI",
    # Transportes Portugal
    "CP", "TAP", "ANA", "REF", "CTT", "TST", "TAP", "ANA",
    # Governo / Documentos
    "CC", "NIF", "NIB", "IRS", "IVA", "SS", "SNS", "INEM",
    "IGF", "TCE", "TC", "PR", "AR", "DR", "CM", "JF", "TA", "TR",
    # Bancos Portugal
    "CGD", "BPI", "BES", "BAN", "MIL", "ACT", "BIG", "BNP",
    # Unidades / Medidas
    "KG", "KM", "ML", "LT", "MT", "CM", "MM", "HA", "M2", "M3",
    # Comum / Internet
    "OK", "ID", "API", "URL", "PDF", "JPG", "PNG", "MP3", "MP4", "ZIP",
    "RAR", "EXE", "TXT", "DOC", "XLS", "PPT", "CSV", "XML",
    "CSS", "JS", "PHP", "SQL", "VPN", "DNS", "IP", "PC", "TV", "HD",
    "SSD", "USB", "RAM", "CPU", "GPU", "LED", "LCD", "BT",
    # Códigos país / Moeda
    "PT", "ES", "FR", "UK", "DE", "IT", "NL", "BE", "CH", "AT",
    "EUR", "GBP", "USD", "CHF",
    # Educação
    "UA", "UC", "UP", "UL", "UM", "UNL", "IST", "FEU", "FCT", "FCU",
    # Saúde
    "SNS", "INEM", "IPO", "HUC", "HSJ", "HSA", "CHU",
    # Outros
    "RE", "NA", "DA", "DE", "DO", "NO", "AO", "EM", "OU", "SE",
    "EU", "VO", "TE", "LO", "LA", "LE", "LI", "LU", "AS", "OS",
    "UM", "JAN", "FEV", "MAR", "ABR", "MAI",
    "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
    "SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM",
    "RTP", "SIC", "TVI", "CMT", "PSP", "GNR",
    # Partidos / Política PT
    "PS", "PP", "BE", "CD", "IL", "CH", "LIV",
    # Empresas PT
    "EDP", "GAL", "NOS", "MEO", "PT", "CTT", "CP",
    # Cidades / Regiões
    "LX", "OP", "FN", "CO", "BG", "AV", "SM",
    # Mais siglas
    "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK", "AN", "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
    "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BQ", "BS", "BV", "BW", "BX", "BY", "BZ",
    "CC", "CD", "CE", "CF", "CG", "CI", "CK", "CL", "CN", "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ",
    "DC", "DD", "DG", "DI", "DK", "DL", "DM", "DN", "DP", "DQ", "DR", "DS", "DT", "DU", "DV", "DW", "DX", "DY", "DZ",
    "EA", "EB", "EC", "ED", "EE", "EF", "EG", "EH", "EI", "EK", "EL", "EP", "EQ", "EV", "EW", "EX", "EY", "EZ",
    "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH", "FI", "FJ", "FK", "FL", "FM", "FN", "FO", "FP", "FQ", "FR", "FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ",
})

# --- EN (English) ---
CONFUSING_IDS_EN: frozenset[str] = frozenset({
    # US States (50)
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    # DC, territories
    "DC", "PR", "VI", "GU", "AS", "MP",
    # UK / Commonwealth
    "UK", "US", "EU", "UN", "NATO", "WHO",
    # Tech / Internet
    "OK", "ID", "API", "URL", "PDF", "JPG", "PNG", "MP3", "MP4", "ZIP",
    "RAR", "EXE", "TXT", "DOC", "XLS", "PPT", "CSV", "XML",
    "CSS", "JS", "PHP", "SQL", "VPN", "DNS", "IP", "PC", "TV", "HD",
    "SSD", "USB", "RAM", "CPU", "GPU", "LED", "LCD", "BT",
    # Business / Finance
    "CEO", "CFO", "CTO", "COO", "HR", "IT", "PR", "QA", "VP",
    "IPO", "ETF", "IRA", "SSN", "EIN", "IRS", "FBI", "CIA", "FDA",
    "SEC", "FTC", "EPA", "NIH", "CDC", "DOD", "DOE",
    # Units
    "KG", "KM", "ML", "LT", "MT", "CM", "MM", "HA", "M2", "M3",
    "LB", "OZ", "FT", "IN", "YD", "MI", "GAL", "PT", "QT",
    # Countries / Currency
    "US", "UK", "EU", "CA", "AU", "NZ", "IE", "IN", "CN", "JP",
    "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF",
    # Education
    "PhD", "MBA", "BA", "BS", "MA", "MS", "JD", "MD", "RN", "PA",
    # Health
    "HIV", "HPV", "DNA", "RNA", "PCR", "ER", "ICU", "OR",
    # Other
    "RE", "NA", "DA", "DE", "DO", "NO", "AO", "EM", "OU", "SE",
    "AS", "OS", "AM", "PM", "AD", "BC", "CE", "IE", "EG", "ET",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
    "NOV", "DEC", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
    # Brands / Companies
    "IBM", "HP", "GM", "GE", "AT", "TM", "FB", "GO", "AM", "MS",
    # More common abbreviations
    "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK", "AN", "AO", "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
    "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BQ", "BS", "BV", "BW", "BX", "BY", "BZ",
    "CC", "CD", "CE", "CF", "CG", "CI", "CK", "CL", "CN", "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ",
    "DC", "DD", "DG", "DI", "DK", "DL", "DM", "DN", "DP", "DQ", "DR", "DS", "DT", "DU", "DV", "DW", "DX", "DY", "DZ",
    "EA", "EB", "EC", "ED", "EE", "EF", "EG", "EH", "EI", "EK", "EL", "EP", "EQ", "EV", "EW", "EX", "EY", "EZ",
    "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH", "FI", "FJ", "FK", "FL", "FM", "FN", "FO", "FP", "FQ", "FR", "FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ",
})

# --- ES (Español) ---
CONFUSING_IDS_ES: frozenset[str] = frozenset({
    # Provincias España (52)
    "AL", "AV", "BA", "BU", "CA", "CO", "CR", "CU", "GE", "GR",
    "GU", "HU", "JA", "LE", "LO", "LU", "MA", "MU", "NA", "OR",
    "OU", "PA", "PM", "PO", "SA", "SE", "SG", "SO", "SS", "TA",
    "TE", "TO", "VA", "VI", "ZA", "CE", "ME", "ML",
    # Comunidades
    "AN", "AR", "AS", "CB", "CL", "CM", "CT", "EX", "GA", "IB",
    "MC", "MD", "NC", "PV", "RI", "VC",
    # Países Latinoamérica
    "AR", "MX", "CO", "CL", "PE", "VE", "EC", "GT", "CU", "BO",
    "DO", "HN", "PY", "SV", "NI", "CR", "PA", "UY", "PR",
    # Documentos / Gobierno
    "DNI", "NIF", "CIF", "NIE", "SS", "IVA", "BOE",
    "REN", "DGT", "INE",
    # Bancos España
    "BB", "BS", "CA", "SA", "BK", "IN", "KO", "SG", "UN",
    # Unidades
    "KG", "KM", "ML", "LT", "MT", "CM", "MM", "HA", "M2", "M3",
    # Tech / Internet
    "OK", "ID", "API", "URL", "PDF", "JPG", "PNG", "MP3", "MP4", "ZIP",
    "RAR", "EXE", "TXT", "DOC", "XLS", "PPT", "CSV", "XML",
    "CSS", "JS", "PHP", "SQL", "VPN", "DNS", "IP", "PC", "TV", "HD",
    "SSD", "USB", "RAM", "CPU", "GPU", "LED", "LCD", "BT",
    # Moneda / Países
    "ES", "AR", "MX", "CO", "CL", "PE", "VE", "EU", "US", "UK",
    "EUR", "USD", "GBP", "MXN", "ARS", "CLP", "COP", "PEN",
    # Salud
    "HIV", "HPV", "DNA", "RNA", "PCR", "SNS", "INS", "SAL",
    # Educación
    "UN", "UA", "UB", "UC", "UM", "UP", "UV",
    # Otros
    "RE", "NA", "DA", "DE", "DO", "NO", "AO", "EM", "OU", "SE",
    "EU", "VO", "TE", "LO", "LA", "LE", "LI", "LU", "AS", "OS",
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT",
    "NOV", "DIC", "LUN", "MIE", "JUE", "VIE", "SAB", "DOM",
    # Partidos / Política ES
    "PS", "PP", "UP", "VO", "CS", "ER", "PN",
    # Empresas ES
    "BB", "BS", "IB", "TE", "RE", "EN", "ED",
    # Más siglas
    "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK", "AN", "AO", "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
    "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BQ", "BS", "BV", "BW", "BX", "BY", "BZ",
    "CC", "CD", "CE", "CF", "CG", "CI", "CK", "CL", "CN", "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ",
    "DC", "DD", "DG", "DI", "DK", "DL", "DM", "DN", "DP", "DQ", "DR", "DS", "DT", "DU", "DV", "DW", "DX", "DY", "DZ",
    "EA", "EB", "EC", "ED", "EE", "EF", "EG", "EH", "EI", "EK", "EL", "EP", "EQ", "EV", "EW", "EX", "EY", "EZ",
    "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH", "FI", "FJ", "FK", "FL", "FM", "FN", "FO", "FP", "FQ", "FR", "FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ",
})

# Mapa locale -> set
CONFUSING_BY_LOCALE: dict[str, frozenset[str]] = {
    "pt-BR": CONFUSING_IDS_PT_BR,
    "pt-PT": CONFUSING_IDS_PT_PT,
    "pt": CONFUSING_IDS_PT_BR,  # fallback pt -> pt-BR
    "en": CONFUSING_IDS_EN,
    "es": CONFUSING_IDS_ES,
}


def is_confusing(id_candidate: str, locale: str = "pt-BR") -> bool:
    """True se o ID pode confundir o utilizador no locale dado."""
    s = CONFUSING_BY_LOCALE.get(locale) or CONFUSING_IDS_PT_BR
    return (id_candidate or "").strip().upper() in s
