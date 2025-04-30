    # File: app/main.py (Versão 5.19 - Sem create_all)

    from fastapi import (FastAPI, Depends, HTTPException, Request, Form, status,
                       UploadFile, File, Query, Path) # Adicionado Path
    from fastapi.responses import HTMLResponse, RedirectResponse, Response
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from sqlalchemy.orm import Session
    from typing import List, Optional
    from contextlib import asynccontextmanager # Para lifespan
    from datetime import date

    # Importa nossos módulos internos
    from app import database, models, schemas, crud, config

    # --- Evento Startup/Shutdown (Opcional, mas bom para logs) ---
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Código a ser executado ANTES do app começar a receber requisições
        print("INFO:     Iniciando aplicação Gestor de Peças...")
        if not database.engine:
            print("ERRO FATAL: Engine do banco não pôde ser criada. Verifique .env e conexão.")
        # Não criamos tabelas aqui mais
        yield
        # Código a ser executado QUANDO o app for parar
        print("INFO:     Finalizando aplicação...")

    # --- Configuração do App FastAPI ---
    app = FastAPI(title="Gestor de Peças Pro++ API v5.19", lifespan=lifespan)
    templates = Jinja2Templates(directory="app/templates")
    # app.mount("/static", StaticFiles(directory="app/static"), name="static")
    get_db = database.get_db

    # --- Helper Flash (Opcional, para mensagens entre redirects) ---
    # Simples implementação, pode ser melhorada com cookies/sessões
    def flash(request: Request, message: str, category: str = "info") -> dict:
        # Em uma implementação real, isso usaria request.session ou cookies
        # Aqui, apenas retornamos um dict para ser usado no redirect com query params
        if category == "success": return {"flash_success": message}
        else: return {"flash_error": message}

    # --- Rotas HTML e API ---
    @app.get("/", response_class=RedirectResponse, include_in_schema=False)
    async def read_root(): return RedirectResponse(url="/pecas")

    # --- Montadoras ---
    @app.get("/montadoras", response_class=HTMLResponse, tags=["Interface Montadoras"])
    async def view_montadoras_page(request: Request, db: Session = Depends(get_db), success_msg: Optional[str]=Query(None), error_msg: Optional[str]=Query(None)):
        montadoras=[]; err_fetch=None
        try: montadoras = crud.get_montadoras(db, limit=1000)
        except Exception as e: err_fetch = f"Erro carregar montadoras: {e}"
        return templates.TemplateResponse( request=request, name="montadoras.html", context={"montadoras": montadoras, "success_message":success_msg, "error_message": error_msg or err_fetch} )

    @app.post("/montadoras", tags=["Interface Montadoras"])
    async def handle_add_montadora( request: Request, nome_montadora: str = Form(..., min_length=2), db: Session = Depends(get_db) ):
        err_msg=None; succ_msg=None; montadoras=[]
        try: mont_c = crud.create_montadora(db, montadora=schemas.MontadoraCreate(nome_montadora=nome_montadora)); succ_msg = f"'{mont_c.nome_montadora}' (Cód: {mont_c.cod_montadora}) criada!"
        except ValueError as e: err_msg = str(e)
        except Exception as e: err_msg = f"Erro inesperado: {e}"
        try: montadoras = crud.get_montadoras(db, limit=1000)
        except Exception: err_msg = err_msg or "Erro recarregar lista."
        ctx = {"montadoras": montadoras, "error_message": err_msg, "success_message": succ_msg}
        resp_list = templates.TemplateResponse(request=request, name="partials/montadora_list.html", context=ctx)
        resp_msg = templates.TemplateResponse(request=request, name="partials/messages.html", context=ctx)
        resp_list.headers["HX-Retarget"] = "#montadora-list-container, #messages"; resp_list.headers["HX-Reswap"] = "innerHTML"
        return HTMLResponse(content=resp_list.body + resp_msg.body, headers=resp_list.headers)

    # --- Peças ---
    @app.get("/pecas", response_class=HTMLResponse, tags=["Interface Peças"])
    async def view_pecas_list( request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0),
                               limit: int = Query(25, ge=1, le=100), search: Optional[str] = Query(None),
                               success_msg: Optional[str]=Query(None), error_msg: Optional[str]=Query(None)):
        pecas = []; error_msg_fetch = None
        try:
            if search and search.strip() and len(search.strip()) >= 1: pecas = crud.search_pecas_crud(db, search_term=search.strip(), skip=skip, limit=limit)
            else: pecas = crud.get_pecas_list(db, skip=skip, limit=limit)
        except Exception as e: print(f"Erro buscar/listar peças: {e}"); error_msg_fetch = "Erro carregar lista."
        return templates.TemplateResponse( request=request, name="pecas_list.html", context={"pecas": pecas, "search_term": search, "success_message": success_msg, "error_message": error_msg or error_msg_fetch} )

    @app.get("/pecas/nova", response_class=HTMLResponse, tags=["Interface Peças"])
    async def view_add_peca_form(request: Request, db: Session = Depends(get_db)):
        montadoras = []; err_msg = None
        try:
            montadoras = crud.get_montadoras(db, limit=1000)
            if not montadoras: err_msg = "Cadastre montadoras primeiro."
        except Exception as e: print(f"Erro form peças: {e}"); err_msg = f"Erro carregar montadoras: {e}"
        portas_opts = ["DD/FR", "DE/FL", "TD/RR", "TE/RL", "PTM/TRK"]
        return templates.TemplateResponse( request=request, name="pecas_add.html", context={"montadoras": montadoras, "error_message": err_msg, "portas_opts": portas_opts} )

    @app.post("/pecas", status_code=status.HTTP_303_SEE_OTHER, response_class=RedirectResponse, tags=["Interface Peças"])
    async def handle_add_peca_variacao( request: Request, # Dados do form...
        cod_montadora: int = Form(...), nome_modelo: str = Form(..., min_length=1), nome_item: str = Form(..., min_length=3), tipo_variacao: str = Form(..., pattern="^[NRP]$"),
        descricao_peca: Optional[str] = Form(None), categoria: Optional[str] = Form(None), codigo_oem: Optional[str] = Form(None), anos_aplicacao: Optional[str] = Form(None),
        posicao_porta: Optional[str] = Form(None), quantidade_estoque: int = Form(..., ge=0), custo_ultima_compra: float = Form(0.0, ge=0),
        aliquota_imposto_percent: float = Form(0.0, ge=0, le=100), custo_estimado_adicional: float = Form(0.0, ge=0), preco_venda: float = Form(..., ge=0),
        data_ultima_compra: Optional[date] = Form(None), imagens: List[UploadFile] = File([], alias="imagens[]"), db: Session = Depends(get_db) ):

        uploaded_image_urls = []; errors = {} # Usar dict para erros
        if len(imagens) > 10: errors["imagens"] = "Máx 10 imagens."
        elif config.cloudinary_configured and imagens:
            for file in imagens:
                if file.filename:
                    try: secure_url = await crud.upload_image_to_cloudinary(file);
                    if secure_url: uploaded_image_urls.append(secure_url)
                    except Exception as e: errors[f"img_{file.filename}"] = f"Upload falhou: {e}"

        peca_schema = None
        if not errors.get("imagens"): # Só valida schema se upload ok (ou sem imagens)
            try:
                peca_schema_data = {k:v for k,v in locals().items() if k in schemas.PecaCreate.model_fields} # Pega dados do form
                peca_schema = schemas.PecaCreate(**peca_schema_data)
            except Exception as p_err: errors["dados"] = f"Dados inválidos: {p_err}"

        redirect_url = "/pecas/nova"; query_params = {}; # Volta pro form por padrão
        if not errors and peca_schema:
            try: peca_criada = crud.create_peca_variacao(db=db, peca_data=peca_schema, image_urls=uploaded_image_urls); query_params = flash(request, f"SKU {peca_criada.sku_variacao} criado!", "success"); redirect_url = "/pecas" # Redireciona pra lista se sucesso
            except ValueError as e: errors["salvar"] = str(e)
            except Exception as e: print(e); errors["salvar"] = "Erro servidor salvar peça."

        if errors: query_params = flash(request, f"Erros: {errors}", "error")

        final_redirect_url = redirect_url
        if query_params.get("flash_success"): final_redirect_url += f"?success_msg={query_params['flash_success']}"
        elif query_params.get("flash_error"): final_redirect_url += f"?error_msg={query_params['flash_error']}"
        return RedirectResponse(url=final_redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    # --- Rotas de Detalhe, Edição, Deleção (A implementar a interface) ---
    @app.get("/pecas/{peca_id}", response_class=HTMLResponse, tags=["Interface Peças"])
    async def view_peca_detail(request: Request, peca_id: int = Path(..., gt=0), db: Session = Depends(get_db), success_msg: Optional[str]=Query(None), error_msg: Optional[str]=Query(None)):
        db_peca = db.query(models.Peca).options( selectinload(models.Peca.imagens), selectinload(models.Peca.montadora_rel), selectinload(models.Peca.modelo_rel) ).filter(models.Peca.id == peca_id).first()
        if not db_peca: raise HTTPException(status_code=404, detail="Peça não encontrada")
        lucro_estimado = crud.calcula_lucro(db_peca)
        # Precisa criar o template peca_detail.html
        return templates.TemplateResponse( request=request, name="placeholder.html", context={"page_title": f"Detalhes Peça {db_peca.sku_variacao}", "peca": db_peca, "imagens": db_peca.imagens, "lucro": lucro_estimado, "success_message": success_msg, "error_message": error_msg} )

    # --- Placeholder para outras páginas ---
    @app.get("/{page_name}", response_class=HTMLResponse, include_in_schema=False)
    async def view_placeholder_page(request: Request, page_name: str):
        known_placeholders = { "estoque": "Estoque | Kits", "kits": "Estoque | Kits",
                               "importar-exportar": "Importar / Exportar", "ajuda": "Ajuda" }
        if page_name in known_placeholders:
            title = known_placeholders[page_name]
            placeholder_path = os.path.join("app", "templates", "placeholder.html")
            if not os.path.exists(placeholder_path):
                 with open(placeholder_path, "w", encoding="utf-8") as f: f.write("{% extends \"base.html\" %}\n{% block title %}{{ page_title }}{% endblock %}\n{% block content %}<h2>{{ page_title }}</h2><p><i>(Página em construção)</i></p>{% endblock %}\n")
            return templates.TemplateResponse(request=request, name="placeholder.html", context={"page_title": title})
        else: raise HTTPException(status_code=404, detail=f"Página '/{page_name}' não encontrada.")

    