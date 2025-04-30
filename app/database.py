    # File: app/database.py (Versão 5.19 - Final Simplificado)
    import os
    import sys
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
    from dotenv import load_dotenv
    from fastapi import HTTPException

    load_dotenv()
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

    engine = None
    SessionLocal = None

    if SQLALCHEMY_DATABASE_URL:
        try:
            engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, echo=False)
            with engine.connect() as connection:
                 print("Conexão inicial com o banco de dados bem sucedida (database.py)!")
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception as e:
            print(f"\n!!! ERRO AO CONECTAR/CRIAR ENGINE: {e} !!!\nVerifique a DATABASE_URL no .env.\n")
            engine = None; SessionLocal = None
    else:
         print("\n!!! ERRO FATAL: DATABASE_URL não definida no .env !!!\n")

    # Base para todos os modelos definidos em models.py
    # models.py importará esta Base
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
    