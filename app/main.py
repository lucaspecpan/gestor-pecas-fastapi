# File: app/main.py (Versão 5.6 - Com Categoria)

from fastapi import (FastAPI, Depends, HTTPException, Request, Form, status,
                   UploadFile, File, Query)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from . import crud, models, schemas, database, config

try:
    print("Verificando/Criando tabelas...")
    if database.engine: models.Base.metadata.create_all(bind=database.engine); print("Tabelas OK.")
    else: print("ERRO FATAL: Engine DB não inicializado.")
except Exception as e: print(f"ERRO ao verificar/criar tabelas: {e}")

app = FastAPI(title="Gestor de Peças Pro++ API v5.6")
templates = Jinja2Templates(directory="app/templates")
# app.mount("/static", StaticFiles(directory="app/static"), name="static")
get_db = database.get_db

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root(): return RedirectResponse(url="/pecas")

# --- Montadoras (Inalterado) ---
@app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
async def view_montadoras_page(request: Request, db: Session = Depends(get_db), success_msg: Optional[str]=None, error_msg: Optional[str]=None):
    montadoras=[]; err_fetch=None
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e: err_fetch = "Erro carregar montadoras."
    return templates.TemplateResponse(request=request, name="montadoras.html", context={"montadoras": montadoras, "success_message":success_msg, "error_message": error_msg or err_fetch})

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
        if not montadoras: err_msg = "Nenhuma montadora cadastrada."
    except Exception as e: print(f"Erro form peças: {e}"); err_msg = "Erro carregar montadoras."
    return templates.TemplateResponse( request=request, name="pecas_add.html", context={"montadoras": montadoras, "error_message": err_msg} )

@app.post("/pecas", tags=["Interface Peças"])
async def handle_add_peca(
    request: Request,
    # Campos do Formulário
    cod_montadora: int = Form(...), cod_modelo: int = Form(..., gt=0),
    tipo_variacao: str = Form(..., pattern="^[NRP]$"), descricao_peca: str = Form(..., min_length=3),
    categoria: Optional[str] = Form(None), # NOVO CAMPO RECEBIDO DO FORM
    codigo_oem: Optional[str] = Form(None), anos_aplicacao: Optional[str] = Form(None),
    posicao_porta: Optional[str] = Form(None), qtd_para_reparar: Optional[int] = Form(0, ge=0),
    custo_insumos: Optional[float] = Form(0.0, ge=0), custo_etiqueta: Optional[float] = Form(0.0, ge=0),
    custo_embalagem: Optional[float] = Form(0.0, ge=0), impostos_percent: Optional[float] = Form(0.0, ge=0, le=100),
    preco_venda: Optional[float] = Form(0.0, ge=0), data_ultima_compra: Optional[date] = Form(None),
    imagens: List[UploadFile] = File([], alias="imagens[]"), db: Session = Depends(get_db) ):

    error_msg = None; success_msg = None; uploaded_image_urls = []

    if len(imagens) > 5: error_msg = "Erro: Máx 5 imagens."; return templates.TemplateResponse(request=request, name="partials/messages.html", context={"error_message": error_msg})

    if config.cloudinary_configured and imagens:
        for file in imagens:
            if file.filename:
                try:
                    print(f"Upload: {file.filename}"); secure_url = await crud.upload_image_to_cloudinary(file)
                    if secure_url: uploaded_image_urls.append(secure_url)
                    else: error_msg = (error_msg or "") + f" Falha upload '{file.filename}'. "
                except HTTPException as e: error_msg = (error_msg or "") + f" Erro upload '{file.filename}': {e.detail}. "
                except Exception as e: print(f"Erro up: {e}"); error_msg = (error_msg or "") + f" Erro upload '{file.filename}'. "

    try: # Validação Pydantic e Criação no DB
        peca_schema = schemas.PecaCreate( # Passa todos os campos recebidos do Form
            descricao_peca=descricao_peca, categoria=categoria, cod_modelo=cod_modelo, tipo_variacao=tipo_variacao,
            codigo_oem=codigo_oem, anos_aplicacao=anos_aplicacao, posicao_porta=posicao_porta,
            qtd_para_reparar=qtd_para_reparar, custo_insumos=custo_insumos, custo_etiqueta=custo_etiqueta,
            custo_embalagem=custo_embalagem, impostos_percent=impostos_percent, preco_venda=preco_venda,
            data_ultima_compra=data_ultima_compra, cod_montadora=cod_montadora )

        if not error_msg: # Só tenta salvar se não houve erro grave antes
            peca_criada = crud.create_peca_variacao( db=db, peca_data=peca_schema, cod_montadora=cod_montadora, image_urls=uploaded_image_urls )
            success_msg = f"Variação SKU {peca_criada.sku_variacao} criada!"
    except ValueError as e: error_msg = (error_msg or "") + f" Erro: {e}"
    except Exception as e_val: print(f"Erro Pydantic/DB: {e_val}"); error_msg = (error_msg or "") + f" Erro dados/salvar: {e_val}"

    context = {"success_message": success_msg, "error_message": error_msg}
    response_msg = templates.TemplateResponse( request=request, name="partials/messages.html", context=context )
    response_msg.headers["HX-Refresh"] = "true" # Recarrega a página
    return response_msg

@app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_pecas_list( request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0),
                           limit: int = Query(25, ge=1, le=100), search: Optional[str] = Query(None, min_length=2, max_length=50) ):
    pecas = []; error_msg = None
    try:
        if search: pecas = crud.search_pecas_crud(db, search_term=search, skip=skip, limit=limit)
        else: pecas = crud.get_pecas_list(db, skip=skip, limit=limit)
    except Exception as e: print(f"Erro buscar peças: {e}"); error_msg = "Erro carregar peças."
    context = { "request": request, "pecas": pecas, "search_term": search, "skip": skip, "limit": limit, "error_message": error_msg }
    return templates.TemplateResponse( request=request, name="pecas_list.html", context=context )

# --- Outras seções (Estoque, Kits, Import/Export, Ajuda) - Usando Placeholder ---
@app.get("/{page_name}", response_class=HTMLResponse, include_in_schema=False)
async def view_placeholder_page(request: Request, page_name: str):
    titles = { "estoque": "Estoque | Kits", "kits": "Estoque | Kits",
               "importar-exportar": "Importar / Exportar", "ajuda": "Ajuda" }
    title = titles.get(page_name, "Página não encontrada")
    # Usaremos um template genérico 'placeholder.html'
    return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": title})

