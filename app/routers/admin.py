from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import func

from app import schemas, utils
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

@router.post("/vouchers", response_model=schemas.Voucher)
def create_voucher_for_user(voucher_in: schemas.VoucherCreate, db: Session = Depends(get_db)):
    """
    Create a new voucher, assign it to a user (by email), and send it via email.
    """
    # Check if account exists, if not create it
    account = db.query(models.Account).filter(models.Account.email == voucher_in.email).first()
    if not account:
        account = models.Account(email=voucher_in.email)
        db.add(account)
        db.commit()
        db.refresh(account)

    # Generate a unique voucher code
    while True:
        code = utils.generate_voucher_code()
        if not db.query(models.Voucher).filter(models.Voucher.code == code).first():
            break

    # Create the voucher
    db_voucher = models.Voucher(
        code=code,
        account_id=account.id,
        duration=voucher_in.duration,
        data_limit=voucher_in.data_limit
    )
    db.add(db_voucher)
    db.commit()
    db.refresh(db_voucher)

    # Send the voucher via email
    subject = "Your Wi-Fi Voucher"
    message = f"Hello,\n\nYour Wi-Fi voucher code is: {db_voucher.code}\n\nIt is valid for {db_voucher.duration} minutes."
    utils.send_email(to_email=str(account.email), subject=subject, message=message)

    return db_voucher

@router.get("/vouchers", response_model=List[schemas.Voucher])
def list_vouchers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all vouchers with pagination.
    """
    vouchers = db.query(models.Voucher).offset(skip).limit(limit).all()
    return vouchers

@router.get("/vouchers/{voucher_id}", response_model=schemas.Voucher)
def get_voucher(voucher_id: int, db: Session = Depends(get_db)):
    """
    Get a specific voucher by ID.
    """
    voucher = db.query(models.Voucher).filter(models.Voucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    return voucher

@router.get("/accounts", response_model=List[schemas.Account])
def list_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all accounts with pagination.
    """
    accounts = db.query(models.Account).offset(skip).limit(limit).all()
    return accounts

@router.get("/accounts/{account_id}", response_model=schemas.Account)
def get_account(account_id: int, db: Session = Depends(get_db)):
    """
    Get a specific account by ID.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.get("/accounts/{account_id}/vouchers", response_model=List[schemas.Voucher])
def get_account_vouchers(account_id: int, db: Session = Depends(get_db)):
    """
    Get all vouchers for a specific account.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    vouchers = db.query(models.Voucher).filter(models.Voucher.account_id == account_id).all()
    return vouchers

@router.get("/transactions", response_model=List[schemas.Transaction])
def list_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all transactions with pagination.
    """
    transactions = db.query(models.Transaction).offset(skip).limit(limit).all()
    return transactions

@router.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """
    Get a specific transaction by ID.
    """
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@router.delete("/vouchers/{voucher_id}")
def delete_voucher(voucher_id: int, db: Session = Depends(get_db)):
    """
    Delete a voucher (mark as expired).
    """
    voucher = db.query(models.Voucher).filter(models.Voucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")

    db.query(models.Voucher).filter(models.Voucher.id == voucher_id).update({"status": "expired"})
    db.commit()
    return {"message": "Voucher marked as expired"}

@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """
    Get system statistics for the dashboard.
    """
    total_accounts = db.query(models.Account).count()
    total_vouchers = db.query(models.Voucher).count()
    active_vouchers = db.query(models.Voucher).filter(models.Voucher.status == "active").count()
    used_vouchers = db.query(models.Voucher).filter(models.Voucher.status == "used").count()
    expired_vouchers = db.query(models.Voucher).filter(models.Voucher.status == "expired").count()
    total_transactions = db.query(models.Transaction).count()

    # Calculate total revenue from completed transactions
    total_revenue_result = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.status == "completed"
    ).scalar()

    total_revenue = float(total_revenue_result) if total_revenue_result else 0.0

    return {
        "total_accounts": total_accounts,
        "total_vouchers": total_vouchers,
        "active_vouchers": active_vouchers,
        "used_vouchers": used_vouchers,
        "expired_vouchers": expired_vouchers,
        "total_transactions": total_transactions,
        "total_revenue": total_revenue
    }
