"""Spanish command parser constants."""

# Regex aliases
LEMBRETE_ALIASES = ["recordatorio", "recordar"]
LISTA_ALIASES = ["lista"]
FEITO_ALIASES = ["hecho"]
REMOVE_ALIASES = ["quitar", "borrar", "eliminar", "suprimir", "del"]

# Category names for /list category add
CATEGORIES = [
    "juego", "juegos", "pel[ií]cula", "pel[ií]culas?", "libro", "libros?", "receta", "recetas?"
]

# NL List Action synonyms
VERBS_MOSTRE = ["muest", "mostr", "ver"]
VERBS_CRIA = ["make", "create", "haz", "crea?r?", "give", "dame"]
ARTICLES = ["la", "las", "el", "los", "un[a]?"]
POSSESSIVES = ["mi", "mis"]
LIST_WORDS = ["lista?"]
PREPOSITIONS_OF = ["de", "llamada", "llamado", "nombrada", "nombrado"]

# NL Lista Sozinha
LISTA_SOZINHA_WORDS = ["lista", "compras", "mercado", "supermercado", "agenda", "calendario", "eventos", "compromisos", "citas", "tareas"]

# NL Adicione Lista
ADICIONE_VERBS = ["a[ñn]adir", "agregar", "poner"]
NAS_WORDS = ["a", "en"]

# NL Lista Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:pon|pone|a[ñn]ade|a[ñn]adir|agrega|agregar)\s+(?:en\s+la|a\s+la)\s+lista"

# Category to list mapping
CATEGORY_TO_LIST = {
    "película": "filmes", "películas": "filmes", "pelicula": "filmes", "peliculas": "filmes",
    "libro": "livros", "libros": "livros",
    "juego": "jogos", "juegos": "jogos",
    "canción": "músicas", "canciones": "músicas",
    "receta": "receitas", "recetas": "receitas",
    "compras": "mercado", "mercado": "mercado", "supermercado": "mercado",
}

# NL Por Lista
POR_LISTA_VERBS = ["pon", "pone", "poner", "agrega", "agregar", "a[ñn]ade", "a[ñn]adir"]
NA_LISTA_WORDS = ["en", "a", "al"]

REMINDER_AGENDA_WORDS = {
    "recordatorios", "recordatorio", "agenda", "agendas", "eventos", "evento",
    "calendario", "calendarios", "compromisos", "compromiso", "citas", "cita",
    "tareas", "tarea"
}
