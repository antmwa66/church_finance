from app import app, PaymentCategory

with app.app_context():
    categories = PaymentCategory.query.all()
    print('Categories:', [c.name for c in categories])
    print('Count:', len(categories))