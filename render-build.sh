#!/usr/bin/env python3
import os
import sys

# Set up the app context
os.environ.setdefault('SECRET_KEY', os.environ.get('SECRET_KEY', 'dev-insecure-secret-key'))
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 'sqlite:///church_finance.db'))
os.environ.setdefault('FLASK_DEBUG', 'false')

print("Starting database initialization...")
print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'not set')}")

from app import app, db, User, PaymentCategory
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create all tables
    try:
        db.create_all()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        try:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                full_name='System Administrator',
                email='admin@church.org',
                phone='0000000000'
            )
            db.session.add(admin)
            db.session.commit()
            print('Default admin created: username=admin, password=admin123')
        except Exception as e:
            print(f"Error creating admin user: {e}")
            db.session.rollback()
            sys.exit(1)
    else:
        print('Admin user already exists')
        # Reset password to ensure it's correct
        try:
            admin.password_hash = generate_password_hash('admin123')
            db.session.commit()
            print('Admin password reset to: admin123')
        except Exception as e:
            print(f"Error resetting admin password: {e}")
            db.session.rollback()
    
    # Create payment categories
    categories = ['Tithe', 'Mission', 'Bills', 'Church Construction', 'Offering', 'Donation']
    for cat_name in categories:
        existing = PaymentCategory.query.filter_by(name=cat_name).first()
        if not existing:
            try:
                category = PaymentCategory(name=cat_name, description=cat_name + ' payments')
                db.session.add(category)
            except Exception as e:
                print(f"Error creating category {cat_name}: {e}")
    try:
        db.session.commit()
        print('Payment categories created')
    except Exception as e:
        print(f"Error committing categories: {e}")
        db.session.rollback()
    
    print('Database initialized successfully')
    
    # Verify admin user exists
    admin_check = User.query.filter_by(username='admin').first()
    if admin_check:
        print(f"Admin user verification: username={admin_check.username}, role={admin_check.role}")
    else:
        print("WARNING: Admin user not found after initialization!")
