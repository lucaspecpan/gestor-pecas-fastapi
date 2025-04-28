# File: app/crud.py (Versão 5.14 - Correção Final Try/Except)
from sqlalchemy.orm import Session, joinedload, load_only, selectinload
from sqlalchemy import func, exc, select, update, delete
from typing import List, Optional, Dict, Any
import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException
from datetime import date
from barcode import EAN13

# Importa de forma absoluta a partir da raiz do pacote 'app'
from app import models, schemas, config

# --- Função Auxiliar EAN13 ---
def generate_ean13(internal_id: int) -> Optional[str]:
    if not internal_id: return None
    try: base_number_str = f"290{internal_id:09d}"[:12]; ean = EAN13(base_number_str); return ean.ean13
    except Exception as e: print(f"AVISO: Erro gerar EAN p/ ID {internal_id}: {e}"); return None

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
    nome_upper = montadora.nome_montadora
    if get_montadora_by_name(db, nome_montadora=nome_upper): raise ValueError(f"Montadora '{nome_upper}' já existe.")
    max_cod = db.query(func.max(models.Montadora.cod_montadora)).scalar(); next_cod = 101 if max_cod is None or max_cod < 101 else max_cod + 1
    try: db_m = models.Montadora(cod_montadora=next_cod, nome_montadora=nome_upper); db.add(db_m); db.commit(); db.refresh(db_m); return db_m
    except exc.SQLAlchemyError as e: db.rollback(); raise ValueError(f"Erro DB: {e}")

# --- CRUD ModeloVeiculo ---
def get_modelo_by_nome_and_montadora(db: Session, nome_modelo: str, cod_montadora: int) -> Optional[models.ModeloVeiculo]:
    return db.query(models.ModeloVeiculo).filter(models.ModeloVeiculo.cod_montadora == cod_montadora, func.upper(models.ModeloVeiculo.nome_modelo) == nome_modelo.upper()).first()
def get_next_modelo_sequencial(db: Session, cod_montadora: int) -> int:
    max_seq = db.query(func.max(models.ModeloVeiculo.cod_sequencial_modelo)).filter(models.ModeloVeiculo.cod_montadora == cod_montadora).scalar()
    return (max_seq or 0) + 1
def get_or_create_modelo(db: Session, nome_modelo: str, cod_montadora: int) -> models.ModeloVeiculo:
    nome_upper = nome_modelo.strip().upper();
    if not nome_upper: raise ValueError("Nome modelo vazio.")
    db_mont = get_montadora_by_cod(db, cod_montadora=cod_montadora);
    if not db_mont: raise ValueError(f"Montadora {cod_montadora} não encontrada.")
    db_mod = get_modelo_by_nome_and_montadora(db, nome_modelo=nome_upper, cod_montadora=cod_montadora)
    if db_mod: return db_mod
    else:
        try:
            next_seq = get_next_modelo_sequencial(db, cod_montadora=cod_montadora)
            novo_mod = models.ModeloVeiculo( cod_montadora=cod_montadora, nome_modelo=nome_upper, cod_sequencial_modelo=next_seq )
            db.add(novo_mod); db.commit(); db.refresh(novo_mod); print(f"Novo modelo: {novo_mod.nome_modelo} (Seq:{next_seq}) p/ Mont {cod_montadora}"); return novo_mod
        except exc.SQLAlchemyError as e:
            db.rollback(); print(f"Erro DB criar modelo {nome_upper}: {e}")
            db_mod_retry = get_modelo_by_nome_and_montadora(db, nome_modelo=nome_upper, cod_montadora=cod_montadora)
            if db_mod_retry: return db_mod_retry
            raise ValueError(f"Erro interno criar/buscar modelo '{nome_upper}'.")

# --- CRUD Peças ---
def get_next_cod_final_item(db: Session, cod_montadora: int, modelo_id: int, nome_item: str) -> int:
    nome_item_upper = nome_item.strip().upper();
    if not nome_item_upper: raise ValueError("Nome Item vazio.")
    try:
        min_cod = db.query(func.min(models.Peca.cod_final_item)).filter(models.Peca.cod_montadora == cod_montadora, models.Peca.cod_modelo == modelo_id, func.upper(models.Peca.nome_item) == nome_item_upper).scalar()
        if min_cod is None: return 999
        elif min_cod <= 0: return -1
        else: return min_cod - 1
    except exc.SQLAlchemyError as e: print(f"Erro DB get_next_cod_final_item: {e}"); return -2

def get_peca_by_id(db: Session, peca_id: int) -> Optional[models.Peca]:
    return db.query(models.Peca).options(joinedload(models.Peca.montadora_rel), joinedload(models.Peca.modelo_rel)).filter(models.Peca.id == peca_id).first()
def get_peca_by_sku_variacao(db: Session, sku_variacao: str) -> Optional[models.Peca]:
    return db.query(models.Peca).options(joinedload(models.Peca.montadora_rel), joinedload(models.Peca.modelo_rel)).filter(models.Peca.sku_variacao == sku_variacao.upper()).first()
def search_pecas_crud(db: Session, search_term: str, skip: int = 0, limit: int = 50) -> List[models.Peca]:
    like_term = f"%{search_term.upper()}%"
    try:
        q = db.query(models.Peca).join(models.Peca.montadora_rel).join(models.Peca.modelo_rel)\
              .filter( models.Peca.sku_variacao.like(like_term) | models.Peca.codigo_base.like(like_term) |
                       models.Peca.descricao_peca.like(like_term) | models.Peca.codigo_oem.like(like_term) |
                       models.Peca.nome_item.like(like_term) | models.Montadora.nome_montadora.like(like_term) |
                       models.ModeloVeiculo.nome_modelo.like(like_term) )\
              .order_by(models.Peca.codigo_base, models.Peca.sku_variacao).offset(skip).limit(limit)
        return q.all()
    except exc.SQLAlchemyError as e: print(f"Erro DB search: {e}"); return []
def get_pecas_list(db: Session, skip: int = 0, limit: int = 100) -> List[models.Peca]:
    try:
        return db.query(models.Peca)\
                 .options(joinedload(models.Peca.montadora_rel).load_only(models.Montadora.nome_montadora),
                          joinedload(models.Peca.modelo_rel).load_only(models.ModeloVeiculo.nome_modelo))\
                 .order_by(models.Peca.codigo_base, models.Peca.sku_variacao).offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB listar: {e}"); return []

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate, image_urls: List[str] = []) -> models.Peca:
    db_modelo = get_or_create_modelo(db, nome_modelo=peca_data.nome_modelo, cod_montadora=peca_data.cod_montadora)
    cod_modelo_id = db_modelo.id; cod_seq_mod = db_modelo.cod_sequencial_modelo
    next_fff = get_next_cod_final_item(db, peca_data.cod_montadora, cod_modelo_id, peca_data.nome_item)
    if next_fff < 0: raise ValueError(f"Limite/Erro({next_fff}) cód item p/ M{peca_data.cod_montadora}/Mod{cod_seq_mod:02d}/{peca_data.nome_item}.")
    codigo_base_sku = f"{peca_data.cod_montadora:03d}{cod_seq_mod:02d}{next_fff:03d}"
    sufixo = peca_data.tipo_variacao if peca_data.tipo_variacao in ['R', 'P'] else None
    sku_variacao_final = codigo_base_sku + (sufixo if sufixo else "")
    if get_peca_by_sku_variacao(db, sku_variacao=sku_variacao_final): raise ValueError(f"SKU Variação '{sku_variacao_final}' já existe.")

    peca_db_data = peca_data.model_dump(exclude={"tipo_variacao", "cod_montadora", "nome_modelo", "quantidade_estoque"})
    peca_db_data['preco_venda'] = peca_db_data.get('preco_venda')
    if isinstance(peca_db_data.get('data_ultima_compra'), date): peca_db_data['data_ultima_compra'] = peca_db_data['data_ultima_compra'].strftime('%Y-%m-%d')
    elif peca_db_data.get('data_ultima_compra') == '': peca_db_data['data_ultima_compra'] = None
    for key in ['nome_item', 'descricao_peca', 'codigo_oem', 'anos_aplicacao', 'posicao_porta', 'categoria']:
        if key in peca_db_data and isinstance(peca_db_data[key], str): peca_db_data[key] = peca_db_data[key].upper()

    db_peca = models.Peca( **peca_db_data, sku_variacao=sku_variacao_final, codigo_base=codigo_base_sku, sufixo_variacao=sufixo,
                           cod_montadora=peca_data.cod_montadora, cod_modelo=cod_modelo_id, cod_final_item=next_fff,
                           quantidade_estoque = peca_data.quantidade_estoque )
    try:
        db.add(db_peca); db.flush(); peca_id = db_peca.id
        if not peca_id: raise ValueError("Falha obter ID peça.")
        ean13 = generate_ean13(peca_id)
        if ean13: db_peca.codigo_ean13 = ean13
        for img_url in image_urls:
            if img_url and isinstance(img_url, str) and img_url.startswith('http'):
                db.add(models.PecaImagem(peca_id=peca_id, url_imagem=img_url))
            else: print(f"AVISO: URL img inválida p/ ID {peca_id}: {img_url}")
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA criar peça: {e}"); raise ValueError(f"Erro interno salvar variação.")

def update_peca_variacao(db: Session, peca_id: int, peca_update_data: schemas.PecaBase) -> Optional[models.Peca]:
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca: return None
    update_data = peca_update_data.model_dump(exclude_unset=True, exclude={'tipo_variacao', 'cod_modelo', 'nome_item', 'quantidade_estoque'})
    for key in ['descricao_peca', 'codigo_oem', 'anos_aplicacao', 'posicao_porta', 'categoria']:
        if key in update_data and isinstance(update_data[key], str): update_data[key] = update_data[key].upper()
    if 'data_ultima_compra' in update_data:
        dt = update_data['data_ultima_compra']
        if isinstance(dt, date): update_data['data_ultima_compra'] = dt.strftime('%Y-%m-%d')
        elif dt == '' or dt is None: update_data['data_ultima_compra'] = None
        else: raise ValueError("Formato data inválido.")
    try:
        for key, value in update_data.items(): setattr(db_peca, key, value)
        db.add(db_peca); db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA update peça {peca_id}: {e}"); raise ValueError("Erro interno atualizar.")

def delete_peca_variacao(db: Session, peca_id: int) -> bool:
    """Deleta uma variação de peça pelo ID, com tratamento de erro correto."""
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca:
        print(f"Peça ID {peca_id} não encontrada para deleção.")
        return False # Peça não encontrada

    # --- Bloco try/except CORRIGIDO (v5.14) ---
    try:
        # Verificar se é componente de algum kit antes de deletar
        componente_em_kit = db.query(models.ComponenteKit).filter(models.ComponenteKit.componente_peca_id == peca_id).first()
        if componente_em_kit:
            kit_pai = get_peca_by_id(db, componente_em_kit.kit_peca_id)
            sku_kit_pai = kit_pai.sku_variacao if kit_pai else f"ID {componente_em_kit.kit_peca_id}"
            # Levanta um erro que será capturado pelo except ValueError abaixo
            raise ValueError(f"Não pode deletar: Peça é componente do Kit {sku_kit_pai}.")

        # Se passou pela verificação, tenta deletar
        print(f"Deletando peça ID {peca_id}, SKU {db_peca.sku_variacao}...")
        db.delete(db_peca)
        db.commit()
        print(f"Peça ID {peca_id} deletada com sucesso.")
        return True

    except ValueError as ve: # Captura o erro levantado acima ou outros ValueErrors
         db.rollback() # Garante rollback se o erro ocorreu antes do commit
         print(f"Erro de Validação ao deletar peça ID {peca_id}: {ve}")
         raise ve # Repassa o erro para o endpoint tratar

    except exc.IntegrityError as e: # Captura erro de restrição de FK
        db.rollback()
        print(f"Erro de Integridade ao deletar peça ID {peca_id}: {e}")
        raise ValueError(f"Erro de integridade ao deletar: {e}")

    except exc.SQLAlchemyError as e: # Captura outros erros do SQLAlchemy
        db.rollback()
        print(f"Erro SQLAlchemy ao deletar peça ID {peca_id}: {e}")
        raise ValueError("Erro interno ao deletar variação da peça.")
    # --- FIM DA CORREÇÃO ---

# --- CRUD Estoque ---
def registrar_movimentacao_crud(db: Session, peca_id: int, tipo_mov: str, quantidade: int, observacao: Optional[str]):
    if not peca_id or tipo_mov not in ['Entrada', 'Saida', 'Ajuste'] or not isinstance(quantidade, int) or quantidade < 0: raise ValueError("Dados inválidos.")
    if tipo_mov != 'Ajuste' and quantidade <= 0: raise ValueError("Qtd > 0 p/ Entrada/Saída.")
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try:
        db.add(models.MovimentacaoEstoque(peca_id=peca_id, tipo_movimentacao=tipo_mov, quantidade=quantidade, observacao=observacao))
        est_atual = db_peca.quantidade_estoque or 0
        if tipo_mov == 'Entrada': db_peca.quantidade_estoque = est_atual + quantidade
        elif tipo_mov == 'Saida': novo_est = est_atual - quantidade; db_peca.quantidade_estoque = novo_est
        elif tipo_mov == 'Ajuste': db_peca.quantidade_estoque = quantidade
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB mov: {e}"); raise ValueError("Erro interno registrar mov.")
def get_movimentacoes_crud(db: Session, peca_id: int, skip: int = 0, limit: int = 50) -> List[models.MovimentacaoEstoque]:
    try: return db.query(models.MovimentacaoEstoque).filter(models.MovimentacaoEstoque.peca_id == peca_id).order_by(models.MovimentacaoEstoque.data_movimentacao.desc()).offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB hist: {e}"); return []

# --- CRUD Kits ---
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

# --- CRUD Imagens ---
async def upload_image_to_cloudinary(file: UploadFile) -> Optional[str]:
    if not config.cloudinary_configured: raise HTTPException(status_code=501, detail="Cloudinary não configurado.")
    try:
        contents = await file.read(); opts = { "folder": "gestor_pecas", "resource_type": "image", "overwrite": False, "unique_filename": True }
        res = cloudinary.uploader.upload(contents, **opts); url = res.get("secure_url")
        if url: print(f"Upload OK: {url}"); return url
    except Exception as e: print(f"ERRO Upload Cloudinary: {e}"); raise HTTPException(status_code=500, detail=f"Erro upload: {e}")

def remove_imagem_crud(db: Session, imagem_id: int) -> bool:
    """Remove a referência da imagem do banco (usando a correção sugerida)."""
    try:
        img = db.query(models.PecaImagem).filter(models.PecaImagem.id == imagem_id).first()
        if img:
            # Opcional: Tentar deletar do Cloudinary aqui antes do commit
            db.delete(img)
            db.commit()
            return True
        else:
            return False # Imagem não encontrada no DB
    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro DB rem img: {e}")
        return False

def get_imagens_crud(db: Session, peca_id: int) -> List[models.PecaImagem]:
    try: return db.query(models.PecaImagem).filter(models.PecaImagem.peca_id == peca_id).order_by(models.PecaImagem.id).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB get imgs: {e}"); return []

