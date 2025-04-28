# File: app/main.py (Versão 5.8 - Corrigido Erro 'os' not defined)

from fastapi import (FastAPI, Depends, HTTPException, Request, Form, status,
                   UploadFile, File, Query)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import os # <-- IMPORT ADICIONADO

# Importa nossos módulos internos
from app import database, models, schemas, crud, config

# Cria/Verifica as tabelas no banco de dados
try:
    print("Verificando/Criando tabelas do banco de dados...")
    if database.engine:
        models.Base.metadata.create_all(bind=database.engine)
        print("Tabelas OK.")
    else:
        print("ERRO FATAL: Engine do banco de dados não inicializado.")
except Exception as e:
    print(f"ERRO ao verificar/criar tabelas: {e}")

# --- Configuração do App FastAPI ---
app = FastAPI(title="Gestor de Peças Pro++ API v5.8") # Versão atualizada
templates = Jinja2Templates(directory="app/templates")
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dependência para obter sessão do DB
get_db = database.get_db

# --- Rotas HTML e API ---

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root():
    return RedirectResponse(url="/pecas") # Página inicial

# --- Montadoras ---
@app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
async def view_montadoras_page(request: Request, db: Session = Depends(get_db), success_msg: Optional[str]=None, error_msg: Optional[str]=None):
    montadoras=[]; err_fetch=None
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e: err_fetch = "Erro carregar montadoras."
    return templates.TemplateResponse( request=request, name="montadoras.html", context={"montadoras": montadoras, "success_message":success_msg, "error_message": error_msg or err_fetch} )

@app.post("/montadoras", tags=["Interface Montadoras"])
async def handle_add_montadora( request: Request, nome_montadora: str = Form(..., min_length=2), db: Session = Depends(get_db) ):
    err_msg=None; succ_msg=None; montadoras=[]
    try: mont_c = crud.create_montadora(db, montadora=schemas.MontadoraCreate(nome_montadora=nome_montadora)); succ_msg = f"'{mont_c.nome_montadora}' (Cód: {mont_c.cod_montadora}) criada!"
    except ValueError as e: err_msg = str(e)
    except Exception as e: err_msg = "Erro inesperado."
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception: err_msg = err_msg or "Erro recarregar lista."
    ctx = {"montadoras": montadoras, "error_message": err_msg, "success_message": succ_msg}
    resp_list = templates.TemplateResponse(request=request, name="partials/montadora_list.html", context=ctx)
    resp_msg = templates.TemplateResponse(request=request, name="partials/messages.html", context=ctx)
    resp_list.headers["HX-Retarget"] = "#montadora-list-container, #messages"; resp_list.headers["HX-Reswap"] = "innerHTML"
    return HTMLResponse(content=resp_list.body + resp_msg.body, headers=resp_list.headers)

# --- Peças ---
@app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_add_peca_form(request: Request, db: Session = Depends(get_db)):
    montadoras = []; err_msg = None
    try:
        montadoras = crud.get_montadoras(db, limit=500)
        if not montadoras: err_msg = "Cadastre montadoras primeiro."
    except Exception as e: print(f"Erro form peças: {e}"); err_msg = "Erro carregar montadoras."
    portas_opts = ["DD/FR", "DE/FL", "TD/RR", "TE/RL", "PTM/TRK"]
    return templates.TemplateResponse( request=request, name="pecas_add.html", context={"montadoras": montadoras, "error_message": err_msg, "portas_opts": portas_opts} )

@app.post("/pecas", tags=["Interface Peças"])
async def handle_add_peca(
    request: Request, cod_montadora: int = Form(...), nome_modelo: str = Form(..., min_length=1),
    nome_item: str = Form(..., min_length=3), tipo_variacao: str = Form(..., pattern="^[NRP]$"),
    descricao_peca: Optional[str] = Form(None), codigo_oem: Optional[str] = Form(None),
    anos_aplicacao: Optional[str] = Form(None), posicao_porta: Optional[str] = Form(None),
    quantidade_estoque: int = Form(..., ge=0), preco_venda: float = Form(..., ge=0),
    custo_ultima_compra: Optional[float] = Form(0.0, ge=0), aliquota_imposto_percent: Optional[float] = Form(0.0, ge=0, le=100),
    custo_estimado_adicional: Optional[float] = Form(0.0, ge=0), data_ultima_compra: Optional[date] = Form(None),
    imagens: List[UploadFile] = File([], alias="imagens[]", max_items=10), db: Session = Depends(get_db) ):

    error_msg = None; success_msg = None; uploaded_image_urls = []
    if len(imagens) > 10: # Re-verifica limite (FastAPI deve tratar, mas é bom ter)
        error_msg = "Erro: Máximo de 10 imagens por vez."
        return templates.TemplateResponse(request=request, name="partials/messages.html", context={"error_message": error_msg})

    if config.cloudinary_configured and imagens:
        for file in imagens:
            if file.filename:
                try:
                    print(f"Upload: {file.filename}"); secure_url = await crud.upload_image_to_cloudinary(file)
                    if secure_url: uploaded_image_urls.append(secure_url)
                    else: error_msg = (error_msg or "") + f" Falha upload '{file.filename}'. "
                except HTTPException as e: error_msg = (error_msg or "") + f" Erro upload '{file.filename}': {e.detail}. "
                except Exception as e: print(f"Erro up: {e}"); error_msg = (error_msg or "") + f" Erro upload '{file.filename}'. "

    try:
        peca_schema_data = { # Monta o dicionário para Pydantic
            "nome_item": nome_item, "tipo_variacao": tipo_variacao, "descricao_peca": descricao_peca,
            "codigo_oem": codigo_oem, "anos_aplicacao": anos_aplicacao, "posicao_porta": posicao_porta,
            "custo_ultima_compra": custo_ultima_compra, "aliquota_imposto_percent": aliquota_imposto_percent,
            "custo_estimado_adicional": custo_estimado_adicional, "preco_venda": preco_venda,
            "data_ultima_compra": data_ultima_compra, "quantidade_estoque": quantidade_estoque,
            "cod_montadora": cod_montadora, "nome_modelo": nome_modelo,
            # Campos não vindos diretamente do form ou opcionais no schema base
            "categoria": None, # Adiciona categoria aqui se o schema PecaCreate precisar
            "qtd_para_reparar": 0 # Removido do modelo, mas se schema precisar...
        }
        # Filtra Nones que não deveriam ser passados se o schema não os espera como Optional
        peca_schema_data_clean = {k: v for k, v in peca_schema_data.items() if v is not None or k in schemas.PecaCreate.__annotations__}

        peca_schema = schemas.PecaCreate(**peca_schema_data_clean)

    except Exception as e_val:
        print(f"Erro validação Pydantic: {e_val}")
        error_msg = (error_msg or "") + f" Erro dados formulário: {e_val}"
        return templates.TemplateResponse( request=request, name="partials/messages.html", context={"error_message": error_msg} )

    if not error_msg:
        try:
            peca_criada = crud.create_peca_variacao( db=db, peca_data=peca_schema, image_urls=uploaded_image_urls )
            success_msg = f"Variação SKU {peca_criada.sku_variacao} criada!"
        except ValueError as e: error_msg = (error_msg or "") + f" Erro ao salvar: {e}"
        except Exception as e: print(f"Erro inesperado salvar peça: {e}"); error_msg = (error_msg or "") + " Erro servidor salvar."

    context = {"success_message": success_msg, "error_message": error_msg}
    response_msg = templates.TemplateResponse( request=request, name="partials/messages.html", context=context )
    response_msg.headers["HX-Refresh"] = "true"
    return response_msg

@app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_pecas_list( request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0),
                           limit: int = Query(25, ge=1, le=100), search: Optional[str] = Query(None) ): # Removido min_length
    pecas = []; error_msg = None
    try:
        # Ajuste: Permite busca vazia para listar todos
        if search is not None and len(search) >= 2: # Só busca se termo tiver >= 2 chars
            pecas = crud.search_pecas_crud(db, search_term=search, skip=skip, limit=limit)
        elif search is None or search == "": # Lista todos se busca vazia ou nula
            pecas = crud.get_pecas_list(db, skip=skip, limit=limit)
        # Se search tiver 1 char, não faz nada (ou poderia retornar msg?)
    except Exception as e: print(f"Erro buscar peças: {e}"); error_msg = "Erro carregar peças."
    context = { "request": request, "pecas": pecas, "search_term": search, "skip": skip, "limit": limit, "error_message": error_msg }
    return templates.TemplateResponse( request=request, name="pecas_list.html", context=context )

# --- Placeholder para outras páginas ---
@app.get("/{page_name}", response_class=HTMLResponse, include_in_schema=False)
async def view_placeholder_page(request: Request, page_name: str):
    known_placeholders = { "estoque": "Estoque | Kits", "kits": "Estoque | Kits",
                           "importar-exportar": "Importar / Exportar", "ajuda": "Ajuda" }
    if page_name in known_placeholders:
        title = known_placeholders[page_name]
        placeholder_path = os.path.join("app", "templates", "placeholder.html")
        if not os.path.exists(placeholder_path):
             with open(placeholder_path, "w", encoding="utf-8") as f: # Adicionado encoding
                 f.write("{% extends \"base.html\" %}\n")
                 f.write("{% block title %}{{ page_title }}{% endblock %}\n")
                 f.write("{% block content %}<h2>{{ page_title }}</h2><p><i>(Página em construção)</i></p>{% endblock %}\n")
        return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": title})
    else:
         # Se não for rota conhecida, levanta 404
         raise HTTPException(status_code=404, detail=f"Página '/{page_name}' não encontrada.")

# --- Adicionar endpoints para Editar/Deletar Peças, Estoque, Kits, Import/Export, Ajuda depois ---

