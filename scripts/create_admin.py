"""Script to create an admin user for the E-Recruitment system."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User


def create_admin():
    """Create an admin user interactively."""
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("E-Recruitment Portal - Admin User Creation")
        print("=" * 50)
        
        # Get user input
        email = input("Enter admin email: ").strip()
        
        # Check if user exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"Error: User with email {email} already exists!")
            return
        
        first_name = input("Enter first name: ").strip()
        last_name = input("Enter last name: ").strip()
        password = input("Enter password: ").strip()
        
        if len(password) < 8:
            print("Error: Password must be at least 8 characters!")
            return
        
        # Create admin user
        admin = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='admin',
            is_active=True
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        print("\n" + "=" * 50)
        print("Admin user created successfully!")
        print(f"Email: {email}")
        print(f"Name: {first_name} {last_name}")
        print(f"Role: admin")
        print("=" * 50)


if __name__ == '__main__':
    create_admin()
