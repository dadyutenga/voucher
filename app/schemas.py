from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    voucher_code: str
    client_mac: Optional[str] = None  # Add this field