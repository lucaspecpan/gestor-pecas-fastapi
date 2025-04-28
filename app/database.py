# File: app/database.py (Versão 5.16 - Corrigido HTTPException)
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from fastapi import HTTPException # <-- IMPORT ADICIONADO

# Importar models aqui para que Base conheça as tabelas antes de create_all
# Garante que models não tenha imports circulares com database
try:
    from app import models # Importa o módulo models
except ImportError:
    # Isso pode acontecer se rodarmos um script que não está dentro do pacote 'app' diretamente
    # Tentar importar de forma diferente pode ser necessário em scripts como seed_db
    # Mas para o FastAPI rodando main.py, isso deve funcionar.
    print("Aviso: Não foi possível importar 'app.models' diretamente. Verifique o contexto de execução.")
    # Tenta importar Base diretamente se models não for encontrado (menos ideal)
    Base = declarative_base()

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    print("\n" + "="*50 + "\n ERRO FATAL: DATABASE_URL não definida no .env!\n" + "="*50 + "\n")
    sys.exit(1)

engine = None
try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as connection:
         print("Conexão inicial com o banco de dados bem sucedida!")
except Exception as e:
    print("\n" + "="*50 + f"\n ERRO AO CONECTAR AO BANCO: {e}\n Verifique a DATABASE_URL no .env.\n" + "="*50 + "\n")
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Base para os modelos ORM - Se a importação de models falhou, usa a Base vazia
if 'models' in locals() and hasattr(models, 'Base'):
     Base = models.Base
else:
     # Se models não pôde ser importado, usa a Base vazia criada acima.
     # Isso pode causar problemas no create_all se chamado daqui.
     print("AVISO: Usando Base declarativa vazia pois 'app.models' não pôde ser importado.")
     Base = declarative_base()


# --- Função para inicializar o DB (Criar tabelas) ---
def init_db():
    """Cria as tabelas no banco de dados se elas não existirem."""
    if not engine:
        print("ERRO: Engine do DB não inicializada, tabelas não podem ser criadas.")
        return
    try:
        print("Verificando/Criando tabelas do banco de dados via init_db()...")
        # Garante que a Base tem os metadados corretos antes de chamar create_all
        # Se models foi importado, Base já tem os metadados.
        if 'models' in locals() and hasattr(models, 'Base'):
            models.Base.metadata.create_all(bind=engine)
            print("Tabelas OK.")
        else:
             print("ERRO: Metadados dos modelos não encontrados para criar tabelas.")

    except Exception as e:
        print(f"ERRO ao verificar/criar tabelas via init_db: {e}")

# --- Função para obter uma sessão do DB ---
def get_db():
    """Obtém uma sessão do banco de dados para usar em um endpoint."""
    if SessionLocal is None:
         # Se a sessão não pôde ser criada (provavelmente falha na conexão inicial)
         raise HTTPException(status_code=503, detail="Configuração do banco de dados indisponível.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

