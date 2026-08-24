from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
from io import BytesIO
import os
import re
import secrets
import smtplib
from email.message import EmailMessage
from sqlalchemy import text
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

app = Flask(__name__)

# Secret key: REQUIRED in production. Falls back to a dev key only when DEBUG is on.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-insecure-secret-key')

# Database: use DATABASE_URL if provided (e.g. Postgres in production), else local SQLite.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///church_finance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', '')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@church.org')

# Debug is OFF by default; enable only with FLASK_DEBUG=true (never in production).
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

RESET_TOKEN_TTL_HOURS = 1

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=True)
    sub_region_id = db.Column(db.Integer, db.ForeignKey('sub_region.id'), nullable=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(120), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    api_token = db.Column(db.String(120), unique=True, nullable=True)
    api_token_expiry = db.Column(db.DateTime, nullable=True)

    region = db.relationship('Region', backref='users', lazy=True, foreign_keys=[region_id])
    sub_region = db.relationship('SubRegion', backref='users', lazy=True, foreign_keys=[sub_region_id])
    church = db.relationship('Church', backref='users', lazy=True, foreign_keys=[church_id])
    created_by = db.relationship('User', backref='created_users', remote_side=[id], foreign_keys=[created_by_id], lazy=True)
    payments = db.relationship('Payment', backref='pastor', lazy=True)


class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', backref='regions', remote_side=[User.id], foreign_keys=[admin_id], lazy=True)
    sub_regions = db.relationship('SubRegion', backref='region', lazy=True, cascade='all, delete-orphan')


class SubRegion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    churches = db.relationship('Church', backref='sub_region', lazy=True, cascade='all, delete-orphan')


class Church(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sub_region_id = db.Column(db.Integer, db.ForeignKey('sub_region.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    payments = db.relationship('Payment', backref='church', lazy=True, cascade='all, delete-orphan')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    pastor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('payment_category.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    paybill_number = db.Column(db.String(20), nullable=False)
    receipt_reference = db.Column(db.String(100), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text)
    allocation_id = db.Column(db.Integer, db.ForeignKey('allocation.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('PaymentCategory', backref='payments', lazy=True)
    allocation = db.relationship('Allocation', backref='payments', lazy=True)


class PaymentCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Allocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False)  # region, sub_region, church
    target_id = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('payment_category.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('allocation.id'), nullable=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('PaymentCategory', backref='allocations', lazy=True)
    created_by = db.relationship('User', backref='allocations_made', lazy=True)
    parent = db.relationship('Allocation', remote_side=[id], backref='children', lazy=True)

    def target_name(self):
        if self.level == 'region':
            obj = Region.query.get(self.target_id)
        elif self.level == 'sub_region':
            obj = SubRegion.query.get(self.target_id)
        elif self.level == 'church':
            obj = Church.query.get(self.target_id)
        else:
            obj = None
        return obj.name if obj else '-'

    def cascaded_amount(self):
        total = db.session.query(db.func.sum(Allocation.amount)).filter(
            Allocation.parent_id == self.id).scalar()
        return float(total or 0.0)

    def remaining_amount(self):
        return self.amount - self.cascaded_amount()

    def _descendant_church_allocation_ids(self):
        if self.level == 'sub_region':
            church_ids = [c.id for c in Church.query.filter_by(sub_region_id=self.target_id).all()]
        elif self.level == 'region':
            sub_ids = [s.id for s in SubRegion.query.filter_by(region_id=self.target_id).all()]
            church_ids = [c.id for c in Church.query.filter(Church.sub_region_id.in_(sub_ids)).all()]
        else:
            return []
        if not church_ids:
            return []
        return [a.id for a in Allocation.query.filter(
            Allocation.level == 'church', Allocation.target_id.in_(church_ids)).all()]

    def paid_amount(self):
        if self.level == 'church':
            total = db.session.query(db.func.sum(Payment.amount)).filter(
                Payment.allocation_id == self.id).scalar()
            return float(total or 0.0)
        child_ids = self._descendant_church_allocation_ids()
        if not child_ids:
            return 0.0
        total = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.allocation_id.in_(child_ids)).scalar()
        return float(total or 0.0)

    def balance(self):
        return self.amount - self.paid_amount()


def region_paid_amount(region_id):
    sub_ids = [s.id for s in SubRegion.query.filter_by(region_id=region_id).all()]
    if not sub_ids:
        return 0.0
    church_ids = [c.id for c in Church.query.filter(Church.sub_region_id.in_(sub_ids)).all()]
    if not church_ids:
        return 0.0
    child_ids = [a.id for a in Allocation.query.filter(
        Allocation.level == 'church', Allocation.target_id.in_(church_ids)).all()]
    if not child_ids:
        return 0.0
    total = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.allocation_id.in_(child_ids)).scalar()
    return float(total or 0.0)


EXCLUDED_ALLOCATION_CATEGORIES = {'tithe', 'tithes', 'offering', 'offerings'}


def allocatable_categories():
    return [c for c in PaymentCategory.query.filter_by(is_active=True).all()
            if c.name.strip().lower() not in EXCLUDED_ALLOCATION_CATEGORIES]


def link_payment_to_allocation(payment, church_id, category_id, amount):
    church_allocations = Allocation.query.filter_by(
        level='church', target_id=church_id, category_id=category_id).all()
    if not church_allocations:
        return None
    chosen = None
    for ca in church_allocations:
        if ca.balance() > 1e-9:
            chosen = ca
            break
    if chosen is None:
        chosen = church_allocations[0]
    payment.allocation_id = chosen.id
    db.session.commit()
    return chosen


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if user is None or user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


ACCOUNT_CATEGORY_MAP = {
    '4378': 'Mission',
    '1958': 'Bills',
    '6248': 'Church Construction',
    '7163': 'Tithe',
    '1111': 'Offering',
    '2222': 'Donation',
    # Add more account suffix to category mappings as needed
    # Format: 'last_4_digits': 'Category Name'
}


def detect_category(account_number):
    if not account_number:
        return None
    for suffix, name in ACCOUNT_CATEGORY_MAP.items():
        if account_number.endswith(suffix):
            return name
    return None


def parse_mpesa_message(message):
    message = message.strip()
    result = {
        'transaction_code': None,
        'amount': None,
        'sender_name': None,
        'sender_phone': None,
        'account_number': None,
        'category': None,
        'payment_date': None,
        'payment_time': None,
        'paybill_number': None,
        'payment_method': None,
        'raw_message': message
    }

    # Extract amount - handle both "Ksh" and "KES" formats
    amount_match = re.search(r'K(?:sh|ES)\s+([\d,]+\.\d{2})', message, re.IGNORECASE)
    if amount_match:
        result['amount'] = float(amount_match.group(1).replace(',', ''))

    # Extract paybill number
    paybill_match = re.search(r'Pay\s*(?:Bill|bill)\s+(\d+)', message, re.IGNORECASE)
    if paybill_match:
        result['paybill_number'] = paybill_match.group(1)

    # Extract account number and get last 4 digits for category detection
    # Handle format like "131***4378" or just plain numbers
    acc_match = re.search(r'account\s+(\d+\*{3}\d{4}|\d+)', message, re.IGNORECASE)
    if acc_match:
        account_full = acc_match.group(1)
        # Extract last 4 digits from account number
        if '*' in account_full:
            account_suffix = account_full[-4:]
        else:
            account_suffix = account_full[-4:] if len(account_full) >= 4 else account_full
        result['account_number'] = account_full
        result['category'] = detect_category(account_suffix)

    # Extract transaction code (M-PESA ref) - more specific pattern
    trans_match = re.search(r'M-PESA\s+ref\s+([A-Z0-9]{8,12})', message, re.IGNORECASE)
    if trans_match:
        result['transaction_code'] = trans_match.group(1)
    else:
        # Fallback: look for code that appears after "ref" or at end of message
        trans_match = re.search(r'ref\s+([A-Z0-9]{8,12})', message, re.IGNORECASE)
        if trans_match:
            result['transaction_code'] = trans_match.group(1)
        else:
            # Last resort: look for typical M-PESA transaction code pattern
            trans_match = re.search(r'\b([A-Z0-9]{8,12})\b', message)
            if trans_match:
                result['transaction_code'] = trans_match.group(1)

    # Extract date and time
    dt_match = re.search(
        r'on\s+(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)',
        message, re.IGNORECASE)
    if dt_match:
        day, month, year, time_part = dt_match.groups()
        year = '20' + year if len(year) == 2 else year
        result['payment_date'] = '{:04d}-{:02d}-{:02d}'.format(int(year), int(month), int(day))
        result['payment_time'] = time_part.strip()

    # Extract sender name (if available)
    sender_match = re.search(r'from\s+([A-Z][A-Z\s]+?)\s*-\s*(\d{3}\*{3}\d{3}|\d{10,12})', message)
    if sender_match:
        result['sender_name'] = sender_match.group(1).strip()
        result['sender_phone'] = sender_match.group(2)

    # Extract payment method
    method_match = re.search(r'via\s+([A-Z][A-Za-z\s]+?)(?:\.|$)', message)
    if method_match:
        result['payment_method'] = method_match.group(1).strip()

    return result


def send_reset_email(user, reset_url):
    mail_server = app.config.get('MAIL_SERVER')
    if not mail_server or not user.email:
        return False
    msg = EmailMessage()
    msg['Subject'] = 'Church Finance - Password Reset'
    msg['From'] = app.config.get('MAIL_DEFAULT_SENDER', 'noreply@church.org')
    msg['To'] = user.email
    msg.set_content(
        'Hello {},\n\nA password reset was requested for your Church Finance account.\n\n'
        'Click the link below to reset your password. This link expires in {} hour(s):\n\n{}\n\n'
        'If you did not request this, you can safely ignore this email.\n\n'
        'Church Finance Team'.format(user.full_name, RESET_TOKEN_TTL_HOURS, reset_url)
    )
    try:
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config.get('MAIL_PORT', 587), timeout=10) as server:
            if app.config.get('MAIL_USE_TLS'):
                server.starttls()
            username = app.config.get('MAIL_USERNAME')
            password = app.config.get('MAIL_PASSWORD')
            if username and password:
                server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as e:
        app.logger.error('Failed to send reset email to %s: %s', user.email, e)
        return False


def migrate_db():
    with app.app_context():
        inspector = db.inspect(db.engine)
        user_cols = [c['name'] for c in inspector.get_columns('user')]
        payment_cols = [c['name'] for c in inspector.get_columns('payment')]
        subregion_cols = [c['name'] for c in inspector.get_columns('sub_region')]
        church_cols = [c['name'] for c in inspector.get_columns('church')]
        with db.engine.begin() as conn:
            if 'reset_token' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN reset_token VARCHAR(120)'))
            if 'reset_token_expiry' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN reset_token_expiry DATETIME'))
            if 'allocation_id' not in payment_cols:
                conn.execute(text('ALTER TABLE "payment" ADD COLUMN allocation_id INTEGER'))
            if 'is_active' not in subregion_cols:
                conn.execute(text('ALTER TABLE sub_region ADD COLUMN is_active BOOLEAN DEFAULT TRUE'))
            if 'is_active' not in church_cols:
                conn.execute(text('ALTER TABLE church ADD COLUMN is_active BOOLEAN DEFAULT TRUE'))
            if 'api_token' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN api_token VARCHAR(120)'))
            if 'api_token_expiry' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN api_token_expiry DATETIME'))


@app.route('/api/parse-mpesa-message', methods=['POST'])
def api_parse_mpesa_message():
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    parsed = parse_mpesa_message(message)
    print(f"API parsed result: {parsed}")  # Debug logging
    return jsonify(parsed)


def api_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'Authorization token required'}), 401
        user = User.query.filter_by(api_token=token).first()
        if not user or not user.api_token_expiry or user.api_token_expiry < datetime.utcnow() or not user.is_active:
            return jsonify({'error': 'Invalid or expired token'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated_function


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password) and user.is_active:
        token = secrets.token_urlsafe(32)
        user.api_token = token
        user.api_token_expiry = datetime.utcnow() + timedelta(days=30)
        db.session.commit()
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'role': user.role,
                'email': user.email,
                'phone': user.phone,
                'region_id': user.region_id,
                'sub_region_id': user.sub_region_id,
                'church_id': user.church_id,
            }
        })
    return jsonify({'error': 'Invalid username or password'}), 401


@app.route('/api/logout', methods=['POST'])
@api_auth_required
def api_logout():
    user = request.current_user
    user.api_token = None
    user.api_token_expiry = None
    db.session.commit()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/me')
@api_auth_required
def api_me():
    user = request.current_user
    region = Region.query.get(user.region_id) if user.region_id else None
    sub_region = SubRegion.query.get(user.sub_region_id) if user.sub_region_id else None
    church = Church.query.get(user.church_id) if user.church_id else None
    return jsonify({
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'role': user.role,
        'email': user.email,
        'phone': user.phone,
        'region_id': user.region_id,
        'region_name': region.name if region else None,
        'sub_region_id': user.sub_region_id,
        'sub_region_name': sub_region.name if sub_region else None,
        'church_id': user.church_id,
        'church_name': church.name if church else None,
        'is_active': user.is_active,
    })


@app.route('/api/dashboard')
@api_auth_required
def api_dashboard():
    user = request.current_user
    role = user.role
    payload = {'role': role}

    if role == 'admin':
        payload['stats'] = {
            'regions': Region.query.count(),
            'regional_bishops': User.query.filter_by(role='regional_bishop').count(),
            'sub_region_bishops': User.query.filter_by(role='sub_region_bishop').count(),
            'local_pastors': User.query.filter_by(role='local_pastor').count(),
            'payments': Payment.query.count(),
            'total_amount': float(db.session.query(db.func.sum(Payment.amount)).scalar() or 0),
        }
    elif role == 'regional_bishop':
        region = Region.query.get(user.region_id) if user.region_id else None
        sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all() if user.region_id else []
        sub_bishops = User.query.filter_by(role='sub_region_bishop', region_id=user.region_id).all()
        pastors = User.query.filter_by(role='local_pastor').join(Church).join(SubRegion).filter(
            SubRegion.region_id == user.region_id
        ).all()
        total_payments = Payment.query.join(Church).join(SubRegion).filter(
            SubRegion.region_id == user.region_id
        ).count()
        total_amount = float(db.session.query(db.func.sum(Payment.amount)).join(Church).join(SubRegion).filter(
            SubRegion.region_id == user.region_id
        ).scalar() or 0)
        payload['stats'] = {
            'region_name': region.name if region else None,
            'sub_regions': len(sub_regions),
            'sub_bishops': len(sub_bishops),
            'pastors': len(pastors),
            'payments': total_payments,
            'total_amount': total_amount,
        }
    elif role == 'sub_region_bishop':
        sub_region = SubRegion.query.get(user.sub_region_id) if user.sub_region_id else None
        churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
        pastors = User.query.filter_by(role='local_pastor', sub_region_id=user.sub_region_id).all()
        total_payments = Payment.query.filter(Payment.pastor_id.in_([p.id for p in pastors])).count() if pastors else 0
        total_amount = float(db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.pastor_id.in_([p.id for p in pastors])
        ).scalar() or 0)
        payload['stats'] = {
            'sub_region_name': sub_region.name if sub_region else None,
            'churches': len(churches),
            'pastors': len(pastors),
            'payments': total_payments,
            'total_amount': total_amount,
        }
    elif role == 'local_pastor':
        church = Church.query.get(user.church_id) if user.church_id else None
        sub_region = SubRegion.query.get(church.sub_region_id) if church and church.sub_region_id else None
        region = Region.query.get(sub_region.region_id) if sub_region and sub_region.region_id else None
        my_payments = Payment.query.filter_by(pastor_id=user.id).all()
        my_total = float(db.session.query(db.func.sum(Payment.amount)).filter_by(pastor_id=user.id).scalar() or 0)
        payload['stats'] = {
            'church_name': church.name if church else None,
            'sub_region_name': sub_region.name if sub_region else None,
            'region_name': region.name if region else None,
            'my_payments': len(my_payments),
            'my_total': my_total,
        }

    return jsonify(payload)


@app.route('/api/sub_regions')
@api_auth_required
def api_sub_regions():
    user = request.current_user
    role = user.role
    if role == 'regional_bishop':
        sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all()
    elif role == 'sub_region_bishop':
        sub_regions = SubRegion.query.filter_by(id=user.sub_region_id).all()
    else:
        sub_regions = []
    return jsonify([{'id': sr.id, 'name': sr.name, 'region_id': sr.region_id, 'is_active': sr.is_active} for sr in sub_regions])


@app.route('/api/sub_regions', methods=['POST'])
@api_auth_required
def api_create_sub_region():
    user = request.current_user
    if user.role not in ['regional_bishop', 'admin']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    region_id = data.get('region_id', user.region_id)
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    sub_region = SubRegion(name=name, region_id=region_id)
    db.session.add(sub_region)
    db.session.commit()
    return jsonify({'id': sub_region.id, 'name': sub_region.name, 'region_id': sub_region.region_id}), 201


@app.route('/api/sub_regions/<int:subregion_id>', methods=['PUT'])
@api_auth_required
def api_update_sub_region(subregion_id):
    user = request.current_user
    sub_region = SubRegion.query.get_or_404(subregion_id)
    if user.role == 'regional_bishop' and sub_region.region_id != user.region_id:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if name:
        sub_region.name = name
    if 'is_active' in data and user.role in ['admin', 'regional_bishop']:
        sub_region.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify({'id': sub_region.id, 'name': sub_region.name, 'is_active': sub_region.is_active})


@app.route('/api/sub_regions/<int:subregion_id>', methods=['DELETE'])
@api_auth_required
def api_delete_sub_region(subregion_id):
    user = request.current_user
    sub_region = SubRegion.query.get_or_404(subregion_id)
    if user.role == 'regional_bishop' and sub_region.region_id != user.region_id:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(sub_region)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


@app.route('/api/churches')
@api_auth_required
def api_churches():
    user = request.current_user
    role = user.role
    if role == 'regional_bishop':
        churches = Church.query.join(SubRegion).filter(SubRegion.region_id == user.region_id).all()
    elif role == 'sub_region_bishop':
        churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all()
    elif role == 'local_pastor':
        churches = Church.query.filter_by(id=user.church_id).all()
    else:
        churches = []
    return jsonify([{'id': c.id, 'name': c.name, 'sub_region_id': c.sub_region_id, 'is_active': c.is_active} for c in churches])


@app.route('/api/churches', methods=['POST'])
@api_auth_required
def api_create_church():
    user = request.current_user
    if user.role not in ['sub_region_bishop', 'admin', 'regional_bishop']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    sub_region_id = data.get('sub_region_id', user.sub_region_id)
    if not name or not sub_region_id:
        return jsonify({'error': 'Name and sub_region_id are required'}), 400
    church = Church(name=name, sub_region_id=sub_region_id)
    db.session.add(church)
    db.session.commit()
    return jsonify({'id': church.id, 'name': church.name, 'sub_region_id': church.sub_region_id}), 201


@app.route('/api/churches/<int:church_id>', methods=['PUT'])
@api_auth_required
def api_update_church(church_id):
    user = request.current_user
    church = Church.query.get_or_404(church_id)
    if user.role == 'sub_region_bishop' and church.sub_region_id != user.sub_region_id:
        return jsonify({'error': 'Forbidden'}), 403
    if user.role == 'regional_bishop':
        sub_region = SubRegion.query.get(church.sub_region_id)
        if not sub_region or sub_region.region_id != user.region_id:
            return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if name:
        church.name = name
    if 'is_active' in data and user.role in ['admin', 'regional_bishop', 'sub_region_bishop']:
        church.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify({'id': church.id, 'name': church.name, 'is_active': church.is_active})


@app.route('/api/churches/<int:church_id>', methods=['DELETE'])
@api_auth_required
def api_delete_church(church_id):
    user = request.current_user
    church = Church.query.get_or_404(church_id)
    if user.role == 'sub_region_bishop' and church.sub_region_id != user.sub_region_id:
        return jsonify({'error': 'Forbidden'}), 403
    if user.role == 'regional_bishop':
        sub_region = SubRegion.query.get(church.sub_region_id)
        if not sub_region or sub_region.region_id != user.region_id:
            return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(church)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


@app.route('/api/pastors')
@api_auth_required
def api_pastors():
    user = request.current_user
    role = user.role
    if role == 'regional_bishop':
        pastors = User.query.filter_by(role='local_pastor').join(Church).join(SubRegion).filter(
            SubRegion.region_id == user.region_id
        ).all()
    elif role == 'sub_region_bishop':
        pastors = User.query.filter_by(role='local_pastor', sub_region_id=user.sub_region_id).all()
    elif role == 'local_pastor':
        pastors = User.query.filter_by(id=user.id).all()
    else:
        pastors = []
    return jsonify([{
        'id': p.id,
        'full_name': p.full_name,
        'email': p.email,
        'phone': p.phone,
        'church_id': p.church_id,
        'church_name': p.church.name if p.church else None,
        'sub_region_id': p.sub_region_id,
        'is_active': p.is_active,
    } for p in pastors])


@app.route('/api/pastors', methods=['POST'])
@api_auth_required
def api_create_pastor():
    user = request.current_user
    if user.role not in ['sub_region_bishop', 'admin', 'regional_bishop']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    church_id = data.get('church_id')
    sub_region_id = data.get('sub_region_id', user.sub_region_id)
    region_id = data.get('region_id', user.region_id)
    if not all([full_name, username, password, church_id]):
        return jsonify({'error': 'full_name, username, password and church_id are required'}), 400
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'error': 'Username already exists'}), 400
    pastor = User(
        username=username,
        password_hash=generate_password_hash(password),
        role='local_pastor',
        full_name=full_name,
        email=email,
        phone=phone,
        region_id=region_id,
        sub_region_id=sub_region_id,
        church_id=church_id,
        created_by_id=user.id,
    )
    db.session.add(pastor)
    db.session.commit()
    return jsonify({'id': pastor.id, 'full_name': pastor.full_name, 'username': pastor.username}), 201


@app.route('/api/pastors/<int:pastor_id>', methods=['PUT'])
@api_auth_required
def api_update_pastor(pastor_id):
    user = request.current_user
    pastor = User.query.get_or_404(pastor_id)
    if pastor.role != 'local_pastor':
        return jsonify({'error': 'Not a pastor'}), 400
    if user.role == 'sub_region_bishop' and pastor.sub_region_id != user.sub_region_id:
        return jsonify({'error': 'Forbidden'}), 403
    if user.role == 'regional_bishop':
        sub_region = SubRegion.query.get(pastor.sub_region_id)
        if not sub_region or sub_region.region_id != user.region_id:
            return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    pastor.full_name = data.get('full_name', pastor.full_name).strip()
    pastor.email = data.get('email', pastor.email).strip()
    pastor.phone = data.get('phone', pastor.phone).strip()
    if 'church_id' in data:
        pastor.church_id = data['church_id']
    if 'is_active' in data and user.role in ['admin', 'regional_bishop', 'sub_region_bishop']:
        pastor.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify({'id': pastor.id, 'full_name': pastor.full_name, 'email': pastor.email, 'phone': pastor.phone, 'church_id': pastor.church_id, 'is_active': pastor.is_active})


@app.route('/api/pastors/<int:pastor_id>', methods=['DELETE'])
@api_auth_required
def api_delete_pastor(pastor_id):
    user = request.current_user
    pastor = User.query.get_or_404(pastor_id)
    if pastor.role != 'local_pastor':
        return jsonify({'error': 'Not a pastor'}), 400
    if user.role == 'sub_region_bishop' and pastor.sub_region_id != user.sub_region_id:
        return jsonify({'error': 'Forbidden'}), 403
    if user.role == 'regional_bishop':
        sub_region = SubRegion.query.get(pastor.sub_region_id)
        if not sub_region or sub_region.region_id != user.region_id:
            return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(pastor)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


@app.route('/api/payments', methods=['POST'])
@api_auth_required
def api_create_payment():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    church_id = data.get('church_id')
    category_id = data.get('category_id')
    amount = data.get('amount')
    paybill_number = data.get('paybill_number', '').strip()
    receipt_reference = data.get('receipt_reference', '').strip()
    payment_date_str = data.get('payment_date')
    notes = data.get('notes', '').strip()
    if not all([church_id, category_id, amount, paybill_number, receipt_reference]):
        return jsonify({'error': 'church_id, category_id, amount, paybill_number and receipt_reference are required'}), 400
    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': 'Amount must be a positive number'}), 400
    payment_date = date.today()
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400
    payment = Payment(
        church_id=church_id,
        pastor_id=user.id,
        category_id=category_id,
        amount=amount_val,
        paybill_number=paybill_number,
        receipt_reference=receipt_reference,
        payment_date=payment_date,
        notes=notes,
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({'id': payment.id, 'amount': payment.amount, 'payment_date': payment.payment_date.isoformat()}), 201


@app.route('/api/payments')
@api_auth_required
def api_payments():
    user = request.current_user
    role = user.role
    query = Payment.query
    if role == 'regional_bishop':
        query = query.join(Church).join(SubRegion).filter(SubRegion.region_id == user.region_id)
    elif role == 'sub_region_bishop':
        query = query.join(Church).filter(Church.sub_region_id == user.sub_region_id)
    elif role == 'local_pastor':
        query = query.filter_by(pastor_id=user.id)
    payments = query.order_by(Payment.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'amount': p.amount,
        'paybill_number': p.paybill_number,
        'receipt_reference': p.receipt_reference,
        'payment_date': p.payment_date.isoformat(),
        'notes': p.notes,
        'church_id': p.church_id,
        'church_name': p.church.name if p.church else None,
        'category_id': p.category_id,
        'category_name': p.category.name if p.category else None,
        'pastor_id': p.pastor_id,
        'pastor_name': p.pastor.full_name if p.pastor else None,
    } for p in payments])


@app.route('/api/reports/regions')
@api_auth_required
def api_reports_regions():
    user = request.current_user
    if user.role not in ['admin', 'regional_bishop']:
        return jsonify({'error': 'Forbidden'}), 403
    category_id = request.args.get('category_id', type=int)
    if user.role == 'regional_bishop':
        regions = Region.query.filter_by(id=user.region_id).all()
    else:
        regions = Region.query.all()
    result = []
    for region in regions:
        sub_regions = SubRegion.query.filter_by(region_id=region.id).all()
        for sub_region in sub_regions:
            if category_id:
                allocation = db.session.query(db.func.sum(Allocation.amount)).filter(
                    Allocation.level == 'sub_region', Allocation.target_id == sub_region.id,
                    Allocation.category_id == category_id
                ).scalar() or 0
                church_ids = [c.id for c in Church.query.filter_by(sub_region_id=sub_region.id).all()]
                contributed = 0
                if church_ids:
                    alloc_ids = [a.id for a in Allocation.query.filter(
                        Allocation.level == 'church', Allocation.target_id.in_(church_ids),
                        Allocation.category_id == category_id
                    ).all()]
                    if alloc_ids:
                        contributed = db.session.query(db.func.sum(Payment.amount)).filter(
                            Payment.allocation_id.in_(alloc_ids), Payment.category_id == category_id
                        ).scalar() or 0
            else:
                allocation = db.session.query(db.func.sum(Allocation.amount)).filter(
                    Allocation.level == 'sub_region', Allocation.target_id == sub_region.id
                ).scalar() or 0
                church_ids = [c.id for c in Church.query.filter_by(sub_region_id=sub_region.id).all()]
                contributed = 0
                if church_ids:
                    alloc_ids = [a.id for a in Allocation.query.filter(
                        Allocation.level == 'church', Allocation.target_id.in_(church_ids)
                    ).all()]
                    if alloc_ids:
                        contributed = db.session.query(db.func.sum(Payment.amount)).filter(
                            Payment.allocation_id.in_(alloc_ids)
                        ).scalar() or 0
            result.append({
                'region_name': region.name,
                'sub_region_name': sub_region.name,
                'allocation': float(allocation),
                'contributed': float(contributed),
                'balance': float(allocation) - float(contributed),
                'percentage': float(contributed) / float(allocation) * 100 if allocation else 0,
            })
    result.sort(key=lambda x: x['percentage'], reverse=True)
    return jsonify(result)


@app.route('/api/categories')
@api_auth_required
def api_categories():
    categories = PaymentCategory.query.order_by(PaymentCategory.name).all()
    return jsonify([{'id': c.id, 'name': c.name, 'description': c.description, 'is_active': c.is_active} for c in categories])


@app.route('/api/profile', methods=['PUT'])
@api_auth_required
def api_update_profile():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    user.full_name = data.get('full_name', user.full_name).strip()
    user.email = data.get('email', user.email).strip()
    user.phone = data.get('phone', user.phone).strip()
    db.session.commit()
    return jsonify({'full_name': user.full_name, 'email': user.email, 'phone': user.phone})


@app.route('/api/profile/password', methods=['POST'])
@api_auth_required
def api_change_password():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    if not current_password or not new_password or not confirm_password:
        return jsonify({'error': 'All fields are required'}), 400
    if not check_password_hash(user.password_hash, current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400
    if new_password != confirm_password:
        return jsonify({'error': 'New passwords do not match'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({'message': 'Password changed successfully'})


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            session['full_name'] = user.full_name
            flash('Welcome back, {}!'.format(user.full_name), 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()
        if user and user.is_active:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=RESET_TOKEN_TTL_HOURS)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            if not send_reset_email(user, reset_url):
                flash('No email server is configured, so your reset link is: {}'.format(reset_url), 'info')
        flash('If an account matches that username or email, password reset instructions have been sent.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not password or password != confirm_password:
            flash('Passwords must match and cannot be empty.', 'danger')
            return render_template('reset_password.html', token=token)
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('reset_password.html', token=token)
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Your password has been reset. Please log in with your new password.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_password or not new_password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('change_password'))

        if not check_password_hash(user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('change_password'))

        if len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'danger')
            return redirect(url_for('change_password'))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user.role == 'regional_bishop':
        return redirect(url_for('regional_dashboard'))
    elif user.role == 'sub_region_bishop':
        return redirect(url_for('subregion_dashboard'))
    elif user.role == 'local_pastor':
        return redirect(url_for('pastor_dashboard'))
    return render_template('dashboard.html', user=user)


# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    total_regions = Region.query.count()
    total_bishops = User.query.filter_by(role='regional_bishop').count()
    total_sub_bishops = User.query.filter_by(role='sub_region_bishop').count()
    total_pastors = User.query.filter_by(role='local_pastor').count()
    total_categories = PaymentCategory.query.count()
    total_payments = Payment.query.count()
    total_amount = db.session.query(db.func.sum(Payment.amount)).scalar() or 0.0
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_regions=total_regions,
                           total_bishops=total_bishops,
                           total_sub_bishops=total_sub_bishops,
                           total_pastors=total_pastors,
                           total_categories=total_categories,
                           total_payments=total_payments,
                           total_amount=total_amount,
                           recent_payments=recent_payments)


@app.route('/admin/categories')
@login_required
@role_required('admin')
def admin_categories():
    categories = PaymentCategory.query.order_by(PaymentCategory.created_at.desc()).all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/create_category', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Category name is required.', 'danger')
            return redirect(url_for('admin_create_category'))
        category = PaymentCategory(name=name, description=description)
        db.session.add(category)
        db.session.commit()
        flash('Payment category "{}" created successfully.'.format(name), 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/create_category.html')


@app.route('/admin/toggle_category/<int:category_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_category(category_id):
    category = PaymentCategory.query.get_or_404(category_id)
    category.is_active = not category.is_active
    db.session.commit()
    status = 'activated' if category.is_active else 'deactivated'
    flash('Category "{}" has been {}.'.format(category.name, status), 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/allocations')
@login_required
@role_required('admin')
def admin_allocations():
    allocations = Allocation.query.order_by(Allocation.created_at.desc()).all()
    regions = Region.query.order_by(Region.name).all()
    categories = allocatable_categories()

    region_totals = {}
    region_paid = {}
    for region in regions:
        total = db.session.query(db.func.sum(Allocation.amount)).filter(
            Allocation.level == 'region', Allocation.target_id == region.id).scalar()
        region_totals[region.id] = float(total or 0.0)
        region_paid[region.id] = region_paid_amount(region.id)
    grand_total = sum(region_totals.values())
    grand_paid = sum(region_paid.values())

    return render_template('admin/allocations.html',
                           allocations=allocations, regions=regions, categories=categories,
                           region_totals=region_totals, region_paid=region_paid,
                           grand_total=grand_total, grand_paid=grand_paid)


@app.route('/admin/create_allocation', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_allocation():
    category_id = request.form.get('category_id')
    description = request.form.get('description', '').strip()
    category = PaymentCategory.query.get(category_id) if category_id else None
    if not category or category.name.strip().lower() in EXCLUDED_ALLOCATION_CATEGORIES:
        flash('Please select a valid allocation category. Tithe and Offering are not allowed.', 'danger')
        return redirect(url_for('admin_allocations'))

    created = 0
    for region in Region.query.order_by(Region.name).all():
        val = request.form.get('amount_{}'.format(region.id), '').strip()
        if not val:
            continue
        try:
            amount_val = float(val)
        except ValueError:
            flash('Invalid amount for {}.'.format(region.name), 'danger')
            return redirect(url_for('admin_allocations'))
        if amount_val <= 0:
            continue
        db.session.add(Allocation(
            level='region', target_id=region.id, category_id=category.id,
            amount=amount_val, created_by_id=session['user_id'], description=description))
        created += 1
    db.session.commit()
    if created:
        flash('Allocation created for {} region(s) in category "{}".'.format(created, category.name), 'success')
    else:
        flash('No allocation amounts were entered.', 'warning')
    return redirect(url_for('admin_allocations'))


@app.route('/admin/create_region', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_region():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Region name is required.', 'danger')
            return redirect(url_for('admin_create_region'))
        existing = Region.query.filter(db.func.lower(Region.name) == name.lower()).first()
        if existing:
            flash('A region with this name already exists.', 'danger')
            return redirect(url_for('admin_create_region'))
        region = Region(name=name, admin_id=session['user_id'])
        db.session.add(region)
        db.session.commit()
        flash('Region "{}" created successfully.'.format(name), 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/create_region.html')


@app.route('/admin/create_bishop', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_bishop():
    regions = Region.query.all()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        region_id = request.form.get('region_id')

        if not all([username, password, full_name, region_id]):
            flash('Username, password, full name, and region are required.', 'danger')
            return redirect(url_for('admin_create_bishop'))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.', 'danger')
            return redirect(url_for('admin_create_bishop'))

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='regional_bishop',
            full_name=full_name,
            email=email,
            phone=phone,
            region_id=region_id,
            created_by_id=session['user_id']
        )
        db.session.add(user)
        db.session.commit()
        flash('Regional Bishop "{}" created successfully.'.format(full_name), 'success')
        return redirect(url_for('admin_create_bishop'))
    return render_template('admin/create_bishop.html', regions=regions)


@app.route('/admin/manage_bishops')
@login_required
@role_required('admin')
def admin_manage_bishops():
    bishops = User.query.filter_by(role='regional_bishop').all()
    return render_template('admin/manage_bishops.html', bishops=bishops)


@app.route('/admin/transfer_bishop/<int:bishop_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_transfer_bishop(bishop_id):
    bishop = User.query.get_or_404(bishop_id)
    if bishop.role != 'regional_bishop':
        flash('Only regional bishops can be transferred.', 'danger')
        return redirect(url_for('admin_manage_bishops'))
    regions = Region.query.all()
    if request.method == 'POST':
        region_id = request.form.get('region_id')
        if not region_id:
            flash('Please select a region.', 'danger')
            return redirect(url_for('admin_transfer_bishop', bishop_id=bishop_id))
        bishop.region_id = region_id
        db.session.commit()
        flash('Bishop "{}" transferred successfully.'.format(bishop.full_name), 'success')
        return redirect(url_for('admin_manage_bishops'))
    return render_template('admin/transfer_bishop.html', bishop=bishop, regions=regions)


@app.route('/admin/manage_sub_bishops')
@login_required
@role_required('admin')
def admin_manage_sub_bishops():
    sub_bishops = User.query.filter_by(role='sub_region_bishop').all()
    return render_template('admin/manage_sub_bishops.html', sub_bishops=sub_bishops)


@app.route('/admin/manage_pastors')
@login_required
@role_required('admin')
def admin_manage_pastors():
    pastors = User.query.filter_by(role='local_pastor').all()
    return render_template('admin/manage_pastors.html', pastors=pastors)


@app.route('/admin/regions')
@login_required
@role_required('admin')
def admin_manage_regions():
    regions = Region.query.order_by(Region.created_at.desc()).all()
    return render_template('admin/manage_regions.html', regions=regions)


@app.route('/admin/edit_region/<int:region_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_region(region_id):
    region = Region.query.get_or_404(region_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Region name is required.', 'danger')
            return render_template('admin/edit_region.html', region=region)
        duplicate = Region.query.filter(
            Region.id != region.id, db.func.lower(Region.name) == name.lower()).first()
        if duplicate:
            flash('A region with this name already exists.', 'danger')
            return render_template('admin/edit_region.html', region=region)
        region.name = name
        db.session.commit()
        flash('Region "{}" updated successfully.'.format(name), 'success')
        return redirect(url_for('admin_manage_regions'))
    return render_template('admin/edit_region.html', region=region)


@app.route('/admin/delete_region/<int:region_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_region(region_id):
    region = Region.query.get_or_404(region_id)
    bishop = User.query.filter(
        User.region_id == region.id,
        User.role.in_(['regional_bishop', 'sub_region_bishop'])
    ).first()
    if bishop:
        flash('Cannot delete region "{}" because bishop {} is assigned to it.'.format(
            region.name, bishop.full_name), 'danger')
        return redirect(url_for('admin_manage_regions'))
    db.session.delete(region)
    db.session.commit()
    flash('Region "{}" deleted successfully.'.format(region.name), 'success')
    return redirect(url_for('admin_manage_regions'))


@app.route('/admin/payments')
@login_required
@role_required('admin')
def admin_payments():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).scalar() or 0.0
    return render_template('admin/payments.html', payments=payments, total_amount=total_amount)


@app.route('/admin/accumulative')
@login_required
@role_required('admin')
def admin_accumulative():
    region_totals = db.session.query(
        Region.name,
        db.func.sum(Payment.amount)
    ).join(SubRegion, Region.id == SubRegion.region_id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).group_by(Region.id).all()

    sub_region_totals = db.session.query(
        SubRegion.name,
        Region.name,
        db.func.sum(Payment.amount)
    ).join(Region, SubRegion.region_id == Region.id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).group_by(SubRegion.id).all()

    pastor_totals = db.session.query(
        User.full_name,
        SubRegion.name,
        Region.name,
        db.func.sum(Payment.amount)
    ).join(Payment, User.id == Payment.pastor_id
    ).join(Church, Payment.church_id == Church.id
    ).join(SubRegion, Church.sub_region_id == SubRegion.id
    ).join(Region, SubRegion.region_id == Region.id
    ).group_by(User.id).all()

    category_totals = db.session.query(
        PaymentCategory.id,
        PaymentCategory.name,
        db.func.sum(Payment.amount)
    ).join(Payment, PaymentCategory.id == Payment.category_id
    ).group_by(PaymentCategory.id).all()

    category_region_totals = db.session.query(
        Region.name,
        PaymentCategory.name,
        db.func.sum(Payment.amount)
    ).join(SubRegion, Region.id == SubRegion.region_id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).join(PaymentCategory, Payment.category_id == PaymentCategory.id
    ).group_by(Region.id, PaymentCategory.id).all()

    category_sub_region_totals = db.session.query(
        SubRegion.name,
        Region.name,
        PaymentCategory.name,
        db.func.sum(Payment.amount)
    ).join(Region, SubRegion.region_id == Region.id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).join(PaymentCategory, Payment.category_id == PaymentCategory.id
    ).group_by(SubRegion.id, PaymentCategory.id).all()

    grand_total = db.session.query(db.func.sum(Payment.amount)).scalar() or 0.0
    total_payments = Payment.query.count()

    return render_template('admin/accumulative.html',
                           region_totals=region_totals,
                           sub_region_totals=sub_region_totals,
                           pastor_totals=pastor_totals,
                           category_totals=category_totals,
                           category_region_totals=category_region_totals,
                           category_sub_region_totals=category_sub_region_totals,
                           grand_total=grand_total,
                           total_payments=total_payments)


@app.route('/admin/payments_by_category_detail/<int:category_id>')
@login_required
@role_required('admin')
def admin_payments_by_category_detail(category_id):
    category = PaymentCategory.query.get_or_404(category_id)
    region_breakdown = db.session.query(
        Region.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(SubRegion, Region.id == SubRegion.region_id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).filter(Payment.category_id == category_id
    ).group_by(Region.id).all()

    sub_region_breakdown = db.session.query(
        SubRegion.name,
        Region.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Region, SubRegion.region_id == Region.id
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).filter(Payment.category_id == category_id
    ).group_by(SubRegion.id).all()

    total_amount = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.category_id == category_id
    ).scalar() or 0.0
    return render_template('admin/payments_by_category_detail.html',
                           category=category,
                           region_breakdown=region_breakdown,
                           sub_region_breakdown=sub_region_breakdown,
                           total_amount=total_amount)


@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash('User "{}" has been {}.'.format(user.full_name, status), 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/regions_report')
@login_required
@role_required('admin')
def admin_regions_report():
    category_id = request.args.get('category_id', type=int)
    download = request.args.get('download')
    category = PaymentCategory.query.get(category_id) if category_id else None

    regions = Region.query.all()
    sub_region_data = []

    for region in regions:
        regional_bishop = User.query.filter_by(role='regional_bishop', region_id=region.id).first()
        regional_bishop_name = regional_bishop.full_name if regional_bishop else 'N/A'
        sub_regions = SubRegion.query.filter_by(region_id=region.id).all()

        for sub_region in sub_regions:
            sub_region_bishops = User.query.filter_by(role='sub_region_bishop', sub_region_id=sub_region.id).all()
            sub_region_bishop_name = sub_region_bishops[0].full_name if sub_region_bishops else 'N/A'

            if category_id:
                sub_region_allocation = db.session.query(db.func.sum(Allocation.amount)).filter(
                    Allocation.level == 'sub_region', Allocation.target_id == sub_region.id,
                    Allocation.category_id == category_id
                ).scalar() or 0
                sub_region_church_ids = [c.id for c in Church.query.filter_by(sub_region_id=sub_region.id).all()]
                sub_region_contributed = 0
                if sub_region_church_ids:
                    church_allocations = [a.id for a in Allocation.query.filter(
                        Allocation.level == 'church', Allocation.target_id.in_(sub_region_church_ids),
                        Allocation.category_id == category_id
                    ).all()]
                    if church_allocations:
                        sub_region_contributed = db.session.query(db.func.sum(Payment.amount)).filter(
                            Payment.allocation_id.in_(church_allocations),
                            Payment.category_id == category_id
                        ).scalar() or 0
            else:
                sub_region_allocation = db.session.query(db.func.sum(Allocation.amount)).filter(
                    Allocation.level == 'sub_region', Allocation.target_id == sub_region.id
                ).scalar() or 0
                sub_region_church_ids = [c.id for c in Church.query.filter_by(sub_region_id=sub_region.id).all()]
                sub_region_contributed = 0
                if sub_region_church_ids:
                    church_allocations = [a.id for a in Allocation.query.filter(
                        Allocation.level == 'church', Allocation.target_id.in_(sub_region_church_ids)
                    ).all()]
                    if church_allocations:
                        sub_region_contributed = db.session.query(db.func.sum(Payment.amount)).filter(
                            Payment.allocation_id.in_(church_allocations)
                        ).scalar() or 0

            balance = sub_region_allocation - sub_region_contributed
            percentage = (sub_region_contributed / sub_region_allocation * 100) if sub_region_allocation > 0 else 0

            sub_region_data.append({
                'regional_bishop': regional_bishop_name,
                'sub_region_name': sub_region.name,
                'sub_region_bishop': sub_region_bishop_name,
                'allocation': sub_region_allocation,
                'contributed': sub_region_contributed,
                'balance': balance,
                'percentage': percentage
            })

    sub_region_data.sort(key=lambda x: x['percentage'], reverse=True)

    if download == '1':
        return _generate_regions_pdf(sub_region_data, category)

    categories = PaymentCategory.query.order_by(PaymentCategory.name).all()
    return render_template('admin/regions_report.html',
                           sub_region_data=sub_region_data,
                           categories=categories,
                           selected_category_id=category_id,
                           category=category)


def _generate_regions_pdf(sub_region_data, category):
    from io import BytesIO
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)

    data = [['S.No', 'Regional Bishop', 'Sub Region', 'Sub Region Bishop', 'Allocation', 'Contributed', 'Balance', 'Percentage Achieved']]
    total_allocation = 0
    total_contributed = 0
    serial_number = 1

    for item in sub_region_data:
        data.append([
            str(serial_number),
            item['regional_bishop'],
            item['sub_region_name'],
            item['sub_region_bishop'],
            f'{item["allocation"]:,.2f}',
            f'{item["contributed"]:,.2f}',
            f'{item["balance"]:,.2f}',
            f'{item["percentage"]:.1f}%'
        ])
        serial_number += 1
        total_allocation += item['allocation']
        total_contributed += item['contributed']

    total_balance = total_allocation - total_contributed
    total_percentage = (total_contributed / total_allocation * 100) if total_allocation > 0 else 0
    data.append([
        '', 'TOTAL', '', '',
        f'{total_allocation:,.2f}',
        f'{total_contributed:,.2f}',
        f'{total_balance:,.2f}',
        f'{total_percentage:.1f}%'
    ])

    table = Table(data, colWidths=[0.4*inch, 1.8*inch, 1.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))

    for i in range(1, len(data) - 1):
        percentage_str = data[i][7]
        if percentage_str:
            percentage = float(percentage_str.replace('%', ''))
            if percentage < 50:
                table.setStyle(TableStyle([('BACKGROUND', (7, i), (7, i), colors.red), ('TEXTCOLOR', (7, i), (7, i), colors.black)]))
            elif percentage < 100:
                table.setStyle(TableStyle([('BACKGROUND', (7, i), (7, i), colors.yellow), ('TEXTCOLOR', (7, i), (7, i), colors.black)]))
            else:
                table.setStyle(TableStyle([('BACKGROUND', (7, i), (7, i), colors.green), ('TEXTCOLOR', (7, i), (7, i), colors.black)]))

    if total_percentage < 50:
        table.setStyle(TableStyle([('BACKGROUND', (7, -1), (7, -1), colors.red), ('TEXTCOLOR', (7, -1), (7, -1), colors.black)]))
    elif total_percentage < 100:
        table.setStyle(TableStyle([('BACKGROUND', (7, -1), (7, -1), colors.yellow), ('TEXTCOLOR', (7, -1), (7, -1), colors.black)]))
    else:
        table.setStyle(TableStyle([('BACKGROUND', (7, -1), (7, -1), colors.green), ('TEXTCOLOR', (7, -1), (7, -1), colors.black)]))

    elements = []
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=getSampleStyleSheet()['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=1
    )
    report_title = f"{category.name} Financial Report" if category else "Regional Financial Report"
    elements.append(Paragraph(report_title, title_style))
    elements.append(Spacer(1, 0.2*inch))

    date_style = ParagraphStyle(
        'CustomDate',
        parent=getSampleStyleSheet()['Normal'],
        fontSize=10,
        alignment=1
    )
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    pdf_data = buffer.getvalue()
    buffer.close()

    filename = f"{category.name.replace(' ', '_')}_Financial_Report.pdf" if category else "Regional_Financial_Report.pdf"
    return send_file(
        BytesIO(pdf_data),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# ==================== REGIONAL BISHOP ROUTES ====================

@app.route('/regional/dashboard')
@login_required
@role_required('regional_bishop')
def regional_dashboard():
    user = User.query.get(session['user_id'])
    region = Region.query.get(user.region_id) if user.region_id else None
    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all() if user.region_id else []
    sub_bishops = User.query.filter_by(role='sub_region_bishop', region_id=user.region_id).all()
    pastors = User.query.filter_by(role='local_pastor').join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).all()
    total_payments = Payment.query.join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).count()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).scalar() or 0.0
    return render_template('regional/dashboard.html',
                           region=region,
                           sub_regions=sub_regions,
                           sub_bishops=sub_bishops,
                           pastors=pastors,
                           total_payments=total_payments,
                           total_amount=total_amount)


@app.route('/regional/create_subregion', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_create_subregion():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Sub-region name is required.', 'danger')
            return redirect(url_for('regional_create_subregion'))
        sub = SubRegion(name=name, region_id=user.region_id)
        db.session.add(sub)
        db.session.commit()
        flash('Sub-region "{}" created successfully.'.format(name), 'success')
        return redirect(url_for('regional_dashboard'))
    return render_template('regional/create_subregion.html')


@app.route('/regional/create_sub_bishop', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_create_sub_bishop():
    user = User.query.get(session['user_id'])
    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        sub_region_id = request.form.get('sub_region_id')

        if not all([username, password, full_name, sub_region_id]):
            flash('Username, password, full name, and sub-region are required.', 'danger')
            return redirect(url_for('regional_create_sub_bishop'))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.', 'danger')
            return redirect(url_for('regional_create_sub_bishop'))

        sub_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='sub_region_bishop',
            full_name=full_name,
            email=email,
            phone=phone,
            region_id=user.region_id,
            sub_region_id=sub_region_id,
            created_by_id=session['user_id']
        )
        db.session.add(sub_user)
        db.session.commit()
        flash('Sub-Region Bishop "{}" created successfully.'.format(full_name), 'success')
        return redirect(url_for('regional_create_sub_bishop'))
    return render_template('regional/create_sub_bishop.html', sub_regions=sub_regions)


@app.route('/regional/transfer_sub_bishop/<int:sub_bishop_id>', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_transfer_sub_bishop(sub_bishop_id):
    sub_bishop = User.query.get_or_404(sub_bishop_id)
    if sub_bishop.role != 'sub_region_bishop':
        flash('Only sub-region bishops can be transferred.', 'danger')
        return redirect(url_for('regional_dashboard'))
    user = User.query.get(session['user_id'])
    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all()
    if request.method == 'POST':
        sub_region_id = request.form.get('sub_region_id')
        if not sub_region_id:
            flash('Please select a sub-region.', 'danger')
            return redirect(url_for('regional_transfer_sub_bishop', sub_bishop_id=sub_bishop_id))
        sub_bishop.sub_region_id = sub_region_id
        db.session.commit()
        flash('Sub-Region Bishop "{}" transferred successfully.'.format(sub_bishop.full_name), 'success')
        return redirect(url_for('regional_dashboard'))
    return render_template('regional/transfer_sub_bishop.html', sub_bishop=sub_bishop, sub_regions=sub_regions)


@app.route('/regional/payments')
@login_required
@role_required('regional_bishop')
def regional_payments():
    user = User.query.get(session['user_id'])
    sub_totals = db.session.query(
        SubRegion.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).filter(SubRegion.region_id == user.region_id
    ).group_by(SubRegion.id).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).scalar() or 0.0
    return render_template('regional/payments.html', sub_totals=sub_totals, total_amount=total_amount)


@app.route('/regional/payments_by_category')
@login_required
@role_required('regional_bishop')
def regional_payments_by_category():
    user = User.query.get(session['user_id'])
    sub_region_totals = db.session.query(
        SubRegion.name,
        PaymentCategory.id,
        PaymentCategory.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).join(PaymentCategory, Payment.category_id == PaymentCategory.id
    ).filter(SubRegion.region_id == user.region_id
    ).group_by(SubRegion.id, PaymentCategory.id).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).scalar() or 0.0
    return render_template('regional/payments_by_category.html', sub_region_totals=sub_region_totals, total_amount=total_amount)


@app.route('/regional/payments_by_category_detail/<int:category_id>')
@login_required
@role_required('regional_bishop')
def regional_payments_by_category_detail(category_id):
    user = User.query.get(session['user_id'])
    category = PaymentCategory.query.get_or_404(category_id)
    sub_region_breakdown = db.session.query(
        SubRegion.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).filter(SubRegion.region_id == user.region_id, Payment.category_id == category_id
    ).group_by(SubRegion.id).all()

    church_breakdown = db.session.query(
        SubRegion.name,
        Church.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Church, SubRegion.id == Church.sub_region_id
    ).join(Payment, Church.id == Payment.church_id
    ).filter(SubRegion.region_id == user.region_id, Payment.category_id == category_id
    ).group_by(Church.id).all()

    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id, Payment.category_id == category_id
    ).scalar() or 0.0
    return render_template('regional/payments_by_category_detail.html',
                           category=category,
                           sub_region_breakdown=sub_region_breakdown,
                           church_breakdown=church_breakdown,
                           total_amount=total_amount)


@app.route('/regional/manage_sub_bishops')
@login_required
@role_required('regional_bishop')
def regional_manage_sub_bishops():
    user = User.query.get(session['user_id'])
    sub_bishops = User.query.filter_by(role='sub_region_bishop', region_id=user.region_id).all()
    return render_template('regional/manage_sub_bishops.html', sub_bishops=sub_bishops)


@app.route('/regional/edit_sub_bishop/<int:sub_bishop_id>', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_edit_sub_bishop(sub_bishop_id):
    user = User.query.get(session['user_id'])
    sub_bishop = User.query.get_or_404(sub_bishop_id)
    
    # Verify the sub-bishop belongs to this regional bishop's region
    if sub_bishop.region_id != user.region_id:
        flash('You do not have permission to edit this sub-bishop.', 'danger')
        return redirect(url_for('regional_manage_sub_bishops'))
    
    if request.method == 'POST':
        sub_bishop.full_name = request.form.get('full_name', '').strip()
        sub_bishop.email = request.form.get('email', '').strip()
        sub_bishop.phone = request.form.get('phone', '').strip()
        sub_bishop.sub_region_id = request.form.get('sub_region_id', type=int)
        db.session.commit()
        flash('Sub-region bishop updated successfully.', 'success')
        return redirect(url_for('regional_manage_sub_bishops'))
    
    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all()
    return render_template('regional/edit_sub_bishop.html', sub_bishop=sub_bishop, sub_regions=sub_regions)


@app.route('/regional/delete_sub_bishop/<int:sub_bishop_id>', methods=['POST'])
@login_required
@role_required('regional_bishop')
def regional_delete_sub_bishop(sub_bishop_id):
    user = User.query.get(session['user_id'])
    sub_bishop = User.query.get_or_404(sub_bishop_id)
    
    # Verify the sub-bishop belongs to this regional bishop's region
    if sub_bishop.region_id != user.region_id:
        flash('You do not have permission to delete this sub-bishop.', 'danger')
        return redirect(url_for('regional_manage_sub_bishops'))
    
    db.session.delete(sub_bishop)
    db.session.commit()
    flash('Sub-region bishop deleted successfully.', 'success')
    return redirect(url_for('regional_manage_sub_bishops'))


@app.route('/regional/toggle_sub_bishop/<int:sub_bishop_id>', methods=['POST'])
@login_required
@role_required('regional_bishop')
def regional_toggle_sub_bishop(sub_bishop_id):
    user = User.query.get(session['user_id'])
    sub_bishop = User.query.get_or_404(sub_bishop_id)
    
    # Verify the sub-bishop belongs to this regional bishop's region
    if sub_bishop.region_id != user.region_id:
        flash('You do not have permission to deactivate this sub-bishop.', 'danger')
        return redirect(url_for('regional_manage_sub_bishops'))
    
    sub_bishop.is_active = not sub_bishop.is_active
    db.session.commit()
    status = 'activated' if sub_bishop.is_active else 'deactivated'
    flash('Sub-region bishop has been {}.'.format(status), 'success')
    return redirect(url_for('regional_manage_sub_bishops'))


@app.route('/regional/manage_subregions')
@login_required
@role_required('regional_bishop')
def regional_manage_subregions():
    user = User.query.get(session['user_id'])
    subregions = SubRegion.query.filter_by(region_id=user.region_id).all()
    return render_template('regional/manage_subregions.html', subregions=subregions)


@app.route('/regional/edit_subregion/<int:subregion_id>', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_edit_subregion(subregion_id):
    user = User.query.get(session['user_id'])
    subregion = SubRegion.query.get_or_404(subregion_id)
    
    # Verify the subregion belongs to this regional bishop's region
    if subregion.region_id != user.region_id:
        flash('You do not have permission to edit this subregion.', 'danger')
        return redirect(url_for('regional_manage_subregions'))
    
    if request.method == 'POST':
        subregion.name = request.form.get('name', '').strip()
        db.session.commit()
        flash('Subregion updated successfully.', 'success')
        return redirect(url_for('regional_manage_subregions'))
    
    return render_template('regional/edit_subregion.html', subregion=subregion)


@app.route('/regional/delete_subregion/<int:subregion_id>', methods=['POST'])
@login_required
@role_required('regional_bishop')
def regional_delete_subregion(subregion_id):
    user = User.query.get(session['user_id'])
    subregion = SubRegion.query.get_or_404(subregion_id)
    
    # Verify the subregion belongs to this regional bishop's region
    if subregion.region_id != user.region_id:
        flash('You do not have permission to delete this subregion.', 'danger')
        return redirect(url_for('regional_manage_subregions'))
    
    db.session.delete(subregion)
    db.session.commit()
    flash('Subregion deleted successfully.', 'success')
    return redirect(url_for('regional_manage_subregions'))


@app.route('/regional/toggle_subregion/<int:subregion_id>', methods=['POST'])
@login_required
@role_required('regional_bishop')
def regional_toggle_subregion(subregion_id):
    user = User.query.get(session['user_id'])
    subregion = SubRegion.query.get_or_404(subregion_id)
    
    # Verify the subregion belongs to this regional bishop's region
    if subregion.region_id != user.region_id:
        flash('You do not have permission to deactivate this subregion.', 'danger')
        return redirect(url_for('regional_manage_subregions'))
    
    subregion.is_active = not subregion.is_active
    db.session.commit()
    status = 'activated' if subregion.is_active else 'deactivated'
    flash('Subregion has been {}.'.format(status), 'success')
    return redirect(url_for('regional_manage_subregions'))


@app.route('/regional/manage_pastors')
@login_required
@role_required('regional_bishop')
def regional_manage_pastors():
    user = User.query.get(session['user_id'])
    pastors = User.query.filter_by(role='local_pastor').join(Church).join(SubRegion).filter(
        SubRegion.region_id == user.region_id
    ).all()
    return render_template('regional/manage_pastors.html', pastors=pastors)


@app.route('/regional/allocations')
@login_required
@role_required('regional_bishop')
def regional_allocations():
    user = User.query.get(session['user_id'])
    region = Region.query.get(user.region_id) if user.region_id else None
    allocations = Allocation.query.filter_by(level='region', target_id=user.region_id).order_by(
        Allocation.created_at.desc()).all() if user.region_id else []
    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all() if user.region_id else []
    cascaded = Allocation.query.filter(
        Allocation.level == 'sub_region',
        Allocation.target_id.in_([sr.id for sr in sub_regions])
    ).all() if sub_regions else []
    cascaded_by_sub = {}
    for c in cascaded:
        cascaded_by_sub.setdefault(c.target_id, []).append(c)
    return render_template('regional/allocations.html', region=region,
                           allocations=allocations, sub_regions=sub_regions,
                           cascaded_by_sub=cascaded_by_sub)


@app.route('/regional/cascade_allocation/<int:allocation_id>', methods=['GET', 'POST'])
@login_required
@role_required('regional_bishop')
def regional_cascade_allocation(allocation_id):
    user = User.query.get(session['user_id'])
    allocation = Allocation.query.get_or_404(allocation_id)
    if allocation.level != 'region' or allocation.target_id != user.region_id:
        flash('You can only cascade allocations for your own region.', 'danger')
        return redirect(url_for('regional_allocations'))

    sub_regions = SubRegion.query.filter_by(region_id=user.region_id).all()
    remaining = allocation.remaining_amount()

    if request.method == 'POST':
        total = 0.0
        children = []
        for sr in sub_regions:
            val = request.form.get('amount_{}'.format(sr.id), '').strip()
            if not val:
                continue
            try:
                amt = float(val)
            except ValueError:
                flash('Invalid amount for {}.'.format(sr.name), 'danger')
                return render_template('regional/cascade_allocation.html',
                                       allocation=allocation, sub_regions=sub_regions, remaining=remaining)
            if amt < 0:
                flash('Amounts cannot be negative.', 'danger')
                return render_template('regional/cascade_allocation.html',
                                       allocation=allocation, sub_regions=sub_regions, remaining=remaining)
            if amt > 0:
                total += amt
                children.append((sr, amt))
        if total > remaining + 1e-9:
            flash('Total allocated (KES {:.2f}) exceeds the remaining allocation (KES {:.2f}).'.format(total, remaining), 'danger')
            return render_template('regional/cascade_allocation.html',
                                   allocation=allocation, sub_regions=sub_regions, remaining=remaining)
        for sr, amt in children:
            db.session.add(Allocation(
                level='sub_region', target_id=sr.id, category_id=allocation.category_id,
                amount=amt, created_by_id=user.id, parent_id=allocation.id))
        db.session.commit()
        flash('Allocation cascaded to {} sub-region(s).'.format(len(children)), 'success')
        return redirect(url_for('regional_allocations'))

    return render_template('regional/cascade_allocation.html',
                           allocation=allocation, sub_regions=sub_regions, remaining=remaining)


# ==================== SUB-REGION BISHOP ROUTES ====================

@app.route('/subregion/dashboard')
@login_required
@role_required('sub_region_bishop')
def subregion_dashboard():
    user = User.query.get(session['user_id'])
    sub_region = SubRegion.query.get(user.sub_region_id) if user.sub_region_id else None
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    pastors = User.query.filter_by(role='local_pastor', sub_region_id=user.sub_region_id).all()
    total_payments = Payment.query.filter(Payment.pastor_id.in_(
        [p.id for p in pastors]
    )).count() if pastors else 0
    total_amount = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.pastor_id.in_([p.id for p in pastors])
    ).scalar() or 0.0
    return render_template('subregion/dashboard.html',
                           sub_region=sub_region,
                           churches=churches,
                           pastors=pastors,
                           total_payments=total_payments,
                           total_amount=total_amount)


@app.route('/subregion/create_church', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_create_church():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Church name is required.', 'danger')
            return redirect(url_for('subregion_create_church'))
        church = Church(name=name, sub_region_id=user.sub_region_id)
        db.session.add(church)
        db.session.commit()
        flash('Church "{}" created successfully.'.format(name), 'success')
        return redirect(url_for('subregion_dashboard'))
    return render_template('subregion/create_church.html')


@app.route('/subregion/create_pastor', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_create_pastor():
    user = User.query.get(session['user_id'])
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        church_id = request.form.get('church_id')

        if not all([username, password, full_name, church_id]):
            flash('Username, password, full name, and church are required.', 'danger')
            return redirect(url_for('subregion_create_pastor'))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.', 'danger')
            return redirect(url_for('subregion_create_pastor'))

        pastor = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='local_pastor',
            full_name=full_name,
            email=email,
            phone=phone,
            sub_region_id=user.sub_region_id,
            church_id=church_id,
            created_by_id=session['user_id']
        )
        db.session.add(pastor)
        db.session.commit()
        flash('Local Pastor "{}" created successfully.'.format(full_name), 'success')
        return redirect(url_for('subregion_create_pastor'))
    return render_template('subregion/create_pastor.html', churches=churches)


@app.route('/subregion/manage_churches')
@login_required
@role_required('sub_region_bishop')
def subregion_manage_churches():
    user = User.query.get(session['user_id'])
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    return render_template('subregion/manage_churches.html', churches=churches)


@app.route('/subregion/edit_church/<int:church_id>', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_edit_church(church_id):
    user = User.query.get(session['user_id'])
    church = Church.query.get_or_404(church_id)
    
    if church.sub_region_id != user.sub_region_id:
        flash('You do not have permission to edit this church.', 'danger')
        return redirect(url_for('subregion_manage_churches'))
    
    if request.method == 'POST':
        church.name = request.form.get('name', '').strip()
        db.session.commit()
        flash('Church updated successfully.', 'success')
        return redirect(url_for('subregion_manage_churches'))
    
    return render_template('subregion/edit_church.html', church=church)


@app.route('/subregion/delete_church/<int:church_id>', methods=['POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_delete_church(church_id):
    user = User.query.get(session['user_id'])
    church = Church.query.get_or_404(church_id)
    
    if church.sub_region_id != user.sub_region_id:
        flash('You do not have permission to delete this church.', 'danger')
        return redirect(url_for('subregion_manage_churches'))
    
    db.session.delete(church)
    db.session.commit()
    flash('Church deleted successfully.', 'success')
    return redirect(url_for('subregion_manage_churches'))


@app.route('/subregion/toggle_church/<int:church_id>', methods=['POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_toggle_church(church_id):
    user = User.query.get(session['user_id'])
    church = Church.query.get_or_404(church_id)
    
    if church.sub_region_id != user.sub_region_id:
        flash('You do not have permission to deactivate this church.', 'danger')
        return redirect(url_for('subregion_manage_churches'))
    
    church.is_active = not church.is_active
    db.session.commit()
    status = 'activated' if church.is_active else 'deactivated'
    flash('Church has been {}.'.format(status), 'success')
    return redirect(url_for('subregion_manage_churches'))


@app.route('/subregion/transfer_pastor/<int:pastor_id>', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_transfer_pastor(pastor_id):
    pastor = User.query.get_or_404(pastor_id)
    if pastor.role != 'local_pastor':
        flash('Only local pastors can be transferred.', 'danger')
        return redirect(url_for('subregion_dashboard'))
    user = User.query.get(session['user_id'])
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    if request.method == 'POST':
        church_id = request.form.get('church_id')
        if not church_id:
            flash('Please select a church.', 'danger')
            return redirect(url_for('subregion_transfer_pastor', pastor_id=pastor_id))
        pastor.church_id = church_id
        db.session.commit()
        flash('Pastor "{}" transferred successfully.'.format(pastor.full_name), 'success')
        return redirect(url_for('subregion_dashboard'))
    return render_template('subregion/transfer_pastor.html', pastor=pastor, churches=churches)


@app.route('/subregion/manage_pastors')
@login_required
@role_required('sub_region_bishop')
def subregion_manage_pastors():
    user = User.query.get(session['user_id'])
    pastors = User.query.filter_by(role='local_pastor', sub_region_id=user.sub_region_id).all()
    return render_template('subregion/manage_pastors.html', pastors=pastors)


@app.route('/subregion/edit_pastor/<int:pastor_id>', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_edit_pastor(pastor_id):
    user = User.query.get(session['user_id'])
    pastor = User.query.get_or_404(pastor_id)
    
    if pastor.role != 'local_pastor' or pastor.sub_region_id != user.sub_region_id:
        flash('You do not have permission to edit this pastor.', 'danger')
        return redirect(url_for('subregion_manage_pastors'))
    
    if request.method == 'POST':
        pastor.full_name = request.form.get('full_name', '').strip()
        pastor.email = request.form.get('email', '').strip()
        pastor.phone = request.form.get('phone', '').strip()
        pastor.church_id = request.form.get('church_id', type=int)
        db.session.commit()
        flash('Pastor updated successfully.', 'success')
        return redirect(url_for('subregion_manage_pastors'))
    
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    return render_template('subregion/edit_pastor.html', pastor=pastor, churches=churches)


@app.route('/subregion/delete_pastor/<int:pastor_id>', methods=['POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_delete_pastor(pastor_id):
    user = User.query.get(session['user_id'])
    pastor = User.query.get_or_404(pastor_id)
    
    if pastor.role != 'local_pastor' or pastor.sub_region_id != user.sub_region_id:
        flash('You do not have permission to delete this pastor.', 'danger')
        return redirect(url_for('subregion_manage_pastors'))
    
    db.session.delete(pastor)
    db.session.commit()
    flash('Pastor deleted successfully.', 'success')
    return redirect(url_for('subregion_manage_pastors'))


@app.route('/subregion/toggle_pastor/<int:pastor_id>', methods=['POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_toggle_pastor(pastor_id):
    user = User.query.get(session['user_id'])
    pastor = User.query.get_or_404(pastor_id)
    
    if pastor.role != 'local_pastor' or pastor.sub_region_id != user.sub_region_id:
        flash('You do not have permission to deactivate this pastor.', 'danger')
        return redirect(url_for('subregion_manage_pastors'))
    
    pastor.is_active = not pastor.is_active
    db.session.commit()
    status = 'activated' if pastor.is_active else 'deactivated'
    flash('Pastor has been {}.'.format(status), 'success')
    return redirect(url_for('subregion_manage_pastors'))


@app.route('/subregion/payments')
@login_required
@role_required('sub_region_bishop')
def subregion_payments():
    user = User.query.get(session['user_id'])
    payments = Payment.query.join(Church).filter(
        Church.sub_region_id == user.sub_region_id
    ).order_by(Payment.created_at.desc()).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).filter(
        Church.sub_region_id == user.sub_region_id
    ).scalar() or 0.0
    return render_template('subregion/payments.html', payments=payments, total_amount=total_amount)


@app.route('/subregion/payments_by_category')
@login_required
@role_required('sub_region_bishop')
def subregion_payments_by_category():
    user = User.query.get(session['user_id'])
    category_totals = db.session.query(
        PaymentCategory.id,
        PaymentCategory.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Payment, PaymentCategory.id == Payment.category_id
    ).join(Church, Payment.church_id == Church.id
    ).filter(Church.sub_region_id == user.sub_region_id
    ).group_by(PaymentCategory.id).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).filter(
        Church.sub_region_id == user.sub_region_id
    ).scalar() or 0.0
    return render_template('subregion/payments_by_category.html', category_totals=category_totals, total_amount=total_amount)


@app.route('/subregion/payments_by_category_detail/<int:category_id>')
@login_required
@role_required('sub_region_bishop')
def subregion_payments_by_category_detail(category_id):
    user = User.query.get(session['user_id'])
    category = PaymentCategory.query.get_or_404(category_id)
    church_breakdown = db.session.query(
        Church.name,
        db.func.count(Payment.id),
        db.func.sum(Payment.amount)
    ).join(Payment, Church.id == Payment.church_id
    ).filter(Church.sub_region_id == user.sub_region_id, Payment.category_id == category_id
    ).group_by(Church.id).all()
    total_amount = db.session.query(db.func.sum(Payment.amount)).join(Church).filter(
        Church.sub_region_id == user.sub_region_id, Payment.category_id == category_id
    ).scalar() or 0.0
    return render_template('subregion/payments_by_category_detail.html',
                           category=category,
                           church_breakdown=church_breakdown,
                           total_amount=total_amount)


@app.route('/subregion/make_payment', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_make_payment():
    user = User.query.get(session['user_id'])
    sub_region = SubRegion.query.get(user.sub_region_id) if user.sub_region_id else None
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    categories = PaymentCategory.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        church_id = request.form.get('church_id')
        category_id = request.form.get('category_id')
        amount = request.form.get('amount', '').strip()
        paybill_number = request.form.get('paybill_number', '').strip()
        receipt_reference = request.form.get('receipt_reference', '').strip()
        payment_date_str = request.form.get('payment_date', '')
        notes = request.form.get('notes', '').strip()

        if not all([church_id, category_id, amount, paybill_number, receipt_reference]):
            flash('Church, category, amount, Paybill number, and Receipt Reference are required.', 'danger')
            return redirect(url_for('subregion_make_payment'))

        try:
            amount_val = float(amount)
            if amount_val <= 0:
                raise ValueError
        except ValueError:
            flash('Amount must be a positive number.', 'danger')
            return redirect(url_for('subregion_make_payment'))

        payment_date = date.today()
        if payment_date_str:
            try:
                payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'danger')
                return redirect(url_for('subregion_make_payment'))

        payment = Payment(
            church_id=church_id,
            pastor_id=user.id,
            category_id=category_id,
            amount=amount_val,
            paybill_number=paybill_number,
            receipt_reference=receipt_reference,
            payment_date=payment_date,
            notes=notes
        )
        db.session.add(payment)
        db.session.commit()
        flash('Payment of KES {:.2f} recorded successfully.'.format(amount_val), 'success')
        return redirect(url_for('subregion_dashboard'))
    return render_template('subregion/make_payment.html', sub_region=sub_region, churches=churches, categories=categories, today_date=date.today().isoformat())


@app.route('/subregion/allocations')
@login_required
@role_required('sub_region_bishop')
def subregion_allocations():
    user = User.query.get(session['user_id'])
    sub_region = SubRegion.query.get(user.sub_region_id) if user.sub_region_id else None
    allocations = Allocation.query.filter_by(level='sub_region', target_id=user.sub_region_id).order_by(
        Allocation.created_at.desc()).all() if user.sub_region_id else []
    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all() if user.sub_region_id else []
    cascaded = Allocation.query.filter(
        Allocation.level == 'church',
        Allocation.target_id.in_([ch.id for ch in churches])
    ).all() if churches else []
    cascaded_by_church = {}
    for c in cascaded:
        cascaded_by_church.setdefault(c.target_id, []).append(c)
    return render_template('subregion/allocations.html', sub_region=sub_region,
                           allocations=allocations, churches=churches,
                           cascaded_by_church=cascaded_by_church)


@app.route('/subregion/cascade_allocation/<int:allocation_id>', methods=['GET', 'POST'])
@login_required
@role_required('sub_region_bishop')
def subregion_cascade_allocation(allocation_id):
    user = User.query.get(session['user_id'])
    allocation = Allocation.query.get_or_404(allocation_id)
    if allocation.level != 'sub_region' or allocation.target_id != user.sub_region_id:
        flash('You can only cascade allocations for your own sub-region.', 'danger')
        return redirect(url_for('subregion_allocations'))

    churches = Church.query.filter_by(sub_region_id=user.sub_region_id).all()
    remaining = allocation.remaining_amount()

    if request.method == 'POST':
        total = 0.0
        children = []
        for ch in churches:
            val = request.form.get('amount_{}'.format(ch.id), '').strip()
            if not val:
                continue
            try:
                amt = float(val)
            except ValueError:
                flash('Invalid amount for {}.'.format(ch.name), 'danger')
                return render_template('subregion/cascade_allocation.html',
                                       allocation=allocation, churches=churches, remaining=remaining)
            if amt < 0:
                flash('Amounts cannot be negative.', 'danger')
                return render_template('subregion/cascade_allocation.html',
                                       allocation=allocation, churches=churches, remaining=remaining)
            if amt > 0:
                total += amt
                children.append((ch, amt))
        if total > remaining + 1e-9:
            flash('Total allocated (KES {:.2f}) exceeds the remaining allocation (KES {:.2f}).'.format(total, remaining), 'danger')
            return render_template('subregion/cascade_allocation.html',
                                   allocation=allocation, churches=churches, remaining=remaining)
        for ch, amt in children:
            db.session.add(Allocation(
                level='church', target_id=ch.id, category_id=allocation.category_id,
                amount=amt, created_by_id=user.id, parent_id=allocation.id))
        db.session.commit()
        flash('Allocation cascaded to {} church(es).'.format(len(children)), 'success')
        return redirect(url_for('subregion_allocations'))

    return render_template('subregion/cascade_allocation.html',
                           allocation=allocation, churches=churches, remaining=remaining)


# ==================== LOCAL PASTOR ROUTES ====================

@app.route('/pastor/allocations')
@login_required
@role_required('local_pastor')
def pastor_allocations():
    user = User.query.get(session['user_id'])
    church = Church.query.get(user.church_id) if user.church_id else None
    allocations = Allocation.query.filter_by(level='church', target_id=user.church_id).order_by(
        Allocation.created_at.desc()).all() if user.church_id else []
    return render_template('pastor/allocations.html', church=church, allocations=allocations)


# ==================== LOCAL PASTOR ROUTES ====================


@app.route('/pastor/dashboard')
@login_required
@role_required('local_pastor')
def pastor_dashboard():
    user = User.query.get(session['user_id'])
    church = Church.query.get(user.church_id) if user.church_id else None
    sub_region = SubRegion.query.get(church.sub_region_id) if church and church.sub_region_id else None
    region = Region.query.get(sub_region.region_id) if sub_region and sub_region.region_id else None
    my_payments = Payment.query.filter_by(pastor_id=user.id).order_by(Payment.created_at.desc()).all()
    my_total = db.session.query(db.func.sum(Payment.amount)).filter_by(pastor_id=user.id).scalar() or 0.0
    return render_template('pastor/dashboard.html',
                           church=church,
                           sub_region=sub_region,
                           region=region,
                           my_payments=my_payments,
                           my_total=my_total)


@app.route('/pastor/make_payment', methods=['GET', 'POST'])
@login_required
@role_required('local_pastor')
def pastor_make_payment():
    user = User.query.get(session['user_id'])
    church = Church.query.get(user.church_id) if user.church_id else None
    categories = PaymentCategory.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount', '').strip()
        paybill_number = request.form.get('paybill_number', '').strip()
        receipt_reference = request.form.get('receipt_reference', '').strip()
        payment_date_str = request.form.get('payment_date', '')
        notes = request.form.get('notes', '').strip()

        if not all([category_id, amount, paybill_number, receipt_reference]):
            flash('Category, amount, Paybill number, and Receipt Reference are required.', 'danger')
            return redirect(url_for('pastor_make_payment'))

        try:
            amount_val = float(amount)
            if amount_val <= 0:
                raise ValueError
        except ValueError:
            flash('Amount must be a positive number.', 'danger')
            return redirect(url_for('pastor_make_payment'))

        payment_date = date.today()
        if payment_date_str:
            try:
                payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'danger')
                return redirect(url_for('pastor_make_payment'))

        payment = Payment(
            church_id=user.church_id,
            pastor_id=user.id,
            category_id=category_id,
            amount=amount_val,
            paybill_number=paybill_number,
            receipt_reference=receipt_reference,
            payment_date=payment_date,
            notes=notes
        )
        db.session.add(payment)
        db.session.commit()

        linked_allocation = link_payment_to_allocation(payment, user.church_id, int(category_id), amount_val)
        if linked_allocation:
            balance = linked_allocation.balance()
            if balance < -1e-9:
                flash('Payment of KES {:.2f} recorded. Warning: exceeds the {} allocation balance (KES {:.2f}).'.format(
                    amount_val, linked_allocation.category.name, balance), 'warning')
            else:
                flash('Payment of KES {:.2f} recorded and deducted from the {} allocation. Remaining balance: KES {:.2f}.'.format(
                    amount_val, linked_allocation.category.name, balance), 'success')
        else:
            flash('Payment of KES {:.2f} recorded successfully.'.format(amount_val), 'success')
        return redirect(url_for('pastor_allocations') if linked_allocation else url_for('pastor_dashboard'))
    return render_template('pastor/make_payment.html', church=church, categories=categories, today_date=date.today().isoformat())


@app.route('/pastor/my_payments')
@login_required
@role_required('local_pastor')
def pastor_my_payments():
    user = User.query.get(session['user_id'])
    payments = Payment.query.filter_by(pastor_id=user.id).order_by(Payment.created_at.desc()).all()
    my_total = db.session.query(db.func.sum(Payment.amount)).filter_by(pastor_id=user.id).scalar() or 0.0
    return render_template('pastor/my_payments.html', payments=payments, my_total=my_total)


@app.route('/pastor/payment/<int:payment_id>')
@login_required
@role_required('local_pastor')
def pastor_payment_detail(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user = User.query.get(session['user_id'])
    if payment.pastor_id != user.id:
        flash('You can only view your own payments.', 'danger')
        return redirect(url_for('pastor_dashboard'))
    return render_template('pastor/payment_detail.html', payment=payment)


def init_db():
    with app.app_context():
        db.create_all()
        migrate_db()
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

        categories = ['Tithe', 'Mission', 'Bills', 'Church Construction', 'Offering', 'Donation']
        for cat_name in categories:
            existing = PaymentCategory.query.filter_by(name=cat_name).first()
            if not existing:
                category = PaymentCategory(name=cat_name, description=cat_name + ' payments')
                db.session.add(category)
        db.session.commit()
        print('Default payment categories created')


# Ensure database tables exist on startup (also covers gunicorn import).
with app.app_context():
    db.create_all()
    migrate_db()

if __name__ == '__main__':
    if not app.config['DEBUG'] and app.config['SECRET_KEY'] == 'dev-insecure-secret-key':
        print('WARNING: Using an insecure default SECRET_KEY. Set the SECRET_KEY environment variable in production.')
    init_db()
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))