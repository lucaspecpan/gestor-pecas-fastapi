# File: app/crud.py (Versão 5.7 - Update/Delete Peça)
from sqlalchemy.orm import Session, joinedload, load_only # Importa joinedload/load_only
from sqlalchemy import func, exc, select, update, delete
from typing import List, Optional, Dict, Any # Importa Dict, Any
import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException
from datetime import date

from . import models, schemas, config

# --- CRUD Montadoras (Inalterado) ---
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
    try:
        min_cod_base = db.query(func.min(models.Peca.cod_final_base))\
                         .filter(models.Peca.cod_montadora == cod_montadora, models.Peca.cod_modelo == cod_modelo)\
                         .scalar()
        if min_cod_base is None: return 999
        elif min_cod_base <= 0: return -1
        else: return min_cod_base - 1
    except exc.SQLAlchemyError as e: print(f"Erro DB get_next_cod_final_base: {e}"); return -2

def get_peca_by_id(db: Session, peca_id: int) -> Optional[models.Peca]:
    # Usa joinedload para já trazer a montadora junto, se necessário exibir depois
    return db.query(models.Peca).options(joinedload(models.Peca.montadora)).filter(models.Peca.id == peca_id).first()

def get_peca_by_sku_variacao(db: Session, sku_variacao: str) -> Optional[models.Peca]:
    return db.query(models.Peca).options(joinedload(models.Peca.montadora)).filter(models.Peca.sku_variacao == sku_variacao).first()

def search_pecas_crud(db: Session, search_term: str, skip: int = 0, limit: int = 50) -> List[models.Peca]:
    like_term = f"%{search_term}%"
    try:
        query = db.query(models.Peca).join(models.Montadora)\
                .filter(
                    models.Peca.sku_variacao.like(like_term) |
                    models.Peca.codigo_base.like(like_term) |
                    models.Peca.descricao_peca.like(like_term) |
                    models.Peca.codigo_oem.like(like_term) |
                    models.Peca.categoria.like(like_term) |
                    models.Montadora.nome_montadora.like(like_term)
                )\
                .order_by(models.Peca.codigo_base, models.Peca.sku_variacao)\
                .offset(skip).limit(limit)
        return query.all()
    except exc.SQLAlchemyError as e: print(f"Erro DB search_pecas_crud: {e}"); return []

def get_pecas_list(db: Session, skip: int = 0, limit: int = 100) -> List[models.Peca]:
    try:
        # Opcional: Carregar montadora junto para evitar N+1 queries na listagem
        return db.query(models.Peca)\
                 .options(joinedload(models.Peca.montadora).load_only(models.Montadora.nome_montadora))\
                 .order_by(models.Peca.codigo_base, models.Peca.sku_variacao)\
                 .offset(skip)\
                 .limit(limit)\
                 .all()
    except exc.SQLAlchemyError as e: print(f"Erro DB listar peças: {e}"); return []

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate,
                         cod_montadora: int, image_urls: List[str] = []) -> models.Peca:
    db_montadora = get_montadora_by_cod(db, cod_montadora=cod_montadora)
    if not db_montadora: raise ValueError(f"Montadora {cod_montadora} não encontrada.")
    next_fff = get_next_cod_final_base(db, cod_montadora, peca_data.cod_modelo)
    if next_fff < 0: raise ValueError(f"Limite/Erro cód base M/M {cod_montadora}/{peca_data.cod_modelo} ({next_fff}).")
    codigo_base_sku = f"{cod_montadora:03d}{peca_data.cod_modelo:02d}{next_fff:03d}"
    sufixo = peca_data.tipo_variacao if peca_data.tipo_variacao in ['R', 'P'] else None
    sku_variacao_final = codigo_base_sku + (sufixo if sufixo else "")
    if get_peca_by_sku_variacao(db, sku_variacao=sku_variacao_final):
        raise ValueError(f"SKU Variação '{sku_variacao_final}' já existe.")

    peca_db_data = peca_data.model_dump(exclude={"tipo_variacao", "cod_montadora"}) # Exclui campos que não são colunas diretas ou já tratados
    peca_db_data['qtd_para_reparar'] = peca_db_data.get('qtd_para_reparar') or 0
    peca_db_data['preco_venda'] = peca_db_data.get('preco_venda')
    if isinstance(peca_db_data.get('data_ultima_compra'), date):
        peca_db_data['data_ultima_compra'] = peca_db_data['data_ultima_compra'].strftime('%Y-%m-%d')
    elif peca_db_data.get('data_ultima_compra') == '': peca_db_data['data_ultima_compra'] = None

    db_peca = models.Peca( **peca_db_data, sku_variacao=sku_variacao_final, codigo_base=codigo_base_sku,
                           sufixo_variacao=sufixo, cod_montadora=cod_montadora, cod_final_base=next_fff )
    try:
        db.add(db_peca); db.flush(); peca_id = db_peca.id
        if not peca_id: raise ValueError("Falha obter ID peça.")
        ean13 = generate_ean13(peca_id)
        if ean13: db_peca.codigo_ean13 = ean13
        for img_url in image_urls:
            if img_url and isinstance(img_url, str) and img_url.startswith('http'):
                db.add(models.PecaImagem(peca_id=peca_id, url_imagem=img_url))
            else: print(f"AVISO: URL img inválida ignorada p/ peça ID {peca_id}: {img_url}")
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA criar peça: {e}"); raise ValueError(f"Erro interno salvar variação.")

# --- NOVO: Update Peça ---
def update_peca_variacao(db: Session, peca_id: int, peca_update_data: schemas.PecaBase) -> Optional[models.Peca]:
    """Atualiza os dados de uma variação de peça existente (exceto SKUs e códigos base)."""
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca:
        return None # Ou raise ValueError("Peça não encontrada")

    # Pega os dados do schema Pydantic como um dicionário
    update_data = peca_update_data.model_dump(exclude_unset=True) # Exclui campos não enviados na requisição

    # Remove campos que NÃO devem ser atualizados diretamente aqui
    # (SKUs, códigos base, tipo/sufixo, estoque - estoque é atualizado por movimentação)
    update_data.pop('tipo_variacao', None) # Tipo não deve mudar após criação
    update_data.pop('cod_modelo', None) # Modelo não deve mudar? A discutir.
    # cod_montadora também não deve mudar

    # Formata data se presente
    if 'data_ultima_compra' in update_data:
        dt = update_data['data_ultima_compra']
        if isinstance(dt, date): update_data['data_ultima_compra'] = dt.strftime('%Y-%m-%d')
        elif dt == '' or dt is None: update_data['data_ultima_compra'] = None
        else: raise ValueError("Formato de data inválido para Última Compra.") # Ou trata melhor

    # Atualiza os campos no objeto SQLAlchemy
    for key, value in update_data.items():
        setattr(db_peca, key, value)

    try:
        db.add(db_peca) # Adiciona o objeto modificado à sessão
        db.commit()    # Salva as alterações
        db.refresh(db_peca) # Recarrega o objeto do DB
        return db_peca
    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro SQLAlchemy ao atualizar peça ID {peca_id}: {e}")
        raise ValueError("Erro interno ao atualizar variação da peça.")

# --- NOVO: Delete Peça ---
def delete_peca_variacao(db: Session, peca_id: int) -> bool:
    """Deleta uma variação de peça pelo ID."""
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca:
        return False # Peça não encontrada

    try:
        # O cascade="all, delete-orphan" nos relacionamentos (imagens, movimentações, componentes_do_kit)
        # deve cuidar de deletar os registros relacionados automaticamente quando a peça é deletada.
        # Verificar se há restrições (como ser componente de um kit) que impediriam a deleção.
        if db_peca.kit_onde_eh_componente:
             raise ValueError("Não é possível deletar: esta peça é componente de um ou mais Kits.")

        db.delete(db_peca)
        db.commit()
        return True
    except exc.IntegrityError as e: # Captura erro de restrição de FK (ex: é componente)
        db.rollback()
        print(f"Erro de Integridade ao deletar peça ID {peca_id}: {e}")
        raise ValueError(f"Não é possível deletar: {e}") # Repassa a mensagem de erro
    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro SQLAlchemy ao deletar peça ID {peca_id}: {e}")
        raise ValueError("Erro interno ao deletar variação da peça.")


# --- CRUD Estoque (Inalterado) ---
def registrar_movimentacao_crud(db: Session, peca_id: int, tipo_mov: str, quantidade: int, observacao: Optional[str]):
    if not peca_id or tipo_mov not in ['Entrada', 'Saida', 'Ajuste'] or not isinstance(quantidade, int) or quantidade < 0: raise ValueError("Dados inválidos.")
    if tipo_mov != 'Ajuste' and quantidade <= 0: raise ValueError("Qtd > 0 p/ Entrada/Saída.")
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try:
        db.add(models.MovimentacaoEstoque(peca_id=peca_id, tipo_movimentacao=tipo_mov, quantidade=quantidade, observacao=observacao))
        estoque_atual = db_peca.quantidade_estoque or 0
        if tipo_mov == 'Entrada': db_peca.quantidade_estoque = estoque_atual + quantidade
        elif tipo_mov == 'Saida': novo_estoque = estoque_atual - quantidade; db_peca.quantidade_estoque = novo_estoque
        elif tipo_mov == 'Ajuste': db_peca.quantidade_estoque = quantidade
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB mov: {e}"); raise ValueError("Erro interno registrar mov.")

def get_movimentacoes_crud(db: Session, peca_id: int, skip: int = 0, limit: int = 50) -> List[models.MovimentacaoEstoque]:
    try: return db.query(models.MovimentacaoEstoque).filter(models.MovimentacaoEstoque.peca_id == peca_id).order_by(models.MovimentacaoEstoque.data_movimentacao.desc()).offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB hist: {e}"); return []

# --- CRUD Kits (Inalterado) ---
def set_kit_status_crud(db: Session, peca_id: int, eh_kit: bool) -> bool:
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try:
        db_peca.eh_kit = eh_kit
        if not eh_kit: db.query(models.ComponenteKit).filter(models.ComponenteKit.kit_peca_id == peca_id).delete()
        db.commit(); return True
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB kit status: {e}"); return False

def get_componentes_crud(db: Session, kit_peca_id: int) -> List[models.ComponenteKit]:
    db_kit = get_peca_by_id(db, kit_peca_id);
    if not db_kit or not db_kit.eh_kit: print(f"ID {kit_peca_id} não é kit."); return []
    try: return db.query(models.ComponenteKit).filter(models.ComponenteKit.kit_peca_id == kit_peca_id).options(joinedload(models.ComponenteKit.componente).load_only(models.Peca.sku_variacao, models.Peca.descricao_peca)).order_by(models.ComponenteKit.id).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB get comps: {e}"); return []

def add_componente_crud(db: Session, kit_peca_id: int, componente_peca_id: int, quantidade: int) -> bool:
    if not isinstance(quantidade, int) or quantidade <= 0: raise ValueError("Qtd inválida.")
    if kit_peca_id == componente_peca_id: raise ValueError("Kit não pode ser comp. dele.")
    db_kit = get_peca_by_id(db, kit_peca_id); db_comp = get_peca_by_id(db, componente_peca_id)
    if not db_kit or not db_comp: raise ValueError("Kit ou Comp. não encontrado.")
    if not db_kit.eh_kit: raise ValueError("Peça principal não é Kit.")
    if db_comp.eh_kit: raise ValueError("Não adicionar Kit como comp.")
    try:
        comp_ex = db.query(models.ComponenteKit).filter_by(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id).first()
        if comp_ex: comp_ex.quantidade_componente = quantidade
        else: db.add(models.ComponenteKit(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id, quantidade_componente=quantidade))
        db.commit(); return True
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB add comp: {e}"); raise ValueError("Erro interno add comp.")

def remove_componente_crud(db: Session, componente_kit_id: int) -> bool:
    try: rows = db.query(models.ComponenteKit).filter(models.ComponenteKit.id == componente_kit_id).delete(); db.commit(); return rows > 0
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB rem comp: {e}"); return False

# --- CRUD Imagens (Inalterado) ---
async def upload_image_to_cloudinary(file: UploadFile) -> Optional[str]:
    if not config.cloudinary_configured: raise HTTPException(status_code=501, detail="Cloudinary não configurado.")
    try:
        contents = await file.read()
        opts = { "folder": "gestor_pecas", "resource_type": "image", "overwrite": False, "unique_filename": True }
        res = cloudinary.uploader.upload(contents, **opts); url = res.get("secure_url")
        if url: print(f"Upload OK: {url}"); return url
    except Exception as e: print(f"ERRO Upload Cloudinary: {e}"); raise HTTPException(status_code=500, detail=f"Erro upload: {e}")

def remove_imagem_crud(db: Session, imagem_id: int) -> bool:
    try:
        img = db.query(models.PecaImagem).filter(models.PecaImagem.id == imagem_id).first()
        if img: db.delete(img); db.commit(); return True
        else: return False
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB rem img: {e}"); return False

def get_imagens_crud(db: Session, peca_id: int) -> List[models.PecaImagem]:
    try: return db.query(models.PecaImagem).filter(models.PecaImagem.peca_id == peca_id).order_by(models.PecaImagem.id).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB get imgs: {e}"); return []
