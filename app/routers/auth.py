from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
import requests
import logging
import re
import uuid

from app import schemas
from app.database import get_db
from app.models.models import Account, Voucher, Transaction, Package
from app.core.config import settings
from app import utils
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# JWT settings
SECRET_KEY = getattr(settings, 'SECRET_KEY', "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    # Ensure password doesn't exceed bcrypt's 72-byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='replace')
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        mobile_number: str = payload.get("sub")
        if mobile_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(Account).filter(Account.mobile_number == mobile_number).first()
    if user is None:
        raise credentials_exception
    return user

def utc_now():
    """Get current UTC time with timezone info"""
    return datetime.now(timezone.utc)

def authenticate_user(db: Session, mobile_number: str, password: str):
    user = db.query(Account).filter(Account.mobile_number == mobile_number).first()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user

def get_client_mac_from_request(request: Request):
    """
    Extract client MAC address from various possible sources
    """
    # Try different headers where MAC might be present
    possible_headers = [
        'X-Forwarded-For',
        'X-Real-IP', 
        'X-Client-MAC',
        'Remote-Addr',
        'HTTP_CLIENT_MAC'
    ]
    
    for header in possible_headers:
        value = request.headers.get(header)
        if value:
            # Simple MAC address pattern check
            if re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', value):
                return value
    
    # Try query parameters
    client_mac = request.query_params.get('client_mac')
    if client_mac and re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', client_mac):
        return client_mac
    
    return None

# Authentication endpoints
@router.post("/register", response_model=schemas.Account)
def register_user(user: schemas.AccountCreate, db: Session = Depends(get_db)):
    """Register a new user with mobile number and password"""
    
    # Check if user already exists
    db_user = db.query(Account).filter(Account.mobile_number == user.mobile_number).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Mobile number already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = Account(
        mobile_number=user.mobile_number,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    try:
        # Normalize the mobile number format
        mobile_number = form_data.username
        
        # Log the original input for debugging
        logger.info(f"Login attempt for: {mobile_number}")
        
        # Better mobile number normalization
        if mobile_number:
            # Strip any whitespace or formatting characters
            mobile_number = re.sub(r'[\s\-()]', '', mobile_number)
            
            # Handle different formats
            if mobile_number.startswith('+'):
                # Remove the + sign to match database format
                mobile_number = mobile_number[1:]
            elif mobile_number.startswith('0'):
                mobile_number = f"255{mobile_number[1:]}"
            elif len(mobile_number) == 9:  # Just the 9 digits
                mobile_number = f"255{mobile_number}"
        
        logger.info(f"Normalized mobile number: {mobile_number}")
        
        # Find the user first
        user = db.query(Account).filter(Account.mobile_number == mobile_number).first()
        
        if not user:
            logger.warning(f"No user found with mobile number: {mobile_number}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found with this mobile number",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user.password_hash):
            logger.warning(f"Invalid password for user: {mobile_number}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # User authenticated, generate token
        logger.info(f"User authenticated successfully: {mobile_number}")
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.mobile_number}, expires_delta=access_token_expires
        )
        
        # Update last login
        user.last_login = utc_now()
        db.commit()
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user_id": str(user.id),
            "mobile_number": user.mobile_number
        }
        
    except HTTPException as he:
        # Re-raise HTTP exceptions directly
        raise he
    except Exception as e:
        # Log the full exception information
        logger.error(f"Token generation error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e) or 'Unknown error'}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/users/me", response_model=schemas.Account)
async def read_users_me(current_user: Account = Depends(get_current_user)):
    """Get current user information"""
    return current_user

# User authentication endpoints
@router.post("/user/login")
async def user_login(login_data: schemas.AccountLogin, db: Session = Depends(get_db)):
    """Authenticate user with mobile number and password"""
    user = authenticate_user(db, login_data.mobile_number, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.mobile_number}, 
        expires_delta=access_token_expires
    )
    
    # Update last login
    user.last_login = utc_now()
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }




@router.post("/validate", response_model=schemas.VoucherValidationResponse)
def validate_voucher(validation_data: schemas.VoucherValidation, db: Session = Depends(get_db)):
    """
    Validate a voucher without consuming it. Useful for checking status.
    """
    try:
        # Find the account by mobile number
        account = db.query(Account).filter(Account.mobile_number == validation_data.mobile_number).first()
        if not account:
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Account not found."
            )

        # Find the voucher
        voucher = db.query(Voucher).filter(
            Voucher.code == validation_data.voucher_code,
            Voucher.account_id == account.id
        ).first()

        if not voucher:
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher not found for this account."
            )

        # Check voucher status and expiry
        if voucher.status == "used":
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher has already been used."
            )
        elif voucher.status == "expired":
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher has expired."
            )
        elif voucher.expires_at and voucher.expires_at < utc_now():
            # Mark as expired
            voucher.status = "expired"
            db.commit()
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher has expired."
            )

        # Voucher is valid
        time_remaining = None
        if voucher.expires_at:
            time_remaining = int((voucher.expires_at - utc_now()).total_seconds() / 60)  # in minutes

        return schemas.VoucherValidationResponse(
            valid=True,
            message="Voucher is valid and ready to use.",
            duration_remaining=time_remaining,
            data_remaining=voucher.data_limit
        )

    except Exception as e:
        logger.error(f"Error validating voucher: {str(e)}")
        return schemas.VoucherValidationResponse(
            valid=False,
            message="An error occurred while validating the voucher."
        )

@router.post("/demo-voucher")
def create_demo_voucher(mobile_number: str, db: Session = Depends(get_db)):
    """
    Create a 10-minute demo voucher for testing purposes.
    """
    try:
        from app import utils
        
        # Check if account exists, if not create one
        account = db.query(Account).filter(Account.mobile_number == mobile_number).first()
        if not account:
            account = Account(mobile_number=mobile_number)
            db.add(account)
            db.commit()
            db.refresh(account)

        # Generate unique voucher code
        while True:
            code = utils.generate_voucher_code()
            if not db.query(Voucher).filter(Voucher.code == code).first():
                break

        # Create demo voucher (10 minutes)
        voucher = Voucher(
            code=code,
            account_id=account.id,
            duration=10,  # 10 minutes
            status="active",
            expires_at=utc_now() + timedelta(minutes=60)  # Valid for 1 hour to be claimed
        )
        db.add(voucher)
        db.commit()
        db.refresh(voucher)

        return {
            "success": True,
            "message": "Demo voucher created successfully!",
            "voucher_code": code,
            "duration": "10 minutes",
            "expires_at": voucher.expires_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error creating demo voucher: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create demo voucher")

# NEW USER DASHBOARD ENDPOINTS

@router.get("/user/dashboard", response_model=schemas.UserDashboard)
async def get_user_dashboard(current_user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user dashboard data with vouchers, transactions, and available packages"""
    try:
        # Get user's vouchers
        vouchers = db.query(Voucher).filter(Voucher.account_id == current_user.id).order_by(Voucher.created_at.desc()).all()
        
        # Get user's transactions  
        transactions = db.query(Transaction).filter(Transaction.account_id == current_user.id).order_by(Transaction.created_at.desc()).all()
        
        # Get available packages
        packages = db.query(Package).filter(Package.is_active == True).all()
        
        return schemas.UserDashboard(
            account=current_user,
            vouchers=vouchers,
            transactions=transactions,
            available_packages=packages
        )
    except Exception as e:
        logger.error(f"Error fetching user dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/dashboard", response_model=schemas.UserDashboard)
async def user_dashboard(current_user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user dashboard data with vouchers, transactions, and available packages"""
    try:
        # Get user's vouchers
        vouchers = db.query(Voucher).filter(Voucher.account_id == current_user.id).order_by(Voucher.created_at.desc()).all()
        
        # Get user's transactions  
        transactions = db.query(Transaction).filter(Transaction.account_id == current_user.id).order_by(Transaction.created_at.desc()).all()
        
        # Get available packages
        packages = db.query(Package).filter(Package.is_active == True).all()
        
        return schemas.UserDashboard(
            account=current_user,
            vouchers=vouchers,
            transactions=transactions,
            available_packages=packages
        )
    except Exception as e:
        logger.error(f"Error fetching user dashboard: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/user/panel", response_class=HTMLResponse)
async def user_panel(request: Request):
    """Serve the user panel HTML page"""
    return templates.TemplateResponse("user_panel.html", {"request": request})

@router.post("/user/purchase-package")
async def purchase_package(
    package_id: str = Form(...),
    current_user: Account = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Initiate package purchase process"""
    # Get package details
    package = db.query(Package).filter(Package.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    
    if not package.is_active:
        raise HTTPException(status_code=400, detail="Package is not available")
    
    # Create payment intent
    payment_intent = schemas.PaymentIntentCreate(
        mobile_number=current_user.mobile_number,
        package_id=package_id
    )
    
    # Return payment details for frontend to handle
    return {
        "package": {
            "id": package.id,
            "name": package.name,
            "price": float(package.price),
            "currency": package.currency,
            "duration": package.duration,
            "data_limit": package.data_limit
        },
        "payment_methods": [
            {"type": "mpesa", "name": "M-Pesa"},
            {"type": "dummy", "name": "Demo Payment (Testing)"}
        ]
    }
