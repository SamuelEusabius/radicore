"""
Kitchen / Chief Chef module views.
Chef manages meals, menu plans, kitchen stock, and meal servings.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, F
from django.utils import timezone

from .models import (
    Meal, MealPlan, KitchenStock, KitchenLog, MealServing,
    DepartmentChoices,
)


def _chef_required(request):
    """Chef or School Admin can access kitchen pages."""
    return request.user.role in ('chief_chef', 'school_admin')


def _chef_only(request):
    """Only Chef can manage kitchen data (CRUD)."""
    return request.user.role == 'chief_chef'


# ============================================================
# CHEF DASHBOARD
# ============================================================

@login_required
def chef_dashboard(request):
    """Chef's main dashboard."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Today's menu
    today_plans = MealPlan.objects.filter(
        school=school, date=today
    ).select_related('meal').order_by('meal__meal_type')

    # Upcoming 7 days
    upcoming = MealPlan.objects.filter(
        school=school,
        date__gt=today,
        date__lte=today + timedelta(days=7),
    ).select_related('meal').order_by('date', 'meal__meal_type')[:20]

    # Today's servings
    today_servings = MealServing.objects.filter(
        school=school,
        meal_plan__date=today,
    ).select_related('meal_plan__meal')

    total_served_today = sum(s.total_served for s in today_servings)

    # Kitchen stock stats
    stock_items = KitchenStock.objects.filter(school=school, is_active=True)
    total_stock_value = sum(item.total_value for item in stock_items)
    low_stock = [s for s in stock_items if s.is_low_stock]
    expiring_soon = [
        s for s in stock_items
        if s.expiry_date and s.expiry_date <= today + timedelta(days=14) and s.expiry_date >= today
    ]

    # Recent logs
    recent_logs = KitchenLog.objects.filter(
        school=school
    ).select_related('stock_item', 'recorded_by').order_by('-created_at')[:10]

    return render(request, 'departments/chef/dashboard.html', {
        'today': today,
        'today_plans': today_plans,
        'upcoming': upcoming,
        'today_servings': today_servings,
        'total_served_today': total_served_today,
        'total_stock_value': total_stock_value,
        'low_stock': low_stock,
        'expiring_soon': expiring_soon,
        'recent_logs': recent_logs,
        'stock_count': stock_items.count(),
    })


# ============================================================
# MEALS
# ============================================================

@login_required
def meal_list(request):
    """List all meals."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = Meal.objects.filter(school=school).order_by('meal_type', 'name')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(name__icontains=search)

    meal_type = request.GET.get('type', '')
    if meal_type:
        qs = qs.filter(meal_type=meal_type)

    return render(request, 'departments/chef/meal_list.html', {
        'meals': qs,
        'search': search,
        'type_filter': meal_type,
        'meal_types': Meal.MEAL_TYPES,
    })


@login_required
def meal_form(request, meal_id=None):
    """Add or edit a meal."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    meal = None
    if meal_id:
        meal = get_object_or_404(Meal, id=meal_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        meal_type = request.POST.get('meal_type', '').strip()
        description = request.POST.get('description', '').strip()
        served_time = request.POST.get('served_time') or None
        cost_per_head = request.POST.get('cost_per_head', '0').strip() or '0'
        is_active = 'is_active' in request.POST

        errors = []
        if not name:
            errors.append('Meal name is required.')
        if not meal_type:
            errors.append('Meal type is required.')

        # Check unique_together
        existing = Meal.objects.filter(school=school, meal_type=meal_type, name=name)
        if meal:
            existing = existing.exclude(id=meal.id)
        if existing.exists():
            errors.append(f'A "{name}" {meal_type} meal already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/chef/meal_form.html', {
                'meal': meal,
                'form_data': request.POST,
                'meal_types': Meal.MEAL_TYPES,
            })

        if meal:
            meal.name = name
            meal.meal_type = meal_type
            meal.description = description
            meal.served_time = served_time
            meal.cost_per_head = cost_per_head
            meal.is_active = is_active
            meal.save()
            messages.success(request, f'Meal "{name}" updated.')
        else:
            Meal.objects.create(
                school=school,
                name=name,
                meal_type=meal_type,
                description=description,
                served_time=served_time,
                cost_per_head=cost_per_head,
                is_active=is_active,
            )
            messages.success(request, f'Meal "{name}" added.')

        return redirect('meal_list')

    return render(request, 'departments/chef/meal_form.html', {
        'meal': meal,
        'meal_types': Meal.MEAL_TYPES,
    })


# ============================================================
# MEAL PLANS (MENU)
# ============================================================

@login_required
def meal_plan_list(request):
    """List meal plans by date."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Date filter (default: this week)
    date_from = request.GET.get('from') or today.isoformat()
    date_to = request.GET.get('to') or (today + timedelta(days=7)).isoformat()

    plans = MealPlan.objects.filter(
        school=school,
        date__gte=date_from,
        date__lte=date_to,
    ).select_related('meal').order_by('date', 'meal__meal_type')

    # Group by date
    plans_by_date = {}
    for plan in plans:
        plans_by_date.setdefault(plan.date, []).append(plan)

    return render(request, 'departments/chef/meal_plan_list.html', {
        'plans_by_date': plans_by_date,
        'date_from': date_from,
        'date_to': date_to,
        'today': today,
    })


@login_required
def meal_plan_form(request, plan_id=None):
    """Add or edit a meal plan."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    plan = None
    if plan_id:
        plan = get_object_or_404(MealPlan, id=plan_id, school=school)

    meals = Meal.objects.filter(school=school, is_active=True).order_by('meal_type', 'name')

    if request.method == 'POST':
        meal_id = request.POST.get('meal', '').strip()
        date_val = request.POST.get('date', '').strip()
        head_count = request.POST.get('head_count', '0').strip() or '0'
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not meal_id:
            errors.append('Meal is required.')
        if not date_val:
            errors.append('Date is required.')

        # Check unique
        if meal_id and date_val:
            existing = MealPlan.objects.filter(school=school, date=date_val, meal_id=meal_id)
            if plan:
                existing = existing.exclude(id=plan.id)
            if existing.exists():
                errors.append('This meal is already planned for this date.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/chef/meal_plan_form.html', {
                'plan': plan,
                'meals': meals,
                'form_data': request.POST,
                'today': date.today(),
            })

        if plan:
            plan.meal_id = meal_id
            plan.date = date_val
            plan.head_count = head_count
            plan.notes = notes
            plan.save()
            messages.success(request, 'Meal plan updated.')
        else:
            MealPlan.objects.create(
                school=school,
                meal_id=meal_id,
                date=date_val,
                head_count=head_count,
                notes=notes,
                created_by=request.user,
            )
            messages.success(request, 'Meal planned.')

        return redirect('meal_plan_list')

    return render(request, 'departments/chef/meal_plan_form.html', {
        'plan': plan,
        'meals': meals,
        'today': date.today(),
    })


@login_required
def meal_plan_delete(request, plan_id):
    """Delete a meal plan."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    plan = get_object_or_404(MealPlan, id=plan_id, school=request.user.school)

    if request.method == 'POST':
        info = f'{plan.meal.name} on {plan.date}'
        plan.delete()
        messages.success(request, f'Removed: {info}')
        return redirect('meal_plan_list')

    return render(request, 'departments/chef/confirm_delete.html', {
        'object_name': f'{plan.meal.name} — {plan.date}',
        'object_type': 'Meal Plan',
        'cancel_url': 'meal_plan_list',
    })


# ============================================================
# MEAL SERVING (record what was served)
# ============================================================

@login_required
def meal_serving_form(request, plan_id):
    """Record a meal serving."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    plan = get_object_or_404(
        MealPlan, id=plan_id, school=request.user.school
    )

    if request.method == 'POST':
        students_served = request.POST.get('students_served', '0').strip() or '0'
        staff_served = request.POST.get('staff_served', '0').strip() or '0'
        guests_served = request.POST.get('guests_served', '0').strip() or '0'
        wastage_plates = request.POST.get('wastage_plates', '0').strip() or '0'
        notes = request.POST.get('notes', '').strip()

        MealServing.objects.create(
            school=request.user.school,
            meal_plan=plan,
            students_served=students_served,
            staff_served=staff_served,
            guests_served=guests_served,
            wastage_plates=wastage_plates,
            notes=notes,
            served_by=request.user,
        )
        messages.success(request, 'Meal serving recorded.')
        return redirect('chef_dashboard')

    return render(request, 'departments/chef/meal_serving_form.html', {
        'plan': plan,
    })


# ============================================================
# KITCHEN STOCK
# ============================================================

@login_required
def kitchen_stock_list(request):
    """List kitchen stock."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = KitchenStock.objects.filter(school=school).order_by('name')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(supplier__icontains=search))

    category = request.GET.get('category', '')
    if category:
        qs = qs.filter(category=category)

    items = list(qs)
    low_stock = [i for i in items if i.is_low_stock]
    total_value = sum(i.total_value for i in items)

    return render(request, 'departments/chef/stock_list.html', {
        'items': items,
        'low_stock': low_stock,
        'total_value': total_value,
        'search': search,
        'category_filter': category,
        'categories': KitchenStock.CATEGORY_CHOICES,
    })


@login_required
def kitchen_stock_form(request, item_id=None):
    """Add or edit a kitchen stock item."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    item = None
    if item_id:
        item = get_object_or_404(KitchenStock, id=item_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', 'other').strip()
        unit = request.POST.get('unit', 'kg').strip()
        quantity = request.POST.get('quantity', '0').strip() or '0'
        reorder_level = request.POST.get('reorder_level', '10').strip() or '10'
        unit_cost = request.POST.get('unit_cost', '0').strip() or '0'
        supplier = request.POST.get('supplier', '').strip()
        expiry_date = request.POST.get('expiry_date') or None
        notes = request.POST.get('notes', '').strip()
        is_active = 'is_active' in request.POST

        errors = []
        if not name:
            errors.append('Item name is required.')

        # Check unique
        existing = KitchenStock.objects.filter(school=school, name=name)
        if item:
            existing = existing.exclude(id=item.id)
        if existing.exists():
            errors.append(f'"{name}" already exists in stock.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/chef/stock_form.html', {
                'item': item,
                'form_data': request.POST,
                'categories': KitchenStock.CATEGORY_CHOICES,
                'units': KitchenStock.UNIT_CHOICES,
            })

        if item:
            old_qty = float(item.quantity)
            item.name = name
            item.category = category
            item.unit = unit
            item.reorder_level = reorder_level
            item.unit_cost = unit_cost
            item.supplier = supplier
            item.expiry_date = expiry_date
            item.notes = notes
            item.is_active = is_active

            new_qty = float(quantity or 0)
            if new_qty != old_qty:
                item.quantity = new_qty
                item.save()
                KitchenLog.objects.create(
                    school=school,
                    stock_item=item,
                    action='adjust',
                    quantity=abs(new_qty - old_qty),
                    balance_after=new_qty,
                    unit_cost=item.unit_cost,
                    reason=f'Manual adjustment ({old_qty} → {new_qty})',
                    recorded_by=request.user,
                )
            else:
                item.save()
            messages.success(request, f'"{name}" updated.')
        else:
            qty = float(quantity or 0)
            new_item = KitchenStock.objects.create(
                school=school,
                name=name,
                category=category,
                unit=unit,
                quantity=qty,
                reorder_level=reorder_level,
                unit_cost=unit_cost,
                supplier=supplier,
                expiry_date=expiry_date,
                notes=notes,
                is_active=is_active,
            )
            if qty > 0:
                KitchenLog.objects.create(
                    school=school,
                    stock_item=new_item,
                    action='in',
                    quantity=qty,
                    balance_after=qty,
                    unit_cost=unit_cost,
                    reason='Initial stock',
                    recorded_by=request.user,
                )
            messages.success(request, f'"{name}" added to stock.')

        return redirect('kitchen_stock_list')

    return render(request, 'departments/chef/stock_form.html', {
        'item': item,
        'categories': KitchenStock.CATEGORY_CHOICES,
        'units': KitchenStock.UNIT_CHOICES,
    })


@login_required
def kitchen_stock_action(request, item_id):
    """Record stock in/out (purchase/usage/wastage)."""
    if not _chef_only(request):
        return redirect('dashboard_home')

    item = get_object_or_404(KitchenStock, id=item_id, school=request.user.school)

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        quantity = request.POST.get('quantity', '').strip()
        reason = request.POST.get('reason', '').strip()

        errors = []
        if not action:
            errors.append('Action is required.')
        if not quantity:
            errors.append('Quantity is required.')

        try:
            qty = float(quantity)
            if qty <= 0:
                errors.append('Quantity must be positive.')
        except ValueError:
            errors.append('Invalid quantity.')

        # For 'out' actions, check balance
        if action in ('used', 'wastage', 'adjust') and not errors:
            if qty > float(item.quantity):
                errors.append(f'Only {item.quantity} {item.unit} available.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('kitchen_stock_action', item_id=item.id)

        # Apply
        if action == 'in':
            item.quantity = float(item.quantity) + qty
        elif action == 'donated':
            item.quantity = float(item.quantity) + qty
        else:  # used, wastage, adjust
            item.quantity = float(item.quantity) - qty

        item.save()

        KitchenLog.objects.create(
            school=request.user.school,
            stock_item=item,
            action=action,
            quantity=qty,
            balance_after=item.quantity,
            unit_cost=item.unit_cost,
            reason=reason or '',
            recorded_by=request.user,
        )

        messages.success(request, f'{action.title()} recorded: {qty} {item.get_unit_display()}')
        return redirect('kitchen_stock_list')

    return render(request, 'departments/chef/stock_action_form.html', {
        'item': item,
        'action_choices': KitchenLog.ACTION_CHOICES,
    })


@login_required
def kitchen_logs(request, item_id=None):
    """View kitchen stock movements."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = KitchenLog.objects.filter(school=school).select_related(
        'stock_item', 'recorded_by'
    ).order_by('-created_at')

    item = None
    if item_id:
        item = get_object_or_404(KitchenStock, id=item_id, school=school)
        qs = qs.filter(stock_item=item)

    action_filter = request.GET.get('action', '')
    if action_filter:
        qs = qs.filter(action=action_filter)

    return render(request, 'departments/chef/stock_logs.html', {
        'logs': qs[:200],
        'item': item,
        'action_filter': action_filter,
        'action_choices': KitchenLog.ACTION_CHOICES,
    })


# ============================================================
# REPORTS
# ============================================================

@login_required
def kitchen_report_pdf(request):
    """PDF report of kitchen stock + recent activity."""
    if not _chef_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from apps.core.pdf_utils import image_to_base64
    import io

    school = request.user.school
    today = date.today()

    stock_items = KitchenStock.objects.filter(
        school=school, is_active=True
    ).order_by('category', 'name')

    # Recent logs (last 30 days)
    thirty_ago = today - timedelta(days=30)
    recent_logs = KitchenLog.objects.filter(
        school=school, created_at__date__gte=thirty_ago
    ).select_related('stock_item', 'recorded_by').order_by('-created_at')[:100]

    total_value = sum(i.total_value for i in stock_items)

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    html_string = render_to_string('departments/chef/kitchen_report_pdf.html', {
        'school': school,
        'stock_items': stock_items,
        'recent_logs': recent_logs,
        'total_value': total_value,
        'today': today,
        'school_logo_b64': school_logo_b64,
        'user': request.user,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'kitchen_report_{today}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(src=io.StringIO(html_string), dest=response, encoding='utf-8')
    return response