from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import get_db
from app.models.models import Account, Voucher, Transaction, Package
from app.schemas.schemas import (
    Package as PackageSchema,
    PackageCreate,
    PackageUpdate,
    AdminDashboard,
    Account as AccountSchema
)
from app.routers.auth import get_current_user, create_access_token
import bcrypt

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# Simple admin authentication (can be enhanced later)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())

def verify_admin(username: str, password: str) -> bool:
    """Verify admin credentials"""
    if username != ADMIN_USERNAME:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD_HASH)

def get_current_admin(request: Request):
    """Check if user is authenticated admin"""
    token = request.cookies.get("admin_token")
    if not token:
        raise HTTPException(status_code=401, detail="Admin authentication required")
    # For simplicity, we'll just check if token exists and equals expected value
    # In production, you'd want proper JWT validation
    if token != "admin_authenticated":
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True

# Admin login page
@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

# Admin login processing
@router.post("/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not verify_admin(username, password):
        return templates.TemplateResponse(
            "admin_login.html", 
            {"request": request, "error": "Invalid username or password"}
        )
    
    # Set admin cookie and redirect to dashboard
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie(key="admin_token", value="admin_authenticated", httponly=True)
    return response

# Admin dashboard
@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # Get dashboard statistics
    total_accounts = db.query(Account).count()
    total_vouchers = db.query(Voucher).count()
    active_vouchers = db.query(Voucher).filter(Voucher.status == "active").count()
    
    # Calculate total revenue
    total_revenue = db.query(func.sum(Transaction.amount)).filter(
        Transaction.status == "completed"
    ).scalar() or Decimal('0')
    
    # Get recent transactions
    recent_transactions = db.query(Transaction).order_by(desc(Transaction.created_at)).limit(10).all()
    
    # Get all packages
    packages = db.query(Package).order_by(Package.created_at).all()
    
    dashboard_data = {
        "total_accounts": total_accounts,
        "total_vouchers": total_vouchers,
        "active_vouchers": active_vouchers,
        "total_revenue": total_revenue,
        "recent_transactions": recent_transactions,
        "packages": packages
    }
    
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, **dashboard_data})

# Package management endpoints
@router.get("/packages", response_model=List[PackageSchema])
async def get_packages(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(Package).all()

@router.post("/packages", response_model=PackageSchema)
async def create_package(package: PackageCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # Check if package ID already exists
    existing = db.query(Package).filter(Package.id == package.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Package ID already exists")
    
    db_package = Package(**package.dict())
    db.add(db_package)
    db.commit()
    db.refresh(db_package)
    return db_package

@router.put("/packages/{package_id}", response_model=PackageSchema)
async def update_package(
    package_id: str, 
    package_update: PackageUpdate, 
    db: Session = Depends(get_db), 
    admin=Depends(get_current_admin)
):
    db_package = db.query(Package).filter(Package.id == package_id).first()
    if not db_package:
        raise HTTPException(status_code=404, detail="Package not found")
    
    update_data = package_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_package, field, value)
    
    db_package.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_package)
    return db_package

@router.delete("/packages/{package_id}")
async def delete_package(package_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    db_package = db.query(Package).filter(Package.id == package_id).first()
    if not db_package:
        raise HTTPException(status_code=404, detail="Package not found")
    
    db.delete(db_package)
    db.commit()
    return {"message": "Package deleted successfully"}

# User management endpoints
@router.get("/users", response_model=List[AccountSchema])
async def get_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    admin=Depends(get_current_admin)
):
    return db.query(Account).offset(skip).limit(limit).all()

@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    user = db.query(Account).filter(Account.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User {'activated' if user.is_active else 'deactivated'} successfully"}

# Admin logout
@router.post("/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(key="admin_token")
    return response
