"""Catálogo de tarefas de limpeza pré-definidas. frequency: weekly | bi-weekly."""

CHORE_CATALOG: dict[str, dict] = {
    # Limpeza geral
    "limpar_banheiro": {"name": "Limpar banheiro (sanita, lavatório, box, chão)", "category": "limpeza_geral"},
    "limpar_quarto": {"name": "Limpar quarto (varrer, tirar pó, organizar cama)", "category": "limpeza_geral"},
    "limpar_sala": {"name": "Limpar sala de estar", "category": "limpeza_geral"},
    "limpar_cozinha": {"name": "Limpar cozinha (bancadas, fogão, chão)", "category": "limpeza_geral"},
    "limpar_varanda": {"name": "Limpar varanda", "category": "limpeza_geral"},
    "limpar_quintal": {"name": "Limpar quintal", "category": "limpeza_geral"},
    "lavar_garagem": {"name": "Lavar a garagem", "category": "limpeza_geral"},
    "tirar_po_moveis": {"name": "Tirar o pó dos móveis", "category": "limpeza_geral"},
    "aspirar_casa": {"name": "Aspirar a casa", "category": "limpeza_geral"},
    "varrer_casa": {"name": "Varrer a casa", "category": "limpeza_geral"},
    "passar_pano_chao": {"name": "Passar pano no chão", "category": "limpeza_geral"},
    "limpar_janelas": {"name": "Limpar janelas", "category": "limpeza_geral"},
    "limpar_espelhos": {"name": "Limpar espelhos", "category": "limpeza_geral"},
    "limpar_portas_macanetas": {"name": "Limpar portas e maçanetas", "category": "limpeza_geral"},
    "limpar_interruptores": {"name": "Limpar interruptores e tomadas", "category": "limpeza_geral"},
    "limpar_rodapes": {"name": "Limpar rodapés", "category": "limpeza_geral"},
    # Cozinha / alimentação
    "cozinhar": {"name": "Cozinhar (refeições do dia)", "category": "cozinha"},
    "fazer_marmita": {"name": "Fazer marmita (preparação para a semana)", "category": "cozinha"},
    "lavar_louca": {"name": "Lavar louça", "category": "cozinha"},
    "guardar_louca": {"name": "Guardar louça limpa", "category": "cozinha"},
    "limpar_geladeira": {"name": "Limpar geladeira / frigorífico", "category": "cozinha"},
    "organizar_despensa": {"name": "Organizar despensa", "category": "cozinha"},
    "jogar_comida_fora": {"name": "Jogar fora comida estragada", "category": "cozinha"},
    "lista_compras": {"name": "Fazer lista de compras", "category": "cozinha"},
    "compras_supermercado": {"name": "Fazer compras de supermercado", "category": "cozinha"},
    # Lavanderia
    "lavar_roupa": {"name": "Lavar roupa", "category": "lavanderia"},
    "estender_roupa": {"name": "Estender roupa", "category": "lavanderia"},
    "recolher_roupa": {"name": "Recolher roupa do estendal", "category": "lavanderia"},
    "dobrar_roupa": {"name": "Dobrar roupa", "category": "lavanderia"},
    "guardar_roupa": {"name": "Guardar roupa", "category": "lavanderia"},
    "passar_roupa": {"name": "Passar roupa a ferro", "category": "lavanderia"},
    "trocar_roupa_cama": {"name": "Trocar roupa de cama", "category": "lavanderia"},
    "trocar_toalhas": {"name": "Trocar toalhas de banho", "category": "lavanderia"},
    # Banheiro / higiene
    "limpar_vaso": {"name": "Limpar vaso sanitário", "category": "banheiro"},
    "limpar_box": {"name": "Limpar box / chuveiro", "category": "banheiro"},
    "limpar_lavatorio": {"name": "Limpar lavatório", "category": "banheiro"},
    "repor_papel": {"name": "Repor papel higiénico", "category": "banheiro"},
    "repor_sabonete": {"name": "Repor sabonete / shampoo", "category": "banheiro"},
    "lavar_tapete_banheiro": {"name": "Lavar tapete do banheiro", "category": "banheiro"},
    # Organização
    "organizar_guarda_roupa": {"name": "Organizar guarda-roupa / roupeiro", "category": "organizacao"},
    "organizar_gavetas": {"name": "Organizar gavetas", "category": "organizacao"},
    "organizar_documentos": {"name": "Organizar documentos / papéis", "category": "organizacao"},
    "organizar_sapatos": {"name": "Organizar sapatos", "category": "organizacao"},
    "destralhar": {"name": "Destralhar (doar/jogar fora)", "category": "organizacao"},
    "arrumar_brinquedos": {"name": "Arrumar brinquedos", "category": "organizacao"},
    "organizar_escritorio": {"name": "Organizar área de trabalho / escritório", "category": "organizacao"},
    # Lixo e reciclagem
    "levar_lixo": {"name": "Levar o lixo ao contentor", "category": "lixo"},
    "separar_reciclavel": {"name": "Separar lixo reciclável", "category": "lixo"},
    "levar_reciclaveis": {"name": "Levar recicláveis ao ecoponto", "category": "lixo"},
    "trocar_sacos_lixo": {"name": "Trocar sacos de lixo", "category": "lixo"},
    # Pets
    "limpar_sujeira_pet": {"name": "Limpar sujeira de pet", "category": "pets"},
    "passear_pet": {"name": "Levar pet para passear", "category": "pets"},
    "comida_pet": {"name": "Dar comida ao pet", "category": "pets"},
    "agua_pet": {"name": "Trocar água do pet", "category": "pets"},
    "caixa_areia": {"name": "Limpar caixa de areia / tapete higiênico", "category": "pets"},
    "escovar_pet": {"name": "Escovar pelo do pet", "category": "pets"},
    # Exterior
    "regar_plantas": {"name": "Regar plantas", "category": "exterior"},
    "podar_plantas": {"name": "Podar plantas pequenas", "category": "exterior"},
    "varrer_entrada": {"name": "Varrear entrada / corredor", "category": "exterior"},
    "limpar_moveis_exterior": {"name": "Limpar móveis de exterior", "category": "exterior"},
    "limpar_grelha": {"name": "Limpar grelha / churrasqueira", "category": "exterior"},
    "verificar_lampadas": {"name": "Verificar lâmpadas queimadas", "category": "exterior"},
    "trocar_lampadas": {"name": "Trocar lâmpadas", "category": "exterior"},
}

CATEGORY_NAMES = {
    "limpeza_geral": "Limpeza geral",
    "cozinha": "Cozinha / alimentação",
    "lavanderia": "Lavanderia / roupas",
    "banheiro": "Banheiro / higiene",
    "organizacao": "Organização e arrumação",
    "lixo": "Lixo e reciclagem",
    "pets": "Pets",
    "exterior": "Exterior / manutenção",
}


def get_chore_name(slug: str) -> str:
    """Retorna o nome legível da tarefa ou o slug se não existir."""
    entry = CHORE_CATALOG.get(slug)
    return (entry and entry.get("name")) or slug.replace("_", " ").title()


def list_catalog_by_category() -> dict[str, list[tuple[str, str]]]:
    """Retorna {category: [(slug, name), ...]}."""
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for slug, data in CHORE_CATALOG.items():
        cat = data.get("category", "outro")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append((slug, data.get("name", slug)))
    return by_cat
