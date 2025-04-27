# File: app/main.py
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, UploadFile, File # Adicionado UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional

# Habilita o uso de respostas com fragmentos HTMX
from htmx_fastapi import Htmx, HtmxResponse

# Importa nossos módulos internos
from . import crud, models, schemas, database

# Cria/Verifica as tabelas no banco de dados ANTES de iniciar o app
# É importante que models.py seja importado antes desta linha
try:
    print("Verificando/Criando tabelas do banco de dados...")
    models.Base.metadata.create_all(bind=database.engine)
    print("Tabelas OK.")
except Exception as e:
    print(f"ERRO FATAL ao verificar/criar tabelas: {e}")
    # Em um cenário real, logar o erro detalhado.
    # Pode ser um problema na DATABASE_URL no .env ou o DB estar offline.
    # O app pode até iniciar, mas falhará nas operações de DB.

# --- Configuração do App FastAPI ---
app = FastAPI(title="Gestor de Peças Pro++ API")

# Configura templates Jinja2 para servir HTML
templates = Jinja2Templates(directory="app/templates")

# Configura arquivos estáticos (CSS, JS, Imagens) - opcional por enquanto
# Descomente a linha abaixo se criar arquivos CSS/JS na pasta static
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dependência para obter sessão do DB em cada requisição
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
    success_msg: Optional[str] = None, # Para mensagens flash (opcional)
    error_msg: Optional[str] = None
):
    """Renderiza a página HTML de gerenciamento de Montadoras."""
    try:
        montadoras = crud.get_montadoras(db, limit=500) # Busca montadoras existentes
    except Exception as e:
        # Se houver erro ao buscar (ex: DB offline), mostra erro na página
        print(f"Erro ao buscar montadoras: {e}")
        montadoras = []
        error_msg = "Erro ao carregar lista de montadoras do banco de dados."

    return templates.TemplateResponse(
        request=request,
        name="montadoras.html", # Arquivo HTML a ser renderizado
        context={"montadoras": montadoras, "success_message": success_msg, "error_message": error_msg}
    )

@app.post("/montadoras", response_class=HtmxResponse, tags=["Interface Montadoras"])
async def handle_add_montadora(
    request: Request,
    nome_montadora: str = Form(..., min_length=2), # Recebe do formulário HTML, validação básica
    db: Session = Depends(get_db),
    hx: Htmx = Htmx() # Dependência para respostas HTMX
):
    """Processa adição de montadora via HTMX e retorna fragmentos atualizados."""
    error_msg = None
    success_msg = None
    montadoras = [] # Inicializa caso ocorra erro antes da busca

    try:
        montadora_criada = crud.create_montadora(db, montadora=schemas.MontadoraCreate(nome_montadora=nome_montadora))
        success_msg = f"'{montadora_criada.nome_montadora}' (Cód: {montadora_criada.cod_montadora}) criada!"
    except ValueError as e: # Captura erro específico de nome duplicado ou falha no DB do CRUD
        error_msg = str(e)
    except Exception as e: # Outros erros inesperados
        print(f"Erro inesperado ao criar montadora: {e}") # Log
        error_msg = "Erro inesperado no servidor ao tentar criar montadora."

    # Sempre busca a lista atualizada para re-renderizar
    try:
         montadoras = crud.get_montadoras(db, limit=500)
    except Exception as e:
         print(f"Erro ao buscar montadoras após tentativa de adição: {e}")
         error_msg = error_msg or "Erro ao recarregar lista de montadoras." # Mantém erro original se já houver

    context = {"montadoras": montadoras, "error_message": error_msg, "success_message": success_msg}

    # Sempre retorna os dois fragmentos para o HTMX atualizar a lista e a área de mensagens
    # O HTMX substituirá o conteúdo dos elementos com IDs correspondentes na página original
    return templates.TemplateResponse(
        request=request,
        name="partials/montadora_list.html", # Template SÓ com a lista
        context=context
    ) + templates.TemplateResponse(
         request=request,
         name="partials/messages.html", # Template SÓ com as mensagens
         context=context
     )

# --- Peças (Endpoints serão adicionados aqui) ---
# Exemplo de estrutura (a implementar)
# @app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
# async def view_pecas_page(request: Request, db: Session = Depends(get_db)): ...

# @app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
# async def view_add_peca_form(request: Request, db: Session = Depends(get_db)): ...

# @app.post("/pecas", response_class=HtmxResponse, tags=["Interface Peças"])
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
