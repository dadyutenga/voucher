"""
Database initialization script to create sample packages
Run this after database migration
"""

from app.database import SessionLocal
from app.models.models import Package
from decimal import Decimal

def create_sample_packages():
    db = SessionLocal()
    try:
        # Check if packages already exist
        existing_packages = db.query(Package).count()
        if existing_packages > 0:
            print(f"✅ Database already has {existing_packages} packages")
            return

        # Create sample packages
        packages = [
            Package(
                id="basic",
                name="Basic Access",
                description="Perfect for quick internet access",
                duration=60,  # 1 hour
                data_limit=None,  # Unlimited
                price=Decimal("1000.00"),  # TZS 1000
                currency="TZS",
                is_active=True
            ),
            Package(
                id="standard",
                name="Standard Access", 
                description="Great for browsing and social media",
                duration=180,  # 3 hours
                data_limit=None,  # Unlimited
                price=Decimal("2500.00"),  # TZS 2500
                currency="TZS",
                is_active=True
            ),
            Package(
                id="premium",
                name="Premium Access",
                description="All-day internet access",
                duration=720,  # 12 hours
                data_limit=None,  # Unlimited
                price=Decimal("5000.00"),  # TZS 5000
                currency="TZS",
                is_active=True
            ),
            Package(
                id="daily",
                name="Daily Pass",
                description="24 hours of unlimited internet",
                duration=1440,  # 24 hours
                data_limit=None,  # Unlimited
                price=Decimal("8000.00"),  # TZS 8000
                currency="TZS",
                is_active=True
            ),
            Package(
                id="data_1gb",
                name="1GB Data Pack",
                description="1GB of data valid for 7 days",
                duration=10080,  # 7 days in minutes
                data_limit=1024,  # 1GB in MB
                price=Decimal("3000.00"),  # TZS 3000
                currency="TZS",
                is_active=True
            ),
            Package(
                id="demo",
                name="Demo Access",
                description="Free 15-minute trial",
                duration=15,  # 15 minutes
                data_limit=None,  # Unlimited
                price=Decimal("0.00"),  # Free
                currency="TZS",
                is_active=True
            )
        ]

        for package in packages:
            db.add(package)
        
        db.commit()
        print(f"✅ Created {len(packages)} sample packages successfully!")
        
        for package in packages:
            print(f"  - {package.name}: {package.currency} {package.price} ({package.duration} min)")
        
    except Exception as e:
        print(f"❌ Error creating packages: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_packages()