# File: app/crud.py (Versão 5.5 - CRUD Completo)
from sqlalchemy.orm import Session
from sqlalchemy import func, exc, select, update, delete
from typing import List, Optional
import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException

from . import models, schemas, config # Importa nossos módulos

# --- CRUD Montadoras ---
# (Funções get_montadora_by_name, get_montadora_by_cod, get_montadora_by_id,
#  get_montadoras, create_montadora - Mantidas como na versão anterior)
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
    except exc.SQLAlchemyError as e: print(f"Erro DB get_next_cod_final_base: {e}"); return -2

def get_peca_by_id(db: Session, peca_id: int) -> Optional[models.Peca]:
    """Busca uma variação de peça pelo seu ID interno."""
    return db.query(models.Peca).filter(models.Peca.id == peca_id).first()

def get_peca_by_sku_variacao(db: Session, sku_variacao: str) -> Optional[models.Peca]:
    """Busca uma variação de peça pelo seu SKU completo (8 ou 9 dígitos)."""
    return db.query(models.Peca).filter(models.Peca.sku_variacao == sku_variacao).first()

def search_pecas_crud(db: Session, search_term: str, skip: int = 0, limit: int = 50) -> List[models.Peca]:
    """Busca peças por SKU Variação, Base, Descrição ou OEM."""
    like_term = f"%{search_term}%"
    try:
        query = db.query(models.Peca).join(models.Montadora)\
                .filter(
                    models.Peca.sku_variacao.like(like_term) |
                    models.Peca.codigo_base.like(like_term) |
                    models.Peca.descricao_peca.like(like_term) |
                    models.Peca.codigo_oem.like(like_term) |
                    models.Montadora.nome_montadora.like(like_term) # Busca por nome da montadora também
                )\
                .order_by(models.Peca.codigo_base, models.Peca.sku_variacao)\
                .offset(skip).limit(limit)
        return query.all()
    except exc.SQLAlchemyError as e: print(f"Erro DB search_pecas_crud: {e}"); return []

def get_pecas_list(db: Session, skip: int = 0, limit: int = 100) -> List[models.Peca]:
    """Busca uma lista paginada de peças/variações."""
    try:
        return db.query(models.Peca)\
                 .order_by(models.Peca.codigo_base, models.Peca.sku_variacao)\
                 .offset(skip)\
                 .limit(limit)\
                 .all()
    except exc.SQLAlchemyError as e: print(f"Erro DB listar peças: {e}"); return []

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate,
                         cod_montadora: int, image_urls: List[str] = []) -> models.Peca:
    """Cria o registro da peça e associa URLs de imagens."""
    db_montadora = get_montadora_by_cod(db, cod_montadora=cod_montadora)
    if not db_montadora: raise ValueError(f"Montadora {cod_montadora} não encontrada.")

    next_fff = get_next_cod_final_base(db, cod_montadora, peca_data.cod_modelo)
    if next_fff < 0: raise ValueError(f"Limite/Erro cód base M/M {cod_montadora}/{peca_data.cod_modelo} ({next_fff}).")

    codigo_base_sku = f"{cod_montadora:03d}{peca_data.cod_modelo:02d}{next_fff:03d}"
    sufixo = peca_data.tipo_variacao if peca_data.tipo_variacao in ['R', 'P'] else None
    sku_variacao_final = codigo_base_sku + (sufixo if sufixo else "")

    if get_peca_by_sku_variacao(db, sku_variacao=sku_variacao_final):
        raise ValueError(f"SKU Variação '{sku_variacao_final}' já existe.")

    # Prepara dados: exclui 'tipo_variacao' e garante defaults corretos
    peca_db_data = peca_data.model_dump(exclude={"tipo_variacao"})
    peca_db_data['qtd_para_reparar'] = peca_db_data.get('qtd_para_reparar', 0) or 0
    peca_db_data['preco_venda'] = peca_db_data.get('preco_venda') # Mantém None se não fornecido
    # Converte data_ultima_compra se necessário (schema já deve ter feito, mas garante)
    if isinstance(peca_db_data.get('data_ultima_compra'), datetime.date):
        peca_db_data['data_ultima_compra'] = peca_db_data['data_ultima_compra'].strftime('%Y-%m-%d')


    db_peca = models.Peca(
        **peca_db_data,
        sku_variacao=sku_variacao_final, codigo_base=codigo_base_sku, sufixo_variacao=sufixo,
        cod_montadora=cod_montadora, cod_final_base=next_fff
    )

    try:
        db.add(db_peca); db.flush()
        peca_id = db_peca.id
        if not peca_id: raise ValueError("Falha ao obter ID da peça.")

        ean13 = generate_ean13(peca_id)
        if ean13: db_peca.codigo_ean13 = ean13

        for img_url in image_urls:
            if img_url: db.add(models.PecaImagem(peca_id=peca_id, url_imagem=img_url))

        db.commit(); db.refresh(db_peca)
        return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA criar peça: {e}"); raise ValueError(f"Erro interno salvar variação.")

# --- TODO: Adicionar funções update_peca_variacao e delete_peca_variacao ---


# --- CRUD Estoque ---
def registrar_movimentacao_crud(db: Session, peca_id: int, tipo_mov: str, quantidade: int, observacao: Optional[str]):
    """Registra movimentação e atualiza estoque (adaptado)."""
    # Validação básica (melhorar conforme necessidade)
    if not peca_id or tipo_mov not in ['Entrada', 'Saida', 'Ajuste'] or not isinstance(quantidade, int) or quantidade < 0:
        raise ValueError("Dados inválidos para movimentação.")
    if tipo_mov != 'Ajuste' and quantidade <= 0:
         raise ValueError("Qtd deve ser > 0 para Entrada/Saída.")

    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca:
        raise ValueError(f"Peça com ID {peca_id} não encontrada.")

    try:
        # Insere movimentação
        db_mov = models.MovimentacaoEstoque(peca_id=peca_id, tipo_movimentacao=tipo_mov, quantidade=quantidade, observacao=observacao)
        db.add(db_mov)

        # Atualiza estoque
        if tipo_mov == 'Entrada':
            db_peca.quantidade_estoque = (db_peca.quantidade_estoque or 0) + quantidade
        elif tipo_mov == 'Saida':
            estoque_atual = db_peca.quantidade_estoque or 0
            # Permitir estoque negativo por enquanto
            db_peca.quantidade_estoque = estoque_atual - quantidade
        elif tipo_mov == 'Ajuste':
            db_peca.quantidade_estoque = quantidade # Ajuste define o valor

        db.commit()
        db.refresh(db_peca) # Atualiza o objeto peça com novo estoque
        return db_peca # Retorna a peça atualizada

    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro DB registrar movimentação: {e}")
        raise ValueError("Erro interno ao registrar movimentação.")

def get_movimentacoes_crud(db: Session, peca_id: int, skip: int = 0, limit: int = 50) -> List[models.MovimentacaoEstoque]:
    """Busca histórico de movimentações de uma peça."""
    try:
        return db.query(models.MovimentacaoEstoque)\
                 .filter(models.MovimentacaoEstoque.peca_id == peca_id)\
                 .order_by(models.MovimentacaoEstoque.data_movimentacao.desc())\
                 .offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB buscar histórico: {e}"); return []


# --- CRUD Kits ---
def set_kit_status_crud(db: Session, peca_id: int, eh_kit: bool):
    """Marca ou desmarca uma peça como kit (adaptado)."""
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try:
        db_peca.eh_kit = eh_kit
        if not eh_kit: # Se desmarcando, remove componentes
            db.query(models.ComponenteKit).filter(models.ComponenteKit.kit_peca_id == peca_id).delete()
        db.commit()
        return True
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB set kit status: {e}"); return False

def get_componentes_crud(db: Session, kit_peca_id: int) -> List[models.ComponenteKit]:
    """Busca os componentes de um kit (adaptado)."""
    try:
        return db.query(models.ComponenteKit)\
                 .filter(models.ComponenteKit.kit_peca_id == kit_peca_id)\
                 .options(selectinload(models.ComponenteKit.componente))\
                 .order_by(models.ComponenteKit.id).all() # Ordena pela ordem de adição ou SKU do componente?
    except exc.SQLAlchemyError as e: print(f"Erro DB get componentes: {e}"); return []

def add_componente_crud(db: Session, kit_peca_id: int, componente_peca_id: int, quantidade: int):
    """Adiciona um componente a um kit (adaptado)."""
    if not isinstance(quantidade, int) or quantidade <= 0: raise ValueError("Quantidade inválida.")
    if kit_peca_id == componente_peca_id: raise ValueError("Kit não pode ser componente dele.")

    db_kit = get_peca_by_id(db, kit_peca_id)
    db_comp = get_peca_by_id(db, componente_peca_id)
    if not db_kit or not db_comp: raise ValueError("Peça Kit ou Componente não encontrada.")
    if not db_kit.eh_kit: raise ValueError("Peça principal não está marcada como Kit.")
    if db_comp.eh_kit: raise ValueError("Não é possível adicionar um Kit como componente.")

    try:
        # Verifica se já existe para dar UPDATE ou INSERT
        componente_existente = db.query(models.ComponenteKit)\
                                 .filter_by(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id)\
                                 .first()
        if componente_existente:
            componente_existente.quantidade_componente = quantidade
        else:
            db_componente = models.ComponenteKit(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id, quantidade_componente=quantidade)
            db.add(db_componente)
        db.commit()
        return True
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB add componente: {e}"); raise ValueError("Erro interno ao adicionar componente.")

def remove_componente_crud(db: Session, componente_kit_id: int):
    """Remove um componente de um kit pelo ID da linha na tabela componentes_kit (adaptado)."""
    try:
        componente = db.query(models.ComponenteKit).filter(models.ComponenteKit.id == componente_kit_id).first()
        if componente:
            db.delete(componente); db.commit(); return True
        else: return False # Não encontrado
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB remove componente: {e}"); return False


# --- CRUD Imagens ---
async def upload_image_to_cloudinary(file: UploadFile) -> Optional[str]:
    """Faz upload para Cloudinary."""
    # Verifica se Cloudinary foi configurado em config.py
    if not config.cloudinary_configured:
         print("AVISO: Cloudinary não configurado. Upload pulado.")
         # Em vez de retornar None, podemos levantar um erro que o endpoint captura
         raise HTTPException(status_code=501, detail="Cloudinary não configurado no servidor.")
         # return None
    try:
        contents = await file.read()
        # Define uma pasta e talvez otimizações no upload
        upload_options = {
             "folder": "gestor_pecas",
             "resource_type": "image",
             # Exemplo de otimização no upload (pode pesar no tempo de upload)
             #"transformation": [{'width': 1500, 'height': 1500, 'crop': 'limit'}, {'quality': "auto:good"}]
             "overwrite": True, # Permite sobrescrever se gerar public_id igual? Melhor evitar.
             "unique_filename": True # Garante nomes únicos no Cloudinary
        }
        upload_result = cloudinary.uploader.upload(contents, **upload_options)
        url = upload_result.get("secure_url")
        if url: print(f"Upload Cloudinary OK: {url}")
        return url
    except Exception as e:
        print(f"ERRO Upload Cloudinary: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no upload da imagem: {e}")
        # return None

def remove_imagem_crud(db: Session, imagem_id: int):
    """Remove a referência da imagem do banco. NÃO deleta do Cloudinary por padrão."""
    try:
        imagem = db.query(models.PecaImagem).filter(models.PecaImagem.id == imagem_id).first()
        if imagem:
             # Opcional: Tentar deletar do Cloudinary ANTES de deletar do DB
             # try:
             #    public_id = ... # Precisa extrair o public_id da URL da imagem
             #    if public_id and config.cloudinary_configured:
             #       cloudinary.api.delete_resources([public_id], resource_type="image")
             #       print(f"Imagem {public_id} deletada do Cloudinary.")
             # except Exception as cloud_e:
             #    print(f"Aviso: Falha ao deletar imagem ID {imagem_id} do Cloudinary: {cloud_e}")
             #    # Continuar para deletar do DB mesmo assim? Ou parar? Decidir a política.

             db.delete(imagem)
             db.commit()
             return True
        else:
             return False # Imagem não encontrada
    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro DB ao remover imagem: {e}")
        return False

def get_imagens_crud(db: Session, peca_id: int) -> List[models.PecaImagem]:
    """Busca as imagens associadas a uma peça."""
    try:
        return db.query(models.PecaImagem)\
                 .filter(models.PecaImagem.peca_id == peca_id)\
                 .order_by(models.PecaImagem.id)\
                 .all()
    except exc.SQLAlchemyError as e: print(f"Erro DB buscar imagens: {e}"); return []
