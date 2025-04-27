# File: app/main.py (Atualizado v5.5 - Endpoints Peças e Upload Cloudinary)

from fastapi import (FastAPI, Depends, HTTPException, Request, Form, status,
                   UploadFile, File) # File e UploadFile para imagens
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional

# Habilita o uso de respostas com fragmentos HTMX (se usado nos templates)
# from htmx_fastapi import Htmx, HtmxResponse # Não estamos usando a lib direta

# Importa nossos módulos internos
from . import crud, models, schemas, database, config # Adicionado config

# Cria/Verifica as tabelas no banco de dados ANTES de iniciar o app
try:
    print("Verificando/Criando tabelas...")
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
app = FastAPI(title="Gestor de Peças Pro++ API")
templates = Jinja2Templates(directory="app/templates")
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dependência para obter sessão do DB
get_db = database.get_db

# --- Rotas HTML e API ---

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root():
    """Redireciona para a nova página inicial (Lista de Peças)."""
    return RedirectResponse(url="/pecas") # MUDOU: Página inicial agora é /pecas

# --- Montadoras (Rotas inalteradas, mas podem ser acessadas por links)---
@app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
async def view_montadoras_page(request: Request, db: Session = Depends(get_db), success_msg: Optional[str] = None, error_msg: Optional[str] = None):
    montadoras = []; error_msg_fetch = None
    try: montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e: error_msg_fetch = "Erro ao carregar montadoras."
    return templates.TemplateResponse( request=request, name="montadoras.html", context={"montadoras": montadoras, "success_message":success_msg, "error_message": error_msg or error_msg_fetch} )

@app.post("/montadoras", tags=["Interface Montadoras"])
async def handle_add_montadora( request: Request, nome_montadora: str = Form(..., min_length=2), db: Session = Depends(get_db) ):
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
    return HTMLResponse(content=response_list.body + response_msg.body)


# --- Peças ---

@app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_add_peca_form(request: Request, db: Session = Depends(get_db)):
    """Renderiza a página HTML com o formulário para adicionar nova peça."""
    montadoras = crud.get_montadoras(db, limit=500) # Para o selectbox
    return templates.TemplateResponse(
        request=request,
        name="pecas_add.html", # Novo template HTML
        context={"montadoras": montadoras} # Passa a lista de montadoras para o template
    )

# Endpoint para processar o formulário de adicionar peça
@app.post("/pecas", tags=["Interface Peças"]) # Idealmente retornaria um status ou fragmento HTMX
async def handle_add_peca(
    request: Request,
    # Campos do Formulário (usando Form(...) para pegar dados de form HTML)
    cod_montadora: int = Form(...),
    cod_modelo: int = Form(..., gt=0),
    tipo_variacao: str = Form(..., pattern="^[NRP]$"), # Validação básica
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
    data_ultima_compra: Optional[datetime.date] = Form(None), # FastAPI tenta converter
    # Arquivos de Imagem (pode receber múltiplos)
    imagens: List[UploadFile] = File([], alias="imagens[]"), # Usa alias se o input name for 'imagens[]'
    db: Session = Depends(get_db)
    # hx: Htmx = Htmx() # Se for usar resposta HTMX específica
):
    """Processa o formulário de adição de peça, faz upload e salva."""
    error_msg = None
    success_msg = None
    uploaded_image_urls = []

    # 1. Upload de Imagens para Cloudinary (se houver)
    if config.cloudinary_configured and imagens:
        if len(imagens) > 5: # Limita o número de uploads por vez
             error_msg = "Erro: Máximo de 5 imagens por vez."
             # Retorna erro ou apenas ignora as extras? Vamos retornar erro.
             # Poderia usar HTMX para retornar só a mensagem de erro aqui.
             return templates.TemplateResponse(
                 request=request, name="partials/messages.html", context={"error_message": error_msg}
             )

        for file in imagens:
            if file.filename: # Verifica se um arquivo foi realmente enviado
                try:
                    # Chama a função CRUD para fazer upload
                    # A função crud.upload_image_to_cloudinary precisa ser 'async' se file.read() for async
                    # Se crud.upload_image_to_cloudinary não for async, pode precisar rodar em thread separada para não bloquear
                    # Vamos assumir que a função CRUD lida com isso ou que os arquivos são pequenos
                    print(f"Fazendo upload de: {file.filename}")
                    secure_url = await crud.upload_image_to_cloudinary(file)
                    if secure_url:
                        uploaded_image_urls.append(secure_url)
                    else:
                        # Se o upload falhar para UMA imagem, o que fazer?
                        # Parar tudo? Continuar sem essa imagem? Adicionar ao erro?
                        error_msg = (error_msg or "") + f" Falha no upload de '{file.filename}'. "
                except HTTPException as e: # Captura erros HTTP específicos do upload (ex: não configurado)
                     error_msg = (error_msg or "") + f" Erro upload: {e.detail}. "
                except Exception as e:
                     print(f"Erro inesperado no upload: {e}")
                     error_msg = (error_msg or "") + f" Erro inesperado no upload de '{file.filename}'. "
        # Se houve erro em algum upload, talvez parar aqui? Ou continuar e salvar sem a imagem?
        # Por ora, vamos continuar e salvar com as URLs que deram certo.

    # 2. Preparar dados da peça para salvar (usando Pydantic Schema)
    peca_schema = schemas.PecaCreate(
        descricao_peca=descricao_peca,
        cod_modelo=cod_modelo,
        tipo_variacao=tipo_variacao,
        codigo_oem=codigo_oem,
        anos_aplicacao=anos_aplicacao,
        posicao_porta=posicao_porta,
        qtd_para_reparar=qtd_para_reparar,
        custo_insumos=custo_insumos,
        custo_etiqueta=custo_etiqueta,
        custo_embalagem=custo_embalagem,
        impostos_percent=impostos_percent,
        preco_venda=preco_venda,
        data_ultima_compra=data_ultima_compra,
        # cod_montadora será passado separadamente para a função CRUD
    )

    # 3. Chamar CRUD para criar a peça e associar imagens
    try:
        # Passa os dados validados pelo schema e as URLs obtidas
        peca_criada = crud.create_peca_variacao(
            db=db,
            peca_data=peca_schema,
            cod_montadora=cod_montadora,
            image_urls=uploaded_image_urls
        )
        success_msg = f"Variação SKU {peca_criada.sku_variacao} criada com {len(uploaded_image_urls)} imagem(ns)!"

    except ValueError as e: # Erro de validação ou DB do CRUD
        error_msg = (error_msg or "") + f" Erro ao salvar peça: {e}"
    except Exception as e:
        print(f"Erro inesperado ao salvar peça: {e}")
        error_msg = (error_msg or "") + " Erro inesperado no servidor ao salvar peça."


    # 4. Preparar e retornar resposta (HTMX ou Recarregar?)
    # Idealmente, HTMX atualizaria só mensagens ou limparia form.
    # Para simplificar, vamos recarregar a página de adicionar com mensagem.
    # Ou redirecionar para a lista. Vamos redirecionar para a lista com msg.

    # Busca montadoras novamente para re-renderizar o form se precisar
    montadoras = crud.get_montadoras(db, limit=500)
    context = {"montadoras": montadoras, "success_message": success_msg, "error_message": error_msg}

    # Retorna SÓ o fragmento de mensagens para o HTMX colocar no div #messages
    # E talvez um header HTMX para limpar o form ou redirecionar (mais avançado)
    response_msg = templates.TemplateResponse( request=request, name="partials/messages.html", context=context )
    # Usaremos um header especial do HTMX para recarregar a página toda após o sucesso/erro
    # Isso limpa o formulário e mostra a mensagem. Não é o ideal para SPA, mas simples.
    response_msg.headers["HX-Refresh"] = "true"
    return response_msg

    # Alternativa: Redirecionar para a lista após sucesso
    # if success_msg and not error_msg:
    #     # Usar RedirectResponse com status 303 See Other para POST->GET
    #     # Poderia passar a mensagem via query param ou cookie (mais complexo)
    #     return RedirectResponse(url="/pecas", status_code=status.HTTP_303_SEE_OTHER)
    # else:
    #     # Se deu erro, re-renderiza o form com a mensagem de erro
    #     return templates.TemplateResponse(request=request, name="pecas_add.html", context=context)


@app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
async def view_pecas_list(request: Request, db: Session = Depends(get_db), skip: int = 0, limit: int = 25, search: Optional[str] = None):
    """Renderiza a página HTML com a lista/busca de peças."""
    pecas = []
    error_msg = None
    try:
        if search:
            pecas = crud.search_pecas_crud(db, search_term=search, skip=skip, limit=limit)
        else:
            # Precisa criar a função get_pecas_list no crud.py
            # pecas = crud.get_pecas_list(db, skip=skip, limit=limit)
            # Por enquanto, busca todos para teste limitado
             pecas = db.query(models.Peca).order_by(models.Peca.codigo_base, models.Peca.sku_variacao).offset(skip).limit(limit).all()

    except Exception as e:
        print(f"Erro ao buscar peças: {e}")
        error_msg = "Erro ao carregar lista de peças."

    return templates.TemplateResponse(
        request=request,
        name="pecas_list.html", # Novo template
        context={"pecas": pecas, "search_term": search, "error_message": error_msg} # Passa peças e termo de busca
    )

# --- Estoque (Endpoints aqui depois) ---
# ...

# --- Kits (Endpoints aqui depois) ---
# ...
