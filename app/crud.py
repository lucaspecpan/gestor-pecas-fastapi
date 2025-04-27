# File: app/crud.py (Atualizado v5.5 - Com Upload Cloudinary)
from sqlalchemy.orm import Session
from sqlalchemy import func, exc, select, update, delete
from typing import List, Optional
import cloudinary # Importa a biblioteca
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException # Para receber arquivos e tratar erros HTTP

from . import models, schemas, config # Importa nossos modelos, schemas e a config do Cloudinary

# --- CRUD Montadoras ---
def get_montadora_by_name(db: Session, nome_montadora: str) -> Optional[models.Montadora]:
    return db.query(models.Montadora).filter(func.upper(models.Montadora.nome_montadora) == nome_montadora.upper()).first()

def get_montadora_by_cod(db: Session, cod_montadora: int) -> Optional[models.Montadora]:
     return db.query(models.Montadora).filter(models.Montadora.cod_montadora == cod_montadora).first()

def get_montadora_by_id(db: Session, montadora_id: int) -> Optional[models.Montadora]:
    return db.query(models.Montadora).filter(models.Montadora.id == montadora_id).first()

def get_montadoras(db: Session, skip: int = 0, limit: int = 100) -> List[models.Montadora]:
    return db.query(models.Montadora).order_by(models.Montadora.cod_montadora).offset(skip).limit(limit).all()

def create_montadora(db: Session, montadora: schemas.MontadoraCreate) -> models.Montadora:
    if get_montadora_by_name(db, nome_montadora=montadora.nome_montadora):
        raise ValueError(f"Montadora '{montadora.nome_montadora}' já existe.")
    max_cod_result = db.query(func.max(models.Montadora.cod_montadora)).scalar()
    next_cod = 101 if max_cod_result is None or max_cod_result < 101 else max_cod_result + 1
    try:
        db_montadora = models.Montadora(cod_montadora=next_cod, nome_montadora=montadora.nome_montadora)
        db.add(db_montadora); db.commit(); db.refresh(db_montadora)
        return db_montadora
    except exc.SQLAlchemyError as e: db.rollback(); raise ValueError(f"Erro DB: {e}")


# --- CRUD Peças ---

def get_next_cod_final_base(db: Session, cod_montadora: int, cod_modelo: int) -> int:
    """Busca o próximo sequencial FFF (999-000) para Montadora/Modelo."""
    try:
        min_cod_base = db.query(func.min(models.Peca.cod_final_base))\
                         .filter(models.Peca.cod_montadora == cod_montadora, models.Peca.cod_modelo == cod_modelo)\
                         .scalar()
        if min_cod_base is None: return 999
        elif min_cod_base <= 0: return -1 # Limite
        else: return min_cod_base - 1
    except exc.SQLAlchemyError as e: print(f"Erro DB get_next_cod_final_base: {e}"); return -2 # Erro DB

def get_peca_by_sku_variacao(db: Session, sku_variacao: str) -> Optional[models.Peca]:
    """Busca uma variação de peça pelo seu SKU completo (8 ou 9 dígitos)."""
    return db.query(models.Peca).filter(models.Peca.sku_variacao == sku_variacao).first()

def search_pecas_crud(db: Session, search_term: str, skip: int = 0, limit: int = 50) -> List[models.Peca]:
    """Busca peças por SKU Variação, Base, Descrição ou OEM."""
    like_term = f"%{search_term}%"
    query = db.query(models.Peca).join(models.Montadora)\
            .filter(
                models.Peca.sku_variacao.like(like_term) |
                models.Peca.codigo_base.like(like_term) |
                models.Peca.descricao_peca.like(like_term) |
                models.Peca.codigo_oem.like(like_term)
            )\
            .order_by(models.Peca.codigo_base, models.Peca.sku_variacao)\
            .offset(skip).limit(limit)
    return query.all()

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate, # Schema com dados básicos
                         cod_montadora: int, # ID da montadora
                         image_urls: List[str] = []) -> models.Peca: # Lista de URLs já upadas
    """Cria o registro da peça no banco e associa URLs de imagens."""

    # 1. Validar Montadora
    db_montadora = get_montadora_by_cod(db, cod_montadora=cod_montadora)
    if not db_montadora: raise ValueError(f"Montadora {cod_montadora} não encontrada.")

    # 2. Obter próximo código FFF
    next_fff = get_next_cod_final_base(db, cod_montadora, peca_data.cod_modelo)
    if next_fff < 0: raise ValueError(f"Limite/Erro cód base M/M {cod_montadora}/{peca_data.cod_modelo} ({next_fff}).")

    # 3. Construir Códigos
    codigo_base_sku = f"{cod_montadora:03d}{peca_data.cod_modelo:02d}{next_fff:03d}"
    sufixo = None
    if peca_data.tipo_variacao in ['R', 'P']: sufixo = peca_data.tipo_variacao
    sku_variacao_final = codigo_base_sku + (sufixo if sufixo else "")

    # 4. Verificar se SKU da Variação já existe
    if get_peca_by_sku_variacao(db, sku_variacao=sku_variacao_final):
        raise ValueError(f"SKU Variação '{sku_variacao_final}' já existe.")

    # 5. Preparar dados e Criar instância Peca
    peca_db_data = peca_data.model_dump(exclude={"tipo_variacao"}) # Exclui campo que não é coluna direta
    db_peca = models.Peca(
        **peca_db_data,
        sku_variacao=sku_variacao_final,
        codigo_base=codigo_base_sku,
        sufixo_variacao=sufixo,
        cod_montadora=cod_montadora,
        cod_final_base=next_fff,
        qtd_para_reparar=peca_data.qtd_para_reparar or 0 # Garante que não seja None
        # quantidade_estoque e eh_kit usam default do modelo
    )

    # 6. Adicionar Peça e gerar EAN
    try:
        db.add(db_peca)
        db.flush() # Obtem o ID antes do commit
        peca_id = db_peca.id
        if not peca_id: raise ValueError("Falha ao obter ID da peça.")

        ean13 = generate_ean13(peca_id)
        if ean13: db_peca.codigo_ean13 = ean13

        # 7. Adicionar referências das imagens (URLs já vieram do upload)
        for img_url in image_urls:
            if img_url: # Garante que a URL não seja vazia
                db_imagem = models.PecaImagem(peca_id=peca_id, url_imagem=img_url)
                db.add(db_imagem)

        db.commit()
        db.refresh(db_peca)
        return db_peca

    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro SQLAlchemy criar peça: {e}")
        raise ValueError(f"Erro interno ao salvar variação.")


# --- CRUD Estoque (Adicionar depois) ---
# def registrar_movimentacao_crud(...)
# def get_movimentacoes_crud(...)

# --- CRUD Kits (Adicionar depois) ---
# def set_kit_status_crud(...)
# def add_componente_crud(...)
# def remove_componente_crud(...)
# def get_componentes_crud(...)

# --- CRUD Imagens (Se precisar de mais operações como deletar) ---
# def remove_imagem_crud(...)


# --- Função de Upload para Cloudinary ---
async def upload_image_to_cloudinary(file: UploadFile) -> Optional[str]:
    """Faz upload de um arquivo para Cloudinary e retorna a URL segura."""
    if not config.cloudinary_configured:
         print("AVISO: Cloudinary não configurado. Upload pulado.")
         # Poderia retornar um erro mais explícito para a interface?
         # raise HTTPException(status_code=501, detail="Cloudinary não configurado no servidor.")
         return None # Ou retorna None para indicar falha silenciosa

    try:
        # Lê o conteúdo do arquivo em memória
        contents = await file.read()
        # Faz o upload para Cloudinary
