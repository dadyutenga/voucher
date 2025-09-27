from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from app.routers import admin, payment, auth
from app.database import SessionLocal
from app.models.models import *

app = FastAPI(title="Wi-Fi Voucher System", description="Production-ready Wi-Fi hotspot with voucher-based access control")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files if they exist
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass  # Static directory doesn't exist, which is fine

# Include routers with proper prefixes
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(payment.router, prefix="/payment", tags=["payment"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# MAIN ENTRY POINTS

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """
    Main entry point - Welcome screen with register/login options
    """
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)  
async def login_page(request: Request):
    """
    Login page for both users and admins
    """
    return templates.TemplateResponse("login.html", {"request": request})

# USER ROUTES

@app.get("/user/login", response_class=HTMLResponse)
async def user_login_page(request: Request):
    """
    User login page
    """
    return templates.TemplateResponse("user_login.html", {"request": request})

@app.get("/user/register", response_class=HTMLResponse)
async def user_register_page(request: Request):
    """
    User registration page
    """
    return templates.TemplateResponse("user_register.html", {"request": request})

@app.get("/user/panel", response_class=HTMLResponse)
async def user_panel_page(request: Request):
    """
    User dashboard/panel for managing vouchers and packages
    """
    return templates.TemplateResponse("user_panel.html", {"request": request})

@app.get("/user/splash", response_class=HTMLResponse)
async def user_splash_page(request: Request):
    """
    Simplified splash page for voucher validation only
    This is called from the captive portal
    """
    return templates.TemplateResponse("user_splash.html", {"request": request})

# ADMIN ROUTES

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """
    Admin login page
    """
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """
    Admin dashboard for system management
    """
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# API HEALTH AND INFO

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "wifi-voucher-system", "version": "2.0.0"}

@app.get("/api/info")
def api_info():
    return {
        "name": "Wi-Fi Voucher System",
        "version": "2.0.0", 
        "description": "Production-ready Wi-Fi access control system",
        "routes": {
            "user": ["/user/login", "/user/register", "/user/user-panel", "/user/splash"],
            "admin": ["/admin/login", "/admin/dashboard"],
            "auth": ["/auth/*"],
            "payment": ["/payment/*"]
        }
    }
