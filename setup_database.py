"""
Complete database setup script for Wi-Fi Voucher System
This script will:
1. Run Alembic migrations to create/update database schema
2. Seed the database with sample packages
"""

import os
import sys
import subprocess
from pathlib import Path
from decimal import Decimal

# Add the app directory to Python path
project_root = Path(__file__).parent
app_dir = project_root / "app"
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.models import Package
from app.core.config import settings

def check_environment():
    """Check if environment is properly configured"""
    print("Checking environment configuration...")
    
    # Check if .env file exists
    env_file = project_root / '.env'
    if not env_file.exists():
        print("ERROR: .env file not found!")
        print("Please copy env_example.txt to .env and configure it")
        return False
    
    # Check DATABASE_URL
    if not settings.DATABASE_URL or settings.DATABASE_URL == "postgresql://user:pass@localhost/dbname":
        print("ERROR: DATABASE_URL not properly configured!")
        print("Please update your .env file with correct database credentials")
        return False
    
    print(f"SUCCESS: Environment configured")
    print(f"Database URL: {settings.DATABASE_URL}")
    return True

def run_alembic_upgrade():
    """Run Alembic migrations to upgrade database schema"""
    try:
        print("Running Alembic migrations...")
        
        # Change to app directory to run alembic
        os.chdir(app_dir)
        
        # Run alembic upgrade
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("SUCCESS: Database migrations completed successfully!")
            if result.stdout:
                print(result.stdout)
        else:
            print("ERROR: Migration failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
        
        # Change back to project root
        os.chdir(project_root)
        return True
        
    except Exception as e:
        print(f"ERROR: Error running migrations: {e}")
        return False

def seed_packages():
    """Seed the database with sample packages"""
    try:
        print("Seeding sample packages...")
        
        db = SessionLocal()
        
        # Check if packages already exist
        existing_count = db.query(Package).count()
        if existing_count > 0:
            print(f"INFO: Database already has {existing_count} packages - skipping seed")
            return True
        
        # Create sample packages
        packages = [
            Package(
                id="demo",
                name="Demo Access",
                description="Free 15-minute trial for new users",
                duration=15,
                data_limit=None,
                price=Decimal("0.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="basic",
                name="Basic Access",
                description="Perfect for quick internet access and messaging",
                duration=60,  # 1 hour
                data_limit=None,
                price=Decimal("1000.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="standard",
                name="Standard Access", 
                description="Great for browsing, social media, and light streaming",
                duration=180,  # 3 hours
                data_limit=None,
                price=Decimal("2500.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="premium",
                name="Premium Access",
                description="All-day internet access for work and entertainment",
                duration=720,  # 12 hours
                data_limit=None,
                price=Decimal("5000.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="daily",
                name="Daily Pass",
                description="24 hours of unlimited internet access",
                duration=1440,  # 24 hours
                data_limit=None,
                price=Decimal("8000.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="data_1gb",
                name="1GB Data Pack",
                description="1GB of high-speed data valid for 7 days",
                duration=10080,  # 7 days in minutes
                data_limit=1024,  # 1GB in MB
                price=Decimal("3000.00"),
                currency="TZS",
                is_active=True
            ),
            Package(
                id="data_500mb",
                name="500MB Data Pack",
                description="500MB of data perfect for essential browsing",
                duration=4320,  # 3 days in minutes
                data_limit=500,  # 500MB
                price=Decimal("1500.00"),
                currency="TZS",
                is_active=True
            )
        ]

        for package in packages:
            db.add(package)
        
        db.commit()
        
        print(f"SUCCESS: Successfully created {len(packages)} sample packages:")
        for package in packages:
            data_info = f" ({package.data_limit}MB)" if package.data_limit else " (Unlimited)"
            print(f"  - {package.name}: {package.currency} {package.price} - {package.duration}min{data_info}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Error seeding packages: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def main():
    """Main setup function"""
    print("Wi-Fi Voucher System Database Setup")
    print("=" * 50)
    
    # Step 0: Check environment
    if not check_environment():
        print("ERROR: Environment check failed")
        sys.exit(1)
    
    # Step 1: Run migrations
    if not run_alembic_upgrade():
        print("ERROR: Database setup failed at migration step")
        sys.exit(1)
    
    # Step 2: Seed sample data
    if not seed_packages():
        print("ERROR: Database setup failed at seeding step")
        sys.exit(1)
    
    print("\nSUCCESS: Database setup completed successfully!")
    print("\nNext steps:")
    print("1. Run the application: python run.py")
    print("2. Access admin panel at: http://localhost:8000/admin/login")
    print("   - Username: admin")
    print("   - Password: admin123")
    print("3. Access user interface at: http://localhost:8000/")

if __name__ == "__main__":
    main()