# File: app/schemas.py (Versão 5.6 - Com Categoria)
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date

model_config = ConfigDict(from_attributes=True)

# --- Montadora Schemas (Inalterado) ---
class MontadoraBase(BaseModel):
    nome_montadora: str = Field(..., min_length=2, max_length=100)
    @validator('nome_montadora', pre=True, always=True) # Adicionado pre=True
    def name_must_not_be_empty(cls, v):
        if not isinstance(v, str) or not v.strip(): raise ValueError('Nome montadora vazio')
        return v.strip().upper()
class MontadoraCreate(MontadoraBase): pass
class Montadora(MontadoraBase):
    id: int; cod_montadora: int; data_cadastro: datetime
    model_config = model_config

# --- Peça Schemas (Atualizado com categoria) ---
class PecaBase(BaseModel):
    descricao_peca: str = Field(..., min_length=3)
    categoria: Optional[str] = Field(None, max_length=100) # NOVO CAMPO
    cod_modelo: int = Field(..., gt=0)
    tipo_variacao: str = Field(..., pattern="^[NRP]$") # N, R, P
    codigo_oem: Optional[str] = Field(None, max_length=50)
    anos_aplicacao: Optional[str] = Field(None, max_length=50)
    posicao_porta: Optional[str] = Field(None, max_length=10)
    qtd_para_reparar: Optional[int] = Field(0, ge=0)
    custo_insumos: Optional[float] = Field(0.0, ge=0)
    custo_etiqueta: Optional[float] = Field(0.0, ge=0)
    custo_embalagem: Optional[float] = Field(0.0, ge=0)
    impostos_percent: Optional[float] = Field(0.0, ge=0, le=100)
    preco_venda: Optional[float] = Field(0.0, ge=0) # Default 0
    data_ultima_compra: Optional[date] = None

    # Validador para strings opcionais
    @validator('codigo_oem', 'descricao_peca', 'anos_aplicacao', 'posicao_porta', 'categoria', pre=True, always=True)
    def sanitize_strings(cls, v):
         if isinstance(v, str):
             stripped = v.strip()
             return stripped if stripped else None
         return v

    # Validador para garantir que tipo_variacao seja maiúsculo
    @validator('tipo_variacao', pre=True, always=True)
    def uppercase_tipo_variacao(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        raise ValueError("Tipo Variação deve ser uma string")


class PecaCreate(PecaBase):
     cod_montadora: int

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
    model_config = model_config

# --- Imagem Schemas (Inalterado) ---
class PecaImagemBase(BaseModel):
    url_imagem: str
class PecaImagem(PecaImagemBase):
    id: int; peca_id: int; data_cadastro: datetime
    model_config = model_config

class PecaComImagens(Peca):
    imagens: List[PecaImagem] = []
    model_config = model_config

# --- Adicionar Schemas para Estoque, Kits depois ---
# Ex:
# class MovimentacaoCreate(BaseModel): ...
# class Movimentacao(BaseModel): ...
# class ComponenteCreate(BaseModel): ...
# class Componente(BaseModel): ...

