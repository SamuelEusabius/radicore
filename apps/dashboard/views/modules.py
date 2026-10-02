"""
Views for toggleable school modules (placeholder pages for now).
Library, Transport, Hostel, Wallet, Cafeteria, etc. will have
their real views here when built.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def school_module_placeholder(request, module_code):
    """Placeholder page for modules that are enabled but not yet built."""
    from apps.schools.modules import MODULES

    info = MODULES.get(module_code, {})
    return render(request, 'dashboard/module_placeholder.html', {
        'module_code': module_code,
        'module_name': info.get('name', module_code.title()),
        'module_description': info.get('description', 'This module is coming soon.'),
    })