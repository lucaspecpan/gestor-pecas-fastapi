# File: app/schemas.py (v5.20 - Correção Definitiva de Herança)
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date

# Configuração Pydantic v2
model_config = ConfigDict(from_attributes=True)

# --- Montadora Schemas ---
class MontadoraBase(BaseModel): # Herda de Pydantic BaseModel
    nome_montadora: str = Field(..., min_length=2, max_length=100)

    @validator('nome_montadora', pre=True, always=True)
    def name_must_not_be_empty_and_upper(cls, v):
        if not isinstance(v, str) or not v.strip(): raise ValueError('Nome montadora vazio')
        return v.strip().upper()

class MontadoraCreate(MontadoraBase): pass

class Montadora(MontadoraBase): # Herda de Pydantic BaseModel
    id: int
    cod_montadora: int
    data_cadastro: datetime
    model_config = model_config

# --- Modelo Veículo Schemas ---
class ModeloVeiculoBase(BaseModel): # Herda de Pydantic BaseModel
    nome_modelo: str = Field(..., min_length=2, max_length=100)

    @validator('nome_modelo', pre=True, always=True)
    def modelo_name_upper(cls, v):
        if not isinstance(v, str) or not v.strip(): raise ValueError('Nome modelo vazio')
        return v.strip().upper()

class ModeloVeiculoCreate(ModeloVeiculoBase):
    cod_montadora: int

class ModeloVeiculo(ModeloVeiculoBase): # Herda de Pydantic BaseModel
    id: int
    cod_montadora: int
    cod_sequencial_modelo: int
    data_cadastro: datetime
    model_config = model_config

# --- Peça Schemas ---
class PecaBase(BaseModel): # Herda de Pydantic BaseModel
    nome_item: str = Field(..., min_length=3, max_length=150)
    tipo_variacao: str = Field(..., pattern="^[NRP]$") # N, R, P
    descricao_peca: Optional[str] = None
    categoria: Optional[str] = Field(None, max_length=100)
    codigo_oem: Optional[str] = Field(None, max_length=50)
    anos_aplicacao: Optional[str] = Field(None, max_length=50)
    posicao_porta: Optional[str] = Field(None, max_length=10)
    quantidade_estoque: int = Field(..., ge=0) # Obrigatório
    # qtd_para_reparar removido
    custo_ultima_compra: float = Field(0.0, ge=0)
    aliquota_imposto_percent: float = Field(0.0, ge=0, le=100)
    custo_estimado_adicional: float = Field(0.0, ge=0)
    preco_venda: float = Field(..., ge=0) # Obrigatório
    data_ultima_compra: Optional[date] = None

    # Validador/Sanitizer
    @validator('*', pre=True, always=True)
    def sanitize_strings_and_uppercase(cls, v, field):
        if isinstance(v, str):
            stripped = v.strip()
            campos_upper = ['nome_item', 'descricao_peca', 'categoria', 'codigo_oem', 'anos_aplicacao', 'posicao_porta']
            return stripped.upper() if stripped and field.name in campos_upper else (stripped if stripped else None)
        return v
    @validator('custo_ultima_compra', 'aliquota_imposto_percent', 'custo_estimado_adicional', pre=True, always=True)
    def default_costs_to_zero(cls, v): return v or 0.0


class PecaCreate(PecaBase):
     cod_montadora: int
     nome_modelo: str # Usuário digita nome

class Peca(PecaBase): # Schema completo para retorno
    id: int
    sku_variacao: str
    codigo_base: str
    sufixo_variacao: Optional[str]
    cod_montadora: int
    cod_modelo: int # ID do modelo_veiculo
    # nome_item já está na Base
    cod_final_item: int # Renomeado
    codigo_ean13: Optional[str]
    # quantidade_estoque já está na Base
    eh_kit: bool
    data_cadastro: datetime
    # Relacionamentos aninhados são opcionais no retorno
    # montadora_rel: Optional[Montadora] = None # Exemplo
    # modelo_veiculo: Optional[ModeloVeiculo] = None # Exemplo
    model_config = model_config

# --- Imagem Schemas ---
class PecaImagemBase(BaseModel): url_imagem: str
class PecaImagemCreate(PecaImagemBase): peca_id: int
class PecaImagem(PecaImagemBase):
    id: int; peca_id: int; data_cadastro: datetime
    model_config = model_config
class PecaComImagens(Peca): imagens: List[PecaImagem] = []; model_config = model_config

# --- Estoque Schemas ---
class MovimentacaoEstoqueBase(BaseModel):
     tipo_movimentacao: str = Field(..., pattern="^(Entrada|Saida|Ajuste)$")
     quantidade: int = Field(..., ge=0)
     observacao: Optional[str] = None
class MovimentacaoEstoqueCreate(MovimentacaoEstoqueBase): peca_id: int
class MovimentacaoEstoque(MovimentacaoEstoqueBase):
    id: int; peca_id: int; data_movimentacao: datetime
    model_config = model_config

# --- Kit Schemas ---
class ComponenteKitBase(BaseModel): componente_peca_id: int; quantidade_componente: int = Field(..., gt=0)
class ComponenteKitCreate(ComponenteKitBase): kit_peca_id: int
class ComponenteKit(ComponenteKitBase):
    id: int; kit_peca_id: int
    # componente: Optional[Peca] = None # Opcional
    model_config = model_config
class KitComComponentes(Peca): componentes_do_kit: List[ComponenteKit] = []; model_config = model_config