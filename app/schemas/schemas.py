from pydantic import BaseModel, validator, Field
from datetime import datetime
from typing import Optional
from decimal import Decimal
import re
import uuid

# Tanzanian mobile number validation
def validate_tz_mobile(mobile_number: str) -> str:
    """Validate Tanzanian mobile number format"""
    # Remove any spaces, hyphens, or plus signs
    cleaned = re.sub(r'[\s\-\+]', '', mobile_number)
    
    # Check if it starts with country code (255) or local format (0)
    if cleaned.startswith('255'):
        if len(cleaned) != 12:
            raise ValueError('Invalid Tanzanian mobile number format')
        return cleaned
    elif cleaned.startswith('0'):
        if len(cleaned) != 10:
            raise ValueError('Invalid Tanzanian mobile number format')
        return '255' + cleaned[1:]  # Convert to international format
    elif len(cleaned) == 9:
        # Assume it's missing the leading 0
        return '255' + cleaned
    else:
        raise ValueError('Invalid Tanzanian mobile number format')

# Account Schemas
class AccountBase(BaseModel):
    mobile_number: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class AccountCreate(AccountBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class AccountLogin(BaseModel):
    mobile_number: str
    password: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class Account(AccountBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

# Package Schemas
class PackageBase(BaseModel):
    name: str
    description: Optional[str] = None
    duration: int = Field(..., gt=0, description="Duration in minutes")
    data_limit: Optional[int] = Field(None, description="Data limit in MB, null for unlimited")
    price: Decimal = Field(..., gt=0)
    currency: str = Field(default="TZS")

class PackageCreate(PackageBase):
    id: str = Field(..., pattern=r'^[a-z0-9_-]+$', description="Package ID (alphanumeric, lowercase)")

class PackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, gt=0)
    data_limit: Optional[int] = None
    price: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = None
    is_active: Optional[bool] = None

class Package(PackageBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Voucher Schemas
class VoucherBase(BaseModel):
    duration: int  # in minutes
    data_limit: Optional[int] = None  # in MB

class VoucherCreate(VoucherBase):
    mobile_number: str
    package_id: Optional[str] = None
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class Voucher(VoucherBase):
    id: uuid.UUID
    code: str
    account_id: uuid.UUID
    package_id: Optional[str] = None
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    package: Optional[Package] = None

    class Config:
        from_attributes = True

# Transaction Schemas
class TransactionBase(BaseModel):
    amount: Decimal
    payment_method: str

class TransactionCreate(TransactionBase):
    account_id: uuid.UUID
    voucher_id: Optional[uuid.UUID] = None
    package_id: Optional[str] = None

class Transaction(TransactionBase):
    id: uuid.UUID
    account_id: uuid.UUID
    voucher_id: Optional[uuid.UUID] = None
    package_id: Optional[str] = None
    status: str
    created_at: datetime
    package: Optional[Package] = None

    class Config:
        from_attributes = True

# Payment Schemas
class PaymentIntentCreate(BaseModel):
    amount: int
    currency: str = "TZS"
    mobile_number: str
    package_id: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class MPesaPaymentRequest(BaseModel):
    phone_number: str
    amount: int
    mobile_number: str
    package_id: str
    payment_reference: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        return validate_tz_mobile(v)

class DummyPaymentRequest(BaseModel):
    mobile_number: str
    amount: int
    package_id: str
    payment_reference: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class PaymentResponse(BaseModel):
    success: bool
    message: str
    payment_reference: Optional[str] = None
    voucher_code: Optional[str] = None
    transaction_id: Optional[uuid.UUID] = None

# Auth Schemas
class LoginRequest(BaseModel):
    mobile_number: str
    voucher_code: str
    client_mac: Optional[str] = None
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class LoginResponse(BaseModel):
    success: bool
    message: str
    redirect_url: Optional[str] = None

# Voucher validation schema
class VoucherValidation(BaseModel):
    mobile_number: str
    voucher_code: str
    
    @validator('mobile_number')
    def validate_mobile_number(cls, v):
        return validate_tz_mobile(v)

class VoucherValidationResponse(BaseModel):
    valid: bool
    message: str
    duration_remaining: Optional[int] = None
    data_remaining: Optional[int] = None

# User Dashboard Schemas
class UserDashboard(BaseModel):
    account: Account
    vouchers: list[Voucher]
    transactions: list[Transaction]
    available_packages: list[Package]

class AdminDashboard(BaseModel):
    total_accounts: int
    total_vouchers: int
    active_vouchers: int
    total_revenue: Decimal
    recent_transactions: list[Transaction]

class VoucherStats(BaseModel):
    total_vouchers: int
    active_vouchers: int
    used_vouchers: int
    expired_vouchers: int
