# File: app/database.py (v5.26 - Correção Indentação/Estrutura Final)
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import sys
from fastapi import HTTPException # Import necessário para get_db

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = None # Inicializa como None

if SQLALCHEMY_DATABASE_URL is None:
    print("\n" + "="*50)
    print(" ERRO FATAL: Variável de ambiente DATABASE_URL não definida! ")
    print(" Verifique se criou o arquivo '.env' na raiz do projeto local")
    print(" e colocou a URL de conexão do PostgreSQL nele.")
    print(" Ex: DATABASE_URL='postgresql://user:pass@host:port/dbname'")
    print("="*50 + "\n")
    # Considerar sys.exit(1) aqui se for crítico
else:
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
        # Testa a conexão brevemente
        with engine.connect() as connection:
            print("Conexão inicial com o banco de dados bem sucedida (database.py)!")
    except Exception as e:
        print("\n" + "="*50)
        print(f" ERRO AO CONECTAR AO BANCO DE DADOS (database.py): {e}")
        print(f" Verifique se a DATABASE_URL no seu arquivo .env local está correta.")
        print(" URL usada (parcialmente oculta):", SQLALCHEMY_DATABASE_URL.split('@')[-1] if '@' in SQLALCHEMY_DATABASE_URL else "URL inválida?")
        print("="*50 + "\n")
        engine = None # Garante que engine é None se falhar

# Só cria SessionLocal se engine foi criado com sucesso
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Base para os modelos ORM
Base = declarative_base()

# Função para obter uma sessão do DB
def get_db():
    if SessionLocal is None:
         # Se SessionLocal não foi criado (erro na conexão inicial)
         raise HTTPException(status_code=503, detail="Serviço de banco de dados indisponível.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()