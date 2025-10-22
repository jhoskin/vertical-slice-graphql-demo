"""
SQLAlchemy ORM models for the clinical metadata demo.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Trial(Base):
    """Clinical trial entity."""
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )

    # Relationships
    trial_sites: Mapped[list["TrialSite"]] = relationship(
        "TrialSite", back_populates="trial"
    )
    protocol_versions: Mapped[list["ProtocolVersion"]] = relationship(
        "ProtocolVersion", back_populates="trial"
    )


class Site(Base):
    """Site entity."""
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    trial_sites: Mapped[list["TrialSite"]] = relationship(
        "TrialSite", back_populates="site"
    )


class TrialSite(Base):
    """Association between trials and sites."""
    __tablename__ = "trial_sites"

    trial_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trials.id"), primary_key=True
    )
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    __table_args__ = (UniqueConstraint("trial_id", "site_id", name="uq_trial_site"),)

    # Relationships
    trial: Mapped["Trial"] = relationship("Trial", back_populates="trial_sites")
    site: Mapped["Site"] = relationship("Site", back_populates="trial_sites")


class ProtocolVersion(Base):
    """Protocol version for a trial."""
    __tablename__ = "protocol_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trials.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )

    # Relationships
    trial: Mapped["Trial"] = relationship("Trial", back_populates="protocol_versions")


class AuditLog(Base):
    """Audit log entry."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )


class SagaOnboardTrial(Base):
    """Saga state for trial onboarding workflow."""
    __tablename__ = "saga_onboard_trial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow()
    )
