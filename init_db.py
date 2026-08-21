from app import app, db, User, PaymentCategory

with app.app_context():
    db.drop_all()
    db.create_all()
    
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        from werkzeug.security import generate_password_hash
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
    
    categories = ['Tithe', 'Mission', 'Bills', 'Church Construction', 'Offering', 'Donation']
    for cat_name in categories:
        existing = PaymentCategory.query.filter_by(name=cat_name).first()
        if not existing:
            category = PaymentCategory(name=cat_name, description=cat_name + ' payments')
            db.session.add(category)
    db.session.commit()
    print('Payment categories created')
    print('Categories:', [c.name for c in PaymentCategory.query.all()])
    print('Database initialized successfully')