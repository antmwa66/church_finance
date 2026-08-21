from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.password_hash = generate_password_hash('admin123')
        db.session.commit()
        print('Admin password reset to: admin123')
    else:
        print('Admin user not found')
