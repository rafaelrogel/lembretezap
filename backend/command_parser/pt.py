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
VERBS_MOSTRE = ["mostr", "ver", "listar?", "exib", "ensina", "queria\\s+ver", "quero\\s+ver", "mostra-me", "mostre-me", "d[aá]-me", "deixa-me\\s+ver"]
VERBS_CRIA = ["cria?r?", "crie?", "fa[çc]a", "faz", "fazer", "faz-me", "cria-me", "quero\\s+criar"]
ARTICLES = ["a", "as", "os", "uma?", "la", "las", "el", "los"]
POSSESSIVES = ["minhas?", "meus?"]
LIST_WORDS = ["lista?"]
PREPOSITIONS_OF = ["de", "denominad", "chamad", "nomead"]

# NL Lista Sozinha
# NL Lista Sozinha
# NL Lista Sozinha (handled by PT if needed, but mainly command based)
LISTA_SOZINHA_WORDS = [
    "lista", "mercado", "compras", "pendentes", "agenda", "agendas",
    "compromissos", "compromisso", "eventos", "evento", "calendário", "calendario",
    "afazeres", "tarefas", "lista de compras", "lista do mercado", "lista de mercado"
]

# NL Adicione Lista
ADICIONE_VERBS = ["adicione", "adiciona", "adicionar", "coloca", "coloque", "colocar", "inclui", "inclua", "incluir", "ponha", "anota", "anote", "põe"]
NAS_WORDS = ["a", "à", "nas?"]

# NL Por Lista
POR_LISTA_VERBS = ["coloca", "coloque", "p[oô]e", "põe", "anota", "anotar", "anote", "inclui", "inclu[ia]", "incluir", "marca", "ponha"]
NA_LISTA_WORDS = ["na", "no", "à", "a"]

# NL Lista Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:coloca|coloque|ponha|p[oô]e|põe|adiciona|adicione|inclui|inclua?|anote?)\s+(?:na|à|a)\s+lista|(?:adiciona|adicione|coloca|coloque)\s+(?:à|a|na)\s+lista"

# NL Outros
ANOTA_VERBS = ["anota", "anotar", "anote", "aponte", "aponta"]
TENHO_WORDS = ["tenho"]
TENHO_DE_WORDS = ["tenho\\s+(?:de|que)", "preciso\\s+(?:de|que)", "necessito\\s+de"]
MUITA_COISA_WORDS = ["muita\\s+coisa", "v[aá]rias\\s+coisas", "v[aá]rias\\s+tarefas", "montes\\s+de\\s+coisa", "um\\s+r[eé]u\\s+de\\s+coisa"]
LEMBRA_COMPRAR_ALTS = [
    "lembra-me de comprar", "lembra me de comprar", "lembre-me de comprar", 
    "não te esqueças de comprar", "não se esqueça de comprar", "não esqueça de comprar", 
    "não esqueças de comprar", "não esqueças de comprar", "lembra de comprar", "lembre de comprar"
]
FILME_LIVRO_VER_ALTS = [
    "filme para ver", "livro para ler", "filmes para ver", "livros para ler", 
    "quero ver o filme", "quero ler o livro", "quero ver o livro", "quero ler o filme",
    "filme para assistir", "filmes para assistir", "quero assistir o filme"
]

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
    "site": "site", "sites": "site",
    "link": "site", "links": "site",
}

REMINDER_AGENDA_WORDS = {
    "lembretes", "lembrete", "agenda", "agendas", "compromissos",
    "compromisso", "eventos", "evento", "calendário", "calendario",
}
