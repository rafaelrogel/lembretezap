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
# NL List Action synonyms
VERBS_MOSTRE = ["enséñ", "enseñ", "muéstr", "muestr", "mostr", "ver", "quiero\\s+ver", "enséñame", "muéstrame", "déjame\\s+ver"]
VERBS_CRIA = ["make", "create", "haz", "hace", "hacer", "crea?r?", "give", "dame", "quisiera", "quiero\\s+crear", "pon"]
ARTICLES = ["la", "las", "el", "los", "un[a]?"]
POSSESSIVES = ["mi", "mis"]
LIST_WORDS = ["lista?"]
PREPOSITIONS_OF = ["de", "llamada", "llamado", "nombrada", "nombrado"]

# NL Lista Sozinha
LISTA_SOZINHA_WORDS = ["lista", "compras", "mercado", "supermercado", "agenda", "calendario", "eventos", "compromisos", "citas", "tareas", "lista de compras", "lista de mercado", "lista del súper", "mandados", "deveres"]

# NL Adicione Lista
ADICIONE_VERBS = ["a[ñn]adir", "a[ñn]ada", "a[ñn]ade", "agregar", "agrega", "agregue", "poner", "pon", "ponga", "incluir", "incluye", "incluya"]
NAS_WORDS = ["a", "en"]

# NL Lista Dois Pontos
LISTA_DOIS_PONTOS_FRAGMENT = r"(?:pon|pone|ponga|a[ñn]ade|a[ñn]ada|agrega|agregue|incluir|incluye|incluya)\s+(?:en\s+la|a\s+la)\s+lista"

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
POR_LISTA_VERBS = ["pon", "pone", "ponga", "poner", "agrega", "agregar", "agregue", "a[ñn]ade", "a[ñn]adir", "a[ñn]ada"]
NA_LISTA_WORDS = ["en", "a", "al"]

# NL Outros
ANOTA_VERBS = ["anota", "anotar", "apunta", "apuntar", "escribe", "escribir", "anote", "apunte"]
TENHO_WORDS = ["tengo"]
TENHO_DE_WORDS = ["tengo\\s+que", "necesito", "debo"]
MUITA_COISA_WORDS = ["muchas\\s+cosas", "varias\\s+cosas", "varias\\s+tareas", "un\\s+mont[oó]n\\s+de\\s+cosas"]
LEMBRA_COMPRAR_ALTS = [
    "recuérdame comprar", "recuerdame comprar", "no olvides comprar", "no te olvides de comprar"
]
FILME_LIVRO_VER_ALTS = [
    "película para ver", "pelicula para ver", "libro para leer", "películas para ver", 
    "libros para leer", "quiero ver la película", "quiero leer el libro"
]

REMINDER_AGENDA_WORDS = {
    "recordatorios", "recordatorio", "agenda", "agendas", "eventos", "evento",
    "calendario", "calendarios", "compromisos", "compromiso", "citas", "cita",
    "tareas", "tarea"
}
