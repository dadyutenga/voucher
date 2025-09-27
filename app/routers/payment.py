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
from app.database import get_db
from app.models.models import Account, Voucher, Transaction, Package

router = APIRouter()

@router.post("/create-payment-intent")
def create_payment_intent(payment_intent_in: schemas.PaymentIntentCreate, db: Session = Depends(get_db)):
    """
    Create a payment intent for M-Pesa or dummy payment.
    Returns payment details for frontend to process.
    """
    try:
        # Get package details
        package = db.query(Package).filter(Package.id == payment_intent_in.package_id).first()
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        if not package.is_active:
            raise HTTPException(status_code=400, detail="Package is not available")

        # Generate unique payment reference
        payment_ref = f"WIFI_{uuid.uuid4().hex[:8].upper()}"

        payment_response = {
            "payment_reference": payment_ref,
            "amount": float(package.price),
            "currency": package.currency,
            "package": {
                "id": package.id,
                "name": package.name,
                "duration": package.duration,
                "data_limit": package.data_limit,
                "price": float(package.price)
            },
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
                "mobile_number": payment_intent_in.mobile_number,
                "package_id": package.id,
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
            transaction = Transaction(
                account_id=None,  # Will be set after callback
                voucher_id=None,  # Will be set after voucher creation
                package_id=payment_data.package_id,
                amount=Decimal(payment_data.amount),
                payment_method="mpesa",
                status="pending",
                transaction_metadata=json.dumps({
                    "payment_reference": payment_data.payment_reference,
                    "phone_number": payment_data.phone_number,
                    "checkout_request_id": result.get("CheckoutRequestID"),
                    "merchant_request_id": result.get("MerchantRequestID"),
                    "mobile_number": payment_data.mobile_number,
                    "package_id": payment_data.package_id
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
        transaction = db.query(Transaction).filter(
            Transaction.transaction_metadata.contains(f'"checkout_request_id": "{checkout_request_id}"')
        ).first()

        if not transaction:
            return {"status": "error", "message": "Transaction not found"}

        # Parse metadata
        metadata = json.loads(transaction.transaction_metadata)

        if result_code == 0:  # Success
            # Payment successful - create voucher
            mobile_number = metadata.get("mobile_number")
            package_id = metadata.get("package_id")
            
            # Get package details
            package = db.query(Package).filter(Package.id == package_id).first()
            if not package:
                transaction.status = "failed"
                db.commit()
                return {"status": "error", "message": "Package not found"}

            # Create or get account
            account = db.query(Account).filter(Account.mobile_number == mobile_number).first()
            if not account:
                # Create account with a default password (user should change it later)
                from app.routers.auth import get_password_hash
                hashed_password = get_password_hash("changeme123")  # Default password
                account = Account(mobile_number=mobile_number, password_hash=hashed_password)
                db.add(account)
                db.commit()
                db.refresh(account)

            # Generate unique voucher code
            while True:
                code = utils.generate_voucher_code()
                if not db.query(Voucher).filter(Voucher.code == code).first():
                    break

            # Create voucher with package details
            voucher = Voucher(
                code=code,
                account_id=account.id,
                package_id=package.id,
                duration=package.duration,
                data_limit=package.data_limit,
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

            # Send voucher via SMS or email if available
            subject = "Your Wi-Fi Voucher - M-Pesa Payment Confirmed"
            data_info = f" and {package.data_limit}MB of data" if package.data_limit else ""
            message = f"""Hello,

Thank you for your M-Pesa payment! Your Wi-Fi voucher is ready.

Voucher Details:
- Code: {voucher.code}
- Package: {package.name}
- Duration: {package.duration} minutes{data_info}
- Status: Active

How to use:
1. Connect to the Wi-Fi network
2. You'll be redirected to the login page
3. Enter your mobile number: {mobile_number}
4. Enter your voucher code: {voucher.code}
5. Enjoy your internet access!

The voucher will automatically expire after {package.duration} minutes of use.

Thank you for choosing our service!

Best regards,
Wi-Fi Support Team"""

            # For now, just log the voucher (you can integrate SMS service later)
            print(f"Voucher created for {mobile_number}: {voucher.code}")

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
        mobile_number = payment_data.mobile_number
        package_id = payment_data.package_id
        amount = payment_data.amount
        
        # Get package details
        package = db.query(Package).filter(Package.id == package_id).first()
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        if not package.is_active:
            raise HTTPException(status_code=400, detail="Package is not available")

        # Create or get account
        account = db.query(Account).filter(Account.mobile_number == mobile_number).first()
        if not account:
            # Create account with a default password (user should change it later)
            from app.routers.auth import get_password_hash
            hashed_password = get_password_hash("changeme123")  # Default password
            account = Account(mobile_number=mobile_number, password_hash=hashed_password)
            db.add(account)
            db.commit()
            db.refresh(account)

        # Generate unique voucher code
        while True:
            code = utils.generate_voucher_code()
            if not db.query(Voucher).filter(Voucher.code == code).first():
                break

        # Create voucher with package details
        voucher = Voucher(
            code=code,
            account_id=account.id,
            package_id=package.id,
            duration=package.duration,
            data_limit=package.data_limit,
            status="active"
        )
        db.add(voucher)
        db.commit()
        db.refresh(voucher)

        # Create transaction record
        transaction = Transaction(
            account_id=account.id,
            voucher_id=voucher.id,
            package_id=package.id,
            amount=Decimal(amount),
            payment_method="dummy",
            status="completed",
            transaction_metadata=json.dumps({
                "payment_reference": payment_data.payment_reference,
                "test_payment": True
            })
        )
        db.add(transaction)
        db.commit()

        # For now, just log the voucher creation (you can integrate SMS service later)
        print(f"Test voucher created for {mobile_number}: {voucher.code}")

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
def get_voucher_plans(db: Session = Depends(get_db)):
    """
    Get available voucher plans from database packages.
    """
    packages = db.query(Package).filter(Package.is_active == True).order_by(Package.price).all()
    
    plans = []
    for package in packages:
        plans.append({
            "id": package.id,
            "name": package.name,
            "duration": package.duration,
            "data_limit": package.data_limit,
            "price": float(package.price),
            "currency": package.currency,
            "description": package.description or f"{package.duration} minutes of {'unlimited' if not package.data_limit else str(package.data_limit) + 'MB'} Wi-Fi access"
        })
    
    return {"plans": plans}

@router.post("/create-demo-voucher")
def create_demo_voucher(mobile_number: str, db: Session = Depends(get_db)):
    """
    Create a free demo voucher for new users.
    This should have rate limiting in production.
    """
    # Check if user already has an active demo voucher
    account = db.query(Account).filter(Account.mobile_number == mobile_number).first()
    if account:
        existing_demo = db.query(Voucher).filter(
            Voucher.account_id == account.id,
            Voucher.duration == 10,  # Demo vouchers are 10 minutes
            Voucher.status == "active"
        ).first()

        if existing_demo:
            return {
                "message": "You already have an active demo voucher",
                "voucher_code": existing_demo.code
            }
    else:
        # Create account with default password
        from app.routers.auth import get_password_hash
        hashed_password = get_password_hash("demo123")  # Default demo password
        account = Account(mobile_number=mobile_number, password_hash=hashed_password)
        db.add(account)
        db.commit()
        db.refresh(account)

    # Generate a unique voucher code
    while True:
        code = utils.generate_voucher_code()
        if not db.query(Voucher).filter(Voucher.code == code).first():
            break

    # Create demo voucher
    db_voucher = Voucher(
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
    transaction = Transaction(
        account_id=account.id,
        voucher_id=db_voucher.id,
        amount=Decimal('0.00'),
        payment_method="demo",
        status="completed"
    )
    db.add(transaction)
    db.commit()

    # For now, just log the voucher creation (you can integrate SMS service later)
    print(f"Demo voucher created for {mobile_number}: {code}")

    return {
        "message": "Demo voucher created",
        "voucher_code": code,
        "duration": 10,
        "mobile_number": mobile_number
    }

@router.get("/transaction/{transaction_id}")
def get_transaction_status(transaction_id: int, db: Session = Depends(get_db)):
    """
    Get transaction status for payment tracking.
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
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
