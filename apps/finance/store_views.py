"""
Store Keeper views — inventory management for the school store.
"""
from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, F
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from apps.accounts.roles import Role
from .store_models import (
    Supplier, ItemCategory, InventoryItem,
    StockReceipt, StockReceiptItem,
    StockIssue, StockIssueItem,
    StockReturn, StockReturnItem,
    StockMovement,
)


# ==========================================================
# ACCESS CONTROL
# ==========================================================

def store_keeper_required(view_func):
    """Allow Store Keepers, Principal, DPA-Admin, Super Admin."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if request.user.role not in (
            Role.STORE_KEEPER,
            Role.PRINCIPAL,
            Role.DEPUTY_ADMIN,
            Role.SUPER_ADMIN,
        ):
            return HttpResponseForbidden("Access denied — Store Keeper area.")
        if request.user.school is None:
            return HttpResponseForbidden("No school linked.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ==========================================================
# DASHBOARD
# ==========================================================

@store_keeper_required
def store_keeper_dashboard(request):
    """Main dashboard with KPIs and action queues."""
    school = request.user.school
    today = timezone.localdate()

    # ---------- KPIs ----------
    items_qs = InventoryItem.objects.filter(school=school, is_active=True)

    total_items = items_qs.count()

    # Stock value = sum(quantity * unit_cost)
    stock_value = items_qs.aggregate(
        total=Sum(F('quantity') * F('unit_cost'))
    )['total'] or 0

    # Low stock: quantity <= min_stock (both positive)
    low_stock_items = items_qs.filter(
        min_stock__gt=0,
        quantity__lte=F('min_stock'),
        quantity__gt=0,
    )
    low_stock_count = low_stock_items.count()

    # Out of stock: quantity <= 0
    out_of_stock_count = items_qs.filter(quantity__lte=0).count()

    # Recent issues (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_issues = StockIssue.objects.filter(
        school=school, issued_date__gte=week_ago,
    ).select_related('issued_by', 'authorized_by').order_by('-issued_date', '-issued_time')[:5]

    issues_this_week = StockIssue.objects.filter(
        school=school, issued_date__gte=week_ago,
    ).count()

    # Recent receipts
    recent_receipts = StockReceipt.objects.filter(
        school=school,
    ).select_related('supplier', 'received_by').order_by('-received_date', '-received_time')[:5]

    receipts_this_month = StockReceipt.objects.filter(
        school=school,
        received_date__gte=today.replace(day=1),
    ).count()

    # Supplier count
    supplier_count = Supplier.objects.filter(school=school, is_active=True).count()

    # Category count
    category_count = ItemCategory.objects.filter(school=school).count()

    context = {
        'school': school,
        'today': today,
        'stats': {
            'total_items': total_items,
            'stock_value': round(stock_value),
            'low_stock': low_stock_count,
            'out_of_stock': out_of_stock_count,
            'suppliers': supplier_count,
            'categories': category_count,
            'issues_this_week': issues_this_week,
            'receipts_this_month': receipts_this_month,
        },
        'low_stock_items': low_stock_items.order_by('quantity')[:8],
        'recent_issues': recent_issues,
        'recent_receipts': recent_receipts,
    }
    return render(request, 'dashboards/store_keeper/dashboard.html', context)


# ==========================================================
# ITEMS
# ==========================================================

@store_keeper_required
def store_items_list(request):
    """Searchable inventory list."""
    school = request.user.school

    qs = InventoryItem.objects.filter(school=school).select_related(
        'category', 'primary_supplier',
    ).order_by('category__name', 'name')

    search = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(description__icontains=search)
        )
    if category_filter:
        qs = qs.filter(category_id=category_filter)
    if status_filter == 'low':
        qs = qs.filter(quantity__lte=F('min_stock'), quantity__gt=0, min_stock__gt=0)
    elif status_filter == 'out':
        qs = qs.filter(quantity__lte=0)
    elif status_filter == 'active':
        qs = qs.filter(is_active=True)

    # Counts
    all_items = InventoryItem.objects.filter(school=school)
    low_count = all_items.filter(min_stock__gt=0, quantity__lte=F('min_stock'), quantity__gt=0).count()
    out_count = all_items.filter(quantity__lte=0).count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'items': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'search': search,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'categories': ItemCategory.objects.filter(school=school).order_by('name'),
        'low_count': low_count,
        'out_count': out_count,
    }
    return render(request, 'dashboards/store_keeper/items_list.html', context)


@store_keeper_required
def store_item_form(request, item_id=None):
    """Create or edit an inventory item."""
    school = request.user.school

    item = None
    if item_id:
        item = get_object_or_404(InventoryItem, pk=item_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        category_id = request.POST.get('category') or None
        unit = request.POST.get('unit', 'pcs').strip()
        description = request.POST.get('description', '').strip()
        storage_location = request.POST.get('storage_location', '').strip()
        unit_cost = request.POST.get('unit_cost') or 0
        min_stock = request.POST.get('min_stock') or 0
        primary_supplier_id = request.POST.get('primary_supplier') or None
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Item name is required.')
        else:
            try:
                if item is None:
                    item = InventoryItem(school=school, quantity=0)
                item.name = name
                item.code = code
                item.category_id = category_id
                item.unit = unit
                item.description = description
                item.storage_location = storage_location
                item.unit_cost = float(unit_cost)
                item.min_stock = float(min_stock)
                item.primary_supplier_id = primary_supplier_id
                item.is_active = is_active
                item.save()
                messages.success(request, f'Item "{item.name}" saved.')
                return redirect('store_items_list')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    context = {
        'school': school,
        'item': item,
        'categories': ItemCategory.objects.filter(school=school).order_by('name'),
        'suppliers': Supplier.objects.filter(school=school, is_active=True).order_by('name'),
    }
    return render(request, 'dashboards/store_keeper/item_form.html', context)


@store_keeper_required
def store_item_detail(request, item_id):
    """One item's full history."""
    school = request.user.school
    item = get_object_or_404(InventoryItem, pk=item_id, school=school)

    movements = StockMovement.objects.filter(
        school=school, item=item,
    ).select_related(
        'performed_by', 'receipt', 'issue', 'stock_return',
    ).order_by('-created_at')[:50]

    context = {
        'school': school,
        'item': item,
        'movements': movements,
    }
    return render(request, 'dashboards/store_keeper/item_detail.html', context)


# ==========================================================
# ISSUES (stock out)
# ==========================================================

@store_keeper_required
def store_issue_list(request):
    """List all stock issues."""
    school = request.user.school

    qs = StockIssue.objects.filter(school=school).select_related(
        'issued_by', 'authorized_by', 'recipient_student', 'recipient_user',
    ).order_by('-issued_date', '-issued_time')

    search = request.GET.get('q', '').strip()
    recipient_filter = request.GET.get('type', '').strip()

    if search:
        qs = qs.filter(
            Q(issue_number__icontains=search)
            | Q(recipient_name__icontains=search)
            | Q(purpose__icontains=search)
        )
    if recipient_filter:
        qs = qs.filter(recipient_type=recipient_filter)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'issues': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'search': search,
        'recipient_filter': recipient_filter,
    }
    return render(request, 'dashboards/store_keeper/issue_list.html', context)


@store_keeper_required
def store_issue_create(request):
    """Record a stock issue (multi-item form)."""
    school = request.user.school
    today = timezone.localdate()

    if request.method == 'POST':
        recipient_type = request.POST.get('recipient_type', 'department')
        recipient_name = request.POST.get('recipient_name', '').strip()
        recipient_student_id = request.POST.get('recipient_student') or None
        recipient_user_id = request.POST.get('recipient_user') or None
        purpose = request.POST.get('purpose', '').strip()
        notes = request.POST.get('notes', '').strip()

        # Collect item lines
        item_ids = request.POST.getlist('item_id[]')
        quantities = request.POST.getlist('quantity[]')

        if not recipient_name:
            messages.error(request, 'Recipient name is required.')
        elif not item_ids or not any(item_ids):
            messages.error(request, 'At least one item is required.')
        else:
            try:
                # Generate issue number
                last = StockIssue.objects.filter(school=school).order_by('-id').first()
                next_num = (last.id + 1) if last else 1
                issue_number = f"ISS-{next_num:05d}"

                issue = StockIssue.objects.create(
                    school=school,
                    issue_number=issue_number,
                    recipient_type=recipient_type,
                    recipient_name=recipient_name,
                    recipient_student_id=recipient_student_id,
                    recipient_user_id=recipient_user_id,
                    purpose=purpose,
                    notes=notes,
                    issued_date=today,
                    issued_time=timezone.localtime().time(),
                    issued_by=request.user,
                )

                created_lines = 0
                for item_id, qty in zip(item_ids, quantities):
                    if not item_id or not qty:
                        continue
                    try:
                        qty = float(qty)
                        if qty <= 0:
                            continue
                        inv_item = InventoryItem.objects.get(pk=item_id, school=school)
                        if inv_item.quantity < qty:
                            messages.warning(request, f'{inv_item.name}: only {inv_item.quantity} in stock, skipped.')
                            continue

                        StockIssueItem.objects.create(
                            issue=issue,
                            item=inv_item,
                            quantity=qty,
                            unit_cost=inv_item.unit_cost,
                        )

                        # Update stock + log movement
                        balance_before = inv_item.quantity
                        inv_item.quantity = inv_item.quantity - qty
                        inv_item.save(update_fields=['quantity', 'updated_at'])

                        StockMovement.objects.create(
                            school=school,
                            item=inv_item,
                            action='issue',
                            quantity=-qty,
                            balance_after=inv_item.quantity,
                            issue=issue,
                            reason=f"Issued to {recipient_name}",
                            performed_by=request.user,
                        )
                        created_lines += 1
                    except (InventoryItem.DoesNotExist, ValueError):
                        continue

                if created_lines == 0:
                    issue.delete()
                    messages.error(request, 'No valid items were issued.')
                else:
                    messages.success(request, f'Stock issue {issue.issue_number} recorded ({created_lines} items).')
                    return redirect('store_issue_detail', issue_id=issue.id)
            except Exception as e:
                messages.error(request, f'Error: {e}')

    context = {
        'school': school,
        'today': today,
        'items': InventoryItem.objects.filter(school=school, is_active=True).order_by('name'),
        'recipient_choices': StockIssue._meta.get_field('recipient_type').choices,
    }
    return render(request, 'dashboards/store_keeper/issue_form.html', context)


@store_keeper_required
def store_issue_detail(request, issue_id):
    """View a stock issue."""
    school = request.user.school
    issue = get_object_or_404(
        StockIssue.objects.select_related('issued_by', 'authorized_by', 'recipient_student', 'recipient_user'),
        pk=issue_id, school=school,
    )
    lines = issue.items.select_related('item').all()

    total_value = sum(line.quantity * line.unit_cost for line in lines)

    context = {
        'school': school,
        'issue': issue,
        'lines': lines,
        'total_value': total_value,
    }
    return render(request, 'dashboards/store_keeper/issue_detail.html', context)


# ==========================================================
# RECEIPTS (stock in)
# ==========================================================

@store_keeper_required
def store_receipt_list(request):
    """List all stock receipts."""
    school = request.user.school

    qs = StockReceipt.objects.filter(school=school).select_related(
        'supplier', 'received_by',
    ).order_by('-received_date', '-received_time')

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'receipts': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
    }
    return render(request, 'dashboards/store_keeper/receipt_list.html', context)


@store_keeper_required
def store_receipt_create(request):
    """Record a stock receipt (goods in)."""
    school = request.user.school
    today = timezone.localdate()

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier') or None
        supplier_invoice_no = request.POST.get('supplier_invoice_no', '').strip()
        notes = request.POST.get('notes', '').strip()

        item_ids = request.POST.getlist('item_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_costs = request.POST.getlist('unit_cost[]')

        if not item_ids or not any(item_ids):
            messages.error(request, 'At least one item is required.')
        else:
            try:
                last = StockReceipt.objects.filter(school=school).order_by('-id').first()
                next_num = (last.id + 1) if last else 1
                receipt_number = f"RCV-{next_num:05d}"

                receipt = StockReceipt.objects.create(
                    school=school,
                    receipt_number=receipt_number,
                    supplier_id=supplier_id,
                    supplier_invoice_no=supplier_invoice_no,
                    received_date=today,
                    received_time=timezone.localtime().time(),
                    notes=notes,
                    received_by=request.user,
                    total_cost=0,
                )

                total = 0
                created_lines = 0

                for item_id, qty, cost in zip(item_ids, quantities, unit_costs):
                    if not item_id or not qty:
                        continue
                    try:
                        qty = float(qty)
                        cost = float(cost or 0)
                        if qty <= 0:
                            continue

                        inv_item = InventoryItem.objects.get(pk=item_id, school=school)

                        StockReceiptItem.objects.create(
                            receipt=receipt,
                            item=inv_item,
                            quantity=qty,
                            unit_cost=cost,
                            line_total=qty * cost,
                        )

                        inv_item.quantity = inv_item.quantity + qty
                        if cost > 0:
                            inv_item.unit_cost = cost
                        inv_item.save(update_fields=['quantity', 'unit_cost', 'updated_at'])

                        StockMovement.objects.create(
                            school=school,
                            item=inv_item,
                            action='receipt',
                            quantity=qty,
                            balance_after=inv_item.quantity,
                            receipt=receipt,
                            reason=f"Received via {receipt_number}",
                            performed_by=request.user,
                        )

                        total += qty * cost
                        created_lines += 1
                    except (InventoryItem.DoesNotExist, ValueError):
                        continue

                if created_lines == 0:
                    receipt.delete()
                    messages.error(request, 'No valid items were recorded.')
                else:
                    receipt.total_cost = total
                    receipt.save(update_fields=['total_cost'])
                    messages.success(request, f'Stock receipt {receipt.receipt_number} recorded ({created_lines} items).')
                    return redirect('store_receipt_list')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    context = {
        'school': school,
        'today': today,
        'items': InventoryItem.objects.filter(school=school, is_active=True).order_by('name'),
        'suppliers': Supplier.objects.filter(school=school, is_active=True).order_by('name'),
    }
    return render(request, 'dashboards/store_keeper/receipt_form.html', context)


# ==========================================================
# LOW STOCK
# ==========================================================

@store_keeper_required
def store_low_stock(request):
    """Reorder list — items below min_stock."""
    school = request.user.school

    items = InventoryItem.objects.filter(
        school=school,
        is_active=True,
        min_stock__gt=0,
    ).filter(
        Q(quantity__lte=F('min_stock')),
    ).select_related('category', 'primary_supplier').order_by('quantity')

    out_of_stock = items.filter(quantity__lte=0)
    low_stock = items.filter(quantity__gt=0)

    context = {
        'school': school,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
        'total': items.count(),
    }
    return render(request, 'dashboards/store_keeper/low_stock.html', context)


# ==========================================================
# CATEGORIES + SUPPLIERS (light CRUD)
# ==========================================================

@store_keeper_required
def store_categories(request):
    """List + quick-add categories."""
    school = request.user.school

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        else:
            ItemCategory.objects.create(school=school, name=name, description=description)
            messages.success(request, f'Category "{name}" added.')

    context = {
        'school': school,
        'categories': ItemCategory.objects.filter(school=school).annotate(item_count=Count('items')).order_by('name'),
    }
    return render(request, 'dashboards/store_keeper/categories.html', context)


@store_keeper_required
def store_suppliers(request):
    """List + quick-add suppliers."""
    school = request.user.school

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        kra_pin = request.POST.get('kra_pin', '').strip()
        if not name:
            messages.error(request, 'Supplier name is required.')
        else:
            Supplier.objects.create(
                school=school, name=name, contact_person=contact_person,
                phone=phone, email=email, kra_pin=kra_pin,
            )
            messages.success(request, f'Supplier "{name}" added.')

    context = {
        'school': school,
        'suppliers': Supplier.objects.filter(school=school).order_by('name'),
    }
    return render(request, 'dashboards/store_keeper/suppliers.html', context)
  
  # ==========================================================
# STOCK VALUATION REPORT
# ==========================================================

@store_keeper_required
def store_valuation_report(request):
    """
    Stock valuation report — every active item with
    quantity × unit_cost, subtotalled per category.
    """
    school = request.user.school

    items = (
        InventoryItem.objects
        .filter(school=school, is_active=True)
        .select_related('category', 'primary_supplier')
        .order_by('category__name', 'name')
    )

    # Group by category for the table
    grouped = {}
    grand_total = Decimal('0.00')
    grand_units = Decimal('0.00')

    for item in items:
        cat_name = item.category.name if item.category else 'Uncategorised'
        line_value = (item.quantity or Decimal('0')) * (item.unit_cost or Decimal('0'))
        grand_total += line_value
        grand_units += (item.quantity or Decimal('0'))

        grouped.setdefault(cat_name, {
            'items': [],
            'subtotal': Decimal('0.00'),
            'units': Decimal('0.00'),
        })
        grouped[cat_name]['items'].append({
            'item': item,
            'line_value': line_value,
        })
        grouped[cat_name]['subtotal'] += line_value
        grouped[cat_name]['units'] += (item.quantity or Decimal('0'))

    # Low stock count for context
    low_count = (
        InventoryItem.objects
        .filter(school=school, is_active=True, min_stock__gt=0)
        .filter(quantity__lte=F('min_stock'))
        .count()
    )

    context = {
        'school': school,
        'grouped': grouped,
        'grand_total': grand_total,
        'grand_units': grand_units,
        'item_count': items.count(),
        'low_count': low_count,
        'generated_at': timezone.now(),
        'generated_by': request.user,
    }
    return render(request, 'dashboards/store_keeper/valuation.html', context)


@store_keeper_required
def store_valuation_pdf(request):
    """
    Same as store_valuation_report but returns a print-ready
    view (client-side window.print() or PDF engine consumes it).
    """
    school = request.user.school

    items = (
        InventoryItem.objects
        .filter(school=school, is_active=True)
        .select_related('category', 'primary_supplier')
        .order_by('category__name', 'name')
    )

    grouped = {}
    grand_total = Decimal('0.00')

    for item in items:
        cat_name = item.category.name if item.category else 'Uncategorised'
        line_value = (item.quantity or Decimal('0')) * (item.unit_cost or Decimal('0'))
        grand_total += line_value
        grouped.setdefault(cat_name, {'items': [], 'subtotal': Decimal('0.00')})
        grouped[cat_name]['items'].append({
            'item': item,
            'line_value': line_value,
        })
        grouped[cat_name]['subtotal'] += line_value

    context = {
        'school': school,
        'grouped': grouped,
        'grand_total': grand_total,
        'generated_at': timezone.now(),
        'generated_by': request.user,
    }
    return render(request, 'pdf/store_valuation.html', context)


# ==========================================================
# STOCK MOVEMENTS — UNIFIED AUDIT TRAIL
# ==========================================================

@store_keeper_required
def store_movements(request):
    """
    Unified audit trail of every stock movement.
    Filterable by action type, item, and date range.
    """
    school = request.user.school

    qs = (
        StockMovement.objects
        .filter(school=school)
        .select_related(
            'item', 'item__category',
            'performed_by',
            'receipt', 'issue', 'stock_return',
        )
        .order_by('-created_at')
    )

    # ---- Filters ----
    action_filter = request.GET.get('action', '').strip()
    item_filter = request.GET.get('item', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()

    if action_filter:
        qs = qs.filter(action=action_filter)
    if item_filter:
        qs = qs.filter(item_id=item_filter)
    if date_from:
        try:
            from datetime import datetime
            qs = qs.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime
            qs = qs.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    # ---- Summary cards (respect filters) ----
    receipts_count = qs.filter(action='receipt').count()
    issues_count = qs.filter(action='issue').count()
    returns_count = qs.filter(action='return').count()
    adjustments_count = qs.filter(action='adjustment').count()
    losses_count = qs.filter(action='loss').count()

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'movements': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'action_filter': action_filter,
        'item_filter': item_filter,
        'date_from': date_from,
        'date_to': date_to,
        'action_choices': StockMovement.ACTION_CHOICES,
        'all_items': InventoryItem.objects.filter(school=school).order_by('name'),
        'counts': {
            'receipts': receipts_count,
            'issues': issues_count,
            'returns': returns_count,
            'adjustments': adjustments_count,
            'losses': losses_count,
        },
    }
    return render(request, 'dashboards/store_keeper/movements.html', context)