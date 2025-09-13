from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
import hmac

from app import schemas
from app.database import SessionLocal
from app.models import models
from app.core.config import settings

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
    Validate voucher and email, then redirect to Meraki grant URL if valid.
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
    voucher_status = voucher.status
    if voucher_status != "active":
        return schemas.LoginResponse(
            success=False,
            message=f"Voucher is {voucher_status}. Please purchase a new voucher."
        )

    # Check if voucher has expired
    now = datetime.utcnow()
    voucher_expires_at = voucher.expires_at
    if voucher_expires_at is not None and voucher_expires_at < now:
        # Mark voucher as expired
        db.query(models.Voucher).filter(models.Voucher.id == voucher.id).update({"status": "expired"})
        db.commit()
        return schemas.LoginResponse(
            success=False,
            message="Voucher has expired. Please purchase a new voucher."
        )

    # Mark voucher as used (you might want to track usage differently)
    db.query(models.Voucher).filter(models.Voucher.id == voucher.id).update({"status": "used"})

    # Set expiry time if not set (for time-based vouchers)
    if voucher_expires_at is None:
        voucher_duration = voucher.duration
        expires_at = now + timedelta(minutes=voucher_duration)
        db.query(models.Voucher).filter(models.Voucher.id == voucher.id).update({"expires_at": expires_at})

    db.commit()

    # Use the correct Meraki base grant URL from settings
    # This constructs the full grant URL with parameters that Meraki expects
    base_url = settings.MERAKI_BASE_GRANT_URL.rstrip('/')
    
    # For Meraki, you typically need to append parameters like:
    # ?continue_url=<original_destination>&duration=<session_duration>
    # The exact format depends on your Meraki network configuration
    grant_url = f"{base_url}?user_id={account.email}&session_duration={voucher.duration}"

    return schemas.LoginResponse(
        success=True,
        message="Login successful! You now have internet access.",
        redirect_url=grant_url
    )

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
    voucher_status = voucher.status
    if voucher_status not in ["active", "used"]:
        return schemas.VoucherValidationResponse(
            valid=False,
            message=f"Voucher is {voucher_status}."
        )

    # Calculate remaining time/data
    duration_remaining = None
    voucher_data_limit = voucher.data_limit

    voucher_expires_at = voucher.expires_at
    if voucher_expires_at is not None:
        remaining_time = voucher_expires_at - datetime.utcnow()
        duration_remaining = max(0, int(remaining_time.total_seconds() / 60))  # in minutes

        if duration_remaining <= 0:
            db.query(models.Voucher).filter(models.Voucher.id == voucher.id).update({"status": "expired"})
            db.commit()
            return schemas.VoucherValidationResponse(
                valid=False,
                message="Voucher has expired."
            )

    return schemas.VoucherValidationResponse(
        valid=True,
        message="Voucher is valid.",
        duration_remaining=duration_remaining,
        data_remaining=voucher_data_limit
    )

@router.get("/demo-voucher")
def create_demo_voucher(email: str, db: Session = Depends(get_db)):
    """
    Create a 10-minute demo voucher for testing purposes.
    This endpoint should be secured in production.
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
    subject = "Your Demo Wi-Fi Voucher"
    message = f"Hello,\n\nYour demo Wi-Fi voucher code is: {db_voucher.code}\n\nIt is valid for 10 minutes.\n\nUse this code on the Wi-Fi splash page to get internet access."
    utils.send_email(to_email=str(account.email), subject=subject, message=message)

    return {
        "message": "Demo voucher created and sent to email",
        "voucher_code": code,
        "duration": 10,
        "email": email
    }

@router.post("/logout")
def logout_user(request: Request):
    """
    Handle user logout. In a Meraki environment, this would typically
    revoke the user's session on the access point.
    """
    # In a real implementation, you'd call Meraki API to revoke the session
    # For now, just return a success message
    return {"message": "Logged out successfully"}
