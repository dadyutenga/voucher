from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = FastAPI()

MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
MERAKI_NETWORK_ID = os.getenv("MERAKI_NETWORK_ID")
MERAKI_BASE_GRANT_URL = os.getenv("MERAKI_BASE_GRANT_URL")

# Optional: serve static files like CSS
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def splash():
    return """
    <html>
        <head><title>Welcome Wi-Fi</title></head>
        <body style="text-align:center; font-family:sans-serif;">
            <h1>Welcome to Ditronics Wi-Fi</h1>
            <form action="/grant" method="post">
                <button type="submit" style="padding:10px 20px; font-size:16px;">Connect</button>
            </form>
        </body>
    </html>
    """


@app.post("/grant")
async def grant_access(request: Request, client_mac: str = Form(...)):
    """
    Grant the connecting client access using Meraki API.
    client_mac must be provided by Meraki redirect.
    """
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json",
    }

    data = {
        "policy": "normal",   # grant normal access
        "duration": 3600      # 1 hour
    }

    url = f"https://api.meraki.com/api/v1/networks/{MERAKI_NETWORK_ID}/clients/{client_mac}/policy"

    try:
        response = requests.put(url, headers=headers, json=data)
        if response.status_code == 200:
            # Redirect client to Meraki grant URL so they are fully authenticated
            return HTMLResponse(f"""
            <html>
                <body>
                    <h2>Access granted! Redirecting...</h2>
                    <script>
                        window.location.href = "{MERAKI_BASE_GRANT_URL}?continue_url=/";
                    </script>
                </body>
            </html>
            """)
        else:
            return HTMLResponse(f"<h2>Failed to grant access: {response.text}</h2>", status_code=500)
    except Exception as e:
        return HTMLResponse(f"<h2>Error: {str(e)}</h2>", status_code=500)
