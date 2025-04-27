# File: app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, exc, select, update, delete # Importa funções SQLAlchemy necessárias
from typing import List, Optional

from . import models, schemas # Importa nossos modelos e schemas

# --- CRUD Montadoras ---
def get_montadora_by_name(db: Session, nome_montadora: str) -> Optional[models.Montadora]:
    """Busca montadora pelo nome (case-insensitive)."""
    return db.query(models.Montadora).filter(func.upper(models.Montadora.nome_montadora) == nome_montadora.upper()).first()

def get_montadora_by_cod(db: Session, cod_montadora: int) -> Optional[models.Montadora]:
     """Busca montadora pelo código sequencial (101, 102...)."""
     return db.query(models.Montadora).filter(models.Montadora.cod_montadora == cod_montadora).first()

def get_montadora_by_id(db: Session, montadora_id: int) -> Optional[models.Montadora]:
    """Busca montadora pelo ID interno do banco."""
    return db.query(models.Montadora).filter(models.Montadora.id == montadora_id).first()

def get_montadoras(db: Session, skip: int = 0, limit: int = 100) -> List[models.Montadora]:
    """Busca lista de montadoras com paginação."""
    return db.query(models.Montadora).order_by(models.Montadora.cod_montadora).offset(skip).limit(limit).all()

def create_montadora(db: Session, montadora: schemas.MontadoraCreate) -> models.Montadora:
    """Cria uma nova montadora, tratando erros."""
    # Validação do schema Pydantic já ocorreu no endpoint FastAPI
    # Verifica nome existente
    if get_montadora_by_name(db, nome_montadora=montadora.nome_montadora):
        raise ValueError(f"Montadora '{montadora.nome_montadora}' já existe.")

    # Encontra próximo código
    max_cod_result = db.query(func.max(models.Montadora.cod_montadora)).scalar()
    next_cod = 101 if max_cod_result is None or max_cod_result < 101 else max_cod_result + 1

    # Cria e salva
    try:
        # Schema já valida e converte nome para upper case se definido no schema
        db_montadora = models.Montadora(
            cod_montadora=next_cod,
            nome_montadora=montadora.nome_montadora # Assume que o schema já tratou (ou tratar aqui .upper())
        )
        db.add(db_montadora)
        db.commit() # Confirma a transação
        db.refresh(db_montadora) # Atualiza o objeto com dados do DB (ID, data_cadastro)
        return db_montadora
    except exc.SQLAlchemyError as e:
        db.rollback() # Desfaz em caso de erro
        print(f"Erro SQLAlchemy ao criar montadora: {e}") # Log do erro
        raise ValueError(f"Erro interno ao salvar montadora no banco.") # Mensagem genérica para o usuário


# --- CRUD Peças ---

def get_next_cod_final_base(db: Session, cod_montadora: int, cod_modelo: int) -> int:
    """Busca o próximo sequencial FFF (999-000) para Montadora/Modelo."""
    try:
        min_cod_base = db.query(func.min(models.Peca.cod_final_base))\
                         .filter(models.Peca.cod_montadora == cod_montadora, models.Peca.cod_modelo == cod_modelo)\
                         .scalar()

        if min_cod_base is None: return 999
        elif min_cod_base <= 0: return -1 # Limite atingido
        else: return min_cod_base - 1
    except exc.SQLAlchemyError as e:
        print(f"Erro DB ao buscar próximo cod_final_base: {e}")
        return -2 # Código de erro para falha no DB

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

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate, # Recebe dados validados pelo Pydantic
                         cod_montadora: int, # Obtido separadamente (ex: do selectbox)
                         uploaded_images: Optional[List] = None) -> models.Peca:
    """Função principal para criar uma nova variação de peça."""

    # 1. Validar Montadora (Opcional, mas bom)
    db_montadora = get_montadora_by_cod(db, cod_montadora=cod_montadora)
    if not db_montadora:
         raise ValueError(f"Montadora com código {cod_montadora} não encontrada.")

    # 2. Obter próximo código FFF
    next_fff = get_next_cod_final_base(db, cod_montadora, peca_data.cod_modelo)
    if next_fff < 0:
        raise ValueError(f"Limite de códigos base ({'000' if next_fff == -1 else 'Erro DB'}) atingido para Montadora {cod_montadora}/Modelo {peca_data.cod_modelo}.")

    # 3. Construir Códigos
    codigo_base_sku = f"{cod_montadora:03d}{peca_data.cod_modelo:02d}{next_fff:03d}"
    sufixo = None
    if peca_data.tipo_variacao in ['R', 'P']: # Apenas R e P
        sufixo = peca_data.tipo_variacao
    sku_variacao_final = codigo_base_sku + (sufixo if sufixo else "")

    # 4. Verificar se SKU da Variação já existe
    db_peca_existente = get_peca_by_sku_variacao(db, sku_variacao=sku_variacao_final)
    if db_peca_existente:
        raise ValueError(f"SKU da Variação '{sku_variacao_final}' já existe.")

    # 5. Preparar dados para o modelo Peca (excluindo tipo_variacao que não é coluna direta)
    peca_dict = peca_data.model_dump(exclude={"tipo_variacao"}) # Pydantic v2

    # 6. Criar instância do Modelo Peca
    db_peca = models.Peca(
        **peca_dict, # Desempacota os dados do schema
        sku_variacao=sku_variacao_final,
        codigo_base=codigo_base_sku,
        sufixo_variacao=sufixo,
        cod_montadora=cod_montadora, # Garante que está correto
        cod_final_base=next_fff
        # quantidade_estoque já tem default 0 no modelo
        # eh_kit já tem default False no modelo
    )

    # 7. Adicionar ao DB e gerar EAN
    try:
        db.add(db_peca)
        db.flush() # Força o DB a atribuir um ID para db_peca ANTES do commit

        peca_id = db_peca.id
        if not peca_id:
            raise ValueError("Não foi possível obter o ID da peça após adicionar.")

        ean13_gerado = generate_ean13(peca_id)
        if ean13_gerado:
            db_peca.codigo_ean13 = ean13_gerado # Atualiza o objeto antes do commit

        # 8. Salvar Imagens (se houver)
        # (A lógica de salvar imagens pode vir aqui ou ser chamada depois)
        # ... (Lógica de salvar arquivos e criar models.PecaImagem) ...

        db.commit() # Confirma tudo
        db.refresh(db_peca) # Recarrega dados do DB
        return db_peca

    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro SQLAlchemy ao criar peça: {e}")
        raise ValueError(f"Erro interno ao salvar variação da peça.")


# --- CRUD Estoque (Adicionar depois) ---
# def registrar_movimentacao_crud(...)
# def get_movimentacoes_crud(...)

# --- CRUD Kits (Adicionar depois) ---
# def set_kit_status_crud(...)
# def add_componente_crud(...)
# def remove_componente_crud(...)
# def get_componentes_crud(...)

# --- CRUD Imagens (Adicionar depois) ---
# def add_imagem_crud(...)
# def remove_imagem_crud(...)
# def get_imagens_crud(...)
