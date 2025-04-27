# File: app/main.py (Versão 5.4 Corrigida - Sem htmx-fastapi)

from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional

# Removida a importação da biblioteca inexistente
# from htmx_fastapi import Htmx, HtmxResponse # <-- REMOVIDO

# Importa nossos módulos internos
from . import crud, models, schemas, database

# Cria/Verifica as tabelas no banco de dados ANTES de iniciar o app
try:
    print("Verificando/Criando tabelas do banco de dados...")
    models.Base.metadata.create_all(bind=database.engine)
    print("Tabelas OK.")
except Exception as e:
    print(f"ERRO FATAL ao verificar/criar tabelas: {e}")

# --- Configuração do App FastAPI ---
app = FastAPI(title="Gestor de Peças Pro++ API")
templates = Jinja2Templates(directory="app/templates")
# app.mount("/static", StaticFiles(directory="app/static"), name="static") # Descomentar se usar CSS/JS

# Dependência para obter sessão do DB
get_db = database.get_db

# --- Rotas HTML e API ---

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def read_root():
    """Redireciona para a página inicial (Montadoras por enquanto)."""
    return RedirectResponse(url="/montadoras")

# --- Montadoras ---
@app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
async def view_montadoras_page(
    request: Request,
    db: Session = Depends(get_db),
    success_msg: Optional[str] = None,
    error_msg: Optional[str] = None
):
    """Renderiza a página HTML de gerenciamento de Montadoras."""
    try:
        montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e:
        print(f"Erro ao buscar montadoras: {e}")
        montadoras = []
        error_msg = "Erro ao carregar lista de montadoras."

    return templates.TemplateResponse(
        request=request,
        name="montadoras.html",
        context={"montadoras": montadoras, "success_message": success_msg, "error_message": error_msg}
    )

# Rota POST ajustada - sem a dependência Htmx
@app.post("/montadoras", tags=["Interface Montadoras"]) # Removido response_class=HtmxResponse (FastAPI lida com o retorno)
async def handle_add_montadora(
    request: Request,
    nome_montadora: str = Form(..., min_length=2),
    db: Session = Depends(get_db)
    # Removido: hx: Htmx = Htmx()
):
    """Processa adição de montadora via form e retorna fragmentos HTML."""
    error_msg = None
    success_msg = None
    montadoras = []

    try:
        montadora_criada = crud.create_montadora(db, montadora=schemas.MontadoraCreate(nome_montadora=nome_montadora))
        success_msg = f"'{montadora_criada.nome_montadora}' (Cód: {montadora_criada.cod_montadora}) criada!"
    except ValueError as e:
        error_msg = str(e)
    except Exception as e:
        print(f"Erro inesperado ao criar montadora: {e}")
        error_msg = "Erro inesperado no servidor."

    # Busca lista atualizada para re-renderizar fragmento
    try:
         montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e:
         print(f"Erro ao buscar montadoras pós-adição: {e}")
         error_msg = error_msg or "Erro ao recarregar lista."

    context = {"montadoras": montadoras, "error_message": error_msg, "success_message": success_msg}

    # Sempre retorna os dois fragmentos concatenados. O HTMX vai usá-los
    # com base nos atributos hx-target e hx-swap definidos no HTML do formulário.
    # Usamos diretamente TemplateResponse do FastAPI.
    response_list = templates.TemplateResponse(
        request=request, name="partials/montadora_list.html", context=context
    )
    response_msg = templates.TemplateResponse(
        request=request, name="partials/messages.html", context=context
    )

    # Retorna o conteúdo dos dois templates. O navegador interpretará isso corretamente
    # se o HTMX estiver esperando HTML. O status code padrão será 200 OK.
    # É importante que os hx-target no HTML estejam corretos.
    return HTMLResponse(content=response_list.body + response_msg.body)


# --- Peças (Endpoints serão adicionados aqui) ---
# Exemplo de estrutura (a implementar)
# @app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
# async def view_pecas_page(request: Request, db: Session = Depends(get_db)): ...

# @app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
# async def view_add_peca_form(request: Request, db: Session = Depends(get_db)): ...

# @app.post("/pecas", tags=["Interface Peças"]) # Provavelmente retornará HTMLResponse também
# async def handle_add_peca(request: Request, ...): ...


# --- Estoque (Endpoints serão adicionados aqui) ---
# ...

# --- Kits (Endpoints serão adicionados aqui) ---
# ...

# --- Outros Endpoints (API pura, se necessário) ---
# Exemplo:
# @app.get("/api/v1/montadoras", response_model=List[schemas.Montadora], tags=["API Montadoras"])
# def api_list_montadoras(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     montadoras = crud.get_montadoras(db, skip=skip, limit=limit)
#     return montadoras
