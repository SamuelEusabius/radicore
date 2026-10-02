"""
Registry of all toggleable modules in the system.
Add new modules here — they'll auto-appear in the Super Admin UI.
"""

MODULES = {
    'library': {
        'name': 'Library Management',
        'description': 'Book catalog, borrowing, returns',
        'icon': 'book',
        'default': False,
    },
    'transport': {
        'name': 'Transport Management',
        'description': 'Bus routes, student assignments, tracking',
        'icon': 'truck',
        'default': False,
    },
    'hostel': {
        'name': 'Hostel / Boarding',
        'description': 'Dormitory allocation, boarding fees',
        'icon': 'home',
        'default': False,
    },
    'wallet': {
        'name': 'Student Wallet',
        'description': 'Pocket money, M-Pesa top-ups, shop purchases',
        'icon': 'credit-card',
        'default': False,
    },
    'cafeteria': {
        'name': 'Cafeteria',
        'description': 'Meal plans, menu management, meal cards',
        'icon': 'coffee',
        'default': False,
    },
    'bulk_sms': {
        'name': 'Bulk SMS',
        'description': 'Send SMS to parents and staff',
        'icon': 'message-square',
        'default': True,
    },
    'sms': {
        'name': 'SMS Notifications',
        'description': 'Automated SMS for attendance, fees, alerts',
        'icon': 'message-square',
        'default': True,
    },
    'mpesa': {
        'name': 'M-Pesa Integration',
        'description': 'Fee collection via M-Pesa STK Push',
        'icon': 'smartphone',
        'default': True,
    },
    'parent_portal': {
        'name': 'Parent Portal',
        'description': 'Parent access to children, fees, grades',
        'icon': 'users',
        'default': True,
    },
    'analytics': {
        'name': 'Analytics & Reports',
        'description': 'Advanced analytics, exam analysis, dashboards',
        'icon': 'bar-chart',
        'default': True,
    },
    'reports': {
        'name': 'Reports',
        'description': 'Generate and download reports (PDF, Excel)',
        'icon': 'file-text',
        'default': True,
    },
}


def get_module_choices():
    """Returns (value, name) tuples for form fields."""
    return [(code, info['name']) for code, info in MODULES.items()]


def get_enabled_modules(school):
    """Returns a set of module codes enabled for a school."""
    if not school:
        return set()
    from apps.schools.models import SchoolModule
    return set(
        SchoolModule.objects.filter(
            school=school, is_enabled=True
        ).values_list('module', flat=True)
    )


def is_module_enabled(school, module_code):
    """Check if a single module is enabled for a school."""
    return module_code in get_enabled_modules(school)