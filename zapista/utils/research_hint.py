"""Mensagens curtas "Estou a pesquisar" quando o pedido pode demorar (receitas, listas de compras, URLs)."""

import re
import random

# Mensagens curtas, simpáticas, com emoji (para enviar antes de pesquisas demoradas)
# ~117 frases para variar e não ficar repetitivo
SEARCHING_MESSAGES = [
    "Estou a pesquisar... 🔍",
    "Vou pesquisar já! 🔎",
    "Paciência, estou a pesquisar 😊",
    "A aceder aos dados... 📡",
    "A buscar na Internet... 🌐",
    "A puxar do servidor... ⏳",
    "A extrair informação... 📄",
    "Um segundinho, estou a ver... 👀",
    "AI em ação! 🤖",
    "A preparar a resposta... ✨",
    "Já vou ter isso! ⚡",
    "A consultar as fontes... 📚",
    "Buscando na Internet... 🌍",
    "Extraindo informação da Internet... 📲",
    "Aguarda um momentinho... ⏱️",
    "Estou a trabalhar nisso... 💪",
    "Quase, quase... 🎯",
    # +100 variações
    "Deixa-me ver isso... 🔎",
    "A procurar por ti... 🧭",
    "Um instante, a carregar... ⏳",
    "A ligar às fontes... 📶",
    "Pesquisa em curso... 📋",
    "A processar o pedido... ⚙️",
    "Já estou a tratar disso... ✅",
    "A recolher informação... 📥",
    "Um momento, por favor... 🙏",
    "A consultar a base de dados... 🗄️",
    "Estou a ver... 👁️",
    "A descarregar dados... 📲",
    "Quase lá! 🏁",
    "A analisar... 🧠",
    "Acedendo à rede... 🌐",
    "Trabalho em progresso... 🛠️",
    "A carregar conteúdo... 📄",
    "Paciência, já lá vou... 😌",
    "A buscar a informação... 🔎",
    "Um segundo só... ⏱️",
    "A fazer a pesquisa... 📖",
    "Estou a tratar disso... 💼",
    "A conectar... 🔌",
    "A processar... ⚡",
    "Já vou buscar isso! 🏃",
    "A ler as fontes... 📰",
    "Aguarda só um pouco... ⏳",
    "A explorar a web... 🕸️",
    "A compilar a resposta... 📝",
    "Deixa-me pesquisar... 🔍",
    "A obter os dados... 📊",
    "Em modo pesquisa... 🎯",
    "A carregar... ⏳",
    "Um momentinho... 🙃",
    "A vasculhar a Internet... 🌍",
    "Estou aí... 👋",
    "A preparar tudo... 🎁",
    "A consultar... 📞",
    "Pesquisa a decorrer... 🔄",
    "A extrair os dados... 📤",
    "Já estou a trabalhar nisso... 💪",
    "A ligar aos servidores... 🖥️",
    "Um instante... ✋",
    "A buscar na web... 🌐",
    "A processar o teu pedido... 📬",
    "Quase a terminar... 🏃‍♂️",
    "A recolher os detalhes... 📋",
    "Acedendo aos dados... 🔓",
    "A ver o que encontro... 👀",
    "Paciência, estou a trabalhar... 😊",
    "A carregar a informação... 📥",
    "A pesquisar por ti... 🔎",
    "Um segundo, a verificar... ✔️",
    "A compilar a lista... 📑",
    "Estou a tratar do pedido... 📮",
    "A conectar às fontes... 🔗",
    "A analisar o conteúdo... 🔬",
    "Já vou ter a resposta! ⚡",
    "A descarregar... 📲",
    "A explorar... 🗺️",
    "Trabalhando nisso... 🛠️",
    "A ler a página... 📄",
    "Aguarda, estou a pesquisar... ⏳",
    "A obter a informação... 📡",
    "Modo pesquisa ativado... 🔍",
    "A carregar os dados... 💾",
    "Um momento, a pesquisar... 🙏",
    "A vasculhar... 🕵️",
    "Estou a chegar lá... 🎯",
    "A preparar a lista... ✨",
    "A consultar a web... 🌍",
    "Pesquisa em andamento... 🔄",
    "A extrair da Internet... 📲",
    "Já estou a ir buscar... 🏃",
    "A ligar à base de dados... 🗄️",
    "Um instante, a carregar... ⏱️",
    "A buscar os ingredientes... 🥘",
    "A processar a pesquisa... ⚙️",
    "Quase a ter a resposta... 🏁",
    "A recolher a informação... 📥",
    "Acedendo à informação... 🔓",
    "A ver o que há... 👁️",
    "A carregar o conteúdo... 📄",
    "Paciência, um segundo... 😌",
    "A pesquisar na Internet... 🌐",
    "A verificar as fontes... 📚",
    "Um segundo, por favor... ✋",
    "A fazer a busca... 🔎",
    "Estou a processar... 💼",
    "A conectar aos dados... 🔌",
    "A analisar as fontes... 🧠",
    "Já vou ter! ⚡",
    "A descarregar dados... 📲",
    "A explorar as receitas... 🍳",
    "Trabalho a decorrer... 🛠️",
    "A ler as informações... 📰",
    "Aguarda um segundo... ⏳",
    "A obter os detalhes... 📊",
    "Pesquisa ativa... 🎯",
    "A carregar... 💾",
    "Um momentinho, a ver... 🙃",
    "A vasculhar a web... 🕸️",
    "Estou quase... 👋",
    "A preparar a informação... 🎁",
    "A consultar as receitas... 📖",
    "Pesquisa a decorrer... 🔄",
    "A extrair conteúdo... 📤",
    "Já estou a pesquisar... 💪",
    "A ligar à web... 🖥️",
    "Um instante só... ✋",
    "A buscar na rede... 🌐",
    "A processar... 📬",
    "Quase a ter a lista... 🏃‍♂️",
    "A recolher... 📋",
    "Acedendo à web... 🔓",
    "A ver o que encontro para ti... 👀",
    "Paciência, estou a buscar... 😊",
    "A carregar os detalhes... 📥",
    "A pesquisar... 🔎",
    "Um segundo, a processar... ✔️",
    "A compilar... 📑",
    "Estou a ir buscar isso... 📮",
    "A conectar... 🔗",
    "A analisar o pedido... 🔬",
    "Já lá vou! ⚡",
    "A descarregar informação... 📲",
    "A explorar os dados... 🗺️",
    "Trabalhando na pesquisa... 🛠️",
    "A ler... 📄",
    "Aguarda, já vou ter... ⏳",
    "A obter... 📡",
    "Em busca! 🔍",
    "A carregar a lista... 💾",
    "Um momento... 🙏",
    "A vasculhar as fontes... 🕵️",
    "Estou a chegar... 🎯",
    "A preparar... ✨",
    "A consultar a Internet... 🌍",
    "Pesquisa em curso... 🔄",
    "A extrair... 📲",
    "Já estou a tratar... 🏃",
    "A ligar... 🗄️",
    "Um instante, a pesquisar... ⏱️",
    "A buscar... 🥘",
    "A processar o teu pedido... ⚙️",
    "Quase! 🏁",
    "A recolher... 📥",
    "Acedendo... 🔓",
    "A ver... 👁️",
]

# Padrões que indicam pedido que pode demorar (receita, lista de compras, URL, pesquisa)
_RECEITA_LIST = re.compile(
    r"\b(receita|receitas|lista\s+de\s+compras?|lista\s+de\s+compra|"
    r"ingredientes|pesquisar|pesquisa|buscar|busca|"
    r"compras?\s+para\s+(?:fazer|uma|receita)|"
    r"faça\s+uma\s+lista|fazer\s+uma\s+lista)\b",
    re.I,
)
_URL = re.compile(r"https?://\S+", re.I)

# Mensagens genéricas (sem "lista") — para URLs sozinhos (Twitter, etc.) não usar "A carregar a lista"
_URL_ONLY_MESSAGES = [
    m for m in SEARCHING_MESSAGES
    if "lista" not in m.lower() and "list" not in m.lower() and "compilar" not in m.lower()
]


def is_research_intent(content: str) -> bool:
    """
    True se a mensagem parece pedir pesquisa/receita/lista de compras/URL
    (operações que podem demorar e justificam aviso "Estou a pesquisar").
    """
    if not content or not content.strip():
        return False
    text = content.strip()
    if _URL.search(text):
        return True
    if _RECEITA_LIST.search(text):
        return True
    return False


def _is_url_only(content: str) -> bool:
    """True se a mensagem é basicamente só um URL (ex.: link partilhado)."""
    if not content or not content.strip():
        return False
    text = content.strip()
    without_url = _URL.sub("", text)
    return len(without_url.strip()) < 15


def get_searching_message(content: str | None = None) -> str:
    """
    Retorna uma mensagem aleatória (curta, com emoji).
    Para URLs sozinhos (ex.: link Twitter), usa mensagens sem "lista" para evitar confusão.
    """
    if content and _is_url_only(content) and _URL_ONLY_MESSAGES:
        return random.choice(_URL_ONLY_MESSAGES)
    return random.choice(SEARCHING_MESSAGES)
