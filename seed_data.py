"""Seed script: creates sample accounts for the church finance hierarchy.

Run from the project directory:  python seed_data.py
Use  python seed_data.py --reset  to wipe all users/regions/churches/payments first.

All generated accounts use the password defined in SAMPLE_PASSWORD below.
"""
import argparse
from datetime import date, timedelta

from app import app, db, User, Region, SubRegion, Church, Payment, PaymentCategory
from werkzeug.security import generate_password_hash

SAMPLE_PASSWORD = 'church123'

REGIONS = [
    {
        'name': 'Nairobi Region',
        'bishop': ('rb_nairobi', 'Bishop Daniel Kimani'),
        'sub_regions': [
            {
                'name': 'Nairobi Central Sub-Region',
                'bishop': ('sb_nairobi_central', 'Sub-Bishop Mary Wanjiru'),
                'churches': [
                    ('Christ Redeemer Church', 'pastor_maryanne', 'Pastor Maryanne Achieng'),
                    ('Faith Tabernacle', 'pastor_johnk', 'Pastor John Kamau'),
                ],
            },
            {
                'name': 'Nairobi East Sub-Region',
                'bishop': ('sb_nairobi_east', 'Sub-Bishop Peter Omondi'),
                'churches': [
                    ('Holy Trinity Church', 'pastor_grace', 'Pastor Grace Nyambura'),
                    ('Victory Chapel', 'pastor_simion', 'Pastor Simion Maina'),
                ],
            },
        ],
    },
    {
        'name': 'Rift Valley Region',
        'bishop': ('rb_rift', 'Bishop Esther Chebet'),
        'sub_regions': [
            {
                'name': 'Nakuru Sub-Region',
                'bishop': ('sb_nakuru', 'Sub-Bishop Samuel Kiptoo'),
                'churches': [
                    ('Nakuru Miracle Centre', 'pastor_faith', 'Pastor Faith Cherotich'),
                    ('Spring of Life Church', 'pastor_davidk', 'Pastor David Koskei'),
                ],
            },
            {
                'name': 'Eldoret Sub-Region',
                'bishop': ('sb_eldoret', 'Sub-Bishop Naomi Rotich'),
                'churches': [
                    ('Eldoret Gospel Church', 'pastor_benjamin', 'Pastor Benjamin Kiplagat'),
                    ('Calvary Assembly', 'pastor_joyce', 'Pastor Joyce Chelagat'),
                ],
            },
        ],
    },
    {
        'name': 'Coast Region',
        'bishop': ('rb_coast', 'Bishop Joseph Mwangi'),
        'sub_regions': [
            {
                'name': 'Mombasa Sub-Region',
                'bishop': ('sb_mombasa', 'Sub-Bishop Aisha Said'),
                'churches': [
                    ('Mombasa Christian Centre', 'pastor_omar', 'Pastor Omar Mwakamba'),
                    ('Glory House Church', 'pastor_zainab', 'Pastor Zainab Mohamed'),
                ],
            },
            {
                'name': 'Kilifi Sub-Region',
                'bishop': ('sb_kilifi', 'Sub-Bishop James Charo'),
                'churches': [
                    ('Kilifi Revival Church', 'pastor_peninah', 'Pastor Peninah Kazungu'),
                    ('Bethany Fellowship', 'pastor_brian', 'Pastor Brian Mwadime'),
                ],
            },
        ],
    },
]


def make_user(username, role, full_name, email=None, phone=None,
              region_id=None, sub_region_id=None, church_id=None, created_by_id=None):
    existing = User.query.filter_by(username=username).first()
    if existing:
        return existing, False
    user = User(
        username=username,
        password_hash=generate_password_hash(SAMPLE_PASSWORD),
        role=role,
        full_name=full_name,
        email=email or (username + '@church.org'),
        phone=phone,
        region_id=region_id,
        sub_region_id=sub_region_id,
        church_id=church_id,
        created_by_id=created_by_id,
    )
    db.session.add(user)
    db.session.commit()
    return user, True


def seed():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            full_name='System Administrator',
            email='admin@church.org',
            phone='0000000000',
        )
        db.session.add(admin)
        db.session.commit()
        print('Default admin recreated: admin / admin123')
    admin_id = admin.id

    created_counts = {'regions': 0, 'sub_regions': 0, 'churches': 0,
                     'regional_bishop': 0, 'sub_region_bishop': 0, 'local_pastor': 0,
                     'payments': 0}

    for region_data in REGIONS:
        rb_username, rb_name = region_data['bishop']
        region_bishop, created = make_user(
            rb_username, 'regional_bishop', rb_name,
            region_id=None, created_by_id=admin_id)
        created_counts['regional_bishop'] += 1 if created else 0

        region = Region.query.filter_by(name=region_data['name']).first()
        if not region:
            region = Region(name=region_data['name'], admin_id=region_bishop.id)
            db.session.add(region)
            db.session.commit()
            created_counts['regions'] += 1

        region_bishop.region_id = region.id
        db.session.commit()

        for sub_data in region_data['sub_regions']:
            sb_username, sb_name = sub_data['bishop']
            sub_bishop, created = make_user(
                sb_username, 'sub_region_bishop', sb_name,
                region_id=region.id, created_by_id=region_bishop.id)
            created_counts['sub_region_bishop'] += 1 if created else 0

            sub_region = SubRegion.query.filter_by(name=sub_data['name'], region_id=region.id).first()
            if not sub_region:
                sub_region = SubRegion(name=sub_data['name'], region_id=region.id)
                db.session.add(sub_region)
                db.session.commit()
                created_counts['sub_regions'] += 1

            sub_bishop.sub_region_id = sub_region.id
            db.session.commit()

            for church_name, p_username, p_name in sub_data['churches']:
                church = Church.query.filter_by(name=church_name, sub_region_id=sub_region.id).first()
                if not church:
                    church = Church(name=church_name, sub_region_id=sub_region.id)
                    db.session.add(church)
                    db.session.commit()
                    created_counts['churches'] += 1

                pastor, created = make_user(
                    p_username, 'local_pastor', p_name,
                    region_id=region.id, sub_region_id=sub_region.id,
                    church_id=church.id, created_by_id=sub_bishop.id)
                created_counts['local_pastor'] += 1 if created else 0

                created_counts['payments'] += seed_payments(pastor, church)

    print('Sample data created:')
    for key, value in created_counts.items():
        print('  {}: {}'.format(key, value))
    print('\nAll sample accounts use password: {}'.format(SAMPLE_PASSWORD))


def seed_payments(pastor, church):
    categories = PaymentCategory.query.filter_by(is_active=True).all()
    if not categories:
        return 0
    count = 0
    for i, category in enumerate(categories[:3]):
        ref = 'SMP{}'.format(pastor.id * 100 + i)
        if Payment.query.filter_by(receipt_reference=ref).first():
            continue
        payment = Payment(
            church_id=church.id,
            pastor_id=pastor.id,
            category_id=category.id,
            amount=round(5000 + i * 1500 + pastor.id * 100, 2),
            paybill_number='174379',
            receipt_reference=ref,
            payment_date=date.today() - timedelta(days=i * 3),
        )
        db.session.add(payment)
        count += 1
    db.session.commit()
    return count


def reset_all():
    confirm = input("This will DELETE all users, regions, churches and payments. Type 'yes' to continue: ")
    if confirm.strip().lower() != 'yes':
        print('Aborted.')
        return
    with app.app_context():
        Payment.query.delete()
        Church.query.delete()
        SubRegion.query.delete()
        Region.query.delete()
        User.query.delete()
        db.session.commit()
        print('All data cleared.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed church finance sample data')
    parser.add_argument('--reset', action='store_true', help='wipe all data first')
    args = parser.parse_args()

    with app.app_context():
        if args.reset:
            reset_all()
        seed()
