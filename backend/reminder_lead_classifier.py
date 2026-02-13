"""
Classificador de lembretes: decide se um lembrete deve ter aviso(s) antes do evento ou não.
- Eventos que exigem aviso antes: reunião, consulta, voo, ônibus, encontro, etc. (usa preferência do utilizador).
- Eventos que não exigem: tomar remédio, acordar, ligar, etc. (só o lembrete na hora).
- Eventos muito longos no tempo (> 5 dias): aviso automático 24h antes, sem perguntar ao cliente.

Listas NEED_ADVANCE_KEYWORDS e NO_ADVANCE_KEYWORDS: 200+ casos cada (ver REMINDER_LEAD_CASES.md).
Em caso de ambiguidade, usa MiMo para classificar (YES/NO).
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zapista.providers.base import LLMProvider

# Segundos em 24h (para aviso automático em eventos longos)
AUTO_LEAD_LONG_EVENT_SECONDS = 86400  # 24h
# Considerar "evento muito longo" se o lembrete for para daqui a mais de 5 dias
LONG_EVENT_THRESHOLD_SECONDS = 5 * 86400


def is_long_duration(in_seconds: int | None) -> bool:
    """True se o evento é daqui a mais de LONG_EVENT_THRESHOLD_SECONDS (ex.: 5 dias)."""
    if in_seconds is None or in_seconds <= 0:
        return False
    return in_seconds >= LONG_EVENT_THRESHOLD_SECONDS


# --- 200+ casos em que É NECESSÁRIO aviso antes do evento ---
# Reuniões, compromissos, viagens, transportes, compromissos formais, eventos com horário de chegada, etc.
NEED_ADVANCE_KEYWORDS = frozenset({
    # Reuniões e trabalho
    "reunião", "reuniao", "reuniões", "reunioes", "meeting", "meetings", "reunião de trabalho",
    "apresentação", "apresentacao", "apresentações", "apresentacoes", "presentation",
    "entrevista", "entrevistas", "interview", "job interview", "entrevista de emprego",
    "conferência", "conferencia", "conferências", "conference", "palestra", "palestras",
    "workshop", "workshops", "seminário", "seminario", "seminários", "webinar", "webinars",
    "call", "calls", "videoconferência", "videoconferencia", "videoconference", "zoom", "teams",
    "reunião com", "meeting with", "reunião com cliente", "reunião com chefe",
    "daily", "standup", "stand-up", "retrospectiva", "planning", "sprint",
    "entrega de projeto", "deadline", "prazo de entrega", "entrega do trabalho",
    # Consultas e saúde (compromissos com hora marcada)
    "consulta", "consultas", "consulta médica", "consulta medica", "consulta ao médico",
    "médico", "medico", "doutor", "doctor", "clínica", "clinica", "hospital",
    "exame", "exames", "exame de sangue", "ressonância", "ressonancia", "ultrassom", "ultra-som",
    "vacina", "vacinação", "vacinacao", "vacina covid", "dose",
    "dentista", "odontólogo", "odontologo", "consulta dentária", "consulta dentaria",
    "fisioterapia", "fisioterapeuta", "terapia", "sessão de terapia", "sessao de terapia",
    "psicólogo", "psicologo", "psicóloga", "psicologa", "psicoterapia",
    "oftalmologista", "oculista", "optometrista", "consulta oftalmológica",
    "cardiologista", "dermatologista", "ginecologista", "pediatra", "urologista",
    "cirurgia", "cirurgia marcada", "operação", "operacao", "surgery",
    # Viagens e transportes
    "voo", "voos", "flight", "flights", "embarque", "check-in", "checkin",
    "aeroporto", "airport", "partida do voo", "saída do voo", "saida do voo",
    "ônibus", "onibus", "autocarro", "autocarros", "bus", "partida do ônibus",
    "saída do ônibus", "saida do onibus", "horário do ônibus", "horario do onibus",
    "barco", "barca", "barcas", "ferry", "ferries", "saída do barco", "saida do barco",
    "trem", "comboio", "comboios", "train", "partida do trem", "estação", "estacao", "station",
    "metro", "metrô", "metropolitano", "subway", "último metro", "ultimo metro",
    "viagem", "viagens", "trip", "partida para viagem", "saída para viagem",
    "transfer", "transfers", "translado", "translados", "pickup", "carro agendado",
    "aluguel de carro", "rent a car", "devolução do carro", "devolucao do carro",
    # Encontros e eventos sociais
    "encontro", "encontros", "encontro com", "meetup", "encontro com amigos",
    "compromisso", "compromissos", "compromisso com", "appointment", "appointments",
    "casamento", "casamentos", "wedding", "bodas", "cerimônia", "cerimonia", "ceremony",
    "festa", "festas", "party", "aniversário", "aniversario", "birthday", "birthday party",
    "formatura", "formaturas", "graduation", "colação de grau", "colacao de grau",
    "jantar", "jantares", "dinner", "almoço de negócios", "almoco de negocios", "business lunch",
    "café com", "cafe com", "coffee meeting", "almoço com", "almoco com",
    "visita", "visitas", "visita a", "visit", "visiting", "visita ao escritório",
    # Educação e provas
    "prova", "provas", "exame escolar", "test", "exam", "exams", "avaliação", "avaliacao",
    "aula", "aulas", "aula de", "class", "lesson", "curso", "cursos", "course",
    "seminário de curso", "trabalho de conclusão", "tcc", "apresentação de tcc",
    "defesa", "defesa de tese", "defesa de dissertação", "defesa de tcc",
    "matrícula", "matricula", "enrollment", "prazo de matrícula",
    "entrega de trabalho", "entrega de tcc", "entrega de relatório", "deadline de entrega",
    # Serviços e compromissos externos
    "corte de cabelo", "cabeleireiro", "haircut", "salão", "salao", "barbearia",
    "manicure", "pedicure", "estética", "estetica", "spa", "massagem agendada",
    "advogado", "advogada", "consulta jurídica", "consultoria", "consultant",
    "contador", "contabilidade", "declaração ir", "declaracao ir", "imposto de renda",
    "banco", "agência bancária", "agencia bancaria", "cartório", "cartorio", "notary",
    "reparo", "reparação", "reparacao", "manutenção agendada", "manutencao agendada",
    "entrega de encomenda", "entrega de pacote", "delivery agendado", "instalação", "instalacao",
    "vistoria", "vistorias", "inspeção", "inspecao", "inspection",
    # Eventos desportivos e culturais
    "jogo", "jogos", "game", "partida", "partidas", "match", "campeonato",
    "cinema", "filme no cinema", "sessão de cinema", "sessao de cinema", "movie",
    "teatro", "peça", "peca", "espetáculo", "espetaculo", "show", "concerto", "concierto",
    "exposição", "exposicao", "exhibition", "museum", "museu", "galeria",
    "show", "show ao vivo", "festival", "festivals", "evento", "eventos", "event",
    # Outros compromissos com hora
    "coleta", "coleta de exames", "retirada de resultado", "retirar resultado",
    "assinar documento", "assinatura", "reunião de assinatura",
    "abertura de empresa", "registro", "registro de documento",
    "test drive", "test-drive", "prova de carro",
    "entrega de chave", "entrega de imóvel", "entrega de imovel", "mudança", "mudanca",
    "fechamento", "fechamento de contrato", "closing",
    "audição", "audicao", "audition", "casting",
    "treino", "treinos", "training", "prática", "pratica", "practice",
    "aula de condução", "aula de direção", "aula de direcao", "driving lesson",
    "carta de condução", "exame de condução", "exame de direção",
    "reunião de condomínio", "reuniao de condominio", "assembleia", "assembleia de condomínio",
    "abertura de conta", "conta bancária", "conta bancaria",
    "espanhol", "inglês", "ingles", "aula de idioma", "language class",
    "yoga", "pilates", "academia", "ginásio", "ginasio", "gym", "personal trainer",
    "nutricionista", "nutrição", "nutricao", "dietitian",
    "cão", "cao", "cachorro", "veterinário", "veterinario", "vet", "pet",
    "lavagem de carro", "troca de óleo", "troca de oleo", "oficina", "mechanic",
    "seguro", "renovação de seguro", "renovacao de seguro",
    "passaporte", "visto", "consulado", "embaixada", "visa",
    "aluguel", "pagamento de aluguel", "rent payment", "condomínio", "condominio",
    "reunião de pais", "reuniao de pais", "parent teacher", "escola", "school",
    "abertura de loja", "inauguração", "inauguracao", "opening",
    "live", "live stream", "webinar ao vivo", "transmissão", "transmissao",
})

# --- 200+ casos em que NÃO é necessário aviso antes (só o lembrete na hora) ---
# Medicação, rotinas, tarefas pontuais, chamadas, coisas que acontecem "na hora"
NO_ADVANCE_KEYWORDS = frozenset({
    # Medicação e saúde rotineira
    "tomar remédio", "tomar remedio", "tomar medicamento", "tomar medicação", "tomar medicacao",
    "tomar comprimido", "comprimido", "comprimidos", "pill", "pills", "take medicine",
    "tomar antibiótico", "tomar antibiotico", "antibiotic", "tomar vitamina", "vitamina",
    "tomar suplemento", "suplemento", "supplement", "tomar ômega", "tomar omega",
    "insulina", "aplicar insulina", "glicemia", "medir glicemia", "medir glicose",
    "inalador", "bombinha", "aspirina", "paracetamol", "ibuprofeno", "dipirona",
    "colírio", "colirio", "eye drops", "gotas", "aplicar colírio",
    "beber água", "beber agua", "drink water", "hidratar", "hydration",
    "alongar", "alongamento", "stretch", "respirar", "breathe", "meditar", "meditation",
    "peso", "pesar", "weigh", "pressão", "pressao", "blood pressure", "medir pressão",
    "dormir", "ir dormir", "sleep", "go to bed", "hora de dormir",
    "acordar", "acordar às", "acordar as", "wake up", "despertar", "alarm",
    # Tarefas domésticas e rotinas
    "lavar louça", "lavar louca", "lavar a louça", "wash dishes", "lavar pratos",
    "lavar roupa", "lavadora", "washing machine", "estender roupa", "secar roupa",
    "passar roupa", "passar a ferro", "iron", "ironing",
    "varrer", "vassoura", "sweep", "aspirar", "aspirar o chão", "vacuum",
    "limpar", "limpeza", "clean", "cleaning", "arrumar", "arrumar a casa",
    "tirar lixo", "lixo", "trash", "reciclagem", "recycling",
    "regar plantas", "regar", "water plants", "plantas",
    "comida do gato", "comida do cão", "comida do cao", "feed the cat", "feed the dog",
    "trocar areia", "litter box", "aquário", "aquario", "fish",
    # Chamadas e comunicações
    "ligar", "ligar para", "ligar ao", "call", "phone call", "telefonar",
    "enviar email", "mandar email", "send email", "email para", "responder email",
    "mensagem", "mandar mensagem", "send message", "whatsapp", "text",
    "devolver chamada", "return call", "retornar ligação", "retornar ligacao",
    "zoom call", "reunião rápida", "reuniao rapida", "quick call",
    # Pagamentos e tarefas administrativas (sem deslocação)
    "pagar conta", "pagar contas", "pay bill", "bills", "conta de luz", "conta de água",
    "pix", "transferência", "transferencia", "transfer", "pagamento", "payment",
    "boleto", "boletos", "vencimento", "due date", "pagamento de boleto",
    "recarga", "recarga de celular", "top up", "recarga de bilhete", "recarga de transporte",
    # Compras e entregas (quando é "lembrar de comprar" não "entrega agendada")
    "comprar", "compras", "buy", "shopping", "mercado", "supermercado", "grocery",
    "lista de compras", "shopping list", "ir ao mercado", "ir ao supermercado",
    "farmácia", "farmacia", "pharmacy", "buscar remédio", "buscar remedio",
    "retirar encomenda", "retirar pacote", "pick up package", "correios", "correio",
    # Trabalho e estudo (tarefas pontuais, não reuniões)
    "enviar relatório", "enviar relatorio", "submit report", "entregar trabalho",
    "enviar proposta", "proposta", "proposal", "enviar orçamento", "enviar orcamento",
    "revisar", "revisar documento", "review", "proofread", "revisar texto",
    "estudar", "study", "ler", "read", "fazer exercícios", "fazer exercicios", "homework",
    "fechar planilha", "fechar relatório", "close report", "backup",
    # Rotinas pessoais
    "café da manhã", "cafe da manha", "breakfast", "almoço", "almoco", "lunch", "jantar",
    "lanche", "lanches", "snack", "merendar",
    "banho", "tomar banho", "shower", "bath",
    "escovar os dentes", "escovar dentes", "brush teeth", "fio dental",
    "creme", "hidratante", "skincare", "rotina da pele",
    "exercício", "exercicio", "exercícios", "exercicios", "exercise", "workout", "corrida", "run",
    "caminhada", "walk", "pedalar", "bike", "cycling",
    # Lembretes muito simples
    "ver", "ver o", "assistir", "watch", "programa", "série", "serie", "series",
    "verificar", "verificar se", "check", "check if",
    "desligar", "desligar o", "turn off", "apagar", "apagar luz",
    "tirar do forno", "tirar do micro-ondas", "tirar do microondas",
    "trocar fralda", "dar mamadeira", "baby", "bebê", "bebe",
    "tomar sol", "sun", "protetor solar", "sunscreen",
    "cortar unha", "unhas", "nails",
    "trocar lençol", "trocar lencol", "trocar lençóis", "change sheets",
    "cortar cabelo em casa", "corte caseiro",
    "tomar antibiótico", "tomar antibiotico", "dose do antibiótico",
    "aplicar pomada", "pomada", "ointment", "creme medicinal",
    "inalação", "inalacao", "nebulização", "nebulizacao",
    "soneca", "nap", "cochilo", "descansar", "rest",
    "tomar chá", "tomar cha", "tea", "café", "cafe", "coffee",
    "lanche da tarde", "lanche da manhã", "lanche da manha",
    "tomar sol", "vitamina d", "vitamina D",
    "verificar porta", "fechar porta", "trancar", "lock",
    "regar jardim", "jardim", "garden",
    "cortar grama", "grama", "lawn", "jardineiro",
    "trocar filtro", "filtro de água", "filtro de agua",
    "pilha", "pilhas", "bateria", "trocar bateria", "carregar celular", "charge phone",
    "tomar antibiótico de 8 em 8", "tomar de 8 em 8 horas",
    "jejum", "jejum para exame", "não comer", "nao comer", "fasting",
    "tomar com estômago vazio", "tomar com estomago vazio", "on empty stomach",
    "tomar após refeição", "tomar apos refeicao", "after meal",
    "lembrete de hidratação", "lembrete de água", "lembrete de agua",
    "pausa", "pausa para descanso", "break", "stretch break",
    "postura", "levantar", "levantar e andar", "get up",
    "olhar 20-20-20", "descansar vista", "eye rest",
    "silêncio", "silencia", "quiet time", "meditação guiada", "meditacao guiada",
    "ouvir podcast", "podcast", "audiobook", "áudio livro", "audio livro",
    "anotar", "anotar ideia", "note", "write down",
    "lembrar de", "não esquecer", "nao esquecer", "don't forget",
    "verificar geladeira", "geladeira", "fridge", "validade", "expiry",
    "trocar lâmpada", "trocar lampada", "light bulb",
    "cortar unha do pé", "unha do pé", "unha do pe",
    "hidratar mãos", "hidratar maos", "hand cream",
    "escovar cabelo", "pente", "comb hair",
    "passar desodorante", "desodorante", "deodorant",
    "colírio de lubrificação", "olho seco", "dry eye",
    "soro fisiológico", "lavar nariz", "nasal",
    "vitamina c", "vitamina C", "zinc", "zinco",
    "remédio para dor", "remedio para dor", "painkiller", "analgésico", "analgesico",
    "antialérgico", "antialergico", "antihistamine", "alergia",
    "remédio para azia", "remedio para azia", "antiácido", "antiacido",
    "laxante", "fibra", "intestino",
    "remédio para tosse", "remedio para tosse", "xarope", "syrup",
    "garganta", "pastilha", "lozenge",
    "compressa", "compressa quente", "compressa fria", "ice pack",
    "curativo", "trocar curativo", "bandage",
    "medir temperatura", "febre", "temperature",
    "oxímetro", "oximetro", "saturação", "saturacao", "oxygen",
    "pesar bebê", "pesar bebe", "baby weight",
    "mamada", "amamentar", "breastfeed", "bombinha de leite",
    "soneca do bebê", "soneca do bebe", "baby nap",
    "trocar fralda", "fralda", "diaper",
    "banho do bebê", "banho do bebe", "baby bath",
    "vacina do bebê", "vacina do bebe", "baby vaccine",
    "consultar receita", "receita médica", "receita medica", "prescription",
    "horário do remédio", "horario do remedio", "medicine schedule",
})


def _normalize_for_match(text: str) -> str:
    """Minúsculas, sem acentos (básico), para matching."""
    if not text:
        return ""
    t = text.lower().strip()
    for a, b in [("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"),
                 ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"), ("ç", "c")]:
        t = t.replace(a, b)
    return t


def _message_needs_advance_by_keywords(message: str) -> bool | None:
    """
    Retorna True se a mensagem contém termos que exigem aviso antes,
    False se contém termos que não exigem, None se ambíguo (não encontrou em nenhuma lista).
    """
    if not message or not message.strip():
        return None
    norm = _normalize_for_match(message)
    # Verificar primeiro "não precisa" para evitar que "tomar remédio antes da consulta" vire need
    for kw in NO_ADVANCE_KEYWORDS:
        if kw in norm:
            return False
    for kw in NEED_ADVANCE_KEYWORDS:
        if kw in norm:
            return True
    return None


async def needs_advance_alert(
    message: str,
    in_seconds: int | None = None,
    scope_provider: "LLMProvider | None" = None,
    scope_model: str = "",
) -> bool:
    """
    True se este lembrete deve ter aviso(s) antes do evento (usa preferência do user).
    False se não (só o lembrete na hora).
    Para eventos muito longos (ex.: > 5 dias), o sistema aplica 24h automaticamente (ver is_long_duration).
    """
    if is_long_duration(in_seconds):
        return True  # Será tratado com 24h fixo no cron
    by_kw = _message_needs_advance_by_keywords(message or "")
    if by_kw is not None:
        return by_kw
    # Ambíguo: usar MiMo para classificar
    if scope_provider and (scope_model or "").strip():
        try:
            prompt = (
                f"The user created a reminder: «{(message or '')[:300]}». "
                "Does this reminder typically NEED one or more advance alerts BEFORE the event time? "
                "Examples that NEED advance alert: meeting, doctor appointment, flight, bus departure, interview, wedding, exam. "
                "Examples that do NOT need advance alert: take medicine at 3pm, wake up at 7am, call someone, send email, drink water. "
                "Reply with ONLY one word: YES or NO."
            )
            r = await scope_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=scope_model,
                max_tokens=5,
                temperature=0,
            )
            out = (r.content or "").strip().upper()
            if "YES" in out:
                return True
            if "NO" in out:
                return False
        except Exception:
            pass
    # Fallback: quando ambíguo e sem MiMo, não adicionar avisos antes (só o lembrete na hora)
    return False
