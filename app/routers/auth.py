from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import requests
import logging
import re

from app import schemas
from app.database import SessionLocal
from app.models import models
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def utc_now():
    """Get current UTC time with timezone info"""
    return datetime.now(timezone.utc)

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
