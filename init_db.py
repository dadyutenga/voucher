"""
Database initialization script for Wi-Fi Voucher System.
Run this script to create the database tables.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from sqlalchemy import create_engine
from app.database import Base
from app.core.config import settings
from app.models import models  # This ensures all models are imported

def init_database():
    """Initialize the database by creating all tables."""
    try:
        print("🔄 Initializing database...")
        print(f"📍 Database URL: {settings.DATABASE_URL}")

        # Create engine
        engine = create_engine(settings.DATABASE_URL)

        # Create all tables
        Base.metadata.create_all(bind=engine)

        print("✅ Database initialized successfully!")
        print("📊 Created tables:")
        for table in Base.metadata.tables.keys():
            print(f"   - {table}")

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your DATABASE_URL in .env file")
        print("3. Ensure the database exists (create it manually if needed)")
        print("4. Verify database user has proper permissions")
        sys.exit(1)

def reset_database():
    """Drop all tables and recreate them. USE WITH CAUTION!"""
    try:
        print("⚠️  RESETTING DATABASE - This will delete all data!")
        confirm = input("Are you sure? Type 'yes' to continue: ")

        if confirm.lower() != 'yes':
            print("❌ Operation cancelled")
            return

        print("🔄 Dropping all tables...")
        engine = create_engine(settings.DATABASE_URL)

        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("🗑️  All tables dropped")

        # Recreate all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database reset successfully!")

    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument("--reset", action="store_true", help="Reset database (WARNING: deletes all data)")

    args = parser.parse_args()

    if args.reset:
        reset_database()
    else:
        init_database()
