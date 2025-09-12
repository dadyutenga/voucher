from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal
import json
import hashlib
import hmac
import uuid
import requests
from typing import Optional

from app import schemas, utils
from app.core.config import settings
from app.database import SessionLocal
from app.models import models

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create-payment-intent")
def create_payment_intent(payment_intent_in: schemas.PaymentIntentCreate):
    """
    Create a payment intent for M-Pesa or dummy payment.
    Returns payment details for frontend to process.
    """
    try:
        # Generate unique payment reference
        payment_ref = f"WIFI_{uuid.uuid4().hex[:8].upper()}"

        # Calculate amount in appropriate currency
        amount_kes = payment_intent_in.amount  # Assuming amount is in KES for M-Pesa

        payment_response = {
            "payment_reference": payment_ref,
            "amount": amount_kes,
            "currency": "KES",
            "payment_methods": [
                {
                    "method": "mpesa",
                    "name": "M-Pesa",
                    "description": "Pay with M-Pesa mobile money",
                    "phone_required": True
                },
                {
                    "method": "dummy",
                    "name": "Test Payment (Demo)",
                    "description": "Simulate successful payment for testing",
                    "phone_required": False
                }
            ],
            "metadata": {
                "email": payment_intent_in.email,
                "duration": payment_intent_in.duration,
                "data_limit": payment_intent_in.data_limit,
                "product_type": "wifi_voucher"
            }
        }

        return payment_response

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/mpesa/initiate")
def initiate_mpesa_payment(payment_data: schemas.MPesaPaymentRequest, db: Session = Depends(get_db)):
    """
    Initiate M-Pesa STK Push payment.
    """
    try:
        # Get M-Pesa access token
        access_token = get_mpesa_access_token()

        if not access_token:
            raise HTTPException(status_code=500, detail="Failed to get M-Pesa access token")

        # Generate timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        # Generate password
        password = generate_mpesa_password(timestamp)

        # STK Push payload
        stk_payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(payment_data.amount),
            "PartyA": payment_data.phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": payment_data.phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": payment_data.payment_reference,
            "TransactionDesc": f"Wi-Fi Voucher - {payment_data.duration} minutes"
        }

        # Make STK Push request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            "https://sandbox-api.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=stk_payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            # Store pending transaction
            transaction = models.Transaction(
                account_id=None,  # Will be set after callback
                voucher_id=None,  # Will be set after voucher creation
                amount=Decimal(payment_data.amount),
                payment_method="mpesa",
                status="pending",
                metadata=json.dumps({
                    "payment_reference": payment_data.payment_reference,
                    "phone_number": payment_data.phone_number,
                    "checkout_request_id": result.get("CheckoutRequestID"),
                    "merchant_request_id": result.get("MerchantRequestID"),
                    "email": payment_data.email,
                    "duration": payment_data.duration,
                    "data_limit": payment_data.data_limit
                })
            )
            db.add(transaction)
            db.commit()

            return {
                "success": True,
                "message": "STK push sent successfully",
                "checkout_request_id": result.get("CheckoutRequestID"),
                "merchant_request_id": result.get("MerchantRequestID"),
                "payment_reference": payment_data.payment_reference
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to initiate M-Pesa payment")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"M-Pesa payment error: {str(e)}")

@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle M-Pesa payment callbacks.
    """
    try:
        payload = await request.json()

        # Extract callback data
        stk_callback = payload.get("Body", {}).get("stkCallback", {})
        result_code = stk_callback.get("ResultCode")
        checkout_request_id = stk_callback.get("CheckoutRequestID")

        # Find the pending transaction
        transaction = db.query(models.Transaction).filter(
            models.Transaction.metadata.contains(f'"checkout_request_id": "{checkout_request_id}"')
        ).first()

        if not transaction:
            return {"status": "error", "message": "Transaction not found"}

        # Parse metadata
        metadata = json.loads(transaction.metadata)

        if result_code == 0:  # Success
            # Payment successful - create voucher
            email = metadata.get("email")
            duration = metadata.get("duration", 30)
            data_limit = metadata.get("data_limit")

            # Create or get account
            account = db.query(models.Account).filter(models.Account.email == email).first()
            if not account:
                account = models.Account(email=email)
                db.add(account)
                db.commit()
                db.refresh(account)

            # Generate unique voucher code
            while True:
                code = utils.generate_voucher_code()
                if not db.query(models.Voucher).filter(models.Voucher.code == code).first():
                    break

            # Create voucher
            voucher = models.Voucher(
                code=code,
                account_id=account.id,
                duration=duration,
                data_limit=data_limit,
                status="active"
            )
            db.add(voucher)
            db.commit()
            db.refresh(voucher)

            # Update transaction
            transaction.status = "completed"
            transaction.account_id = account.id
            transaction.voucher_id = voucher.id
            db.commit()

            # Send voucher via email
            subject = "Your Wi-Fi Voucher - M-Pesa Payment Confirmed"
            data_info = f" and {data_limit}MB of data" if data_limit else ""
            message = f"""Hello,

Thank you for your M-Pesa payment! Your Wi-Fi voucher is ready.

Voucher Details:
- Code: {voucher.code}
- Duration: {duration} minutes{data_info}
- Status: Active

How to use:
1. Connect to the Wi-Fi network
2. You'll be redirected to the login page
3. Enter your email: {email}
4. Enter your voucher code: {voucher.code}
5. Enjoy your internet access!

The voucher will automatically expire after {duration} minutes of use.

Thank you for choosing our service!

Best regards,
Wi-Fi Support Team"""

            utils.send_email(to_email=email, subject=subject, message=message)

        else:
            # Payment failed
            transaction.status = "failed"
            db.commit()

        return {"status": "success"}

    except Exception as e:
        print(f"M-Pesa callback error: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/dummy/process")
def process_dummy_payment(payment_data: schemas.DummyPaymentRequest, db: Session = Depends(get_db)):
    """
    Process a dummy payment for testing purposes.
    This simulates a successful payment instantly.
    """
    try:
        email = payment_data.email
        duration = payment_data.duration
        data_limit = payment_data.data_limit
        amount = payment_data.amount

        # Create or get account
        account = db.query(models.Account).filter(models.Account.email == email).first()
        if not account:
            account = models.Account(email=email)
            db.add(account)
            db.commit()
            db.refresh(account)

        # Generate unique voucher code
        while True:
            code = utils.generate_voucher_code()
            if not db.query(models.Voucher).filter(models.Voucher.code == code).first():
                break

        # Create voucher
        voucher = models.Voucher(
            code=code,
            account_id=account.id,
            duration=duration,
            data_limit=data_limit,
            status="active"
        )
        db.add(voucher)
        db.commit()
        db.refresh(voucher)

        # Create transaction record
        transaction = models.Transaction(
            account_id=account.id,
            voucher_id=voucher.id,
            amount=Decimal(amount),
            payment_method="dummy",
            status="completed",
            metadata=json.dumps({
                "payment_reference": payment_data.payment_reference,
                "test_payment": True
            })
        )
        db.add(transaction)
        db.commit()

        # Send voucher via email
        subject = "Your Wi-Fi Voucher - Test Payment Successful"
        data_info = f" and {data_limit}MB of data" if data_limit else ""
        message = f"""Hello,

Your test payment was successful! Here's your Wi-Fi voucher:

Voucher Details:
- Code: {voucher.code}
- Duration: {duration} minutes{data_info}
- Status: Active

How to use:
1. Connect to the Wi-Fi network
2. You'll be redirected to the login page
3. Enter your email: {email}
4. Enter your voucher code: {voucher.code}
5. Enjoy your internet access!

This was a test payment. In production, you would use M-Pesa or other payment methods.

Best regards,
Wi-Fi Support Team"""

        utils.send_email(to_email=email, subject=subject, message=message)

        return {
            "success": True,
            "message": "Payment processed successfully",
            "voucher_code": voucher.code,
            "payment_reference": payment_data.payment_reference,
            "transaction_id": transaction.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing error: {str(e)}")

@router.get("/plans")
def get_voucher_plans():
    """
    Get available voucher plans with pricing in KES.
    """
    plans = [
        {
            "id": "demo",
            "name": "Demo Access",
            "duration": 10,  # minutes
            "data_limit": None,
            "price": 0,  # Free
            "currency": "KES",
            "description": "10 minutes of free Wi-Fi access"
        },
        {
            "id": "basic",
            "name": "Basic Access",
            "duration": 60,  # 1 hour
            "data_limit": None,
            "price": 50,  # KES 50
            "currency": "KES",
            "description": "1 hour of unlimited Wi-Fi access"
        },
        {
            "id": "standard",
            "name": "Standard Access",
            "duration": 180,  # 3 hours
            "data_limit": None,
            "price": 100,  # KES 100
            "currency": "KES",
            "description": "3 hours of unlimited Wi-Fi access"
        },
        {
            "id": "premium",
            "name": "Premium Access",
            "duration": 720,  # 12 hours
            "data_limit": None,
            "price": 200,  # KES 200
            "currency": "KES",
            "description": "12 hours of unlimited Wi-Fi access"
        },
        {
            "id": "daily",
            "name": "Daily Pass",
            "duration": 1440,  # 24 hours
            "data_limit": None,
            "price": 300,  # KES 300
            "currency": "KES",
            "description": "24 hours of unlimited Wi-Fi access"
        },
        {
            "id": "data_500mb",
            "name": "500MB Data Pack",
            "duration": 4320,  # 3 days
            "data_limit": 500,  # 500MB
            "price": 150,  # KES 150
            "currency": "KES",
            "description": "500MB of data valid for 3 days"
        },
        {
            "id": "data_1gb",
            "name": "1GB Data Pack",
            "duration": 10080,  # 7 days
            "data_limit": 1024,  # 1GB
            "price": 250,  # KES 250
            "currency": "KES",
            "description": "1GB of data valid for 7 days"
        }
    ]

    return {"plans": plans}

@router.post("/create-demo-voucher")
def create_demo_voucher(email: str, db: Session = Depends(get_db)):
    """
    Create a free demo voucher for new users.
    This should have rate limiting in production.
    """
    # Check if user already has an active demo voucher
    account = db.query(models.Account).filter(models.Account.email == email).first()
    if account:
        existing_demo = db.query(models.Voucher).filter(
            models.Voucher.account_id == account.id,
            models.Voucher.duration == 10,  # Demo vouchers are 10 minutes
            models.Voucher.status == "active"
        ).first()

        if existing_demo:
            return {
                "message": "You already have an active demo voucher",
                "voucher_code": existing_demo.code
            }
    else:
        # Create account
        account = models.Account(email=email)
        db.add(account)
        db.commit()
        db.refresh(account)

    # Generate a unique voucher code
    while True:
        code = utils.generate_voucher_code()
        if not db.query(models.Voucher).filter(models.Voucher.code == code).first():
            break

    # Create demo voucher
    db_voucher = models.Voucher(
        code=code,
        account_id=account.id,
        duration=10,  # 10 minutes
        data_limit=None,
        status="active"
    )
    db.add(db_voucher)
    db.commit()
    db.refresh(db_voucher)

    # Create transaction record for the free voucher
    transaction = models.Transaction(
        account_id=account.id,
        voucher_id=db_voucher.id,
        amount=Decimal('0.00'),
        payment_method="demo",
        status="completed"
    )
    db.add(transaction)
    db.commit()

    # Send email
    subject = "Your FREE Wi-Fi Demo Voucher"
    message = f"""Hello,

Welcome! Here's your free demo Wi-Fi voucher:

Voucher Code: {code}
Duration: 10 minutes
Data: Unlimited

How to use:
1. Connect to the Wi-Fi network
2. Enter your email: {email}
3. Enter your voucher code: {code}
4. Enjoy 10 minutes of free internet!

Want more time? Purchase a full voucher plan for extended access.

Best regards,
Wi-Fi Support Team"""

    utils.send_email(to_email=email, subject=subject, message=message)

    return {
        "message": "Demo voucher created and sent to email",
        "voucher_code": code,
        "duration": 10
    }

@router.get("/transaction/{transaction_id}")
def get_transaction_status(transaction_id: int, db: Session = Depends(get_db)):
    """
    Get transaction status for payment tracking.
    """
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "transaction_id": transaction.id,
        "status": transaction.status,
        "amount": float(transaction.amount),
        "payment_method": transaction.payment_method,
        "created_at": transaction.created_at
    }

# M-Pesa helper functions
def get_mpesa_access_token():
    """Get M-Pesa access token."""
    try:
        consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')

        if not consumer_key or not consumer_secret:
            return None

        api_url = "https://sandbox-api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

        response = requests.get(
            api_url,
            auth=(consumer_key, consumer_secret),
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get('access_token')
        return None

    except Exception as e:
        print(f"Error getting M-Pesa access token: {e}")
        return None

def generate_mpesa_password(timestamp):
    """Generate M-Pesa password."""
    try:
        shortcode = getattr(settings, 'MPESA_SHORTCODE', '')
        passkey = getattr(settings, 'MPESA_PASSKEY', '')

        password_str = shortcode + passkey + timestamp
        password = hashlib.sha256(password_str.encode()).hexdigest()

        import base64
        return base64.b64encode(password.encode()).decode()

    except Exception as e:
        print(f"Error generating M-Pesa password: {e}")
        return ""
