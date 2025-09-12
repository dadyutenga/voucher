from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.routers import admin, payment, auth

app = FastAPI(title="Wi-Fi Voucher System", description="Wi-Fi hotspot with voucher-based access control")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(payment.router, prefix="/payment", tags=["payment"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.get("/")
def read_root():
    return {"message": "Wi-Fi Voucher System API", "version": "1.0.0"}

@app.get("/splash", response_class=HTMLResponse)
async def splash_page(request: Request):
    """
    Serve the splash page for Wi-Fi login.
    This would typically be called from the Meraki captive portal.
    """
    return templates.TemplateResponse("splash.html", {"request": request})

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "wifi-voucher-api"}
