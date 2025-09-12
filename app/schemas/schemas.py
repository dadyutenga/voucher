from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from decimal import Decimal

# Account Schemas
class AccountBase(BaseModel):
    email: EmailStr

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Voucher Schemas
class VoucherBase(BaseModel):
    duration: int  # in minutes
    data_limit: Optional[int] = None  # in MB

class VoucherCreate(VoucherBase):
    email: EmailStr

class Voucher(VoucherBase):
    id: int
    code: str
    account_id: int
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Transaction Schemas
class TransactionBase(BaseModel):
    amount: Decimal
    payment_method: str

class TransactionCreate(TransactionBase):
    account_id: int
    voucher_id: Optional[int] = None

class Transaction(TransactionBase):
    id: int
    account_id: int
    voucher_id: Optional[int] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Payment Schemas
class PaymentIntentCreate(BaseModel):
    amount: int
    currency: str = "KES"
    email: EmailStr
    duration: int = 30  # default 30 minutes
    data_limit: Optional[int] = None

class MPesaPaymentRequest(BaseModel):
    phone_number: str
    amount: int
    email: EmailStr
    duration: int = 30
    data_limit: Optional[int] = None
    payment_reference: str

class DummyPaymentRequest(BaseModel):
    email: EmailStr
    amount: int
    duration: int = 30
    data_limit: Optional[int] = None
    payment_reference: str

class PaymentResponse(BaseModel):
    success: bool
    message: str
    payment_reference: Optional[str] = None
    voucher_code: Optional[str] = None
    transaction_id: Optional[int] = None

# Auth Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    voucher_code: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    redirect_url: Optional[str] = None

# Voucher validation schema
class VoucherValidation(BaseModel):
    email: EmailStr
    voucher_code: str

class VoucherValidationResponse(BaseModel):
    valid: bool
    message: str
    duration_remaining: Optional[int] = None
    data_remaining: Optional[int] = None
