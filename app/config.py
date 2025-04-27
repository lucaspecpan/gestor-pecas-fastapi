# File: app/config.py
import os
import cloudinary
from dotenv import load_dotenv

load_dotenv() # Carrega variáveis do .env

# Configuração Cloudinary
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary_configured = False
if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True # Força HTTPS nas URLs
        )
        cloudinary_configured = True
        print("Cloudinary configurado com sucesso!")
    except Exception as e:
        print(f"ERRO ao configurar Cloudinary: {e}")
else:
    print("AVISO: Credenciais Cloudinary não encontradas no .env. Upload de imagens será desabilitado.")

# Você pode adicionar outras configurações do app aqui se necessário
# Ex: APP_TITLE = "Gestor Pro++"
