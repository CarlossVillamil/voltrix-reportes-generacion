"""Modelos SQLAlchemy de las tablas creadas por db/init.sql."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

GRANULARIDADES = ("hora", "dia", "mes")
MODOS = ("secuencial", "paralelo")
NIVELES = ("planta", "activo")
ESTADOS = ("en_curso", "completado", "error")


class Base(DeclarativeBase):
    pass


class EjecucionCalculo(Base):
    __tablename__ = "ejecucion_calculo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64))
    equipo_consumidor: Mapped[str | None] = mapped_column(String(16))
    modo: Mapped[str] = mapped_column(String(10))
    workers: Mapped[int] = mapped_column(Integer)
    granularidad: Mapped[str] = mapped_column(String(4))
    nivel: Mapped[str] = mapped_column(String(6))
    planta_ids: Mapped[str | None] = mapped_column(Text)
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(12), server_default="en_curso")
    elementos: Mapped[int | None] = mapped_column(Integer)
    generados: Mapped[int | None] = mapped_column(Integer)
    duracion_ms: Mapped[int | None] = mapped_column(Integer)
    mensaje_error: Mapped[str | None] = mapped_column(Text)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("modo IN ('secuencial', 'paralelo')"),
        CheckConstraint("granularidad IN ('hora', 'dia', 'mes')"),
        CheckConstraint("nivel IN ('planta', 'activo')"),
        CheckConstraint("estado IN ('en_curso', 'completado', 'error')"),
        CheckConstraint("hasta > desde"),
    )


class AgregadoGeneracion(Base):
    __tablename__ = "agregado_generacion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    planta_id: Mapped[str] = mapped_column(String(64))
    activo_id: Mapped[str | None] = mapped_column(String(64))
    tipo_activo: Mapped[str | None] = mapped_column(String(32))
    granularidad: Mapped[str] = mapped_column(String(4))
    periodo_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    periodo_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    energia_kwh: Mapped[float] = mapped_column(Float)
    potencia_promedio_kw: Mapped[float | None] = mapped_column(Float)
    potencia_maxima_kw: Mapped[float | None] = mapped_column(Float)
    numero_lecturas: Mapped[int] = mapped_column(Integer)
    capacidad_nominal_kw: Mapped[float | None] = mapped_column(Float)
    factor_planta: Mapped[float | None] = mapped_column(Float)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ejecucion_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ejecucion_calculo.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("granularidad IN ('hora', 'dia', 'mes')"),
        CheckConstraint("energia_kwh >= 0"),
        CheckConstraint("numero_lecturas >= 0"),
        CheckConstraint("periodo_fin > periodo_inicio"),
        UniqueConstraint(
            "planta_id", "activo_id", "granularidad", "periodo_inicio",
            name="uq_agregado_periodo",
            postgresql_nulls_not_distinct=True,
        ),
    )
