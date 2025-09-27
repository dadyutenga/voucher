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

# Dependency - get_db will be imported from database.py instead
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
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
    # Try to get from query parameters (Meraki usually provides this)
    client_mac = request.query_params.get('client_mac')
    if client_mac:
        return client_mac
    
    # Try alternative parameter names that Meraki might use
    for param in ['mac', 'client_mac', 'user_mac', 'device_mac']:
        mac = request.query_params.get(param)
        if mac:
            return mac
    
    # Try to get from headers (some captive portals use this)
    for header in ['X-Client-Mac', 'X-Device-Mac', 'Client-Mac']:
        mac = request.headers.get(header)
        if mac:
            return mac
    
    # If not found, return None
    return None

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
    
    logger.info(f"✅ New user registered: {user.mobile_number}")
    return db_user

@router.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login with mobile number and password to get access token"""
    user = authenticate_user(db, form_data.username, form_data.password)  # username field contains mobile number
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = utc_now()
    db.commit()
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.mobile_number}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login/account", response_model=schemas.Account)
def login_user(login_data: schemas.AccountLogin, db: Session = Depends(get_db)):
    """Login with mobile number and password"""
    user = authenticate_user(db, login_data.mobile_number, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password"
        )
    
    # Update last login
    user.last_login = utc_now()
    db.commit()
    
    return user

@router.get("/me", response_model=schemas.Account)
def read_users_me(current_user: models.Account = Depends(get_current_user)):
    """Get current user information"""
    return current_user

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
    account = db.query(models.Account).filter(models.Account.mobile_number == login_data.mobile_number).first()
    if not account:
        return schemas.LoginResponse(
            success=False,
            message="Account not found. Please check your mobile number."
        )

    # Find the voucher
    voucher = db.query(models.Voucher).filter(
        models.Voucher.code == login_data.voucher_code,
        models.Voucher.account_id == account.id
    ).first()

    if not voucher:
        return schemas.LoginResponse(
            success=False,
            message="Invalid voucher code for this mobile number."
        )

    # Check voucher status and expiry
    if voucher.status != "active":
        return schemas.LoginResponse(
            success=False,
            message=f"Voucher is {voucher.status}. Please purchase a new voucher."
        )

    # Check if voucher has expired
    now = utc_now()
    if voucher.expires_at and voucher.expires_at < now:
        # Mark voucher as expired
        voucher.status = "expired"
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Set expiry time if not set (for time-based vouchers)
    if not voucher.expires_at:
        expires_at = now + timedelta(minutes=voucher.duration)
        voucher.expires_at = expires_at
        db.commit()

    # Include client_mac in the grant URL if available
    if client_mac:
        grant_url = f"/auth/grant?mobile_number={login_data.mobile_number}&voucher_code={login_data.voucher_code}&client_mac={client_mac}"
        logger.info(f"🔗 PRODUCTION: Grant URL with MAC: {grant_url}")
    else:
        grant_url = f"/auth/grant?mobile_number={login_data.mobile_number}&voucher_code={login_data.voucher_code}"
        logger.error("❌ PRODUCTION: No client_mac available - this will likely fail at grant step")

    return schemas.LoginResponse(
        success=True,
        message="Voucher validated! You will be connected to Wi-Fi.",
        redirect_url=grant_url
    )
@router.post("/login", response_model=schemas.LoginResponse)
def login_with_voucher(login_data: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Validate voucher and email, then redirect to grant URL if valid.
    This endpoint is called from the Meraki splash page.
    """
    # Get client_mac from login data or request parameters
    client_mac = login_data.client_mac or request.query_params.get('client_mac')
    
    logger.info(f"🔍 PRODUCTION: Login request - Email: {login_data.email}, MAC: {client_mac}")
    
    # Find the account by email
    account = db.query(models.Account).filter(models.Account.email == login_data.email).first()
    if not account:
        return schemas.LoginResponse(
            success=False,
            message="Account not found. Please check your email address."
        )

    # Find the voucher
    voucher = db.query(models.Voucher).filter(
        models.Voucher.code == login_data.voucher_code,
        models.Voucher.account_id == account.id
    ).first()

    if not voucher:
        return schemas.LoginResponse(
            success=False,
            message="Invalid voucher code for this email address."
        )

    # Check voucher status and expiry
    if voucher.status != "active":
        return schemas.LoginResponse(
            success=False,
            message=f"Voucher is {voucher.status}. Please purchase a new voucher."
        )

    # Check if voucher has expired
    now = utc_now()
    if voucher.expires_at and voucher.expires_at < now:
        # Mark voucher as expired
        voucher.status = "expired"
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Don't mark voucher as used yet - wait until we successfully grant access
    
    # Set expiry time if not set (for time-based vouchers)
    if not voucher.expires_at:
        expires_at = now + timedelta(minutes=voucher.duration)
        voucher.expires_at = expires_at
        db.commit()

    # CRITICAL FIX: Include client_mac in the grant URL if available
    if client_mac:
        grant_url = f"/auth/grant?email={login_data.email}&voucher_code={login_data.voucher_code}&client_mac={client_mac}"
        logger.info(f"🔗 PRODUCTION: Grant URL with MAC: {grant_url}")
    else:
        # For production, we should have the MAC - log this as an issue
        grant_url = f"/auth/grant?email={login_data.email}&voucher_code={login_data.voucher_code}"
        logger.error("❌ PRODUCTION: No client_mac available - this will likely fail at grant step")

    return schemas.LoginResponse(
        success=True,
        message="Voucher validated! You will be connected to Wi-Fi.",
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
    Grant the connecting client access using Meraki API.
    This endpoint receives the client_mac from Meraki and grants access.
    """
    
    # Get client MAC from multiple sources - PRODUCTION VERSION
    if not client_mac:
        client_mac = request.query_params.get('client_mac')
    
    # Try alternative parameter names that Meraki might use
    if not client_mac:
        for param in ['mac', 'client_mac', 'user_mac', 'device_mac']:
            mac = request.query_params.get(param)
            if mac:
                client_mac = mac
                break
    
    # Try to get from headers (some captive portals use this)
    if not client_mac:
        for header in ['X-Client-Mac', 'X-Device-Mac', 'Client-Mac']:
            mac = request.headers.get(header)
            if mac:
                client_mac = mac
                break
    
    # PRODUCTION: If no client_mac found, return error - NO DUMMY MAC
    if not client_mac:
        logger.error("❌ PRODUCTION ERROR: No client_mac provided by Meraki")
        return HTMLResponse("""
        <html>
            <head><title>Configuration Error</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>❌ Configuration Error</h2>
                <p><strong>No client MAC address provided</strong></p>
                <p>This usually means the Meraki splash page is not configured correctly.</p>
                <div style="background:#fff3cd; padding:15px; margin:20px; border-radius:5px; border-left:4px solid #ffc107;">
                    <strong>For Network Administrators:</strong><br>
                    Please ensure the Meraki splash page is configured to pass the client_mac parameter to this grant URL.
                </div>
                <a href="/">
                    <button style="padding:12px 24px; font-size:16px; background:#dc3545; color:white; border:none; border-radius:5px; cursor:pointer;">
                        🏠 Back to Login
                    </button>
                </a>
            </body>
        </html>
        """, status_code=400)
    
    # Validate MAC address format (basic validation)
    if client_mac:
        # Remove any formatting and validate
        mac_clean = re.sub(r'[^0-9a-fA-F]', '', client_mac)
        if len(mac_clean) == 12:
            # Format as standard MAC address
            client_mac = ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2)).lower()
        else:
            logger.error(f"❌ PRODUCTION ERROR: Invalid MAC address format: {client_mac}")
            return HTMLResponse(f"""
            <html>
                <head><title>Invalid MAC Address</title></head>
                <body style="text-align:center; font-family:sans-serif; padding:50px;">
                    <h2>❌ Invalid MAC Address</h2>
                    <p><strong>Received MAC:</strong> {client_mac}</p>
                    <p>The MAC address format is invalid.</p>
                    <div style="background:#f8d7da; padding:15px; margin:20px; border-radius:5px; border-left:4px solid #dc3545;">
                        <strong>Expected Format:</strong> 12 hexadecimal characters (e.g., 001122334455 or 00:11:22:33:44:55)
                    </div>
                    <a href="/">
                        <button style="padding:12px 24px; font-size:16px; background:#dc3545; color:white; border:none; border-radius:5px; cursor:pointer;">
                            🔄 Try Again
                        </button>
                    </a>
                </body>
            </html>
            """, status_code=400)
    
    logger.info(f"✅ PRODUCTION: Processing grant request for MAC: {client_mac}, Email: {email}")

    # Get email and voucher_code from query params if not provided
    if not email:
        email = request.query_params.get('email')
    if not voucher_code:
        voucher_code = request.query_params.get('voucher_code')

    voucher = None
    # If we have email and voucher_code, verify the voucher again
    if email and voucher_code:
        account = db.query(models.Account).filter(models.Account.email == email).first()
        if account:
            voucher = db.query(models.Voucher).filter(
                models.Voucher.code == voucher_code,
                models.Voucher.account_id == account.id,
                models.Voucher.status.in_(["active", "used"])
            ).first()
            
            if not voucher:
                logger.error(f"❌ PRODUCTION: Voucher validation failed for {email}")
                return HTMLResponse("""
                <html>
                    <body style="text-align:center; font-family:sans-serif; padding:50px;">
                        <h2>❌ Voucher validation failed</h2>
                        <p>Unable to validate your voucher. Please try again.</p>
                        <a href="/">
                            <button style="padding:10px 20px; font-size:16px; background:#667eea; color:white; border:none; border-radius:5px; cursor:pointer;">
                                Back to Login
                            </button>
                        </a>
                    </body>
                </html>
                """, status_code=400)
        else:
            logger.error(f"❌ PRODUCTION: Account not found for email: {email}")

    # PRODUCTION: Validate Meraki API configuration
    if not settings.MERAKI_API_KEY or not settings.MERAKI_NETWORK_ID:
        logger.error("❌ PRODUCTION ERROR: Meraki API not configured")
        return HTMLResponse("""
        <html>
            <head><title>System Configuration Error</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>❌ System Configuration Error</h2>
                <p>Meraki API credentials are not configured.</p>
                <div style="background:#f8d7da; padding:15px; margin:20px; border-radius:5px; border-left:4px solid:#dc3545;">
                    <strong>Administrator:</strong> Please configure MERAKI_API_KEY and MERAKI_NETWORK_ID
                </div>
                <a href="/">
                    <button style="padding:12px 24px; font-size:16px; background:#dc3545; color:white; border:none; border-radius:5px; cursor:pointer;">
                        🏠 Back to Login
                    </button>
                </a>
            </body>
        </html>
        """, status_code=500)

    # Prepare Meraki API request for PRODUCTION
    headers = {
        "X-Cisco-Meraki-API-Key": settings.MERAKI_API_KEY,
        "Content-Type": "application/json",
    }

    # Determine session duration (default 1 hour if no voucher info)
    session_duration = 3600  # 1 hour default
    
    if voucher:
        # Calculate remaining time for the voucher
        if voucher.expires_at:
            # Use timezone-aware datetime comparison
            now = utc_now()
            remaining_seconds = int((voucher.expires_at - now).total_seconds())
            session_duration = max(300, remaining_seconds)  # At least 5 minutes
        else:
            session_duration = voucher.duration * 60  # Convert minutes to seconds

    data = {
        "policy": "normal",  # Grant normal access
        "duration": session_duration
    }

    # Meraki API endpoint to set client policy
    api_url = f"https://api.meraki.com/api/v1/networks/{settings.MERAKI_NETWORK_ID}/clients/{client_mac}/policy"

    try:
        logger.info(f"🚀 PRODUCTION: Attempting to grant access to client {client_mac} for {session_duration} seconds")
        logger.info(f"🌐 PRODUCTION: Calling Meraki API: {api_url}")
        
        response = requests.put(api_url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ PRODUCTION SUCCESS: Granted access to client {client_mac}")
            
            # Mark voucher as used now that we successfully granted access
            if voucher and voucher.status == "active":
                voucher.status = "used"
                db.commit()
                logger.info(f"📝 PRODUCTION: Marked voucher {voucher.code} as used")
            
            # Return the JSON response directly as per your example
            return response.json()
            
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
            
    except requests.Timeout:
        logger.error(f"⏰ PRODUCTION: Timeout error calling Meraki API")
        return HTMLResponse("""
        <html>
            <head><title>Connection Timeout</title></head>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>⏰ Connection Timeout</h2>
                <p>The Wi-Fi system is taking too long to respond.</p>
                <p>This might be a temporary network issue.</p>
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
    # Find the account by email
    account = db.query(models.Account).filter(models.Account.email == validation_data.email).first()
    if not account:
        return schemas.VoucherValidationResponse(
            valid=False,
            message="Account not found."
        )

    # Find the voucher
    voucher = db.query(models.Voucher).filter(
        models.Voucher.code == validation_data.voucher_code,
        models.Voucher.account_id == account.id
    ).first()

    if not voucher:
        return schemas.VoucherValidationResponse(
            valid=False,
            message="Invalid voucher code."
        )

    # Check voucher status
    if voucher.status not in ["active", "used"]:
        return schemas.VoucherValidationResponse(
            valid=False,
            message=f"Voucher is {voucher.status}."
        )

    # Calculate remaining time/data
    duration_remaining = None
    if voucher.expires_at:
        now = utc_now()
        remaining_time = voucher.expires_at - now
        duration_remaining = max(0, int(remaining_time.total_seconds() / 60))  # in minutes

        if duration_remaining <= 0:
            voucher.status = "expired"
            db.commit()
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher has expired."
            )

    return schemas.VoucherValidationResponse(
        valid=True,
        message="Voucher is valid.",
        duration_remaining=duration_remaining,
        data_remaining=voucher.data_limit
    )

@router.post("/demo-voucher")
def create_demo_voucher(email: str, db: Session = Depends(get_db)):
    """
    Create a 10-minute demo voucher for testing purposes.
    """
    from app import utils

    # Check if account exists, if not create it
    account = db.query(models.Account).filter(models.Account.email == email).first()
    if not account:
        account = models.Account(email=email)
        db.add(account)
        db.commit()
        db.refresh(account)

    # Generate a unique voucher code
    while True:
        code = utils.generate_voucher_code()
        if not db.query(models.Voucher).filter(models.Voucher.code == code).first():
            break

    # Create demo voucher (10 minutes)
    db_voucher = models.Voucher(
        code=code,
        account_id=account.id,
        duration=10,  # 10 minutes demo
        data_limit=None,
        status="active"
    )
    db.add(db_voucher)
    db.commit()
    db.refresh(db_voucher)

    # Send the voucher via email
    try:
        subject = "Your Demo Wi-Fi Voucher - Ditronics"
        message = f"""Hello,

Your demo Wi-Fi voucher code is: {db_voucher.code}

This voucher is valid for 10 minutes of free Wi-Fi access.

Use this code on the Wi-Fi splash page to get internet access.

Thank you for choosing Ditronics Wi-Fi!"""
        
        utils.send_email(to_email=str(account.email), subject=subject, message=message)
        logger.info(f"✅ Demo voucher {code} sent to {email}")
    except Exception as e:
        logger.error(f"❌ Failed to send email: {str(e)}")

    return {
        "message": "Demo voucher created successfully",
        "voucher_code": code,
        "duration": 10,
        "email": email
    }

# NEW USER DASHBOARD ENDPOINTS

@router.get("/user/dashboard", response_model=schemas.UserDashboard)
async def get_user_dashboard(current_user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user dashboard data with vouchers, transactions, and available packages"""
    # Get user's vouchers
    vouchers = db.query(Voucher).filter(Voucher.account_id == current_user.id).order_by(Voucher.created_at.desc()).all()
    
    # Get user's transactions
    transactions = db.query(Transaction).filter(Transaction.account_id == current_user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    
    # Get available packages
    packages = db.query(Package).filter(Package.is_active == True).order_by(Package.price).all()
    
    return schemas.UserDashboard(
        account=current_user,
        vouchers=vouchers,
        transactions=transactions,
        available_packages=packages
    )

@router.get("/user/panel", response_class=HTMLResponse)
async def user_panel_page(request: Request, current_user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    """User dashboard page"""
    # Get dashboard data
    vouchers = db.query(Voucher).filter(Voucher.account_id == current_user.id).order_by(Voucher.created_at.desc()).all()
    transactions = db.query(Transaction).filter(Transaction.account_id == current_user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    packages = db.query(Package).filter(Package.is_active == True).order_by(Package.price).all()
    
    return templates.TemplateResponse("user_panel.html", {
        "request": request,
        "user": current_user,
        "vouchers": vouchers,
        "transactions": transactions,
        "packages": packages
    })

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
        "payment_reference": f"PKG_{uuid.uuid4().hex[:8].upper()}",
        "redirect_url": f"/payment/process?package_id={package_id}"
    }
