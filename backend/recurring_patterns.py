"""
~500 padrões de eventos tipicamente recorrentes em pt-PT, pt-BR, es e en.
Usado para detectar quando pedir automaticamente a recorrência ao utilizador.
"""

# Cada item é uma string normalizada (lowercase, sem acentos) para match como substring.
# Um conceito pode ter várias variantes nos 4 idiomas.
RECURRING_PATTERNS: frozenset[str] = frozenset({
    # Medicamentos / remédios (40)
    "remedio", "remédio", "medicamento", "medicina", "medicine", "medication",
    "medicación", "medicacion", "tomar remédio", "tomar remedio", "tomar medicamento",
    "tomar medicina", "take medicine", "take medication", "tomar medicación",
    "tomar medicacion", "pill", "pílula", "pilula", "pastilla", "tablet",
    "comprimido", "cápsula", "capsula", "capsule", "dose", "dosagem",
    "pressão", "pressao", "presión", "blood pressure", "hipertensão",
    "hipertensão", "hypertension", "insulina", "insulin", "vitamina",
    "vitamin", "suplemento", "supplement", "supplement",
    # Água e hidratação (20)
    "água", "agua", "water", "beber água", "beber agua", "drink water",
    "beber água", "hidratação", "hidratacao", "hydration", "hidratarse",
    "copo de água", "glass of water", "vaso de agua",
    # Refeições (60)
    "almoço", "almoco", "lunch", "almuerzo", "jantar", "dinner", "cena",
    "supper", "pequeno-almoço", "pequeno almoco", "breakfast", "desayuno",
    "café da manhã", "cafe da manha", "café", "cafe", "coffee", "café",
    "lanche", "snack", "merienda", "refeição", "refeicao", "meal",
    "comida", "food", "alimentação", "alimentacao", "nutrition",
    "alimentación", "alimentacion", "dieta", "diet", "comer",
    "eat", "comer", "lunch", "breakfast", "dinner", "almuerzo",
    "desayuno", "cena", "merienda", "comida",
    # Exercício e fitness (50)
    "exercício", "exercicio", "exercise", "ejercicio", "academia",
    "gym", "ginásio", "ginasio", "corrida", "run", "running",
    "caminhada", "walk", "caminata", "yoga", "pilates", "alongamento",
    "stretch", "estiramiento", "musculação", "musculacao", "muscle",
    "treino", "treino", "workout", "entrenamiento", "fitness",
    "natação", "natacao", "swim", "nadar", "cycling", "ciclismo",
    "bike", "bicicleta", "caminhar", "andar", "correr",
    # Sono e descanso (25)
    "dormir", "sleep", "descansar", "rest", "descanso",
    "acordar", "wake", "despertar", "levantar", "get up",
    "soneca", "nap", "siesta", "sono", "sleep", "sueño",
    "horário", "horario", "schedule", "rutina", "routine",
    # Higiene pessoal (30)
    "banho", "bath", "ducha", "shower", "higiene", "hygiene",
    "escovar dentes", "brush teeth", "cepillar dientes", "lavar rosto",
    "wash face", "lavar cara", "creme", "cream", "crema",
    "skincare", "cuidados pele", "skin care",
    # Casa e limpeza (35)
    "limpeza", "cleaning", "limpieza", "lavar roupa", "wash clothes",
    "laundry", "lavandería", "lavanderia", "louça", "louca", "dishes",
    "platos", "aspirar", "vacuum", "aspirar", "varrer", "sweep",
    "arrumar", "tidy", "ordenar", "organizar", "organize",
    # Trabalho e produtividade (40)
    "reunião", "reuniao", "meeting", "reunión", "reunion",
    "standup", "daily", "diário", "diario", "daily",
    "relatório", "relatorio", "report", "informe", "check",
    "review", "revisar", "revisão", "revisao", "backup",
    "sync", "sincronizar", "email", "e-mail", "correio",
    # Pets (25)
    "animal", "pet", "cão", "cao", "dog", "perro",
    "gato", "cat", "comida do gato", "cat food", "comida do cão",
    "dog food", "passear", "walk dog", "pasear", "veterinário",
    "veterinario", "vet", "vacina", "vaccine", "vacuna",
    # Plantas e jardim (20)
    "plantas", "plants", "plantas", "regar", "water plants",
    "regar plantas", "jardim", "garden", "jardín", "jardin",
    "fertilizar", "fertilize", "abono",
    # Finanças (35)
    "pagar conta", "pay bill", "pagar cuenta", "pix", "transferência",
    "transferencia", "transfer", "investimento", "investment",
    "poupança", "poupanca", "savings", "ahorro", "extrato",
    "statement", "extracto", "imposto", "tax", "impuesto",
    "fatura", "invoice", "factura", "boleto", "rent", "aluguel",
    # Crianças e família (30)
    "creche", "nursery", "guardería", "guarderia", "escola",
    "school", "escuela", "buscar criança", "pick up child",
    "levar criança", "drop off", "actividade", "activity",
    "dever", "homework", "tarea", "dever de casa",
    # Saúde e médico (45)
    "consulta", "appointment", "cita", "médico", "medico",
    "doctor", "dentista", "dentist", "fisioterapia", "physiotherapy",
    "fisioterapia", "fisio", "analise", "analysis", "análise",
    "exame", "exam", "examen", "check-up", "checkup",
    "peso", "weight", "peso", "pressão arterial", "blood pressure",
    "glicemia", "blood sugar", "diabetes", "medicação",
    # Transporte (20)
    "ônibus", "onibus", "bus", "autobús", "metro", "subway",
    "metrô", "carro", "car", "coche", "combustível",
    "fuel", "gasolina", "gasoline", "gas", "estacionar",
    # Compras e supermercado (25)
    "supermercado", "supermarket", "supermercado", "compras",
    "shopping", "compras", "mercado", "market", "mercado",
    "lista de compras", "shopping list", "lista compras",
    # Leitura e estudo (25)
    "leitura", "reading", "lectura", "ler", "read", "leer",
    "estudar", "study", "estudiar", "curso", "course",
    "aula", "class", "clase", "formação", "formacao",
    "training", "formación", "formacion",
    # Outros recorrentes (60)
    "respirar", "breathe", "respirar", "meditação", "meditacao",
    "meditation", "meditación", "meditacion", "journal", "diário",
    "diario", "gratidão", "gratidao", "gratitude", "gratitud",
    "contraceptive", "anticoncepcional", "anticonceptivo",
    "lente", "lens", "lentilla", "colírio", "colirio", "eye drops",
    "inhalador", "inhaler", "bomba", "pump", "oxímetro",
    "oximeter", "termómetro", "thermometer", "tensão",
    "tension", "colesterol", "cholesterol", "thyroid", "tireoide",
    "filtro", "filter", "maintenance", "manutenção", "manutencao",
    "renovação", "renovacao", "renewal", "renovación",
    # Mais: pt-PT, pt-BR, es, en (até ~500)
    "despertador", "alarm", "alarma", "acordar", "wake up",
    "levantar", "get up", "levantarse", "pequeno-almoço",
    "pequeno almoco", "morning routine", "rutina matinal",
    "tomar banho", "take a shower", "duchar", "banho",
    "lavar dentes", "escovar os dentes", "cepillarse",
    "lavar a louça", "lavar louca", "wash dishes", "lavar platos",
    "tirar o lixo", "take out trash", "sacar basura",
    "contar calorias", "count calories", "contar calorias",
    "pesar-se", "weigh", "pesarse", "medir peso",
    "tomar sol", "sun exposure", "tomar sol", "vitamina d",
    "protector solar", "sunscreen", "protetor solar",
    "hidratante", "moisturizer", "crema hidratante",
    "passar fio dental", "floss", "usar hilo dental",
    "enxaguante bucal", "mouthwash", "enjuague bucal",
    "colírio", "colirio", "gotas", "drops", "gotas oculares",
    "insulina", "aplicar insulina", "insulin shot",
    "medir glicose", "measure blood sugar", "medir glucosa",
    "tensão arterial", "blood pressure", "presión arterial",
    "oxímetro", "oximeter", "saturómetro", "pulsioxímetro",
    "inalação", "inhalation", "inhalador", "bombinha",
    "soro fisiológico", "saline", "suero fisiológico",
    "seringa", "syringe", "jeringa", "aplicar medicamento",
    "tomar comprimido", "take pill", "tomar pastilla",
    "jejum", "fasting", "ayuno", "jejum intermitente",
    "proteína", "protein", "proteina", "shake", "batido",
    "smoothie", "sumo", "juice", "zumo", "suco verde",
    "chá", "cha", "tea", "té", "te", "infusão", "infusion",
    "café", "coffee", "taza", "xícara", "xicara", "cup",
    "lactação", "lactation", "lactancia", "bombear leite",
    "pump milk", "ordenha", "extrair leite",
    "fralda", "diaper", "pañal", "trocar fralda",
    "dar de mamar", "breastfeed", "dar pecho", "amamentar",
    "biberon", "biberón", "bottle", "mamadeira",
    "sesta", "nap", "siesta", "soneca", "descanso",
    "desligar ecrã", "screen off", "apagar pantalla",
    "meditação", "meditacion", "mindfulness", "respirar fundo",
    "diário de gratidão", "gratitude journal", "diario gratitud",
    "afirmacoes", "affirmations", "afirmaciones",
    "visualização", "visualization", "visualización",
    "alongar", "stretch", "estiramiento", "aquecimento",
    "warm up", "calentamiento", "arrefecimento", "cool down",
    "treino de força", "strength training", "entrenamiento fuerza",
    "cardio", "cardiovascular", "aeróbico", "aerobico",
    "passadeira", "treadmill", "cinta correr", "esteira",
    "elíptica", "elliptical", "bicicleta estática",
    "pesos", "weights", "pesas", "halteres", "dumbbells",
    "proteína pós-treino", "post workout", "proteína después",
    "descanso activo", "active recovery", "descanso activo",
    "dia de pernas", "leg day", "día piernas", "día de piernas",
    "dia de braços", "arm day", "día brazos",
    "abdominais", "abs", "abdominales", "core", "núcleo",
    "reporteria", "reporting", "informes", "status update",
    "timesheet", "registo horas", "registro horas", "hora entrada",
    "hora saída", "clock in", "clock out", "entrada", "salida",
    "reunião equipa", "team meeting", "reunión equipo",
    "one-on-one", "1:1", "one to one", "reunião individual",
    "retrospetiva", "retrospective", "retrospectiva",
    "planning", "planificação", "planejamento", "planificación",
    "sprint", "semanas", "iteração", "iteracion",
})

# Padrões para detectar pedido de lembrete SEM tempo (natural language ou /lembrete)
_REMINDER_REQUEST_PREFIXES = (
    "/lembrete ", "/lembrete\t",  # /lembrete X (sem data/hora)
    "lembrar de", "lembrete de", "me lembre", "me lembre de", "quero lembrar",
    "quero lembrar de", "preciso lembrar", "preciso lembrar de",
    "lembra-me", "lembra me", "recordar", "recordarme", "recordar de",
    "recordarme de", "quiero recordar", "recuérdame", "recuerdame",
    "remind me", "remind me to", "i need to remember", "remember to",
    "don't forget", "dont forget", "no olvides", "no olvides de",
    "não esqueça", "nao esqueca", "não esqueças", "lembre-me",
)

# Prefixos soltos que, combinados com termo recorrente no resto, indicam pedido de lembrete
_SOFT_REMINDER_PREFIXES = (
    "quero ", "preciso ", "gostaria de ", "lembra ", "me lembra ",
    "quiero ", "necesito ", "i want ", "i need ", "remind me ",
)

# Termos que NUNCA indicam lembrete quando sozinhos após prefixo (são lista/compras)
_SOFT_EXCLUDE_REST = frozenset({
    "mercado", "compras", "lista", "pendentes", "supermercado",
    "market", "shopping", "list", "pending",
})


def _normalize(t: str) -> str:
    """Lowercase, remove acentos."""
    if not t:
        return ""
    import unicodedata
    s = (t or "").lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def is_in_recurring_list(message: str) -> bool:
    """True se a mensagem contém algum padrão recorrente conhecido."""
    norm_msg = _normalize(message or "")
    if len(norm_msg) < 3:
        return False
    return any(_normalize(p) in norm_msg for p in RECURRING_PATTERNS)


def looks_like_reminder_without_time(content: str) -> tuple[bool, str | None]:
    """
    True se parece pedido de lembrete sem data/hora especificada.
    Retorna (bool, message_extract) onde message_extract é o texto do lembrete.
    """
    import re
    t = (content or "").strip()
    if not t or len(t) > 500:
        return False, None
    tl = t.lower()
    # Tempo explícito? (evitar falsos positivos)
    time_patterns = [
        r"\d{1,2}\s*h", r"\d{1,2}:\d{2}", r"amanhã", r"amanha", r"tomorrow",
        r"amanha", r"mañana", r"manana", r"hoje", r"today", r"hoy",
        r"daqui a", r"em \d+", r"em \d+ (min|hora|dia)", r"todo dia",
        r"diariamente", r"a cada", r"segunda", r"terça", r"segunda-feira",
        r"\d{1,2}\s*(de|/)\s*(janeiro|fevereiro|março|julho|etc)",
    ]
    for pat in time_patterns:
        if re.search(pat, tl, re.I):
            return False, None
    for prefix in _REMINDER_REQUEST_PREFIXES:
        if t.strip().lower().startswith(prefix.strip().lower()):
            rest = t[len(prefix):].strip()
            rest = re.sub(r"^(que|of|to|de)\s+", "", rest, flags=re.I).strip()
            if rest and len(rest) >= 3:
                return True, rest
        # Também "quero que me lembres de X"
        if prefix in tl and len(tl) > len(prefix) + 5:
            idx = tl.find(prefix)
            rest = t[idx + len(prefix):].strip()
            rest = re.sub(r"^(que|of|to|de)\s+", "", rest, flags=re.I).strip()
            if rest and len(rest) >= 3:
                return True, rest

    # "Quero beber agua", "Preciso tomar remédio" — prefixo solto + termo recorrente
    for prefix in _SOFT_REMINDER_PREFIXES:
        if tl.startswith(prefix) and len(t) > len(prefix) + 2:
            rest = t[len(prefix):].strip()
            rest = re.sub(r"^(que|of|to|de)\s+", "", rest, flags=re.I).strip()
            # Excluir: "preciso mercado", "quero compras" = lista, não lembrete
            if rest and rest.lower() in _SOFT_EXCLUDE_REST:
                return False, None
            if rest and len(rest) >= 3 and is_in_recurring_list(rest):
                return True, rest
    return False, None
