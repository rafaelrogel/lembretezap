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
LISTA_SOZINHA_WORDS = ["list"]

# NL Adicione Lista
ADICIONE_VERBS = ["add", "put"]
NAS_WORDS = ["to\\s+(?:the\\s+)?", "on\\s+(?:the\\s+)?"]

# NL List Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:add|put)\s+(?:to\s+(?:the\s+)?|on\s+(?:the\s+)?)?list"

# Category to list mapping
CATEGORY_TO_LIST = {
    "movie": "filme", "movies": "filme", "film": "filme", "films": "filme",
    "book": "livro", "books": "livro",
    "music": "musica", "song": "musica", "songs": "musica",
    "recipe": "receita", "recipes": "receita",
    "game": "jogo", "games": "jogo",
    "note": "nota", "notes": "nota",
    "shopping": "mercado", "grocery": "mercado", "groceries": "mercado", "market": "mercado",
}

REMINDER_AGENDA_WORDS = {
    "reminders", "reminder", "calendar", "agenda"
}
