#!/usr/bin/env python3
"""
Database initialization script for PythonAnywhere
Run this once after deploying to set up the database
"""
import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, PaymentCategory
from werkzeug.security import generate_password_hash

def initialize_database():
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("Database tables created/verified")
            
            # Create admin user if it doesn't exist
            admin = User.query.filter_by(username='admin').first()
            if not admin:
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
            else:
                print('Admin user already exists')
            
            # Create payment categories
            categories = ['Tithe', 'Mission', 'Bills', 'Church Construction', 'Offering', 'Donation']
            for cat_name in categories:
                existing = PaymentCategory.query.filter_by(name=cat_name).first()
                if not existing:
                    category = PaymentCategory(name=cat_name, description=cat_name + ' payments')
                    db.session.add(category)
            db.session.commit()
            print('Payment categories initialized')
            print('Database initialization completed successfully!')
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            db.session.rollback()
            sys.exit(1)

if __name__ == '__main__':
    initialize_database()
