"""
Startup script for Wi-Fi Voucher System FastAPI application.
This script handles application initialization and startup.
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'DATABASE_URL',
        'SMTP_SERVER',
        'SMTP_USERNAME',
        'SMTP_PASSWORD',
        'SENDER_EMAIL'
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please create a .env file based on .env.example")
        return False

    return True

def run_development():
    """Run the application in development mode."""
    print("🚀 Starting Wi-Fi Voucher System in development mode...")

    if not check_environment():
        sys.exit(1)

    # Import here to avoid issues with environment variables
    try:
        from app.main import app
        print("✅ Application imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import application: {e}")
        sys.exit(1)

    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8090,
        reload=True,
        log_level="info",
        reload_dirs=["app"],
        access_log=True
    )

def run_production():
    """Run the application in production mode."""
    print("🏭 Starting Wi-Fi Voucher System in production mode...")

    if not check_environment():
        sys.exit(1)

    try:
        from app.main import app
        print("✅ Application imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import application: {e}")
        sys.exit(1)

    # Run with uvicorn in production mode
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=int(os.getenv("WORKERS", 1)),
        log_level="warning",
        access_log=False
    )

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Wi-Fi Voucher System Runner")
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        default="dev",
        help="Run mode: dev (development) or prod (production)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("🌐 Wi-Fi Voucher System")
    print("=" * 50)

    # Set environment variables for host and port if provided
    if args.host != "0.0.0.0":
        os.environ["HOST"] = args.host
    if args.port != 8000:
        os.environ["PORT"] = str(args.port)

    if args.mode == "prod":
        run_production()
    else:
        run_development()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Shutting down Wi-Fi Voucher System...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
