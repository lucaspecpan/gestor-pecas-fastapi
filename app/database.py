# File: app/database.py (Versão 5.17 - Simplificado)
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from fastapi import HTTPException # Mantido para get_db

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    print("\n" + "="*50 + "\n ERRO FATAL: DATABASE_URL não definida no .env!\n" + "="*50 + "\n")
    engine = None
else:
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        with engine.connect() as connection:
             print("Conexão inicial com o banco de dados bem sucedida!")
    except Exception as e:
        print("\n" + "="*50 + f"\n ERRO AO CONECTAR AO BANCO: {e}\n Verifique a DATABASE_URL no .env.\n" + "="*50 + "\n")
        engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Base para os modelos ORM - models.py importará esta Base
Base = declarative_base()

# --- Função para obter uma sessão do DB ---
def get_db():
    """Obtém uma sessão do banco de dados para usar em um endpoint."""
    if SessionLocal is None:
         raise HTTPException(status_code=503, detail="Configuração do banco de dados indisponível.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# REMOVIDA a função init_db daqui
