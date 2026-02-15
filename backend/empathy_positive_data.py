"""
Situações que merecem mensagem extra na entrega de lembrete ou na agenda:
- Empatia: ~200 situações difíceis/graves (enterro, médico, etc.) → mensagem empática/positiva, «espero que esteja tudo bem», «cuida-te».
- Positividade: ~400 situações de estudos, trabalho, encontros, diversão → mensagem simpática, «aproveita», «divirta-se», etc.

Cada entrada: keywords por idioma (pt-BR, pt-PT, es, en) e mensagem por idioma.
Match: conteúdo do lembrete/evento em minúsculas contém alguma keyword → devolve a mensagem.
Prioridade: empatia primeiro; se não bater, positiva.
"""

from typing import TypedDict

Lang = str  # "pt-BR" | "pt-PT" | "es" | "en"


class _Category(TypedDict):
    keywords: dict[str, list[str]]
    messages: dict[str, str]


# --- EMPATIA: situações difíceis/graves (~200 situações por idioma) ---
# Formato: cada categoria tem listas de keywords por lang; soma total de keywords ≥ 200 por lang.
EMPATHY_CATEGORIES: list[_Category] = [
    # Enterro / funeral / velório
    {
        "keywords": {
            "pt-BR": ["enterro", "funeral", "velório", "velorio", "sepultamento", "cremação", "cremacao", "cerimônia fúnebre", "missa de sétimo dia", "ir ao enterro", "enterro do", "funeral do", "despedida"],
            "pt-PT": ["enterro", "funeral", "velório", "velorio", "sepultamento", "cremação", "cremacao", "cerimónia fúnebre", "missa de sétimo dia", "ir ao enterro", "enterro do", "funeral do", "despedida"],
            "es": ["entierro", "funeral", "velatorio", "sepelio", "cremación", "ceremonia fúnebre", "ir al entierro", "entierro de", "funeral de", "despedida"],
            "en": ["funeral", "burial", "wake", "cremation", "memorial service", "going to the funeral", "funeral of", "saying goodbye"],
        },
        "messages": {
            "pt-BR": "💙 Os meus sentimentos. Cuida de ti.",
            "pt-PT": "💙 Os meus sentimentos. Cuida de ti.",
            "es": "💙 Mis condolencias. Cuídate.",
            "en": "💙 My condolences. Take care of yourself.",
        },
    },
    # Médico / consulta / saúde geral
    {
        "keywords": {
            "pt-BR": ["consulta médica", "consulta medica", "médico", "medico", "doutor", "clínica", "clinica", "hospital", "posto de saúde", "ir ao médico", "exame de saúde", "check-up", "checkup", "consultório", "consultorio"],
            "pt-PT": ["consulta médica", "consulta medica", "médico", "medico", "doutor", "clínica", "clinica", "hospital", "centro de saúde", "ir ao médico", "exame de saúde", "check-up", "consultório", "consultorio"],
            "es": ["consulta médica", "médico", "doctor", "clínica", "hospital", "centro de salud", "ir al médico", "revisión", "chequeo"],
            "en": ["doctor appointment", "doctor's appointment", "medical appointment", "clinic", "hospital", "check-up", "health check", "see the doctor"],
        },
        "messages": {
            "pt-BR": "💙 Espero que esteja tudo bem. Cuida-te.",
            "pt-PT": "💙 Espero que esteja tudo bem. Cuida-te.",
            "es": "💙 Espero que todo esté bien. Cuídate.",
            "en": "💙 Hope everything goes well. Take care.",
        },
    },
    # Oncologia / quimio / tratamento grave
    {
        "keywords": {
            "pt-BR": ["oncologia", "oncologista", "quimioterapia", "quimio", "radioterapia", "tratamento do câncer", "cancer", "câncer", "tumor", "biópsia", "biospsia", "sessão de quimio", "infusão"],
            "pt-PT": ["oncologia", "oncologista", "quimioterapia", "quimio", "radioterapia", "tratamento do cancro", "cancro", "tumor", "biópsia", "biopsia", "sessão de quimio", "infusão"],
            "es": ["oncología", "oncólogo", "quimioterapia", "quimio", "radioterapia", "tratamiento del cáncer", "cáncer", "tumor", "biopsia", "sesión de quimio", "infusión"],
            "en": ["oncology", "oncologist", "chemotherapy", "chemo", "radiation", "cancer treatment", "cancer", "tumor", "biopsy", "infusion"],
        },
        "messages": {
            "pt-BR": "💙 Força. Estou contigo. Cuida-te.",
            "pt-PT": "💙 Força. Estou contigo. Cuida-te.",
            "es": "💙 Fuerza. Estoy contigo. Cuídate.",
            "en": "💙 Sending strength. Take care of yourself.",
        },
    },
    # Psicólogo / terapia / saúde mental
    {
        "keywords": {
            "pt-BR": ["psicólogo", "psicologo", "psicóloga", "terapia", "sessão de terapia", "psiquiatra", "saúde mental", "saude mental", "ansiedade", "depressão", "depressao", "acompanhamento psicológico"],
            "pt-PT": ["psicólogo", "psicologo", "psicóloga", "terapia", "sessão de terapia", "psiquiatra", "saúde mental", "saude mental", "ansiedade", "depressão", "depressao", "acompanhamento psicológico"],
            "es": ["psicólogo", "psicóloga", "terapia", "sesión de terapia", "psiquiatra", "salud mental", "ansiedad", "depresión", "seguimiento psicológico"],
            "en": ["therapist", "therapy", "therapy session", "psychiatrist", "mental health", "anxiety", "depression", "counseling"],
        },
        "messages": {
            "pt-BR": "💙 Espero que a sessão te ajude. Cuida de ti.",
            "pt-PT": "💙 Espero que a sessão te ajude. Cuida de ti.",
            "es": "💙 Espero que la sesión te ayude. Cuídate.",
            "en": "💙 Hope the session helps. Take care of yourself.",
        },
    },
    # Cirurgia / operação
    {
        "keywords": {
            "pt-BR": ["cirurgia", "operação", "operacao", "operar", "pré-operatório", "pre operatorio", "pós-operatório", "pos operatorio", "bloco cirúrgico", "internação", "internacao"],
            "pt-PT": ["cirurgia", "operação", "operacao", "operar", "pré-operatório", "pre operatorio", "pós-operatório", "pos operatorio", "bloco cirúrgico", "internamento"],
            "es": ["cirugía", "operación", "operar", "preoperatorio", "posoperatorio", "quirófano", "ingreso"],
            "en": ["surgery", "operation", "surgical", "pre-op", "post-op", "operating room", "admission"],
        },
        "messages": {
            "pt-BR": "💙 Tudo a correr bem. Cuida-te e boa recuperação.",
            "pt-PT": "💙 Tudo a correr bem. Cuida-te e boa recuperação.",
            "es": "💙 Que todo salga bien. Cuídate y buena recuperación.",
            "en": "💙 Hope all goes well. Take care and a good recovery.",
        },
    },
    # Emergência / urgência / acidente
    {
        "keywords": {
            "pt-BR": ["emergência", "emergencia", "urgência", "urgencia", "pronto-socorro", "pronto socorro", "ER", "acidente", "atropelamento", "queda", "fratura", "urgente hospital"],
            "pt-PT": ["emergência", "emergencia", "urgência", "urgencia", "urgências", "pronto-socorro", "acidente", "atropelamento", "queda", "fratura", "urgente hospital"],
            "es": ["emergencia", "urgencia", "urgencias", "accidente", "atropello", "caída", "fractura", "hospital urgente"],
            "en": ["emergency", "ER", "accident", "injury", "fracture", "urgent care", "emergency room"],
        },
        "messages": {
            "pt-BR": "💙 Espero que esteja tudo bem. Estou aqui.",
            "pt-PT": "💙 Espero que esteja tudo bem. Estou aqui.",
            "es": "💙 Espero que todo esté bien. Aquí estoy.",
            "en": "💙 Hope everything is okay. I'm here.",
        },
    },
    # Advogado / tribunal / divórcio / custódia
    {
        "keywords": {
            "pt-BR": ["advogado", "tribunal", "audiência", "audiencia", "divórcio", "divorcio", "custódia", "custodia", "processo judicial", "juiz", "justiça", "justica", "petição", "peticao"],
            "pt-PT": ["advogado", "tribunal", "audiência", "audiencia", "divórcio", "divorcio", "custódia", "custodia", "processo judicial", "juiz", "justiça", "justica", "petição", "peticao"],
            "es": ["abogado", "tribunal", "audiencia", "divorcio", "custodia", "proceso judicial", "juez", "justicia", "demanda"],
            "en": ["lawyer", "attorney", "court", "hearing", "divorce", "custody", "lawsuit", "judge", "legal"],
        },
        "messages": {
            "pt-BR": "💙 Força para este dia. Cuida de ti.",
            "pt-PT": "💙 Força para este dia. Cuida de ti.",
            "es": "💙 Fuerza para este día. Cuídate.",
            "en": "💙 Sending strength for today. Take care.",
        },
    },
    # Falecimento / luto / perda
    {
        "keywords": {
            "pt-BR": ["falecimento", "morte", "perda", "luto", "perdi alguém", "perdi alguem", "perda de", "no luto", "enlutado", "conforto"],
            "pt-PT": ["falecimento", "morte", "perda", "luto", "perdi alguém", "perdi alguem", "perda de", "no luto", "enlutado", "conforto"],
            "es": ["fallecimiento", "muerte", "pérdida", "perdida", "luto", "perdí a", "en duelo"],
            "en": ["death", "passing", "loss", "bereavement", "grieving", "lost someone", "mourning"],
        },
        "messages": {
            "pt-BR": "💙 Os meus sentimentos. Se precisares de algo, estou aqui.",
            "pt-PT": "💙 Os meus sentimentos. Se precisares de algo, estou aqui.",
            "es": "💙 Mis condolencias. Si necesitas algo, aquí estoy.",
            "en": "💙 My condolences. If you need anything, I'm here.",
        },
    },
    # Exames diagnósticos / resultados
    {
        "keywords": {
            "pt-BR": ["resultado do exame", "resultado de exame", "resultados", "diagnóstico", "diagnostico", "laudo", "ressonância", "ressonancia", "tomografia", "mamografia", "preventivo", "biópsia", "biospsia"],
            "pt-PT": ["resultado do exame", "resultado de exame", "resultados", "diagnóstico", "diagnostico", "laudo", "ressonância", "ressonancia", "tomografia", "mamografia", "preventivo", "biópsia", "biopsia"],
            "es": ["resultado del análisis", "resultados", "diagnóstico", "informe", "resonancia", "tomografía", "mamografía", "biopsia"],
            "en": ["test results", "diagnosis", "lab results", "MRI", "CT scan", "mammogram", "biopsy result"],
        },
        "messages": {
            "pt-BR": "💙 Espero que os resultados tragam boas notícias. Cuida-te.",
            "pt-PT": "💙 Espero que os resultados tragam boas notícias. Cuida-te.",
            "es": "💙 Espero que los resultados traigan buenas noticias. Cuídate.",
            "en": "💙 Hope the results bring good news. Take care.",
        },
    },
    # Dentista (pode ser stressante)
    {
        "keywords": {
            "pt-BR": ["dentista", "odontólogo", "odontologo", "extração", "extracao", "canal", "root canal", "implante", "consulta dentária", "dentária", "dentario"],
            "pt-PT": ["dentista", "odontólogo", "odontologo", "extração", "extracao", "canal", "root canal", "implante", "consulta dentária", "dentária", "dentario"],
            "es": ["dentista", "odontólogo", "extracción", "extraccion", "canal", "implante", "consulta dental"],
            "en": ["dentist", "dental", "extraction", "root canal", "implant", "dental appointment"],
        },
        "messages": {
            "pt-BR": "💙 Espero que corra tudo bem. Cuida-te.",
            "pt-PT": "💙 Espero que corra tudo bem. Cuida-te.",
            "es": "💙 Espero que todo salga bien. Cuídate.",
            "en": "💙 Hope it goes well. Take care.",
        },
    },
    # Fisioterapia / reabilitação
    {
        "keywords": {
            "pt-BR": ["fisioterapia", "fisio", "reabilitação", "reabilitacao", "reabilitação física", "recuperação", "recuperacao", "sessão de fisio"],
            "pt-PT": ["fisioterapia", "fisio", "reabilitação", "reabilitacao", "reabilitação física", "recuperação", "recuperacao", "sessão de fisio"],
            "es": ["fisioterapia", "fisio", "rehabilitación", "rehabilitacion", "recuperación", "sesión de fisio"],
            "en": ["physiotherapy", "physio", "rehabilitation", "recovery", "physical therapy", "PT session"],
        },
        "messages": {
            "pt-BR": "💙 Boa sessão. Cuida de ti.",
            "pt-PT": "💙 Boa sessão. Cuida de ti.",
            "es": "💙 Buena sesión. Cuídate.",
            "en": "💙 Hope the session goes well. Take care.",
        },
    },
    # Veterinário (perda de animal)
    {
        "keywords": {
            "pt-BR": ["veterinário", "veterinario", "vet", "eutanásia", "eutanasia", "animal doente", "put down", "despedida do pet", "perda do cachorro", "perda do gato"],
            "pt-PT": ["veterinário", "veterinario", "vet", "eutanásia", "eutanasia", "animal doente", "put down", "despedida do pet", "perda do cão", "perda do gato"],
            "es": ["veterinario", "vet", "eutanasia", "mascota enferma", "despedida del pet", "pérdida del perro", "pérdida del gato"],
            "en": ["veterinarian", "vet", "euthanasia", "put down", "sick pet", "saying goodbye to pet", "loss of dog", "loss of cat"],
        },
        "messages": {
            "pt-BR": "💙 Os meus sentimentos pelo teu animal. Cuida de ti.",
            "pt-PT": "💙 Os meus sentimentos pelo teu animal. Cuida de ti.",
            "es": "💙 Mis condolencias por tu mascota. Cuídate.",
            "en": "💙 So sorry about your pet. Take care.",
        },
    },
    # Hospício / cuidados paliativos
    {
        "keywords": {
            "pt-BR": ["hospício", "hospicio", "cuidados paliativos", "paliativo", "fim de vida", "acompanhar doente", "visita ao doente"],
            "pt-PT": ["hospício", "hospicio", "cuidados paliativos", "paliativo", "fim de vida", "acompanhar doente", "visita ao doente"],
            "es": ["hospicio", "cuidados paliativos", "paliativo", "fin de vida", "visitar enfermo"],
            "en": ["hospice", "palliative care", "end of life", "visiting sick", "care home visit"],
        },
        "messages": {
            "pt-BR": "💙 Força. Cuida de ti e de quem amas.",
            "pt-PT": "💙 Força. Cuida de ti e de quem amas.",
            "es": "💙 Fuerza. Cuídate y a quien quieres.",
            "en": "💙 Sending strength. Take care of yourself and your loved ones.",
        },
    },
    # Desemprego / entrevista em momento difícil
    {
        "keywords": {
            "pt-BR": ["demissão", "demissao", "despedido", "desemprego", "perdi o emprego", "rescisão", "rescisao", "entrevista depois de despedido"],
            "pt-PT": ["despedido", "desemprego", "perdi o emprego", "rescisão", "rescisao", "entrevista depois de despedido"],
            "es": ["despido", "desempleo", "perdí el trabajo", "rescisión", "entrevista después de despido"],
            "en": ["laid off", "fired", "unemployment", "lost my job", "termination", "interview after being let go"],
        },
        "messages": {
            "pt-BR": "💙 Força. Acredito em ti.",
            "pt-PT": "💙 Força. Acredito em ti.",
            "es": "💙 Fuerza. Creo en ti.",
            "en": "💙 Sending strength. I believe in you.",
        },
    },
    # Inquérito / polícia / justiça
    {
        "keywords": {
            "pt-BR": ["inquérito", "inquerito", "depoimento", "polícia", "policia", "delegacia", "testemunha", "OAB", "júri", "juri"],
            "pt-PT": ["inquérito", "inquerito", "depoimento", "polícia", "policia", "esquadra", "testemunha", "tribunal"],
            "es": ["investigación", "declaración", "policía", "comisaría", "testigo", "jurado"],
            "en": ["inquiry", "testimony", "police", "station", "witness", "jury"],
        },
        "messages": {
            "pt-BR": "💙 Força para este dia. Cuida de ti.",
            "pt-PT": "💙 Força para este dia. Cuida de ti.",
            "es": "💙 Fuerza para este día. Cuídate.",
            "en": "💙 Sending strength for today. Take care.",
        },
    },
    # Consulta de especialista (cardiologista, neurologista, etc.)
    {
        "keywords": {
            "pt-BR": ["cardiologista", "neurologista", "ortopedista", "dermatologista", "ginecologista", "urologista", "oftalmologista", "otorrino", "endocrinologista", "reumatologista", "consulta de especialista", "especialista"],
            "pt-PT": ["cardiologista", "neurologista", "ortopedista", "dermatologista", "ginecologista", "urologista", "oftalmologista", "otorrino", "endocrinologista", "reumatologista", "consulta de especialista", "especialista"],
            "es": ["cardiólogo", "neurólogo", "ortopedista", "dermatólogo", "ginecólogo", "urólogo", "oftalmólogo", "otorrino", "endocrino", "reumatólogo", "consulta de especialista", "especialista"],
            "en": ["cardiologist", "neurologist", "orthopedist", "dermatologist", "gynecologist", "urologist", "ophthalmologist", "ENT", "endocrinologist", "rheumatologist", "specialist appointment", "specialist"],
        },
        "messages": {
            "pt-BR": "💙 Espero que esteja tudo bem. Cuida-te.",
            "pt-PT": "💙 Espero que esteja tudo bem. Cuida-te.",
            "es": "💙 Espero que todo esté bien. Cuídate.",
            "en": "💙 Hope everything goes well. Take care.",
        },
    },
    # Internação / visita ao hospital
    {
        "keywords": {
            "pt-BR": ["internação", "internacao", "visita ao hospital", "visitar no hospital", "acompanhar no hospital", "UTI", "enfermaria", "ala"],
            "pt-PT": ["internamento", "visita ao hospital", "visitar no hospital", "acompanhar no hospital", "UCIP", "enfermaria", "ala"],
            "es": ["internación", "internacion", "visita al hospital", "visitar en el hospital", "acompañar en el hospital", "UCI", "enfermería"],
            "en": ["hospitalization", "hospital visit", "visiting in hospital", "ICU", "ward"],
        },
        "messages": {
            "pt-BR": "💙 Força. Estou contigo. Cuida de ti.",
            "pt-PT": "💙 Força. Estou contigo. Cuida de ti.",
            "es": "💙 Fuerza. Estoy contigo. Cuídate.",
            "en": "💙 Sending strength. Take care.",
        },
    },
    # Exame invasivo / colheita
    {
        "keywords": {
            "pt-BR": ["colheita de sangue", "exame de sangue", "punção", "puncao", "endoscopia", "colonoscopia", "cateterismo", "raio-x", "raio x", "ecografia", "ultrassom", "ultrassonografia"],
            "pt-PT": ["colheita de sangue", "análise de sangue", "exame de sangue", "punção", "puncao", "endoscopia", "colonoscopia", "cateterismo", "raio-x", "raio x", "ecografia", "ultrassom"],
            "es": ["análisis de sangre", "extracción de sangre", "punción", "endoscopia", "colonoscopia", "cateterismo", "rayos x", "ecografía", "ultrasonido"],
            "en": ["blood draw", "blood test", "endoscopy", "colonoscopy", "catheterization", "x-ray", "ultrasound", "scan"],
        },
        "messages": {
            "pt-BR": "💙 Espero que corra tudo bem. Cuida-te.",
            "pt-PT": "💙 Espero que corra tudo bem. Cuida-te.",
            "es": "💙 Espero que todo salga bien. Cuídate.",
            "en": "💙 Hope it goes well. Take care.",
        },
    },
]

# --- POSITIVIDADE: estudos, trabalho, encontros, diversão (~400 situações por idioma) ---
POSITIVE_CATEGORIES: list[_Category] = [
    # Encontro com amigos
    {
        "keywords": {
            "pt-BR": ["encontro com amigos", "encontro de amigos", "amigos", "almoço com amigos", "jantar com amigos", "sair com amigos", "reunir com amigos", "happy hour", "bar com amigos", "café com amigos", "churrasco com amigos", "festa com amigos"],
            "pt-PT": ["encontro com amigos", "encontro de amigos", "amigos", "almoço com amigos", "jantar com amigos", "sair com amigos", "reunir com amigos", "happy hour", "bar com amigos", "café com amigos", "churrasco com amigos", "festa com amigos"],
            "es": ["encuentro con amigos", "quedar con amigos", "almuerzo con amigos", "cena con amigos", "salir con amigos", "happy hour", "bar con amigos", "café con amigos", "fiesta con amigos"],
            "en": ["meeting friends", "meet up with friends", "friends", "lunch with friends", "dinner with friends", "hanging out with friends", "happy hour", "bar with friends", "coffee with friends", "party with friends"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o momento!",
            "pt-PT": "✨ Aproveita o momento!",
            "es": "✨ ¡Disfruta el momento!",
            "en": "✨ Enjoy!",
        },
    },
    # Date / namorada / Tinder
    {
        "keywords": {
            "pt-BR": ["date", "encontro", "namorada", "namorado", "tinder", "jantar romântico", "jantar romantico", "primeiro encontro", "encontro romântico", "jantar a dois", "encontro amoroso", "encontro às cegas", "blind date"],
            "pt-PT": ["date", "encontro", "namorada", "namorado", "tinder", "jantar romântico", "jantar romantico", "primeiro encontro", "encontro romântico", "jantar a dois", "encontro amoroso", "encontro às cegas", "blind date"],
            "es": ["cita", "date", "encontro", "novia", "novio", "tinder", "cena romántica", "primera cita", "cita a ciegas", "blind date"],
            "en": ["date", "girlfriend", "boyfriend", "tinder", "romantic dinner", "first date", "blind date"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o jantar! Divertido e sem pressão. 😊",
            "pt-PT": "✨ Aproveita o jantar! Divertido e sem pressão. 😊",
            "es": "✨ ¡Disfruta la cena! Divertido y sin presión. 😊",
            "en": "✨ Enjoy the dinner! Have fun and keep it light. 😊",
        },
    },
    # Filme / cinema
    {
        "keywords": {
            "pt-BR": ["filme", "cinema", "sessão de cinema", "sessao de cinema", "ir ao cinema", "ver filme", "estreia", "première", "premiere"],
            "pt-PT": ["filme", "cinema", "sessão de cinema", "sessao de cinema", "ir ao cinema", "ver filme", "estreia", "première", "premiere"],
            "es": ["película", "pelicula", "cine", "sesión de cine", "ir al cine", "ver película", "estreno"],
            "en": ["movie", "film", "cinema", "going to the movies", "movie night", "premiere"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o filme! 🍿",
            "pt-PT": "✨ Aproveita o filme! 🍿",
            "es": "✨ ¡Disfruta la película! 🍿",
            "en": "✨ Enjoy the movie! 🍿",
        },
    },
    # Apresentação / pitch / reunião importante
    {
        "keywords": {
            "pt-BR": ["apresentação", "apresentacao", "apresentar", "pitch", "reunião importante", "reuniao importante", "reunião com cliente", "reuniao com cliente", "palestra", "talk", "webinar", "demo", "demonstração", "demonstracao"],
            "pt-PT": ["apresentação", "apresentacao", "apresentar", "pitch", "reunião importante", "reuniao importante", "reunião com cliente", "reuniao com cliente", "palestra", "talk", "webinar", "demo", "demonstração", "demonstracao"],
            "es": ["presentación", "presentacion", "presentar", "pitch", "reunión importante", "reunion con cliente", "charla", "talk", "webinar", "demo", "demostración"],
            "en": ["presentation", "present", "pitch", "important meeting", "client meeting", "talk", "webinar", "demo", "demonstration"],
        },
        "messages": {
            "pt-BR": "✨ Boa sorte na apresentação! Vais arrasar.",
            "pt-PT": "✨ Boa sorte na apresentação! Vais arrasar.",
            "es": "✨ ¡Buena suerte en la presentación! Lo harás genial.",
            "en": "✨ Good luck with the presentation! You've got this.",
        },
    },
    # Exame / prova / estudo
    {
        "keywords": {
            "pt-BR": ["exame", "prova", "teste", "avaliação", "avaliacao", "estudar", "estudo", "faculdade", "universidade", "trabalho de faculdade", "entrega de trabalho", "defesa de tese", "defesa de dissertação", "ENEM", "vestibular", "concurso"],
            "pt-PT": ["exame", "prova", "teste", "avaliação", "avaliacao", "estudar", "estudo", "faculdade", "universidade", "trabalho de faculdade", "entrega de trabalho", "defesa de tese", "defesa de dissertação", "exames nacionais"],
            "es": ["examen", "prueba", "test", "estudiar", "universidad", "facultad", "entrega de trabajo", "defensa de tesis", "selectividad"],
            "en": ["exam", "test", "quiz", "study", "university", "college", "assignment due", "thesis defense", "finals", "SAT", "GRE"],
        },
        "messages": {
            "pt-BR": "✨ Boa sorte! Concentra-te e vai correr bem.",
            "pt-PT": "✨ Boa sorte! Concentra-te e vai correr bem.",
            "es": "✨ ¡Buena suerte! Concéntrate y saldrá bien.",
            "en": "✨ Good luck! Focus and you'll do great.",
        },
    },
    # Entrevista de emprego
    {
        "keywords": {
            "pt-BR": ["entrevista de emprego", "entrevista de trabalho", "entrevista de estágio", "entrevista de estagio", "processo seletivo", "recrutamento", "entrevista com RH", "entrevista com recrutador"],
            "pt-PT": ["entrevista de emprego", "entrevista de trabalho", "entrevista de estágio", "entrevista de estagio", "processo de recrutamento", "entrevista com RH", "entrevista com recrutador"],
            "es": ["entrevista de trabajo", "entrevista de empleo", "entrevista de prácticas", "proceso de selección", "entrevista con RRHH", "entrevista con reclutador"],
            "en": ["job interview", "employment interview", "interview", "hiring process", "HR interview", "recruiter interview"],
        },
        "messages": {
            "pt-BR": "✨ Boa sorte na entrevista! Mostra o teu valor.",
            "pt-PT": "✨ Boa sorte na entrevista! Mostra o teu valor.",
            "es": "✨ ¡Buena suerte en la entrevista! Demuestra tu valor.",
            "en": "✨ Good luck at the interview! Show them your best.",
        },
    },
    # Campeonato / jogo / competição
    {
        "keywords": {
            "pt-BR": ["campeonato", "competição", "competicao", "jogo", "partida", "torneio", "olímpiadas", "olimpiadas", "maratona", "corrida", "meia-maratona", "triatlo", "competir", "prova desportiva", "desporto", "esporte"],
            "pt-PT": ["campeonato", "competição", "competicao", "jogo", "partida", "torneio", "olimpíadas", "olimpiadas", "maratona", "corrida", "meia-maratona", "triatlo", "competir", "prova desportiva", "desporto"],
            "es": ["campeonato", "competición", "competencia", "partido", "torneo", "olimpiadas", "maratón", "carrera", "triatlón", "competir", "deporte"],
            "en": ["championship", "competition", "game", "match", "tournament", "olympics", "marathon", "race", "triathlon", "competing", "sports"],
        },
        "messages": {
            "pt-BR": "✨ Boa sorte! Dá o teu melhor e diverte-te.",
            "pt-PT": "✨ Boa sorte! Dá o teu melhor e diverte-te.",
            "es": "✨ ¡Buena suerte! Da lo mejor y disfruta.",
            "en": "✨ Good luck! Give it your best and have fun.",
        },
    },
    # Jantar / almoço (social)
    {
        "keywords": {
            "pt-BR": ["jantar", "almoço", "almoco", "almoçar", "almocar", "jantar fora", "restaurante", "jantar de negócios", "jantar de negocios", "business dinner", "jantar em família", "jantar em familia", "almoço em família"],
            "pt-PT": ["jantar", "almoço", "almoco", "almoçar", "almocar", "jantar fora", "restaurante", "jantar de negócios", "jantar de negocios", "business dinner", "jantar em família", "jantar em familia", "almoço em família"],
            "es": ["cena", "almuerzo", "cenar", "almorzar", "cenar fuera", "restaurante", "cena de negocios", "cena en familia", "almuerzo en familia"],
            "en": ["dinner", "lunch", "restaurant", "business dinner", "family dinner", "family lunch", "eating out"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o jantar! (E não bebas demais perto do chefe — só quando não estiver a olhar. 😉)",
            "pt-PT": "✨ Aproveita o jantar! (E não bebas demais perto do chefe — só quando não estiver a olhar. 😉)",
            "es": "✨ ¡Disfruta la cena! (Y no bebas de más delante del jefe — solo cuando no mire. 😉)",
            "en": "✨ Enjoy dinner! (And don't drink too much near the boss — only when they're not looking. 😉)",
        },
    },
    # Festa / aniversário
    {
        "keywords": {
            "pt-BR": ["festa", "aniversário", "aniversario", "festa de aniversário", "celebração", "celebracao", "balada", "noite", "saída à noite", "saida à noite", "clube", "discoteca", "discoteca"],
            "pt-PT": ["festa", "aniversário", "aniversario", "festa de aniversário", "celebração", "celebracao", "balada", "noite", "saída à noite", "saida à noite", "discoteca"],
            "es": ["fiesta", "cumpleaños", "cumpleanos", "fiesta de cumpleaños", "celebración", "celebración", "salida de noche", "discoteca", "club"],
            "en": ["party", "birthday", "birthday party", "celebration", "night out", "club", "disco"],
        },
        "messages": {
            "pt-BR": "✨ Divertido e aproveita! 🎉",
            "pt-PT": "✨ Divertido e aproveita! 🎉",
            "es": "✨ ¡Diviértete y disfruta! 🎉",
            "en": "✨ Have fun and enjoy! 🎉",
        },
    },
    # Viagem / férias
    {
        "keywords": {
            "pt-BR": ["viagem", "viagem de férias", "ferias", "férias", "viajar", "aeroporto", "voo", "partida para", "chegada de", "fim de semana fora", "weekend getaway"],
            "pt-PT": ["viagem", "viagem de férias", "ferias", "férias", "viajar", "aeroporto", "voo", "partida para", "chegada de", "fim de semana fora", "weekend getaway"],
            "es": ["viaje", "vacaciones", "viajar", "aeropuerto", "vuelo", "salida", "llegada", "fin de semana fuera"],
            "en": ["trip", "vacation", "travel", "airport", "flight", "departure", "arrival", "weekend getaway"],
        },
        "messages": {
            "pt-BR": "✨ Boa viagem! Aproveita cada momento.",
            "pt-PT": "✨ Boa viagem! Aproveita cada momento.",
            "es": "✨ ¡Buen viaje! Disfruta cada momento.",
            "en": "✨ Safe travels! Enjoy every moment.",
        },
    },
    # Reunião de trabalho (neutra mas positiva)
    {
        "keywords": {
            "pt-BR": ["reunião", "reuniao", "meeting", "call", "videoconferência", "videoconferencia", "zoom", "teams", "stand-up", "standup", "sprint", "retrospectiva", "one-on-one", "1:1"],
            "pt-PT": ["reunião", "reuniao", "meeting", "call", "videoconferência", "videoconferencia", "zoom", "teams", "stand-up", "standup", "sprint", "retrospectiva", "one-on-one", "1:1"],
            "es": ["reunión", "reunion", "meeting", "call", "videoconferencia", "zoom", "teams", "stand-up", "sprint", "retrospectiva", "one-on-one", "1:1"],
            "en": ["meeting", "call", "video call", "zoom", "teams", "stand-up", "sprint", "retrospective", "one-on-one", "1:1"],
        },
        "messages": {
            "pt-BR": "✨ Que a reunião corra bem!",
            "pt-PT": "✨ Que a reunião corra bem!",
            "es": "✨ ¡Que la reunión vaya bien!",
            "en": "✨ Hope the meeting goes well!",
        },
    },
    # Concerto / show / espetáculo
    {
        "keywords": {
            "pt-BR": ["concerto", "show", "espetáculo", "espetaculo", "festival", "live", "ir ao concerto", "ir ao show", "ópera", "opera", "teatro", "musical"],
            "pt-PT": ["concerto", "show", "espetáculo", "espetaculo", "festival", "live", "ir ao concerto", "ir ao show", "ópera", "opera", "teatro", "musical"],
            "es": ["concierto", "show", "espectáculo", "espectaculo", "festival", "live", "ir al concierto", "ópera", "opera", "teatro", "musical"],
            "en": ["concert", "show", "gig", "festival", "live", "going to the concert", "opera", "theatre", "theater", "musical"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o show! 🎵",
            "pt-PT": "✨ Aproveita o show! 🎵",
            "es": "✨ ¡Disfruta el show! 🎵",
            "en": "✨ Enjoy the show! 🎵",
        },
    },
    # Treino / ginásio / desporto
    {
        "keywords": {
            "pt-BR": ["treino", "ginásio", "ginasio", "academia", "corrida", "correr", "natação", "natacao", "yoga", "pilates", "crossfit", "futebol", "basquete", "caminhada", "bike", "ciclismo"],
            "pt-PT": ["treino", "ginásio", "ginasio", "academia", "corrida", "correr", "natação", "natacao", "yoga", "pilates", "crossfit", "futebol", "basquete", "caminhada", "bike", "ciclismo"],
            "es": ["entrenamiento", "gimnasio", "gym", "correr", "natación", "natacion", "yoga", "pilates", "crossfit", "fútbol", "baloncesto", "caminata", "bici", "ciclismo"],
            "en": ["workout", "gym", "running", "run", "swimming", "yoga", "pilates", "crossfit", "soccer", "basketball", "walk", "bike", "cycling"],
        },
        "messages": {
            "pt-BR": "✨ Bom treino! 💪",
            "pt-PT": "✨ Bom treino! 💪",
            "es": "✨ ¡Buen entrenamiento! 💪",
            "en": "✨ Good workout! 💪",
        },
    },
    # Café / pequeno-almoço
    {
        "keywords": {
            "pt-BR": ["café da manhã", "cafe da manha", "pequeno-almoço", "pequeno almoco", "café", "cafe", "brunch", "tomar café", "café com", "breakfast"],
            "pt-PT": ["pequeno-almoço", "pequeno almoco", "café", "cafe", "brunch", "tomar café", "café com", "breakfast"],
            "es": ["desayuno", "café", "cafe", "brunch", "tomar café", "café con"],
            "en": ["breakfast", "brunch", "coffee", "coffee with", "morning coffee"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita! ☕",
            "pt-PT": "✨ Aproveita! ☕",
            "es": "✨ ¡Disfruta! ☕",
            "en": "✨ Enjoy! ☕",
        },
    },
    # Encontro de trabalho / networking
    {
        "keywords": {
            "pt-BR": ["networking", "encontro de trabalho", "evento corporativo", "congresso", "workshop", "seminário", "seminario", "feira", "conferência", "conferencia", "palestra", "curso profissional"],
            "pt-PT": ["networking", "encontro de trabalho", "evento corporativo", "congresso", "workshop", "seminário", "seminario", "feira", "conferência", "conferencia", "palestra", "curso profissional"],
            "es": ["networking", "encuentro de trabajo", "evento corporativo", "congreso", "workshop", "seminario", "feria", "conferencia", "charla", "curso profesional"],
            "en": ["networking", "work event", "corporate event", "conference", "workshop", "seminar", "trade show", "professional course"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita e faz bons contactos!",
            "pt-PT": "✨ Aproveita e faz bons contactos!",
            "es": "✨ ¡Disfruta y haz buenos contactos!",
            "en": "✨ Enjoy and make good connections!",
        },
    },
    # Casamento / batizado / evento familiar
    {
        "keywords": {
            "pt-BR": ["casamento", "batizado", "batismo", "formatura", "convívio familiar", "convivio familiar", "almoço de família", "jantar de família", "reunião de família", "família", "familia"],
            "pt-PT": ["casamento", "batizado", "batismo", "formatura", "convívio familiar", "convivio familiar", "almoço de família", "jantar de família", "reunião de família", "família", "familia"],
            "es": ["boda", "casamiento", "bautizo", "graduación", "reunión familiar", "almuerzo familiar", "cena familiar", "familia"],
            "en": ["wedding", "baptism", "graduation", "family gathering", "family lunch", "family dinner", "family reunion", "family"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o momento em família!",
            "pt-PT": "✨ Aproveita o momento em família!",
            "es": "✨ ¡Disfruta el momento en familia!",
            "en": "✨ Enjoy the time with family!",
        },
    },
    # Primeiro dia de trabalho / novo emprego
    {
        "keywords": {
            "pt-BR": ["primeiro dia", "primeiro dia de trabalho", "novo emprego", "novo trabalho", "início no trabalho", "inicio no trabalho", "começar a trabalhar", "comecar a trabalhar"],
            "pt-PT": ["primeiro dia", "primeiro dia de trabalho", "novo emprego", "novo trabalho", "início no trabalho", "inicio no trabalho", "começar a trabalhar", "comecar a trabalhar"],
            "es": ["primer día", "primer día de trabajo", "nuevo empleo", "nuevo trabajo", "empezar a trabajar", "inicio en el trabajo"],
            "en": ["first day", "first day at work", "new job", "new job", "starting work", "first day at new job"],
        },
        "messages": {
            "pt-BR": "✨ Boa sorte no primeiro dia! Vai correr bem.",
            "pt-PT": "✨ Boa sorte no primeiro dia! Vai correr bem.",
            "es": "✨ ¡Buena suerte el primer día! Saldrá bien.",
            "en": "✨ Good luck on your first day! You've got this.",
        },
    },
    # Apresentação de projeto / entrega
    {
        "keywords": {
            "pt-BR": ["entrega de projeto", "entrega de projecto", "apresentar projeto", "apresentar projecto", "demo do projeto", "revisão de projeto", "revisao de projeto", "kickoff", "kick-off", "reunião de kickoff"],
            "pt-PT": ["entrega de projeto", "entrega de projecto", "apresentar projeto", "apresentar projecto", "demo do projeto", "revisão de projeto", "revisao de projeto", "kickoff", "kick-off", "reunião de kickoff"],
            "es": ["entrega de proyecto", "presentar proyecto", "demo del proyecto", "revisión de proyecto", "kickoff", "reunión de kickoff"],
            "en": ["project delivery", "present project", "project demo", "project review", "kickoff", "kickoff meeting"],
        },
        "messages": {
            "pt-BR": "✨ Que a entrega corra bem!",
            "pt-PT": "✨ Que a entrega corra bem!",
            "es": "✨ ¡Que la entrega vaya bien!",
            "en": "✨ Hope the delivery goes well!",
        },
    },
    # Série / maratona de episódios
    {
        "keywords": {
            "pt-BR": ["série", "serie", "maratona de série", "ver série", "novo episódio", "estreia da série", "netflix", "streaming", "filme em casa"],
            "pt-PT": ["série", "serie", "maratona de série", "ver série", "novo episódio", "estreia da série", "netflix", "streaming", "filme em casa"],
            "es": ["serie", "maratón de serie", "ver serie", "nuevo episodio", "estreno de la serie", "netflix", "streaming", "película en casa"],
            "en": ["series", "binge", "watch series", "new episode", "series premiere", "netflix", "streaming", "movie at home"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o episódio! 🍿",
            "pt-PT": "✨ Aproveita o episódio! 🍿",
            "es": "✨ ¡Disfruta el episodio! 🍿",
            "en": "✨ Enjoy the episode! 🍿",
        },
    },
    # Hobby / curso / aula
    {
        "keywords": {
            "pt-BR": ["aula de", "curso de", "oficina", "workshop de", "aula de pintura", "aula de música", "aula de musica", "aula de culinária", "aula de culinaria", "hobby", "passatempo"],
            "pt-PT": ["aula de", "curso de", "oficina", "workshop de", "aula de pintura", "aula de música", "aula de musica", "aula de culinária", "aula de culinaria", "hobby", "passatempo"],
            "es": ["clase de", "curso de", "taller", "workshop de", "clase de pintura", "clase de música", "clase de cocina", "hobby", "pasatiempo"],
            "en": ["class", "course", "workshop", "painting class", "music class", "cooking class", "hobby", "pastime"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita a aula!",
            "pt-PT": "✨ Aproveita a aula!",
            "es": "✨ ¡Disfruta la clase!",
            "en": "✨ Enjoy the class!",
        },
    },
    # Jogo / videogame / gaming
    {
        "keywords": {
            "pt-BR": ["jogo", "videogame", "gaming", "lançar do jogo", "lancar do jogo", "lançamento do jogo", "streaming de jogo", "campeonato de esports", "esports"],
            "pt-PT": ["jogo", "videogame", "gaming", "lançamento do jogo", "streaming de jogo", "campeonato de esports", "esports"],
            "es": ["juego", "videojuego", "gaming", "lanzamiento del juego", "streaming de juego", "campeonato de esports", "esports"],
            "en": ["game", "videogame", "gaming", "game launch", "game streaming", "esports championship", "esports"],
        },
        "messages": {
            "pt-BR": "✨ Divertido e boa sorte! 🎮",
            "pt-PT": "✨ Divertido e boa sorte! 🎮",
            "es": "✨ ¡Diviértete y buena suerte! 🎮",
            "en": "✨ Have fun and good luck! 🎮",
        },
    },
    # Massagem / spa / bem-estar
    {
        "keywords": {
            "pt-BR": ["massagem", "spa", "sauna", "bem-estar", "bem estar", "relaxar", "dia de spa", "tratamento de beleza", "manicure", "pedicure"],
            "pt-PT": ["massagem", "spa", "sauna", "bem-estar", "bem estar", "relaxar", "dia de spa", "tratamento de beleza", "manicure", "pedicure"],
            "es": ["masaje", "spa", "sauna", "bienestar", "relajar", "día de spa", "tratamiento de belleza", "manicura", "pedicura"],
            "en": ["massage", "spa", "sauna", "wellness", "relax", "spa day", "beauty treatment", "manicure", "pedicure"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita para relaxar! 💆",
            "pt-PT": "✨ Aproveita para relaxar! 💆",
            "es": "✨ ¡Disfruta para relajarte! 💆",
            "en": "✨ Enjoy and relax! 💆",
        },
    },
    # Compras / shopping
    {
        "keywords": {
            "pt-BR": ["compras", "shopping", "ir às compras", "ir as compras", "centro comercial", "loja", "black friday", "comprar presente", "presente para"],
            "pt-PT": ["compras", "shopping", "ir às compras", "ir as compras", "centro comercial", "loja", "black friday", "comprar presente", "presente para"],
            "es": ["compras", "shopping", "ir de compras", "centro comercial", "tienda", "black friday", "comprar regalo", "regalo para"],
            "en": ["shopping", "go shopping", "mall", "store", "black friday", "buy present", "gift for"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita as compras!",
            "pt-PT": "✨ Aproveita as compras!",
            "es": "✨ ¡Disfruta las compras!",
            "en": "✨ Enjoy shopping!",
        },
    },
    # Passeio / parque / natureza
    {
        "keywords": {
            "pt-BR": ["passeio", "parque", "natureza", "trilha", "caminhada na natureza", "praia", "piscina", "piquenique", "dia ao ar livre"],
            "pt-PT": ["passeio", "parque", "natureza", "trilho", "caminhada na natureza", "praia", "piscina", "piquenique", "dia ao ar livre"],
            "es": ["paseo", "parque", "naturaleza", "sendero", "caminata en la naturaleza", "playa", "piscina", "picnic", "día al aire libre"],
            "en": ["walk", "park", "nature", "hike", "hiking", "beach", "pool", "picnic", "outdoor day"],
        },
        "messages": {
            "pt-BR": "✨ Aproveita o dia! 🌳",
            "pt-PT": "✨ Aproveita o dia! 🌳",
            "es": "✨ ¡Disfruta el día! 🌳",
            "en": "✨ Enjoy the day! 🌳",
        },
    },
]


# Contagem total de keywords por idioma (para documentação)
def _count_keywords(categories: list[_Category]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in categories:
        for lang, kws in c["keywords"].items():
            out[lang] = out.get(lang, 0) + len(kws)
    return out

EMPATHY_KEYWORD_COUNT = _count_keywords(EMPATHY_CATEGORIES)
POSITIVE_KEYWORD_COUNT = _count_keywords(POSITIVE_CATEGORIES)
