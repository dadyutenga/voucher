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
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.mobile_number}, expires_delta=access_token_expires
    )
    
    # Update last login
    user.last_login = utc_now()
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}

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

@router.post("/login/account", response_model=dict)
async def account_login(login_data: schemas.AccountLogin, db: Session = Depends(get_db)):
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
        "user": {
            "id": str(user.id),
            "mobile_number": user.mobile_number,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }
    }

# Legacy endpoints for backward compatibility (using mobile_number instead of email)
@router.post("/login", response_model=schemas.LoginResponse)  
def login_with_voucher(login_data: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Validate voucher and mobile number, then redirect to grant URL if valid.
    This endpoint is called from the Meraki splash page.
    """
    # Get client_mac from login data or request parameters
    client_mac = login_data.client_mac or request.query_params.get('client_mac')
    
    logger.info(f"🔍 PRODUCTION: Login request - Mobile: {login_data.mobile_number}, MAC: {client_mac}")
    
    # Find the account by mobile number
    account = db.query(Account).filter(Account.mobile_number == login_data.mobile_number).first()
    if not account:
        return schemas.LoginResponse(
            success=False,
            message="Account not found. Please check your mobile number."
        )

    # Find the voucher
    voucher = db.query(Voucher).filter(
        Voucher.code == login_data.voucher_code,
        Voucher.account_id == account.id
    ).first()

    if not voucher:
        return schemas.LoginResponse(
            success=False,
            message="Invalid voucher code for this account."
        )

    if voucher.status != "active":
        return schemas.LoginResponse(
            success=False,
            message=f"Voucher is {voucher.status}. Please contact support or purchase a new voucher."
        )

    # Check if voucher has expired
    if voucher.expires_at and voucher.expires_at < utc_now():
        # Mark as expired
        voucher.status = "expired"
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Voucher is valid, mark as used and redirect to grant
    voucher.status = "used"
    voucher.used_at = utc_now()
    db.commit()

    # Construct grant URL
    base_url = str(request.base_url).rstrip('/')
    grant_url = f"{base_url}/auth/grant"
    
    # Add parameters
    params = []
    if client_mac:
        params.append(f"client_mac={client_mac}")
    params.append(f"mobile_number={login_data.mobile_number}")
    params.append(f"voucher_code={login_data.voucher_code}")
    
    if params:
        grant_url += "?" + "&".join(params)

    logger.info(f"✅ PRODUCTION: Voucher valid, redirecting to: {grant_url}")

    return schemas.LoginResponse(
        success=True,
        message="Access granted! Redirecting to Wi-Fi...",
        redirect_url=grant_url
    )

@router.post("/login/legacy", response_model=schemas.LoginResponse)
def login_with_voucher_legacy(login_data: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Legacy endpoint - Validate voucher and email, then redirect to grant URL if valid.
    This endpoint maintains backward compatibility with email-based system.
    """
    # Get client_mac from login data or request parameters
    client_mac = login_data.client_mac or request.query_params.get('client_mac')
    
    logger.info(f"🔍 PRODUCTION: Legacy login request - Mobile: {login_data.mobile_number}, MAC: {client_mac}")
    
    # Find the account by mobile number (updated from email)
    account = db.query(Account).filter(Account.mobile_number == login_data.mobile_number).first()
    if not account:
        return schemas.LoginResponse(
            success=False,
            message="Account not found. Please check your mobile number."
        )

    # Find the voucher
    voucher = db.query(Voucher).filter(
        Voucher.code == login_data.voucher_code,
        Voucher.account_id == account.id
    ).first()

    if not voucher:
        return schemas.LoginResponse(
            success=False,
            message="Invalid voucher code for this account."
        )

    if voucher.status != "active":
        return schemas.LoginResponse(
            success=False,
            message=f"Voucher is {voucher.status}. Please contact support or purchase a new voucher."
        )

    # Check if voucher has expired
    if voucher.expires_at and voucher.expires_at < utc_now():
        # Mark as expired
        voucher.status = "expired"
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Voucher is valid, mark as used and redirect to grant
    voucher.status = "used"
    voucher.used_at = utc_now()
    db.commit()

    # Construct grant URL
    base_url = str(request.base_url).rstrip('/')
    grant_url = f"{base_url}/auth/grant"
    
    # Add parameters
    params = []
    if client_mac:
        params.append(f"client_mac={client_mac}")
    params.append(f"mobile_number={login_data.mobile_number}")
    params.append(f"voucher_code={login_data.voucher_code}")
    
    if params:
        grant_url += "?" + "&".join(params)

    logger.info(f"✅ PRODUCTION: Legacy voucher valid, redirecting to: {grant_url}")

    return schemas.LoginResponse(
        success=True,
        message="Access granted! Redirecting to Wi-Fi...",
        redirect_url=grant_url
    )

@router.post("/grant")
@router.get("/grant")
async def grant_access(
    request: Request, 
    email: str = None,
    voucher_code: str = None,
    client_mac: str = Form(None), 
    db: Session = Depends(get_db)
):
    """
    Grant network access by calling Meraki API.
    This endpoint is called after successful voucher validation.
    """
    
    try:
        # Get parameters from query string if not in form
        if not email:
            email = request.query_params.get('email')
        if not voucher_code:
            voucher_code = request.query_params.get('voucher_code')  
        if not client_mac:
            client_mac = request.query_params.get('client_mac')

        logger.info(f"🔑 PRODUCTION: Grant access request - Email: {email}, Voucher: {voucher_code}, MAC: {client_mac}")

        # Verify the voucher is still valid and used
        if email and voucher_code:
            account = db.query(Account).filter(Account.email == email).first()
            if account:
                voucher = db.query(Voucher).filter(
                    Voucher.code == voucher_code,
                    Voucher.account_id == account.id,
                    Voucher.status.in_(["active", "used"])
                ).first()

                if not voucher:
                    logger.warning(f"⚠️  PRODUCTION: Invalid voucher during grant: {voucher_code}")
                    return HTMLResponse(f"""
                    <html>
                        <head><title>Access Denied</title></head>
                        <body style="text-align:center; font-family:sans-serif; padding:50px;">
                            <h2>❌ Access Denied</h2>
                            <p>Invalid or expired voucher code.</p>
                            <a href="/">
                                <button style="padding:12px 24px; font-size:16px; background:#007bff; color:white; border:none; border-radius:5px; cursor:pointer;">
                                    🔄 Try Again
                                </button>
                            </a>
                        </body>
                    </html>
                    """, status_code=403)

        # Try to grant access via Meraki API
        meraki_api_key = getattr(settings, 'MERAKI_API_KEY', None)
        meraki_network_id = getattr(settings, 'MERAKI_NETWORK_ID', None)
        
        if meraki_api_key and meraki_network_id and client_mac:
            logger.info(f"🌐 PRODUCTION: Attempting Meraki API call for MAC: {client_mac}")
            
            # Meraki API endpoint for granting access
            url = f"https://api.meraki.com/api/v1/networks/{meraki_network_id}/clients/{client_mac}/policy"
            
            headers = {
                'X-Cisco-Meraki-API-Key': meraki_api_key,
                'Content-Type': 'application/json'
            }
            
            # Grant policy (allow internet access)
            data = {
                'mac': client_mac,
                'type': 'Group policy',
                'groupPolicyId': 'normal'  # This should be configured in your Meraki dashboard
            }

            response = requests.put(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ PRODUCTION: Meraki access granted for MAC: {client_mac}")
                return HTMLResponse(f"""
                <html>
                    <head>
                        <title>Access Granted</title>
                        <meta http-equiv="refresh" content="3;url=http://www.google.com">
                    </head>
                    <body style="text-align:center; font-family:sans-serif; padding:50px;">
                        <h2>🎉 Wi-Fi Access Granted!</h2>
                        <p>Welcome to our Wi-Fi network!</p>
                        <p><strong>Your voucher:</strong> {voucher_code}</p>
                        <div style="margin:20px;">
                            <div style="display:inline-block; padding:20px; background:#d4edda; border-radius:10px; color:#155724;">
                                ✅ Connection successful!<br>
                                You will be redirected to Google in 3 seconds...
                            </div>
                        </div>
                        <p style="color:#666; font-size:14px;">
                            If you're not redirected automatically, 
                            <a href="http://www.google.com" style="color:#007bff;">click here</a>
                        </p>
                    </body>
                </html>
                """)
            else:
                logger.error(f"❌ PRODUCTION: Meraki API error: {response.status_code} - {response.text}")
                return HTMLResponse(f"""
                <html>
                    <head><title>Connection Failed</title></head>
                    <body style="text-align:center; font-family:sans-serif; padding:50px;">
                        <h2>❌ Failed to Grant Access</h2>
                        <p><strong>Meraki API Error:</strong> {response.status_code}</p>
                        <div style="background:#f8f9fa; padding:15px; margin:20px; border-radius:5px; font-family:monospace;">
                            {response.text}
                        </div>
                        <p>Please contact technical support or try again later.</p>
                        <a href="/">
                            <button style="padding:12px 24px; font-size:16px; background:#dc3545; color:white; border:none; border-radius:5px; cursor:pointer;">
                                🔄 Try Again
                            </button>
                        </a>
                    </body>
                </html>
                """, status_code=500)
        else:
            # No Meraki integration or missing parameters - show success page
            logger.info("ℹ️ PRODUCTION: No Meraki integration, showing success page")
            return HTMLResponse(f"""
            <html>
                <head>
                    <title>Access Granted</title>
                    <meta http-equiv="refresh" content="3;url=http://www.google.com">
                </head>
                <body style="text-align:center; font-family:sans-serif; padding:50px;">
                    <h2>🎉 Welcome to Wi-Fi!</h2>
                    <p>Your access has been validated.</p>
                    <p><strong>Voucher Code:</strong> {voucher_code or 'N/A'}</p>
                    <div style="margin:20px;">
                        <div style="display:inline-block; padding:20px; background:#d1ecf1; border-radius:10px; color:#0c5460;">
                            ℹ️ You should now have internet access.<br>
                            Redirecting to Google in 3 seconds...
                        </div>
                    </div>
                    <p style="color:#666; font-size:14px;">
                        If you're not redirected automatically, 
                        <a href="http://www.google.com" style="color:#007bff;">click here</a>
                    </p>
                </body>
            </html>
            """)

    except requests.Timeout:
        logger.error("⏰ PRODUCTION: Timeout calling Meraki API")
        return HTMLResponse(f"""
        <html>
            <head><title>Connection Timeout</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>⏰ Connection Timeout</h2>
                <p>The request to grant access timed out.</p>
                <a href="/">
                    <button style="padding:12px 24px; font-size:16px; background:#ffc107; color:#212529; border:none; border-radius:5px; cursor:pointer;">
                        🔄 Try Again
                    </button>
                </a>
            </body>
        </html>
        """, status_code=500)
    except requests.RequestException as e:
        logger.error(f"🌐 PRODUCTION: Request error: {str(e)}")
        return HTMLResponse(f"""
        <html>
            <head><title>Connection Error</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>🌐 Connection Error</h2>
                <p>Unable to connect to the Wi-Fi system:</p>
                <div style="background:#f8f9fa; padding:15px; margin:20px; border-radius:5px; font-family:monospace;">
                    {str(e)}
                </div>
                <p>Please try again later or contact support.</p>
                <a href="/">
                    <button style="padding:12px 24px; font-size:16px; background:#17a2b8; color:white; border:none; border-radius:5px; cursor:pointer;">
                        🔄 Try Again
                    </button>
                </a>
            </body>
        </html>
        """, status_code=500)
    except Exception as e:
        logger.error(f"💥 PRODUCTION: Unexpected error: {str(e)}")
        return HTMLResponse(f"""
        <html>
            <head><title>System Error</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>💥 System Error</h2>
                <p>An unexpected error occurred:</p>
                <div style="background:#f8f9fa; padding:15px; margin:20px; border-radius:5px; font-family:monospace;">
                    {str(e)}
                </div>
                <a href="/">
                    <button style="padding:12px 24px; font-size:16px; background:#6f42c1; color:white; border:none; border-radius:5px; cursor:pointer;">
                        🏠 Back to Login
                    </button>
                </a>
            </body>
        </html>
        """, status_code=500)

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
