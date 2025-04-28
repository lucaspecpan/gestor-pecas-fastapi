# File: app/models.py (Versão 5.8 - Verificação Final)
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Float,
                        ForeignKey, CheckConstraint, UniqueConstraint, Index, Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base # Importa a Base do nosso database.py

class Montadora(Base):
    __tablename__ = "montadoras"
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, unique=True, index=True, nullable=False)
    nome_montadora = Column(String(100), unique=True, index=True, nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    modelos = relationship("ModeloVeiculo", back_populates="montadora", cascade="all, delete-orphan")
    pecas = relationship("Peca", back_populates="montadora_rel")

class ModeloVeiculo(Base):
    __tablename__ = "modelos_veiculo"
    id = Column(Integer, primary_key=True, index=True)
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    nome_modelo = Column(String(100), nullable=False)
    cod_sequencial_modelo = Column(Integer, nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('cod_montadora', 'nome_modelo', name='uq_montadora_modelo_nome'),
        UniqueConstraint('cod_montadora', 'cod_sequencial_modelo', name='uq_montadora_modelo_seq'),
        Index('idx_modelo_montadora_nome', "cod_montadora", "nome_modelo"),
    )
    montadora = relationship("Montadora", back_populates="modelos")
    pecas = relationship("Peca", back_populates="modelo_rel")

class Peca(Base):
    __tablename__ = "pecas"
    id = Column(Integer, primary_key=True, index=True)
    sku_variacao = Column(String(15), unique=True, index=True, nullable=False)
    codigo_base = Column(String(8), index=True, nullable=False)
    sufixo_variacao = Column(String(1), CheckConstraint("sufixo_variacao IN ('R', 'P')"), nullable=True)
    cod_montadora = Column(Integer, ForeignKey("montadoras.cod_montadora"), nullable=False)
    cod_modelo = Column(Integer, ForeignKey("modelos_veiculo.id"), nullable=False)
    nome_item = Column(String(150), nullable=False, index=True)
    # CORRIGIDO: Renomeado de cod_final_base para cod_final_item consistentemente
    cod_final_item = Column(Integer, nullable=False) # Sequencial FFF (999-000) por Montadora/Modelo/NomeItem
    descricao_peca = Column(Text)
    categoria = Column(String(100), index=True) # Campo Categoria mantido conforme solicitado antes
    codigo_oem = Column(String(50), index=True)
    anos_aplicacao = Column(String(50))
    posicao_porta = Column(String(10))
    quantidade_estoque = Column(Integer, nullable=False, default=0)
    # qtd_para_reparar foi removido
    eh_kit = Column(Boolean, nullable=False, default=False)
    custo_ultima_compra = Column(Float, default=0.0)
    aliquota_imposto_percent = Column(Float, default=0.0)
    custo_estimado_adicional = Column(Float, default=0.0)
    preco_venda = Column(Float, nullable=False, default=0.0)
    codigo_ean13 = Column(String(13))
    data_ultima_compra = Column(String(10))
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    montadora_rel = relationship("Montadora", back_populates="pecas")
    modelo_rel = relationship("ModeloVeiculo", back_populates="pecas")
    imagens = relationship("PecaImagem", back_populates="peca", cascade="all, delete-orphan")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="peca", cascade="all, delete-orphan")
    componentes_do_kit = relationship("ComponenteKit", foreign_keys="ComponenteKit.kit_peca_id", back_populates="kit", cascade="all, delete-orphan")
    kit_onde_eh_componente = relationship("ComponenteKit", foreign_keys="ComponenteKit.componente_peca_id", back_populates="componente")

    __table_args__ = (
        Index('idx_pecas_busca_fff', "cod_montadora", "cod_modelo", "nome_item"),
        Index('idx_pecas_codigo_base', "codigo_base"),
        Index('idx_pecas_sku_variacao', "sku_variacao"),
        Index('idx_pecas_categoria', "categoria"), # Índice adicionado
        Index('idx_pecas_porta', "posicao_porta"),
        Index('idx_pecas_anos', "anos_aplicacao"),
    )

class PecaImagem(Base):
    __tablename__ = "peca_imagens"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    url_imagem = Column(String(512), nullable=False)
    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())
    peca = relationship("Peca", back_populates="imagens")

class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacoes_estoque"
    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_movimentacao = Column(String(15), CheckConstraint("tipo_movimentacao IN ('Entrada', 'Saida', 'Ajuste')"), nullable=False)
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
    __table_args__ = ( UniqueConstraint('kit_peca_id', 'componente_peca_id', name='uq_kit_componente'),
                       Index('idx_comp_kit_id', "kit_peca_id"), Index('idx_comp_comp_id', "componente_peca_id"), )
