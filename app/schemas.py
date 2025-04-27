# File: app/schemas.py
from pydantic import BaseModel, Field, validator, ConfigDict # Import ConfigDict for v2 Pydantic
from typing import Optional, List
from datetime import datetime

# Configuração para Pydantic v2 (se aplicável, garante compatibilidade)
# Substitui o antigo `class Config: orm_mode = True`
model_config = ConfigDict(from_attributes=True)

# --- Montadora Schemas ---
class MontadoraBase(BaseModel):
    nome_montadora: str = Field(..., min_length=2, max_length=100, examples=["HYUNDAI"])

    @validator('nome_montadora')
    def name_must_not_be_empty(cls, v):
        if not v.strip(): raise ValueError('Nome da montadora não pode ser vazio')
        return v.strip().upper()

class MontadoraCreate(MontadoraBase):
    pass

class Montadora(MontadoraBase):
    id: int
    cod_montadora: int
    data_cadastro: datetime
    model_config = model_config # Aplica configuração

# --- Peça Schemas (Iniciais) ---
# Schema Base (campos comuns na criação e leitura)
class PecaBase(BaseModel):
    descricao_peca: str = Field(..., min_length=3)
    cod_modelo: int = Field(..., gt=0)
    tipo_variacao: str = Field(..., pattern="^[NRP]$") # N, R, P
    codigo_oem: Optional[str] = Field(None, max_length=50)
    custo_insumos: Optional[float] = Field(0.0, ge=0)
    custo_etiqueta: Optional[float] = Field(0.0, ge=0)
    custo_embalagem: Optional[float] = Field(0.0, ge=0)
    impostos_percent: Optional[float] = Field(0.0, ge=0, le=100)
    preco_venda: Optional[float] = Field(None, ge=0) # Pode ser None ao criar
    data_ultima_compra: Optional[datetime] = None # Pydantic lida bem com datas

    @validator('codigo_oem', 'descricao_peca', pre=True, always=True)
    def sanitize_string_input(cls, v):
         # Remove espaços extras e converte para None se vazio
         if isinstance(v, str):
             stripped = v.strip()
             return stripped if stripped else None
         return v

# Schema para Criação (precisa de mais infos)
class PecaCreate(PecaBase):
    cod_montadora: int # Precisa saber a montadora ao criar

# Schema para Leitura/Retorno (inclui campos gerados)
class Peca(PecaBase):
    id: int
    sku_variacao: str
    codigo_base: str
    sufixo_variacao: Optional[str] # R ou P
    cod_montadora: int
    cod_final_base: int
    codigo_ean13: Optional[str]
    quantidade_estoque: int
    eh_kit: bool
    data_cadastro: datetime
    # montadora: Montadora # Pode incluir dados da montadora aninhados se necessário

    model_config = model_config # Aplica configuração

# --- Imagem Schemas ---
class PecaImagemBase(BaseModel):
    nome_arquivo_imagem: str

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
