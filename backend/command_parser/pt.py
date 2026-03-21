"""Portuguese (PT-PT and PT-BR) command parser constants."""

# Regex aliases
LEMBRETE_ALIASES = ["lembrete"]
LISTA_ALIASES = ["lista"]
FEITO_ALIASES = ["feito"]
REMOVE_ALIASES = ["remove", "deletar", "apagar"]

# Category names for /list category add
CATEGORIES = [
    "filme", "filmes", "livro", "livros", "musica", "musicas", "m[uú]sicas?",
    "s[ée]ries?", "jogo", "jogos", "receita", "receitas", "notas?", "sites?", "links?"
]

# NL List Action synonyms
VERBS_MOSTRE = ["mostr", "ver", "listar?", "exib"]
VERBS_CRIA = ["cria?r?", "crie?", "fa[çc]a", "faz", "fazer"]
ARTICLES = ["a", "as", "os", "uma?", "la", "las", "el", "los"]
POSSESSIVES = ["minha?", "minhas", "meus", "meu"]
LIST_WORDS = ["lista?"]
PREPOSITIONS_OF = ["de", "denominad", "chamad", "nomead"]

# NL Lista Sozinha
LISTA_SOZINHA_WORDS = ["lista", "mercado", "compras", "pendentes"]

# NL Adicione Lista
ADICIONE_VERBS = ["adicione", "adiciona", "adicionar", "coloca", "coloque", "colocar"]
NAS_WORDS = ["a", "à", "nas?"]

# NL Por Lista
POR_LISTA_VERBS = ["coloca", "coloque", "p[oô]e", "põe", "anota", "anotar", "inclui", "incluir", "marca"]
NA_LISTA_WORDS = ["na", "no", "è", "a"]

# NL Lista Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:coloca|coloque|p[oô]e|põe|adiciona|adicione|inclui|incluir)\s+(?:na|à|a)\s+lista|(?:adiciona|adicione|coloca|coloque)\s+(?:à|a|na)\s+lista"

# NL Outros
ANOTA_VERBS = ["anota", "anotar"]
TENHO_WORDS = ["tenho"]
TENHO_DE_WORDS = ["tenho\\s+(?:de|que)"]
MUITA_COISA_WORDS = ["muita\\s+coisa", "v[aá]rias\\s+coisas", "v[aá]rias\\s+tarefas"]
LEMBRA_COMPRAR_FRAGMENT = r"(?:lembra[- ]?me\s+de\s+comprar|n[aã]o\s+esque[cç]as?\s+de\s+comprar|lembra\s+de\s+comprar)"
FILME_LIVRO_VER_FRAGMENT = r"(?:(?:filme|livro)\s+para\s+(?:ver|ler)\s*:\s*|quero\s+(?:ver|ler)\s+(?:o\s+)?(?:filme|livro)\s+)"

# Category to list mapping
CATEGORY_TO_LIST = {
    "filme": "filmes", "filmes": "filmes",
    "livro": "livros", "livros": "livros",
    "musica": "músicas", "musicas": "músicas", "música": "músicas", "músicas": "músicas",
    "série": "séries", "séries": "séries", "serie": "séries", "series": "séries",
    "receita": "receitas", "receitas": "receitas",
    "jogo": "jogos", "jogos": "jogos",
    "mercado": "mercado", "supermercado": "mercado", "compras": "mercado",
    "nota": "notas", "notas": "notas",
    "site": "sites", "sites": "sites",
    "link": "sites", "links": "sites",
}

REMINDER_AGENDA_WORDS = {
    "lembretes", "lembrete", "agenda", "agendas", "compromissos",
    "compromisso", "eventos", "evento", "calendário", "calendario",
}
