# File: app/schemas.py (Versão 5.7 - Refatorado Modelo/Item/Custo)
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date

# Configuração Pydantic v2
model_config = ConfigDict(from_attributes=True)

# --- Montadora Schemas ---
class MontadoraBase(BaseModel):
    nome_montadora: str = Field(..., min_length=2, max_length=100)

    @validator('nome_montadora', pre=True, always=True)
    def name_must_not_be_empty_upper(cls, v):
        if not isinstance(v, str) or not v.strip(): raise ValueError('Nome montadora vazio')
        return v.strip().upper() # Garante UpperCase

class MontadoraCreate(MontadoraBase):
    pass

class Montadora(MontadoraBase):
    id: int
    cod_montadora: int
    data_cadastro: datetime
    model_config = model_config

# --- ModeloVeiculo Schemas ---
class ModeloVeiculoBase(BaseModel):
    nome_modelo: str = Field(..., min_length=1, max_length=100)
    cod_montadora: int # Referência à montadora

    @validator('nome_modelo', pre=True, always=True)
    def modelo_name_upper(cls, v):
        if not isinstance(v, str) or not v.strip(): raise ValueError('Nome modelo vazio')
        return v.strip().upper()

class ModeloVeiculoCreate(ModeloVeiculoBase):
    pass # Para criar, precisa do nome e cod_montadora

class ModeloVeiculo(ModeloVeiculoBase):
    id: int
    cod_sequencial_modelo: int # Código sequencial gerado
    data_cadastro: datetime
    # montadora: Montadora # Pode incluir dados da montadora se necessário
    model_config = model_config

# --- Peça Schemas (Refatorado) ---
class PecaBase(BaseModel):
    # Identificação do Item
    nome_item: str = Field(..., min_length=3, max_length=150) # Nome do item agora é chave
    tipo_variacao: str = Field(..., pattern="^[NRP]$") # N, R, P

    # Descrição e Aplicação
    descricao_peca: Optional[str] = None # Descrição específica da variação
    codigo_oem: Optional[str] = Field(None, max_length=50)
    anos_aplicacao: Optional[str] = Field(None, max_length=50)
    posicao_porta: Optional[str] = Field(None, max_length=10)

    # Custos e Preço (Refatorado)
    custo_ultima_compra: Optional[float] = Field(0.0, ge=0)
    aliquota_imposto_percent: Optional[float] = Field(0.0, ge=0, le=100)
    custo_estimado_adicional: Optional[float] = Field(0.0, ge=0)
    preco_venda: float = Field(..., ge=0) # Tornar preço obrigatório? Ou default 0? Obrigatório por enquanto.

    # Outros
    data_ultima_compra: Optional[date] = None
    quantidade_estoque: int = Field(..., ge=0) # Estoque inicial obrigatório ao criar? Sim.
    # qtd_para_reparar foi removido do modelo Peca

    # Validadores
    @validator('nome_item', 'descricao_peca', 'codigo_oem', 'anos_aplicacao', 'posicao_porta', pre=True, always=True)
    def sanitize_and_upper_strings(cls, v):
         if isinstance(v, str):
             stripped = v.strip().upper() # Converte para Maiúsculas
             return stripped if stripped else None
         return v

    @validator('tipo_variacao', pre=True, always=True)
    def uppercase_tipo_variacao(cls, v):
        if isinstance(v, str): return v.strip().upper()
        raise ValueError("Tipo Variação deve ser string")

class PecaCreate(PecaBase):
     # Para criar, precisamos saber a qual montadora e modelo pertence
     cod_montadora: int
     # O usuário digitará o NOME do modelo, não o ID interno
     nome_modelo: str = Field(..., min_length=1, max_length=100)

     @validator('nome_modelo', pre=True, always=True)
     def modelo_create_name_upper(cls, v):
         if not isinstance(v, str) or not v.strip(): raise ValueError('Nome modelo vazio')
         return v.strip().upper()

class Peca(PecaBase): # Schema completo para retorno
    id: int
    sku_variacao: str
    codigo_base: str
    sufixo_variacao: Optional[str] # R ou P
    cod_montadora: int
    cod_modelo: int # ID da tabela modelos_veiculo
    cod_final_item: int # Sequencial FFF
    codigo_ean13: Optional[str]
    eh_kit: bool
    data_cadastro: datetime
    # Relacionamentos podem ser carregados se necessário
    # montadora_rel: Montadora
    # modelo_rel: ModeloVeiculo
    model_config = model_config

# --- Imagem Schemas (Inalterado) ---
class PecaImagemBase(BaseModel): url_imagem: str
class PecaImagem(PecaImagemBase): id: int; peca_id: int; data_cadastro: datetime; model_config = model_config
class PecaComImagens(Peca): imagens: List[PecaImagem] = []; model_config = model_config

# --- Estoque Schemas ---
class MovimentacaoBase(BaseModel):
    tipo_movimentacao: str = Field(..., pattern="^(Entrada|Saida|Ajuste)$") # Tipos básicos
    quantidade: int = Field(..., gt=0, description="Quantidade a ser movimentada (positiva)")
    observacao: Optional[str] = None

class MovimentacaoCreate(MovimentacaoBase):
    peca_id: int # ID da variação a ser movimentada

class Movimentacao(MovimentacaoBase):
    id: int
    peca_id: int
    data_movimentacao: datetime
    model_config = model_config

# --- Kit Schemas ---
class ComponenteKitBase(BaseModel):
    componente_peca_id: int # ID da variação componente
    quantidade_componente: int = Field(1, gt=0)

class ComponenteKitCreate(ComponenteKitBase):
     pass # kit_peca_id virá da URL ou contexto

class ComponenteKit(ComponenteKitBase):
    id: int
    kit_peca_id: int
    # Pode incluir dados do componente se necessário
    # componente: Peca
    model_config = model_config

class KitComComponentes(Peca): # Assume que Peca já tem eh_kit=True
     componentes_do_kit: List[ComponenteKit] = []
     model_config = model_config

