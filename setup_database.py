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
from dotenv import load_dotenv
from decimal import Decimal

# Load environment variables
load_dotenv()

def run_command(command, description):
    """Run a command and return success status"""
    print(f"Running: {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd="app")
        if result.returncode == 0:
            print(f"SUCCESS: {description}")
            if result.stdout.strip():
                print(f"STDOUT: {result.stdout}")
            return True
        else:
            print(f"ERROR: {description}")
            if result.stdout.strip():
                print(f"STDOUT: {result.stdout}")
            if result.stderr.strip():
                print(f"STDERR: {result.stderr}")
            return False
    except Exception as e:
        print(f"ERROR: {description} - {str(e)}")
        return False

def check_database_status():
    """Check if database exists and has tables"""
    try:
        from sqlalchemy import create_engine, text
        from app.core.config import settings
        
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            # Check which tables exist
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """))
            existing_tables = [row[0] for row in result.fetchall()]
            
            required_tables = ['accounts', 'packages', 'vouchers', 'transactions']
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            print(f"INFO: Found tables: {existing_tables}")
            
            if not existing_tables:
                print("INFO: No tables found in database")
                return "empty"
            elif missing_tables:
                print(f"INFO: Missing tables: {missing_tables}")
                return "partial"
            else:
                print("INFO: All required tables exist")
                return "complete"
                
    except Exception as e:
        print(f"INFO: Database connection failed: {str(e)}")
        return "missing"

def mark_database_as_migrated():
    """Mark the current database state as migrated"""
    print("Marking current database state as baseline...")
    return run_command(
        "alembic stamp b90d767a4c25", 
        "Mark database as migrated"
    )

def run_migration():
    """Run Alembic migrations"""
    print("Running database migrations...")
    return run_command(
        "alembic upgrade head",
        "Database migration"
    )

def reset_database():
    """Reset the database completely"""
    print("WARNING: This will delete all existing data!")
    response = input("Are you sure you want to reset the database? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Database reset cancelled.")
        return False
    
    try:
        from sqlalchemy import create_engine
        from app.core.config import settings
        from app.database import Base
        
        engine = create_engine(settings.DATABASE_URL)
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("SUCCESS: All tables dropped")
        
        print("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: All tables created")
        
        # Mark as migrated
        return run_command(
            "alembic stamp b90d767a4c25",
            "Mark database as migrated"
        )
        
    except Exception as e:
        print(f"ERROR: Database reset failed - {str(e)}")
        return False

def create_sample_data():
    """Create sample packages and admin user"""
    try:
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        from app.core.config import settings
        from app.models.models import Package, Account
        from app.utils import hash_password
        import uuid
        
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        print("Creating sample packages...")
        
        # Check if packages already exist (with try-catch for missing table)
        try:
            existing_count = db.query(Package).count()
            if existing_count > 0:
                print(f"INFO: Database already has {existing_count} packages - skipping package creation")
            else:
                create_packages = True
        except Exception:
            # Table doesn't exist or other error, try to create packages anyway
            create_packages = True
        
        if create_packages:
            # Create sample packages with correct field names
            packages = [
                Package(
                    id="demo",
                    name="Demo Access", 
                    description="Free 15-minute demo access",
                    price=Decimal("0.00"),
                    duration=15,  # 15 minutes
                    data_limit=None,  # Unlimited data
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="basic", 
                    name="Basic Access",
                    description="1 hour internet access", 
                    price=Decimal("1000.00"),
                    duration=60,  # 1 hour
                    data_limit=None,  # Unlimited data
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="standard",
                    name="Standard Access", 
                    description="3 hours internet access",
                    price=Decimal("2500.00"),
                    duration=180,  # 3 hours
                    data_limit=None,  # Unlimited data
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="premium",
                    name="Premium Access",
                    description="12 hours internet access", 
                    price=Decimal("5000.00"),
                    duration=720,  # 12 hours
                    data_limit=None,  # Unlimited data
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="daily",
                    name="Daily Pass", 
                    description="24 hours unlimited access",
                    price=Decimal("8000.00"),
                    duration=1440,  # 24 hours
                    data_limit=None,  # Unlimited data
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="data_1gb",
                    name="1GB Data Pack",
                    description="1GB of high-speed data valid for 7 days",
                    price=Decimal("3000.00"),
                    duration=10080,  # 7 days in minutes
                    data_limit=1024,  # 1GB in MB
                    currency="TZS",
                    is_active=True
                ),
                Package(
                    id="data_500mb",
                    name="500MB Data Pack",
                    description="500MB of data perfect for essential browsing",
                    price=Decimal("1500.00"),
                    duration=4320,  # 3 days in minutes
                    data_limit=500,  # 500MB
                    currency="TZS",
                    is_active=True
                )
            ]
            
            try:
                for package in packages:
                    db.add(package)
                    print(f"  + Added package: {package.name}")
                
                db.commit()
                print(f"SUCCESS: Created {len(packages)} sample packages")
            except Exception as e:
                print(f"ERROR: Failed to create packages - {str(e)}")
                db.rollback()
        
        # Create admin account
        print("Creating admin account...")
        admin_mobile = "+255712345678"  # Default admin mobile
        
        try:
            existing_admin = db.query(Account).filter(Account.mobile_number == admin_mobile).first()
            
            if not existing_admin:
                admin_account = Account(
                    id=uuid.uuid4(),
                    mobile_number=admin_mobile,
                    password_hash=hash_password("admin123"),
                    is_active=True
                )
                db.add(admin_account)
                db.commit()
                print(f"  + Created admin account: {admin_mobile}")
                print("  + Admin password: admin123")
            else:
                print(f"  - Admin account already exists: {admin_mobile}")
        except Exception as e:
            print(f"ERROR: Failed to create admin account - {str(e)}")
            db.rollback()
        
        db.close()
        print("SUCCESS: Sample data creation completed")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to create sample data - {str(e)}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

def main():
    print("Wi-Fi Voucher System Database Setup")
    print("==================================================")
    
    # Check environment
    print("Checking environment configuration...")
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        print("Please ensure your .env file is properly configured")
        return
    
    print("SUCCESS: Environment configured")
    print(f"Database URL: {database_url}")
    
    # Check database status
    db_status = check_database_status()
    
    if db_status == "complete":
        print("\nAll database tables exist. Choose an option:")
        print("1. Add sample data only (recommended)")
        print("2. Reset database completely (WARNING: deletes all data)")
        print("3. Exit without changes")
        
        choice = input("Enter your choice (1/2/3): ").strip()
        
        if choice == "1":
            if create_sample_data():
                print("\nSUCCESS: Sample data added!")
                print_next_steps()
            else:
                print("ERROR: Failed to add sample data")
                
        elif choice == "2":
            if reset_database():
                if create_sample_data():
                    print("\nSUCCESS: Database reset and setup complete!")
                    print_next_steps()
            else:
                print("ERROR: Failed to reset database")
                
        elif choice == "3":
            print("Setup cancelled.")
        else:
            print("Invalid choice. Setup cancelled.")
    
    elif db_status == "partial":
        print("\nSome database tables are missing. Choose an option:")
        print("1. Run migrations to create missing tables (recommended)")
        print("2. Reset database completely (WARNING: deletes all data)")
        print("3. Exit without changes")
        
        choice = input("Enter your choice (1/2/3): ").strip()
        
        if choice == "1":
            if run_migration():
                if create_sample_data():
                    print("\nSUCCESS: Database migration and setup complete!")
                    print_next_steps()
            else:
                print("ERROR: Migration failed")
                
        elif choice == "2":
            if reset_database():
                if create_sample_data():
                    print("\nSUCCESS: Database reset and setup complete!")
                    print_next_steps()
            else:
                print("ERROR: Failed to reset database")
                
        elif choice == "3":
            print("Setup cancelled.")
        else:
            print("Invalid choice. Setup cancelled.")
            
    elif db_status == "empty":
        print("Running migrations to create tables...")
        if run_migration():
            if create_sample_data():
                print("\nSUCCESS: Database setup complete!")
                print_next_steps()
        else:
            print("ERROR: Database setup failed at migration step")
            
    else:
        print("ERROR: Cannot connect to database")
        print("Please check your PostgreSQL server and .env configuration")

def print_next_steps():
    """Print next steps for the user"""
    print("\nNext steps:")
    print("1. Run the application: python run.py")
    print("2. Access admin at: http://localhost:8000/admin/login")
    print("   - Mobile: +255712345678")
    print("   - Password: admin123")
    print("3. Access user interface at: http://localhost:8000/")

if __name__ == "__main__":
    main()