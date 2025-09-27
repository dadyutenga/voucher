from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    mobile_number = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    vouchers = relationship("Voucher", back_populates="owner")
    transactions = relationship("Transaction", back_populates="account")

class Package(Base):
    __tablename__ = "packages"
    
    id = Column(String, primary_key=True, index=True)  # e.g., "basic", "premium"
    name = Column(String, nullable=False)
    description = Column(Text)
    duration = Column(Integer, nullable=False)  # in minutes
    data_limit = Column(Integer)  # in MB, null for unlimited
    price = Column(DECIMAL, nullable=False)
    currency = Column(String, default="TZS")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Voucher(Base):
    __tablename__ = "vouchers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    package_id = Column(String, ForeignKey("packages.id"), nullable=True)
    duration = Column(Integer, nullable=False)  # in minutes
    data_limit = Column(Integer)  # in MB
    status = Column(String, default="active") # active, used, expired
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    used_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("Account", back_populates="vouchers")
    package = relationship("Package")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    voucher_id = Column(UUID(as_uuid=True), ForeignKey("vouchers.id"), nullable=True)
    package_id = Column(String, ForeignKey("packages.id"), nullable=True)
    amount = Column(DECIMAL, nullable=False)
    payment_method = Column(String, nullable=False)
    status = Column(String, nullable=False)
    transaction_metadata = Column(JSON, nullable=True)  # Store additional payment data as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="transactions")
    package = relationship("Package")
