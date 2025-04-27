# File: app/models.py (Versão 5.6 - Com Categoria)
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Float,
                        ForeignKey, CheckConstraint, UniqueConstraint, Index, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Montadora(Base):
    __tablename__ = "montadoras"
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, unique=True, index=True, nullable=False)
    nome_montadora = Column(String(100), unique=True, index=True, nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    pecas = relationship("Peca", back_populates="montadora")

class Peca(Base):
    __tablename__ = "pecas"
    id = Column(Integer, primary_key=True, index=True)
    sku_variacao = Column(String(15), unique=True, index=True, nullable=False)
    codigo_base = Column(String(8), index=True, nullable=False)
    sufixo_variacao = Column(String(1), CheckConstraint("sufixo_variacao IN ('R', 'P')"), nullable=True)
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    cod_modelo = Column(Integer, nullable=False) # Assumindo que este é um ID interno ou código simples do modelo
    cod_final_base = Column(Integer, nullable=False)
    descricao_peca = Column(Text, nullable=False) # Tornar descrição obrigatória
    categoria = Column(String(100), index=True) # NOVO CAMPO: Ex: "Máquina Vidro", "Componente Reparo"
    codigo_oem = Column(String(50), index=True)
    codigo_ean13 = Column(String(13))
    anos_aplicacao = Column(String(50)) # Ex: "98-07", "2009-2014"
    posicao_porta = Column(String(10)) # Ex: "TD/RR", "DE/FL", "PTM/TRK"
    quantidade_estoque = Column(Integer, nullable=False, default=0) # Estoque PRONTO (N/R)
    qtd_para_reparar = Column(Integer, nullable=False, default=0) # Estoque aguardando reparo (pode ser usado para P também?)
    eh_kit = Column(Boolean, nullable=False, default=False)
    custo_insumos = Column(Float, default=0.0)
    custo_etiqueta = Column(Float, default=0.0)
    custo_embalagem = Column(Float, default=0.0)
    impostos_percent = Column(Float, default=0.0)
    preco_venda = Column(Float, default=0.0) # Preço igual para N e R, 0 para P?
    data_ultima_compra = Column(String(10))
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    montadora = relationship("Montadora", back_populates="pecas")
    imagens = relationship("PecaImagem", back_populates="peca", cascade="all, delete-orphan")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="peca", cascade="all, delete-orphan")
    componentes_do_kit = relationship("ComponenteKit", foreign_keys="ComponenteKit.kit_peca_id", back_populates="kit", cascade="all, delete-orphan")
    kit_onde_eh_componente = relationship("ComponenteKit", foreign_keys="ComponenteKit.componente_peca_id", back_populates="componente")

    __table_args__ = (
        Index('idx_pecas_busca_final', "cod_montadora", "cod_modelo"),
        Index('idx_pecas_codigo_base', "codigo_base"),
        Index('idx_pecas_sku_variacao', "sku_variacao"),
        Index('idx_pecas_categoria', "categoria"), # Indice para novo campo
        Index('idx_pecas_anos', "anos_aplicacao"),
        Index('idx_pecas_porta', "posicao_porta"),
    )

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
    # Ajustar tipos conforme necessidade (EntradaN, EntradaR, SaidaVenda, SaidaReparo, AjustePos, AjusteNeg...)
    tipo_movimentacao = Column(String(15), CheckConstraint("tipo_movimentacao IN ('Entrada', 'Saida', 'Ajuste', 'ParaReparo', 'DeReparo')"), nullable=False)
    quantidade = Column(Integer, nullable=False) # Afeta quantidade_estoque ou qtd_para_reparar?
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

