# File: app/database.py (Versão 5.18 - Simplificado)
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from fastapi import HTTPException # Mantido para get_db

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
SessionLocal = None

if SQLALCHEMY_DATABASE_URL:
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        # Testa a conexão inicial
        with engine.connect() as connection:
             print("Conexão inicial com o banco de dados bem sucedida (database.py)!")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    except Exception as e:
        print("\n" + "="*50 + f"\n ERRO AO CONECTAR/CRIAR ENGINE: {e}\n Verifique a DATABASE_URL no .env.\n" + "="*50 + "\n")
        engine = None # Garante que engine é None se falhar
        SessionLocal = None
else:
     print("\n" + "="*50 + "\n ERRO FATAL: DATABASE_URL não definida no .env!\n" + "="*50 + "\n")


# Base para os modelos ORM - models.py importará esta Base
Base = declarative_base()

# --- Função para obter uma sessão do DB ---
def get_db():
    """Obtém uma sessão do banco de dados para usar em um endpoint."""
    if SessionLocal is None:
         # Se a sessão não pôde ser criada (provavelmente falha na conexão inicial)
         # Log do erro já deve ter aparecido no console ao iniciar
         raise HTTPException(status_code=503, detail="Configuração do banco de dados indisponível.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# A função init_db() foi removida daqui.
# A criação das tabelas será feita explicitamente no seed_db.py ou main.py (se necessário).

