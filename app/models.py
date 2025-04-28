# File: app/models.py (Versão 5.7 - Completo e Corrigido)
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Float,
                        ForeignKey, CheckConstraint, UniqueConstraint, Index, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# Importa a Base do nosso database.py (caminho relativo funciona aqui)
from .database import Base

class Montadora(Base):
    __tablename__ = "montadoras"
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, unique=True, index=True, nullable=False)
    nome_montadora = Column(String(100), unique=True, index=True, nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento um-para-muitos com Modelos
    modelos = relationship("ModeloVeiculo", back_populates="montadora", cascade="all, delete-orphan")
    # Relacionamento direto com Peças (nome diferente para evitar conflito)
    pecas = relationship("Peca", back_populates="montadora_rel")

# --- Tabela Modelos de Veículos ---
class ModeloVeiculo(Base):
    __tablename__ = "modelos_veiculo"
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    nome_modelo = Column(String(100), nullable=False) # Ex: "GOLF MK4", "SORENTO"
    cod_sequencial_modelo = Column(Integer, nullable=False) # Ex: 1, 2, 3... (sequencial POR montadora)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    # Chave única composta para garantir que um nome de modelo seja único por montadora
    __table_args__ = (
        UniqueConstraint('cod_montadora', 'nome_modelo', name='uq_montadora_modelo_nome'),
        UniqueConstraint('cod_montadora', 'cod_sequencial_modelo', name='uq_montadora_modelo_seq'),
        Index('idx_modelo_montadora_nome', "cod_montadora", "nome_modelo"), # Índice para busca
    )

    montadora = relationship("Montadora", back_populates="modelos")
    # Relacionamento um-para-muitos com Peças (um modelo tem várias peças)
    pecas = relationship("Peca", back_populates="modelo_rel")

class Peca(Base):
    __tablename__ = "pecas"
    id = Column(Integer, primary_key=True, index=True)
    sku_variacao = Column(String(15), unique=True, index=True, nullable=False) # MMMXXFFF ou MMMXXFFFR/P
    codigo_base = Column(String(8), index=True, nullable=False) # MMMXXFFF
    sufixo_variacao = Column(String(1), CheckConstraint("sufixo_variacao IN ('R', 'P')"), nullable=True) # R ou P (NULL para N)

    # Chaves estrangeiras e códigos relacionados
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    cod_modelo = Column(Integer, ForeignKey("modelos_veiculo.id"), nullable=False) # FK para ID da tabela Modelos
    nome_item = Column(String(150), nullable=False, index=True) # Ex: "MAQUINA VIDRO ELETRICO"
    cod_final_item = Column(Integer, nullable=False) # Sequencial FFF (999-000) por Montadora/Modelo/NomeItem

    # Campos descritivos e de aplicação
    descricao_peca = Column(Text) # Descrição específica da VARIAÇÃO
    codigo_oem = Column(String(50), index=True)
    anos_aplicacao = Column(String(50)) # Ex: "98-07", "2009-2014"
    posicao_porta = Column(String(10)) # Ex: "TD/RR", "DE/FL", "PTM/TRK"

    # Estoque
    quantidade_estoque = Column(Integer, nullable=False, default=0) # Estoque PRONTO (N/R/P) da VARIAÇÃO

    # Kit
    eh_kit = Column(Boolean, nullable=False, default=False)

    # Custos e Preço (Refatorado)
    custo_ultima_compra = Column(Float, default=0.0)
    aliquota_imposto_percent = Column(Float, default=0.0)
    custo_estimado_adicional = Column(Float, default=0.0)
    preco_venda = Column(Float, nullable=False, default=0.0)

    # Outros
    codigo_ean13 = Column(String(13))
    data_ultima_compra = Column(String(10)) # Formato AAAA-MM-DD
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos SQLAlchemy
    montadora_rel = relationship("Montadora", back_populates="pecas")
    modelo_rel = relationship("ModeloVeiculo", back_populates="pecas") # Relacionamento com ModeloVeiculo
    imagens = relationship("PecaImagem", back_populates="peca", cascade="all, delete-orphan")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="peca", cascade="all, delete-orphan")
    componentes_do_kit = relationship("ComponenteKit", foreign_keys="ComponenteKit.kit_peca_id", back_populates="kit", cascade="all, delete-orphan")
    kit_onde_eh_componente = relationship("ComponenteKit", foreign_keys="ComponenteKit.componente_peca_id", back_populates="componente")

    # Índices importantes
    __table_args__ = (
        Index('idx_pecas_busca_fff', "cod_montadora", "cod_modelo", "nome_item"), # Índice para buscar próximo FFF
        Index('idx_pecas_codigo_base', "codigo_base"),
        Index('idx_pecas_sku_variacao', "sku_variacao"),
        Index('idx_pecas_porta', "posicao_porta"),
        Index('idx_pecas_anos', "anos_aplicacao"),
    )

# --- Tabelas de Imagem, Movimentação, Kit (Estrutura base inalterada, FKs corretas) ---
class PecaImagem(Base):
    __tablename__ = "peca_imagens"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    url_imagem = Column(String(512), nullable=False) # URL Cloudinary
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    peca = relationship("Peca", back_populates="imagens")

class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacoes_estoque"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_movimentacao = Column(String(15), CheckConstraint("tipo_movimentacao IN ('Entrada', 'Saida', 'Ajuste')"), nullable=False) # Simplificado
    quantidade = Column(Integer, nullable=False) # Afeta pecas.quantidade_estoque
    observacao = Column(Text)
    data_movimentacao = Column(DateTime(timezone=True), server_default=func.now())
    peca = relationship("Peca", back_populates="movimentacoes")

class ComponenteKit(Base):
    __tablename__ = "componentes_kit"
    id = Column(Integer, primary_key=True, index=True)
    kit_peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    componente_peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantidade_componente = Column(Integer, nullable=False, default=1)
    kit = relationship("Peca", foreign_keys=[kit_peca_id], back_populates="componentes_do_kit")
    componente = relationship("Peca", foreign_keys=[componente_peca_id], back_populates="kit_onde_eh_componente")
    __table_args__ = ( UniqueConstraint('kit_peca_id', 'componente_peca_id', name='uq_kit_componente'),
                       Index('idx_comp_kit_id', "kit_peca_id"), Index('idx_comp_comp_id', "componente_peca_id"), )

