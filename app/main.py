# File: app/main.py (Versão 5.5 - Corrigido SyntaxError)

from fastapi import (FastAPI, Depends, HTTPException, Request, Form, status,
                   UploadFile, File, Query) # Adicionado Query para paginação/busca
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date # Para validar data

# Importa nossos módulos internos
from . import crud, models, schemas, database, config # Adicionado config

# Cria/Verifica as tabelas no banco de dados ANTES de iniciar o app
# É importante que models.py seja importado antes desta linha
try:
    print("Verificando/Criando tabelas do banco de dados...")
    # Garante que o engine foi criado antes de tentar criar tabelas
    if database.engine:
        models.Base.metadata.create_all(bind=database.engine)
        print("Tabelas OK.")
    else:
        print("ERRO FATAL: Engine do banco de dados não inicializado. Verifique DATABASE_URL no .env")
        # Considerar sair do app aqui se o engine falhar
        # import sys; sys.exit(1)
except Exception as e:
    print(f"ERRO ao verificar/criar tabelas: {e}")

# --- Configuração do App FastAPI ---
app = FastAPI(title="Gestor de Peças Pro++ API v5.5")
templates = Jinja2Templates(directory="app/templates")
# Descomentar se usar CSS/JS estático
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dependência para obter sessão do DB
get_db = database.get_db

# --- Rotas HTML e API ---

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root():
    """Redireciona para a nova página inicial (Lista de Peças)."""
    return RedirectResponse(url="/pecas") # MUDOU: Página inicial agora é /pecas

# --- Montadoras (Mantidas, mas menos centrais) ---
@app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
async def view_montadoras_page(request: Request, db: Session = Depends(get_db), success_msg: Optional[str] = None, error_msg: Optional[str] = None):
    """Renderiza a página HTML de gerenciamento de Montadoras."""
    montadoras = []; error_msg_fetch = None
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e: error_msg_fetch = "Erro ao carregar montadoras."
    return templates.TemplateResponse( request=request, name="montadoras.html", context={"montadoras": montadoras, "success_message":success_msg, "error_message": error_msg or error_msg_fetch} )

@app.post("/montadoras", tags=["Interface Montadoras"])
async def handle_add_montadora( request: Request, nome_montadora: str = Form(..., min_length=2), db: Session = Depends(get_db) ):
    """Processa adição de montadora e retorna fragmentos HTML."""
    error_msg = None; success_msg = None; montadoras = []
    try:
        montadora_criada = crud.create_montadora(db, montadora=schemas.MontadoraCreate(nome_montadora=nome_montadora))
        success_msg = f"'{montadora_criada.nome_montadora}' (Cód: {montadora_criada.cod_montadora}) criada!"
    except ValueError as e: error_msg = str(e)
    except Exception as e: error_msg = "Erro inesperado no servidor."
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception: error_msg = error_msg or "Erro ao recarregar lista."
    context = {"montadoras": montadoras, "error_message": error_msg, "success_message": success_msg}
    # Retorna fragmentos para HTMX
    response_list = templates.TemplateResponse(request=request, name="partials/montadora_list.html", context=context)
    response_msg = templates.TemplateResponse(request=request, name="partials/messages.html", context=context)
    # Define o header para o HTMX substituir os dois blocos
    response_list.headers["HX-Retarget"] = "#montadora-list-container, #messages"
    response_list.headers["HX-Reswap"] = "innerHTML" # Define como substituir
    # Combine o conteúdo. O header do primeiro será usado.
    return HTMLResponse(content=response_list.body + response_msg.body, headers=response_list.headers)


# --- Peças ---

@app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_add_peca_form(request: Request, db: Session = Depends(get_db)):
    """Renderiza a página HTML com o formulário para adicionar nova peça/variação."""
    montadoras = []
    error_msg = None
    try:
        montadoras = crud.get_montadoras(db, limit=500) # Para o selectbox
        if not montadoras:
             error_msg = "Nenhuma montadora cadastrada. Adicione uma montadora primeiro."
    except Exception as e:
         print(f"Erro ao buscar montadoras para form: {e}")
         error_msg = "Erro ao carregar montadoras."

    return templates.TemplateResponse(
        request=request,
        name="pecas_add.html", # Template do formulário
        context={"montadoras": montadoras, "error_message": error_msg}
    )

@app.post("/pecas", tags=["Interface Peças"])
async def handle_add_peca(
    request: Request,
    # Campos do Formulário
    cod_montadora: int = Form(...),
    cod_modelo: int = Form(..., gt=0),
    tipo_variacao: str = Form(..., pattern="^[NRP]$"),
    descricao_peca: str = Form(..., min_length=3),
    codigo_oem: Optional[str] = Form(None),
    anos_aplicacao: Optional[str] = Form(None),
    posicao_porta: Optional[str] = Form(None),
    qtd_para_reparar: Optional[int] = Form(0, ge=0),
    custo_insumos: Optional[float] = Form(0.0, ge=0),
    custo_etiqueta: Optional[float] = Form(0.0, ge=0),
    custo_embalagem: Optional[float] = Form(0.0, ge=0),
    impostos_percent: Optional[float] = Form(0.0, ge=0, le=100),
    preco_venda: Optional[float] = Form(0.0, ge=0),
    data_ultima_compra: Optional[date] = Form(None),
    # Arquivos de Imagem
    imagens: List[UploadFile] = File([], alias="imagens[]"),
    db: Session = Depends(get_db)
):
    """Processa o formulário, faz upload para Cloudinary e salva a variação da peça."""
    error_msg = None
    success_msg = None
    uploaded_image_urls = []

    # 1. Validações Iniciais
    if len(imagens) > 5:
        error_msg = "Erro: Máximo de 5 imagens por vez."
        # Retorna erro imediatamente via HTMX
        return templates.TemplateResponse(
            request=request, name="partials/messages.html", context={"error_message": error_msg}
        )

    # 2. Upload de Imagens para Cloudinary (se configurado e houver imagens)
    if config.cloudinary_configured and imagens:
        for file in imagens:
            if file.filename: # Garante que é um arquivo real
                try:
                    print(f"Tentando upload de: {file.filename}")
                    secure_url = await crud.upload_image_to_cloudinary(file) # Chama a função CRUD
                    if secure_url:
                        uploaded_image_urls.append(secure_url)
                    else:
                        error_msg = (error_msg or "") + f" Falha silenciosa no upload de '{file.filename}'. "
                except HTTPException as e: # Captura erro HTTP do upload (ex: Cloudinary não config)
                     error_msg = (error_msg or "") + f" Erro upload '{file.filename}': {e.detail}. "
                except Exception as e:
                     print(f"Erro inesperado upload: {e}")
                     error_msg = (error_msg or "") + f" Erro inesperado upload '{file.filename}'. "
        # Se houve erro em algum upload, podemos decidir parar ou continuar
        # if error_msg: # Descomente para parar se qualquer upload falhar
        #    return templates.TemplateResponse(request=request, name="partials/messages.html", context={"error_message": error_msg})

    # 3. Preparar dados da peça para salvar (Schema Pydantic)
    try:
        peca_schema = schemas.PecaCreate(
            descricao_peca=descricao_peca, cod_modelo=cod_modelo, tipo_variacao=tipo_variacao,
            codigo_oem=codigo_oem, anos_aplicacao=anos_aplicacao, posicao_porta=posicao_porta,
            qtd_para_reparar=qtd_para_reparar, custo_insumos=custo_insumos, custo_etiqueta=custo_etiqueta,
            custo_embalagem=custo_embalagem, impostos_percent=impostos_percent, preco_venda=preco_venda,
            data_ultima_compra=data_ultima_compra,
            cod_montadora=cod_montadora # Passa cod_montadora aqui para validação se necessário no schema
        )
    except Exception as e_val: # Erro na validação Pydantic
        print(f"Erro validação Pydantic: {e_val}")
        error_msg = (error_msg or "") + f" Erro nos dados do formulário: {e_val}"
        # Retorna erro para o usuário
        return templates.TemplateResponse( request=request, name="partials/messages.html", context={"error_message": error_msg} )


    # 4. Chamar CRUD para criar a peça no banco
    if not error_msg: # Só tenta salvar se não houve erro de upload/validação grave
        try:
            peca_criada = crud.create_peca_variacao(
                db=db, peca_data=peca_schema, cod_montadora=cod_montadora,
                image_urls=uploaded_image_urls )
            success_msg = f"Variação SKU {peca_criada.sku_variacao} criada com {len(uploaded_image_urls)} imagem(ns)!"
        except ValueError as e: # Erro de validação ou DB do CRUD
            error_msg = (error_msg or "") + f" Erro ao salvar: {e}"
        except Exception as e:
            print(f"Erro inesperado ao salvar peça: {e}")
            error_msg = (error_msg or "") + " Erro inesperado no servidor ao salvar."

    # 5. Preparar e retornar resposta HTMX (apenas mensagens)
    context = {"success_message": success_msg, "error_message": error_msg}
    response_msg = templates.TemplateResponse( request=request, name="partials/messages.html", context=context )

    # Diz ao HTMX para recarregar a página toda após a resposta ser processada
    response_msg.headers["HX-Refresh"] = "true"
    return response_msg


@app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_pecas_list(
    request: Request,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=2, max_length=50)
):
    """Renderiza a página HTML com a lista/busca de peças/variações."""
    pecas = []
    error_msg = None
    try:
        if search:
            pecas = crud.search_pecas_crud(db, search_term=search, skip=skip, limit=limit)
        else:
            pecas = crud.get_pecas_list(db, skip=skip, limit=limit) # Usa a função CRUD
    except Exception as e:
        print(f"Erro ao buscar peças: {e}")
        error_msg = "Erro ao carregar lista de peças."

    context = { "request": request, "pecas": pecas, "search_term": search,
                "skip": skip, "limit": limit, "error_message": error_msg }
    return templates.TemplateResponse( request=request, name="pecas_list.html", context=context )


# --- Estoque (Endpoints aqui depois) ---
@app.get("/estoque", response_class=HTMLResponse, tags=["Interface Estoque"])
async def view_estoque_page(request: Request):
     # Precisa criar o template estoque.html
     return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": "Estoque"})

# --- Kits (Endpoints aqui depois) ---
@app.get("/kits", response_class=HTMLResponse, tags=["Interface Kits"])
async def view_kits_page(request: Request):
     # Precisa criar o template kits.html
     return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": "Kits"})

# --- Importar/Exportar (Endpoints aqui depois) ---
@app.get("/importar-exportar", response_class=HTMLResponse, tags=["Interface Import/Export"])
async def view_import_export_page(request: Request):
     # Precisa criar o template import_export.html
     return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": "Importar/Exportar"})

# --- Ajuda (Endpoints aqui depois) ---
@app.get("/ajuda", response_class=HTMLResponse, tags=["Interface Ajuda"])
async def view_help_page(request: Request):
     # Precisa criar o template ajuda.html
     return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": "Ajuda"})

# Placeholder para páginas não implementadas
@app.get("/placeholder", response_class=HTMLResponse, include_in_schema=False)
async def view_placeholder(request: Request, page_title: str = "Em Construção"):
     return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": page_title})

