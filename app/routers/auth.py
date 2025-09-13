from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import requests
import logging

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

@router.post("/login", response_model=schemas.LoginResponse)
def login_with_voucher(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Validate voucher and email, then redirect to grant URL if valid.
    This endpoint is called from the Meraki splash page.
    """
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
    now = datetime.utcnow()
    if voucher.expires_at and voucher.expires_at < now:
        # Mark voucher as expired
        voucher.status = "expired"
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Mark voucher as used
    voucher.status = "used"
    
    # Set expiry time if not set (for time-based vouchers)
    if not voucher.expires_at:
        expires_at = now + timedelta(minutes=voucher.duration)
        voucher.expires_at = expires_at

    db.commit()

    # Store the voucher info for the grant endpoint
    # In production, you'd use Redis or session storage for this
    grant_url = f"/auth/grant?email={login_data.email}&voucher_code={login_data.voucher_code}"

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
    
    # Get client MAC from form data or query params
    if not client_mac:
        # Try to get from query params (for testing)
        client_mac = request.query_params.get('client_mac')
    
    if not client_mac:
        logger.error("No client MAC address provided")
        return HTMLResponse("""
        <html>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>❌ Error: No client MAC address found</h2>
                <p>Unable to identify your device. Please try connecting again.</p>
                <a href="/" style="text-decoration:none;">
                    <button style="padding:10px 20px; font-size:16px; background:#667eea; color:white; border:none; border-radius:5px; cursor:pointer;">
                        Back to Login
                    </button>
                </a>
            </body>
        </html>
        """, status_code=400)

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
                logger.error(f"Voucher validation failed for {email}")
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
            logger.error(f"Account not found for email: {email}")

    # Prepare Meraki API request
    headers = {
        "X-Cisco-Meraki-API-Key": settings.MERAKI_API_KEY,
        "Content-Type": "application/json",
    }

    # Determine session duration (default 1 hour if no voucher info)
    session_duration = 3600  # 1 hour default
    
    if voucher:
        # Calculate remaining time for the voucher
        if voucher.expires_at:
            remaining_seconds = int((voucher.expires_at - datetime.utcnow()).total_seconds())
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
        logger.info(f"Attempting to grant access to client {client_mac} for {session_duration} seconds")
        response = requests.put(api_url, headers=headers, json=data)
        
        if response.status_code == 200:
            logger.info(f"Successfully granted access to client {client_mac}")
            
            # Create a success page that redirects to Meraki grant URL
            success_html = f"""
            <html>
                <head>
                    <title>Wi-Fi Access Granted</title>
                    <meta http-equiv="refresh" content="3;url={settings.MERAKI_BASE_GRANT_URL}">
                </head>
                <body style="text-align:center; font-family:sans-serif; padding:50px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white;">
                    <div style="background:white; color:#333; padding:40px; border-radius:20px; max-width:500px; margin:0 auto; box-shadow:0 15px 35px rgba(0,0,0,0.1);">
                        <h1>✅ Access Granted!</h1>
                        <p style="font-size:18px; margin:20px 0;">Welcome to Ditronics Wi-Fi</p>
                        <p>Session Duration: {session_duration // 60} minutes</p>
                        <p>You will be redirected automatically...</p>
                        <div style="margin-top:30px;">
                            <div style="border:2px solid #667eea; border-radius:50%; width:40px; height:40px; margin:0 auto; animation:spin 1s linear infinite;"></div>
                        </div>
                    </div>
                    <style>
                        @keyframes spin {{
                            0% {{ transform: rotate(0deg); }}
                            100% {{ transform: rotate(360deg); }}
                        }}
                    </style>
                    <script>
                        setTimeout(function() {{
                            window.location.href = "{settings.MERAKI_BASE_GRANT_URL}?continue_url=/";
                        }}, 3000);
                    </script>
                </body>
            </html>
            """
            return HTMLResponse(success_html)
        else:
            logger.error(f"Meraki API error: {response.status_code} - {response.text}")
            return HTMLResponse(f"""
            <html>
                <body style="text-align:center; font-family:sans-serif; padding:50px;">
                    <h2>❌ Failed to grant access</h2>
                    <p>Error: {response.status_code} - {response.text}</p>
                    <p>Please contact support or try again later.</p>
                    <a href="/">
                        <button style="padding:10px 20px; font-size:16px; background:#667eea; color:white; border:none; border-radius:5px; cursor:pointer;">
                            Back to Login
                        </button>
                    </a>
                </body>
            </html>
            """, status_code=500)
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return HTMLResponse(f"""
        <html>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>❌ Connection Error</h2>
                <p>Unable to connect to Wi-Fi system: {str(e)}</p>
                <p>Please try again later.</p>
                <a href="/">
                    <button style="padding:10px 20px; font-size:16px; background:#667eea; color:white; border:none; border-radius:5px; cursor:pointer;">
                        Back to Login
                    </button>
                </a>
            </body>
        </html>
        """, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return HTMLResponse(f"""
        <html>
            <body style="text-align:center; font-family:sans-serif; padding:50px;">
                <h2>❌ System Error</h2>
                <p>An unexpected error occurred: {str(e)}</p>
                <a href="/">
                    <button style="padding:10px 20px; font-size:16px; background:#667eea; color:white; border:none; border-radius:5px; cursor:pointer;">
                        Back to Login
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
        remaining_time = voucher.expires_at - datetime.utcnow()
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
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")

    return {
        "message": "Demo voucher created successfully",
        "voucher_code": code,
        "duration": 10,
        "email": email
    }
