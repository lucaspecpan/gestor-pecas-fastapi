# File: app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import sys # Para sair se o DB não for configurado

load_dotenv() # Carrega variáveis do .env (que estará no seu PC)

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    # Esta mensagem aparecerá no console quando você rodar localmente se o .env estiver faltando/incorreto
    print("\n" + "="*50)
    print(" ERRO FATAL: Variável de ambiente DATABASE_URL não definida! ")
    print(" Verifique se você criou o arquivo '.env' na raiz do projeto local")
    print(" e colocou a URL de conexão do seu banco PostgreSQL nele.")
    print(" Ex: DATABASE_URL='postgresql://user:pass@host:port/dbname'")
    print("="*50 + "\n")
    # Em um ambiente de produção real, você poderia logar isso em vez de printar
    # sys.exit(1) # Descomente se quiser que o app pare imediatamente se não achar a URL

# Se a URL não for encontrada, engine será None, o que causará erro depois.
# Poderíamos tratar isso melhor, mas por ora, o print acima avisa.
engine = None
if SQLALCHEMY_DATABASE_URL:
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        # Testa a conexão brevemente (opcional, mas bom para debug inicial)
        with engine.connect() as connection:
             print("Conexão inicial com o banco de dados bem sucedida!")
    except Exception as e:
        print("\n" + "="*50)
        print(f" ERRO AO CONECTAR AO BANCO DE DADOS: {e}")
        print(f" Verifique se a DATABASE_URL no seu arquivo .env local está correta:")
        print(f" URL usada (parcialmente oculta): {'***'.join(SQLALCHEMY_DATABASE_URL.split('@')) if '@' in SQLALCHEMY_DATABASE_URL else SQLALCHEMY_DATABASE_URL}")
        print("="*50 + "\n")
        engine = None # Garante que engine é None se falhar
        # sys.exit(1) # Descomente para parar se a conexão falhar

# Só cria SessionLocal se engine foi criado com sucesso
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Base para os modelos ORM
Base = declarative_base()

# Função para obter uma sessão do DB
def get_db():
    if SessionLocal is None:
         # Isso acontecerá se a DATABASE_URL não foi definida ou a conexão falhou
         # Lança um erro que o FastAPI/usuário verá
         raise HTTPException(status_code=503, detail="Configuração do banco de dados indisponível.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
