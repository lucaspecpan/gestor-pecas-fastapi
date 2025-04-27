# File: app/schemas.py (Atualizado v5.5)
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date # Import date

model_config = ConfigDict(from_attributes=True)

# --- Montadora Schemas (Inalterado) ---
class MontadoraBase(BaseModel):
    nome_montadora: str = Field(..., min_length=2, max_length=100)
    @validator('nome_montadora')
    def name_must_not_be_empty(cls, v):
        if not v.strip(): raise ValueError('Nome montadora vazio')
        return v.strip().upper()
class MontadoraCreate(MontadoraBase): pass
class Montadora(MontadoraBase):
    id: int; cod_montadora: int; data_cadastro: datetime
    model_config = model_config

# --- Peça Schemas (Atualizado) ---
class PecaBase(BaseModel):
    descricao_peca: str = Field(..., min_length=3)
    cod_modelo: int = Field(..., gt=0)
    tipo_variacao: str = Field(..., pattern="^[NRP]$") # N, R, P
    codigo_oem: Optional[str] = Field(None, max_length=50)
    anos_aplicacao: Optional[str] = Field(None, max_length=50) # NOVO
    posicao_porta: Optional[str] = Field(None, max_length=10) # NOVO
    qtd_para_reparar: Optional[int] = Field(0, ge=0) # NOVO (Estoque pronto vem depois)
    custo_insumos: Optional[float] = Field(0.0, ge=0)
    custo_etiqueta: Optional[float] = Field(0.0, ge=0)
    custo_embalagem: Optional[float] = Field(0.0, ge=0)
    impostos_percent: Optional[float] = Field(0.0, ge=0, le=100)
    preco_venda: Optional[float] = Field(0.0, ge=0) # Default 0, pode ser alterado
    data_ultima_compra: Optional[date] = None # Usa 'date' do datetime

    # Validador para strings opcionais (limpa ou define None)
    @validator('codigo_oem', 'descricao_peca', 'anos_aplicacao', 'posicao_porta', pre=True, always=True)
    def sanitize_strings(cls, v):
         if isinstance(v, str):
             stripped = v.strip()
             return stripped if stripped else None
         return v

class PecaCreate(PecaBase):
     cod_montadora: int # Necessário para criar

class Peca(PecaBase): # Schema completo para retorno
    id: int
    sku_variacao: str
    codigo_base: str
    sufixo_variacao: Optional[str] # R ou P
    cod_montadora: int
    cod_final_base: int
    codigo_ean13: Optional[str]
    quantidade_estoque: int # Estoque pronto
    eh_kit: bool
    data_cadastro: datetime
    # Se quiser incluir a montadora completa no retorno:
    # montadora: Montadora
    model_config = model_config

# --- Imagem Schemas (Atualizado) ---
class PecaImagemBase(BaseModel):
    url_imagem: str # Agora armazena a URL

class PecaImagem(PecaImagemBase):
    id: int
    peca_id: int
    data_cadastro: datetime
    model_config = model_config

# Schema para retornar Peça com suas Imagens
class PecaComImagens(Peca):
    imagens: List[PecaImagem] = []
    model_config = model_config

# --- Adicionar Schemas para Estoque, Kits depois ---
