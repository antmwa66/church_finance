from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
import os
import re
import secrets
import smtplib
from email.message import EmailMessage
from sqlalchemy import text

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

    churches = db.relationship('Church', backref='sub_region', lazy=True, cascade='all, delete-orphan')


class Church(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sub_region_id = db.Column(db.Integer, db.ForeignKey('sub_region.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

    transaction_match = re.search(r'([A-Z0-9]{10,12})', message)
    if transaction_match:
        result['transaction_code'] = transaction_match.group(1)

    amount_match = re.search(r'KES\s+([\d,]+\.\d{2})', message, re.IGNORECASE)
    if amount_match:
        result['amount'] = float(amount_match.group(1).replace(',', ''))

    sender_match = re.search(r'from\s+([A-Z][A-Z\s]+?)\s*-\s*(\d{3}\*{3}\d{3}|\d{10,12})', message)
    if sender_match:
        result['sender_name'] = sender_match.group(1).strip()
        result['sender_phone'] = sender_match.group(2)

    paybill_match = re.search(r'Paybill\s+(\d+)', message, re.IGNORECASE)
    if paybill_match:
        result['paybill_number'] = paybill_match.group(1)
        after = message[paybill_match.end():]
        acc_match = re.search(r'(\d{3,})', after)
        if acc_match:
            result['account_number'] = acc_match.group(1)
    if not result['account_number']:
        acc_match = re.search(r'(?:Account|Acc)\.?\s*(\d+)', message, re.IGNORECASE)
        if acc_match:
            result['account_number'] = acc_match.group(1)

    if result['account_number']:
        result['category'] = detect_category(result['account_number'])

    dt_match = re.search(
        r'(?:\bon\s*)?(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})'
        r'(?:\s+at\s+|\s+)(\d{1,2}:\d{2}\s*(?:AM|PM)?)?',
        message, re.IGNORECASE)
    if dt_match:
        day, month, year, time_part = dt_match.groups()
        year = '20' + year if len(year) == 2 else year
        result['payment_date'] = '{:04d}-{:02d}-{:02d}'.format(int(year), int(month), int(day))
        if time_part:
            result['payment_time'] = time_part.strip()

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
        with db.engine.begin() as conn:
            if 'reset_token' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN reset_token VARCHAR(120)'))
            if 'reset_token_expiry' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN reset_token_expiry DATETIME'))
            if 'allocation_id' not in payment_cols:
                conn.execute(text('ALTER TABLE "payment" ADD COLUMN allocation_id INTEGER'))


@app.route('/api/parse-mpesa-message', methods=['POST'])
def api_parse_mpesa_message():
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    parsed = parse_mpesa_message(message)
    return jsonify(parsed)


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