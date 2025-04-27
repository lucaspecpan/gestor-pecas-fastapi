# File: app/models.py
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Float,
                        ForeignKey, CheckConstraint, UniqueConstraint, Index, Text) # Adicionado Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base # Importa a Base do nosso database.py

class Montadora(Base):
    __tablename__ = "montadoras"
    # Usando ID interno como PK
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, unique=True, index=True, nullable=False) # O código 101, 102...
    nome_montadora = Column(String(100), unique=True, index=True, nullable=False) # Tamanho definido
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    pecas = relationship("Peca", back_populates="montadora", cascade="all, delete-orphan") # Se deletar montadora, deleta peças? Ou RESTRICT?

class Peca(Base):
    __tablename__ = "pecas"
    id = Column(Integer, primary_key=True, index=True)
    sku_variacao = Column(String(15), unique=True, index=True, nullable=False) # Tamanho definido
    codigo_base = Column(String(8), index=True, nullable=False) # Tamanho definido
    sufixo_variacao = Column(String(1), CheckConstraint("sufixo_variacao IN ('R', 'P')"), nullable=True)
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    cod_modelo = Column(Integer, nullable=False)
    cod_final_base = Column(Integer, nullable=False)
    descricao_peca = Column(Text) # Usar Text para descrições mais longas
    codigo_oem = Column(String(50), index=True) # Tamanho definido
    codigo_ean13 = Column(String(13)) # Tamanho definido
    quantidade_estoque = Column(Integer, nullable=False, default=0)
    eh_kit = Column(Boolean, nullable=False, default=False)
    custo_insumos = Column(Float, default=0.0)
    custo_etiqueta = Column(Float, default=0.0)
    custo_embalagem = Column(Float, default=0.0)
    impostos_percent = Column(Float, default=0.0)
    preco_venda = Column(Float, default=0.0)
    data_ultima_compra = Column(String(10)) # Formato AAAA-MM-DD
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    montadora = relationship("Montadora", back_populates="pecas")
    imagens = relationship("PecaImagem", back_populates="peca", cascade="all, delete-orphan")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="peca", cascade="all, delete-orphan")
    componentes_do_kit = relationship("ComponenteKit", foreign_keys="ComponenteKit.kit_peca_id", back_populates="kit", cascade="all, delete-orphan")
    kit_onde_eh_componente = relationship("ComponenteKit", foreign_keys="ComponenteKit.componente_peca_id", back_populates="componente")

    # Índices compostos (melhor definir aqui)
    __table_args__ = (
        Index('idx_pecas_busca_final', "cod_montadora", "cod_modelo"),
        Index('idx_pecas_codigo_base', "codigo_base"), # Adiciona índice explícito
        Index('idx_pecas_sku_variacao', "sku_variacao"), # Adiciona índice explícito
    )

class PecaImagem(Base):
    __tablename__ = "peca_imagens"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    nome_arquivo_imagem = Column(String(255), nullable=False) # Tamanho definido
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    peca = relationship("Peca", back_populates="imagens")

class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacoes_estoque"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_movimentacao = Column(String(10), CheckConstraint("tipo_movimentacao IN ('Entrada', 'Saida', 'Ajuste')"), nullable=False)
    quantidade = Column(Integer, nullable=False)
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

    __table_args__ = (
        UniqueConstraint('kit_peca_id', 'componente_peca_id', name='uq_kit_componente'),
        Index('idx_comp_kit_id', "kit_peca_id"), # Índice explícito
        Index('idx_comp_comp_id', "componente_peca_id"), # Índice explícito
    )
