from django.db import migrations
from decimal import Decimal


PLANS = [
    {
        'name': 'Basic',
        'code': 'basic',
        'min_students': 0,
        'max_students': 500,
        'max_teachers': 30,
        'monthly_price': Decimal('3000'),
        'term_price': Decimal('8000'),
        'contract_1y_price': Decimal('28000'),
        'contract_2y_price': Decimal('54000'),
        'order': 1,
        'features': [
            'Up to 500 students',
            'M-Pesa fee collection',
            'SMS notifications',
            'Report cards & receipts',
            'Parent portal access',
            'Attendance tracking',
        ],
    },
    {
        'name': 'Basic+',
        'code': 'basic-plus',
        'min_students': 501,
        'max_students': 1000,
        'max_teachers': 60,
        'monthly_price': Decimal('5000'),
        'term_price': Decimal('12000'),
        'contract_1y_price': Decimal('45000'),
        'contract_2y_price': Decimal('90000'),
        'order': 2,
        'features': [
            'Up to 1000 students',
            'M-Pesa fee collection',
            'Bulk SMS notifications',
            'Report cards & receipts',
            'Parent portal access',
            'Attendance tracking',
            'Basic reports',
        ],
    },
    {
        'name': 'Pro',
        'code': 'pro',
        'min_students': 1001,
        'max_students': 1500,
        'max_teachers': 100,
        'monthly_price': Decimal('8000'),
        'term_price': Decimal('20000'),
        'contract_1y_price': Decimal('76000'),
        'contract_2y_price': Decimal('145000'),
        'order': 3,
        'features': [
            'Up to 1500 students',
            'M-Pesa fee collection',
            'Bulk SMS notifications',
            'Advanced reports',
            'Parent portal access',
            'Priority support',
            'Custom fee structures',
        ],
    },
    {
        'name': 'Pro+',
        'code': 'pro-plus',
        'min_students': 1501,
        'max_students': 2000,
        'max_teachers': 150,
        'monthly_price': Decimal('11500'),
        'term_price': Decimal('28000'),
        'contract_1y_price': Decimal('110000'),
        'contract_2y_price': Decimal('205000'),
        'order': 4,
        'features': [
            'Up to 2000 students',
            'All Pro features',
            'Advanced analytics',
            'Priority support',
            'Bulk data import',
            'API access',
        ],
    },
    {
        'name': 'Enterprise',
        'code': 'enterprise',
        'min_students': 2001,
        'max_students': 99999,
        'max_teachers': 999,
        'monthly_price': Decimal('15000'),
        'term_price': Decimal('35000'),
        'contract_1y_price': Decimal('115000'),
        'contract_2y_price': Decimal('240000'),
        'order': 5,
        'features': [
            'Unlimited students',
            'All Pro+ features',
            'Dedicated account manager',
            'Custom integrations',
            'SLA guarantee',
            'On-site training',
        ],
    },
]


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('schools', 'SubscriptionPlan')
    SubscriptionPlan.objects.all().delete()
    for plan_data in PLANS:
        SubscriptionPlan.objects.create(**plan_data)


def unseed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('schools', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(code__in=[p['code'] for p in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('schools', '0006_alter_schoolsubscription_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]