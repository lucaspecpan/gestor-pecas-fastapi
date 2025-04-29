# File: app/config.py (v5.24 - Opções Cloudinary)
import os
import cloudinary
from dotenv import load_dotenv

load_dotenv() # Carrega variáveis do .env

# --- Configuração Banco de Dados (Lida pelo database.py) ---
# DATABASE_URL = os.getenv("DATABASE_URL") # Lida no database.py

# --- Configuração Cloudinary ---
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
            secure=True # Força HTTPS
        )
        cloudinary_configured = True
        print("Cloudinary configurado com sucesso (config.py)!")
    except Exception as e:
        print(f"ERRO ao configurar Cloudinary (config.py): {e}")
else:
    print("AVISO: Credenciais Cloudinary não encontradas no .env. Upload desabilitado.")

# --- Opções de Upload Cloudinary (Ajustar conforme necessidade) ---

# Ativar remoção de fundo? Requer Add-on pago no Cloudinary!
CLOUDINARY_REMOVE_BG = os.getenv("CLOUDINARY_REMOVE_BG", "false").lower() == "true"
# Pasta para upload no Cloudinary
CLOUDINARY_UPLOAD_FOLDER = "gestor_pecas"
# Transformações padrão a serem aplicadas NO UPLOAD (se desejado)
# Ex: Limitar tamanho, remover fundo se ativo. CUIDADO: Altera o original!
# É geralmente MELHOR aplicar transformações na URL de exibição.
CLOUDINARY_DEFAULT_UPLOAD_TRANSFORMATION = []
if CLOUDINARY_REMOVE_BG:
     print("AVISO: Remoção de fundo Cloudinary ativada (requer add-on pago).")
     # Adiciona a transformação de remoção de fundo
     CLOUDINARY_DEFAULT_UPLOAD_TRANSFORMATION.append(
         {'effect': "background_removal"}
         # Você pode adicionar mais opções aqui se o add-on suportar,
         # como refinar a borda, etc. Consulte a documentação do add-on.
     )
# Exemplo: Limitar tamanho no upload (manter proporção, máx 1500x1500)
# CLOUDINARY_DEFAULT_UPLOAD_TRANSFORMATION.append(
#     {'width': 1500, 'height': 1500, 'crop': 'limit'}
# )

# --- Transformações Padrão para EXIBIÇÃO (via URL) ---
# Para Thumbnails (ex: na lista de peças)
CLOUDINARY_TRANSFORM_THUMB = "w_150,h_100,c_pad,b_auto,q_auto,f_auto"
# Para Imagem Principal (ex: na página de detalhes) - Maior, mas otimizada
CLOUDINARY_TRANSFORM_DETAIL = "w_600,h_600,c_pad,b_auto,q_auto:good,f_auto"
# Para Marketplaces (Alta qualidade, tamanho específico se necessário)
CLOUDINARY_TRANSFORM_MARKETPLACE = "w_1200,h_1200,c_pad,b_rgb:ffffff,q_90" # Ex: 1200x1200 fundo branco, alta qualidade JPG (sem f_auto)

# --- Outras Configurações ---
# ...