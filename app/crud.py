# File: app/crud.py (v5.25 - Correção Final try/except Kit)
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, exc, select, update, delete
from typing import List, Optional
import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException
from datetime import date # Importa date corretamente

# Importa nossos módulos internos
from . import models, schemas, config, database
from barcode import EAN13 # Importa EAN13

# --- CRUD Montadoras (Correto) ---
def get_montadora_by_name(db: Session, nome_montadora: str) -> Optional[models.Montadora]:
    return db.query(models.Montadora).filter(func.upper(models.Montadora.nome_montadora) == nome_montadora.upper()).first()
def get_montadora_by_cod(db: Session, cod_montadora: int) -> Optional[models.Montadora]:
     return db.query(models.Montadora).filter(models.Montadora.cod_montadora == cod_montadora).first()
def get_montadora_by_id(db: Session, montadora_id: int) -> Optional[models.Montadora]:
    return db.query(models.Montadora).filter(models.Montadora.id == montadora_id).first()
def get_montadoras(db: Session, skip: int = 0, limit: int = 1000) -> List[models.Montadora]:
    return db.query(models.Montadora).order_by(models.Montadora.cod_montadora).offset(skip).limit(limit).all()
def create_montadora(db: Session, montadora: schemas.MontadoraCreate) -> models.Montadora:
    if get_montadora_by_name(db, nome_montadora=montadora.nome_montadora): raise ValueError(f"Montadora '{montadora.nome_montadora}' já existe.")
    max_cod = db.query(func.max(models.Montadora.cod_montadora)).scalar(); next_cod = 101 if max_cod is None or max_cod < 101 else max_cod + 1
    try: db_m = models.Montadora(cod_montadora=next_cod, nome_montadora=montadora.nome_montadora); db.add(db_m); db.commit(); db.refresh(db_m); return db_m
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA mont: {e}"); raise ValueError(f"Erro DB.")

# --- CRUD Modelos de Veículo (Correto) ---
def get_modelo_by_nome_and_montadora(db: Session, nome_modelo: str, cod_montadora: int) -> Optional[models.ModeloVeiculo]:
    return db.query(models.ModeloVeiculo).filter(models.ModeloVeiculo.cod_montadora == cod_montadora, func.upper(models.ModeloVeiculo.nome_modelo) == nome_modelo.upper()).first()
def get_next_cod_sequencial_modelo(db: Session, cod_montadora: int) -> int:
    max_seq = db.query(func.max(models.ModeloVeiculo.cod_sequencial_modelo)).filter(models.ModeloVeiculo.cod_montadora == cod_montadora).scalar()
    return (max_seq or 0) + 1
def get_or_create_modelo(db: Session, nome_modelo: str, cod_montadora: int) -> models.ModeloVeiculo:
    db_mont = get_montadora_by_cod(db, cod_montadora);
    if not db_mont: raise ValueError(f"Montadora {cod_montadora} não encontrada.")
    nome_upper = nome_modelo.strip().upper();
    if not nome_upper: raise ValueError("Nome modelo vazio.")
    db_mod = get_modelo_by_nome_and_montadora(db, nome_upper, cod_montadora)
    if db_mod: return db_mod
    else:
        next_seq = get_next_cod_sequencial_modelo(db, cod_montadora)
        try: new_mod = models.ModeloVeiculo(cod_montadora=cod_montadora, nome_modelo=nome_upper, cod_sequencial_modelo=next_seq); db.add(new_mod); db.commit(); db.refresh(new_mod); return new_mod
        except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA mod: {e}"); db_mod_retry = get_modelo_by_nome_and_montadora(db, nome_upper, cod_montadora);
        if db_mod_retry: return db_mod_retry; raise ValueError(f"Erro criar/buscar modelo.")

# --- CRUD Peças (Correto) ---
def get_next_cod_final_item(db: Session, cod_montadora: int, cod_modelo_id: int, nome_item: str) -> int: # Usa cod_modelo_id
    try:
        nome_item_upper = nome_item.strip().upper()
        min_cod = db.query(func.min(models.Peca.cod_final_item)).filter(models.Peca.cod_montadora == cod_montadora, models.Peca.cod_modelo == cod_modelo_id, func.upper(models.Peca.nome_item) == nome_item_upper).scalar() # Filtra por cod_modelo_id
        if min_cod is None: return 999
        elif min_cod <= 0: return -1
        else: return min_cod - 1
    except exc.SQLAlchemyError as e: print(f"Erro DB get_next_fff: {e}"); return -2
def get_peca_by_id(db: Session, peca_id: int) -> Optional[models.Peca]: return db.query(models.Peca).filter(models.Peca.id == peca_id).first()
def get_peca_by_sku_variacao(db: Session, sku_variacao: str) -> Optional[models.Peca]: return db.query(models.Peca).filter(models.Peca.sku_variacao == sku_variacao).first()
def search_pecas_crud(db: Session, search_term: str, skip: int = 0, limit: int = 50) -> List[models.Peca]:
    like = f"%{search_term.upper()}%";
    try:
        q = db.query(models.Peca).join(models.Peca.montadora_rel).join(models.Peca.modelo_veiculo).filter( models.Peca.sku_variacao.like(like) | models.Peca.codigo_base.like(like) | func.upper(models.Peca.descricao_peca).like(like) | func.upper(models.Peca.codigo_oem).like(like) | func.upper(models.Peca.nome_item).like(like) | func.upper(models.Montadora.nome_montadora).like(like) | func.upper(models.ModeloVeiculo.nome_modelo).like(like) ).order_by(models.Peca.codigo_base, models.Peca.sku_variacao).offset(skip).limit(limit); return q.all()
    except exc.SQLAlchemyError as e: print(f"Erro DB search: {e}"); return []
def get_pecas_list(db: Session, skip: int = 0, limit: int = 100) -> List[models.Peca]:
    try: return db.query(models.Peca).options(joinedload(models.Peca.montadora_rel), joinedload(models.Peca.modelo_veiculo)).order_by(models.Peca.codigo_base, models.Peca.sku_variacao).offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB list: {e}"); return []

def create_peca_variacao(db: Session, peca_data: schemas.PecaCreate, image_urls: List[str] = []) -> models.Peca:
    db_modelo = get_or_create_modelo(db, nome_modelo=peca_data.nome_modelo, cod_montadora=peca_data.cod_montadora)
    cod_modelo_id = db_modelo.id; cod_seq_modelo = db_modelo.cod_sequencial_modelo
    next_fff = get_next_cod_final_item(db, peca_data.cod_montadora, cod_modelo_id, peca_data.nome_item)
    if next_fff < 0: raise ValueError(f"Limite/Erro({next_fff}) cód item M{peca_data.cod_montadora}/Mod{cod_seq_modelo:02d}/{peca_data.nome_item}.")
    codigo_base = f"{peca_data.cod_montadora:03d}{cod_seq_modelo:02d}{next_fff:03d}"
    sufixo = peca_data.tipo_variacao if peca_data.tipo_variacao in ['R', 'P'] else None
    sku_variacao = codigo_base + (sufixo if sufixo else "")
    if get_peca_by_sku_variacao(db, sku_variacao=sku_variacao): raise ValueError(f"SKU Variação '{sku_variacao}' já existe.")

    peca_db_data = peca_data.model_dump(exclude={"tipo_variacao", "cod_montadora", "nome_modelo"})
    peca_db_data['preco_venda'] = peca_db_data.get('preco_venda')
    if isinstance(peca_db_data.get('data_ultima_compra'), date): peca_db_data['data_ultima_compra'] = peca_db_data['data_ultima_compra'].strftime('%Y-%m-%d')
    elif not peca_db_data.get('data_ultima_compra'): peca_db_data['data_ultima_compra'] = None

    # Aplica Uppercase antes de criar o objeto
    for key in ['nome_item', 'descricao_peca', 'categoria', 'codigo_oem', 'anos_aplicacao', 'posicao_porta']:
         if key in peca_db_data and isinstance(peca_db_data[key], str):
              peca_db_data[key] = peca_db_data[key].strip().upper() if peca_db_data[key] else None

    db_peca = models.Peca( **peca_db_data, sku_variacao=sku_variacao, codigo_base=codigo_base, sufixo_variacao=sufixo,
                          cod_montadora=peca_data.cod_montadora, cod_modelo=cod_modelo_id, cod_final_item=next_fff )
    try:
        db.add(db_peca); db.flush(); peca_id = db_peca.id
        if not peca_id: raise ValueError("Falha ID peça.")
        ean13 = generate_ean13(peca_id)
        if ean13: db_peca.codigo_ean13 = ean13
        for img_url in image_urls:
            if img_url: db.add(models.PecaImagem(peca_id=peca_id, url_imagem=img_url))
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA criar peça: {e}"); raise ValueError(f"Erro interno salvar variação.")

def update_peca_variacao(db: Session, peca_id: int, peca_update_data: schemas.PecaBase) -> Optional[models.Peca]:
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: return None
    update_data = peca_update_data.model_dump(exclude_unset=True, exclude={'tipo_variacao', 'quantidade_estoque', 'cod_modelo', 'nome_item'})
    campos_str_upper = ['descricao_peca', 'categoria', 'codigo_oem', 'anos_aplicacao', 'posicao_porta']
    try:
        for key, value in update_data.items():
            if key == 'data_ultima_compra': value = value.strftime('%Y-%m-%d') if isinstance(value, date) else None
            elif key in campos_str_upper and isinstance(value, str): value = value.strip().upper() if value else None
            setattr(db_peca, key, value)
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro SQLA update peça {peca_id}: {e}"); raise ValueError("Erro interno atualizar.")

def delete_peca_variacao(db: Session, peca_id: int) -> bool:
    db_peca = get_peca_by_id(db, peca_id)
    if not db_peca: return False
    comp_em_kit = db.query(models.ComponenteKit).filter(models.ComponenteKit.componente_peca_id == peca_id).first()
    if comp_em_kit: kit_pai = get_peca_by_id(db, comp_em_kit.kit_peca_id); kit_sku = kit_pai.sku_variacao if kit_pai else f"ID {comp_em_kit.kit_peca_id}"; raise ValueError(f"Peça (SKU: {db_peca.sku_variacao}) é componente do Kit {kit_sku}.")
    try:
        # TODO: Deletar imagens Cloudinary
        db.delete(db_peca); db.commit(); return True
    # CORREÇÃO: Adicionado bloco except
    except exc.SQLAlchemyError as e:
        db.rollback()
        print(f"Erro DB ao deletar peça ID {peca_id}: {e}")
        raise ValueError("Erro interno ao deletar peça.")


# --- CRUD Estoque (Correto) ---
def registrar_movimentacao_crud(db: Session, peca_id: int, tipo_mov: str, quantidade: int, observacao: Optional[str]):
    if not peca_id or tipo_mov not in ['Entrada', 'Saida', 'Ajuste'] or not isinstance(quantidade, int) or quantidade < 0: raise ValueError("Dados inválidos.")
    if tipo_mov != 'Ajuste' and quantidade <= 0: raise ValueError("Qtd > 0 p/ Entrada/Saída.")
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try:
        db_mov = models.MovimentacaoEstoque(peca_id=peca_id, tipo_movimentacao=tipo_mov, quantidade=quantidade, observacao=observacao)
        db.add(db_mov)
        if tipo_mov == 'Entrada': db_peca.quantidade_estoque = (db_peca.quantidade_estoque or 0) + quantidade
        elif tipo_mov == 'Saida': db_peca.quantidade_estoque = (db_peca.quantidade_estoque or 0) - quantidade
        elif tipo_mov == 'Ajuste': db_peca.quantidade_estoque = quantidade
        db.commit(); db.refresh(db_peca); return db_peca
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB mov: {e}"); raise ValueError("Erro DB mov.")
def get_movimentacoes_crud(db: Session, peca_id: int, skip: int = 0, limit: int = 50) -> List[models.MovimentacaoEstoque]:
    try: return db.query(models.MovimentacaoEstoque).filter(models.MovimentacaoEstoque.peca_id == peca_id).order_by(models.MovimentacaoEstoque.data_movimentacao.desc()).offset(skip).limit(limit).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB hist: {e}"); return []

# --- CRUD Kits (Corrigido try/except) ---
def set_kit_status_crud(db: Session, peca_id: int, eh_kit: bool):
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    try: # CORREÇÃO: Adicionado try
        db_peca.eh_kit = eh_kit;
        if not eh_kit: db.query(models.ComponenteKit).filter(models.ComponenteKit.kit_peca_id == peca_id).delete()
        db.commit(); return True
    # CORREÇÃO: Adicionado except
    except exc.SQLAlchemyError as e:
        db.rollback(); print(f"Erro DB kit status: {e}"); return False

def get_componentes_crud(db: Session, kit_peca_id: int) -> List[models.ComponenteKit]:
    try: return db.query(models.ComponenteKit).filter(models.ComponenteKit.kit_peca_id == kit_peca_id).options(selectinload(models.ComponenteKit.componente)).order_by(models.ComponenteKit.id).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB get comps: {e}"); return []

def add_componente_crud(db: Session, kit_peca_id: int, componente_peca_id: int, quantidade: int):
    if not isinstance(quantidade, int) or quantidade <= 0: raise ValueError("Qtd inválida.")
    if kit_peca_id == componente_peca_id: raise ValueError("Kit não pode ser componente.")
    db_kit = get_peca_by_id(db, kit_peca_id); db_comp = get_peca_by_id(db, componente_peca_id)
    if not db_kit or not db_comp: raise ValueError("Kit ou Comp não encontrado.")
    if not db_kit.eh_kit: raise ValueError("Peça não é Kit.")
    if db_comp.eh_kit: raise ValueError("Não add Kit como comp.")
    try: # CORREÇÃO: Adicionado try
        comp_exist = db.query(models.ComponenteKit).filter_by(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id).first()
        if comp_exist: comp_exist.quantidade_componente = quantidade
        else: db.add(models.ComponenteKit(kit_peca_id=kit_peca_id, componente_peca_id=componente_peca_id, quantidade_componente=quantidade))
        db.commit(); return True
    # CORREÇÃO: Adicionado except
    except exc.SQLAlchemyError as e:
        db.rollback(); print(f"Erro DB add comp: {e}"); raise ValueError("Erro DB add comp.")

def remove_componente_crud(db: Session, componente_kit_id: int):
    try: # CORREÇÃO: Adicionado try
        comp = db.query(models.ComponenteKit).filter(models.ComponenteKit.id == componente_kit_id).first();
        if comp: db.delete(comp); db.commit(); return True
        else: return False
    # CORREÇÃO: Adicionado except
    except exc.SQLAlchemyError as e:
         db.rollback(); print(f"Erro DB rem comp: {e}"); return False

# --- CRUD Imagens (Correto) ---
async def upload_image_to_cloudinary(file: UploadFile) -> Optional[str]:
    if not config.cloudinary_configured: raise HTTPException(status_code=501, detail="Cloudinary não config.")
    try:
        contents = await file.read()
        opts = {"folder": config.CLOUDINARY_UPLOAD_FOLDER, "resource_type": "image", "unique_filename": True}
        if config.CLOUDINARY_DEFAULT_UPLOAD_TRANSFORMATION: opts["transformation"] = config.CLOUDINARY_DEFAULT_UPLOAD_TRANSFORMATION
        res = cloudinary.uploader.upload(contents, **opts); url = res.get("secure_url")
        if url: print(f"Upload OK: {url}"); return url
        else: raise HTTPException(status_code=500, detail="Falha upload (sem URL).")
    except HTTPException as http_exc: raise http_exc
    except Exception as e: print(f"ERRO Upload Cloudinary: {e}"); raise HTTPException(status_code=500, detail=f"Erro upload: {e}")
def add_imagem_crud(db: Session, peca_id: int, url_imagem: str):
    db_peca = get_peca_by_id(db, peca_id);
    if not db_peca: raise ValueError(f"Peça ID {peca_id} não encontrada.")
    if not url_imagem: raise ValueError("URL imagem vazia.")
    try: db_img = models.PecaImagem(peca_id=peca_id, url_imagem=url_imagem); db.add(db_img); db.commit()
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB add img ref: {e}"); raise ValueError("Erro DB add img ref.")
def remove_imagem_crud(db: Session, imagem_id: int) -> bool:
    try:
        img = db.query(models.PecaImagem).filter(models.PecaImagem.id == imagem_id).first()
        if img: db.delete(img); db.commit(); return True
        else: return False
    except exc.SQLAlchemyError as e: db.rollback(); print(f"Erro DB rem img: {e}"); return False
def get_imagens_crud(db: Session, peca_id: int) -> List[models.PecaImagem]:
    try: return db.query(models.PecaImagem).filter(models.PecaImagem.peca_id == peca_id).order_by(models.PecaImagem.id).all()
    except exc.SQLAlchemyError as e: print(f"Erro DB get imgs: {e}"); return []

# --- Helper EAN (Correto) ---
def generate_ean13(internal_id):
    if not internal_id: return None
    try: base = f"290{internal_id:09d}"[:12]; return EAN13(base).ean13
    except: return None