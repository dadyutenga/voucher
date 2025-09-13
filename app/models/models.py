from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vouchers = relationship("Voucher", back_populates="owner")
    transactions = relationship("Transaction", back_populates="account")

class Voucher(Base):
    __tablename__ = "vouchers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    duration = Column(Integer, nullable=False)  # in minutes
    data_limit = Column(Integer)  # in MB
    status = Column(String, default="active") # active, used, expired
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

    owner = relationship("Account", back_populates="vouchers")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.id"), nullable=True)
    amount = Column(DECIMAL, nullable=False)
    payment_method = Column(String, nullable=False)
    status = Column(String, nullable=False)
    transaction_metadata = Column(JSON, nullable=True)  # Store additional payment data as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="transactions")
