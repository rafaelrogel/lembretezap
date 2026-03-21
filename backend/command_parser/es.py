"""Spanish command parser constants."""

# Regex aliases
LEMBRETE_ALIASES = ["recordatorio", "recordar"]
LISTA_ALIASES = ["lista"]
FEITO_ALIASES = ["hecho"]
REMOVE_ALIASES = ["quitar", "borrar"]

# Category names for /list category add
CATEGORIES = [
    "juego", "juegos", "pel[ií]cula", "pel[ií]culas?", "libro", "libros?", "receta", "recetas?"
]

# NL List Action synonyms
VERBS_MOSTRE = ["mu[^\s]str", "ver"]
VERBS_CRIA = ["make", "create", "haz", "crea?r?", "give", "dame"]
ARTICLES = ["la", "las", "el", "los", "un[a]?"]
POSSESSIVES = ["mi", "mis"]
LIST_WORDS = ["lista?"]
PREPOSITIONS_OF = ["de", "llamada", "llamado", "nombrada", "nombrado"]

# NL Adicione Lista
ADICIONE_VERBS = ["a[ñn]adir"]

# NL Lista Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:pon|pone|a[ñn]ade|a[ñn]adir|agrega|agregar)\s+(?:en\s+la|a\s+la)\s+lista"

# Category to list mapping
CATEGORY_TO_LIST = {
    "película": "filme", "películas": "filme", "pelicula": "filme", "peliculas": "filme",
    "libro": "livro", "libros": "livro",
    "juego": "jogo", "juegos": "jogo",
    "canción": "musica", "canciones": "musica",
    "receta": "receita", "recetas": "receita",
}

REMINDER_AGENDA_WORDS = {
    "recordatorios", "recordatorio"
}
