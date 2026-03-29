"""English command parser constants."""

# Regex aliases
LEMBRETE_ALIASES = ["reminder", "remind"]
LISTA_ALIASES = ["list"]
FEITO_ALIASES = ["done"]
REMOVE_ALIASES = ["remove", "delete", "del"]

# Category names for /list category add
CATEGORIES = [
    "movie", "movies", "film", "films", "book", "books",
    "music", "song", "songs", "recipe", "recipes",
    "game", "games", "note", "notes", "site", "sites", "link", "links"
]

# NL List Action synonyms
VERBS_MOSTRE = ["show", "display", "view"]
VERBS_CRIA = ["make", "create", "give"]
ARTICLES = ["the", "an?"]
POSSESSIVES = ["my"]
LIST_WORDS = ["list"]
PREPOSITIONS_OF = ["of", "called", "named"]

# NL Lista Sozinha (handled by PT if needed, but mainly command based)
LISTA_SOZINHA_WORDS = ["list", "grocery", "groceries", "market", "shopping", "agenda", "calendar", "reminders", "events", "tasks"]

# NL Adicione Lista
ADICIONE_VERBS = ["add", "put", "insert", "include"]
NAS_WORDS = ["to", "on", "into", "onto"]

# NL List Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:add|put|insert|include)\s+(?:to\s+(?:the\s+)?|on\s+(?:the\s+)?)?list"

# NL Outros
ANOTA_VERBS = ["note", "notes", "write", "record", "jot", "mark"]
TENHO_WORDS = ["have"]
TENHO_DE_WORDS = ["i\\s+have\\s+(?:to|gotta)", "i\\s+need\\s+to", "i\\s+must"]
MUITA_COISA_WORDS = ["a\\s+lot\\s+of\\s+stuff", "lots\\s+of\\s+things", "various\\s+tasks", "many\\s+things"]
LEMBRA_COMPRAR_ALTS = [
    "remind me to buy", "dont forget to buy", "don't forget to buy", "remind me of buying"
]
FILME_LIVRO_VER_ALTS = [
    "movie to watch", "book to read", "movies to watch", "books to read", 
    "want to watch the movie", "want to read the book"
]

# Category to list mapping
CATEGORY_TO_LIST = {
    "movie": "filmes", "movies": "filmes", "film": "filmes", "films": "filmes",
    "book": "livros", "books": "livros",
    "music": "músicas", "song": "músicas", "songs": "músicas",
    "recipe": "receitas", "recipes": "receitas",
    "game": "jogos", "games": "jogos",
    "note": "notas", "notes": "notas",
    "shopping": "mercado", "grocery": "mercado", "groceries": "mercado", "market": "mercado",
}

# NL Por Lista
POR_LISTA_VERBS = ["put", "add"]
NA_LISTA_WORDS = ["in", "on"]

REMINDER_AGENDA_WORDS = {
    "reminders", "reminder", "calendar", "agenda", "events", "event",
    "appointments", "appointment", "tasks", "task"
}
