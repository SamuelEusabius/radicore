"""
Student Wallet views.
- Accountant: manage all wallets, top-up, withdraw
- Class Teacher: view class wallets, withdraw for students
- Parent: view children's wallets, top-up, transaction history
- Student: view own balance, QR, transactions
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone

from .wallet_models import StudentWallet, WalletTransaction
from .wallet_notifications import notify_wallet_topup, notify_wallet_withdrawal


# ============================================================
# HELPERS
# ============================================================

def _get_or_create_wallet(student):
    wallet, _ = StudentWallet.objects.get_or_create(
        student=student,
        defaults={
            'school': student.school,
            'balance': Decimal('0.00'),
        }
    )
    return wallet


def _accountant_required(request):
    return request.user.role in ('accountant', 'school_admin')


def _class_teacher_required(request):
    return request.user.role in ('teacher',)


# ============================================================
# ACCOUNTANT — All Wallets
# ============================================================

@login_required
def wallet_dashboard(request):
    """Accountant's wallet dashboard."""
    if not _accountant_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school

    # Stats
    wallets = StudentWallet.objects.filter(school=school).select_related('student')
    total_balance = sum(w.balance for w in wallets)
    total_wallets = wallets.count()
    active_wallets = sum(1 for w in wallets if w.balance > 0)
    locked_wallets = wallets.filter(is_locked=True).count()

    # Recent transactions
    recent_tx = WalletTransaction.objects.filter(
        wallet__school=school
    ).select_related('wallet__student', 'initiated_by').order_by('-created_at')[:20]

    # Today's activity
    today = timezone.now().date()
    today_deposits = WalletTransaction.objects.filter(
        wallet__school=school,
        tx_type='deposit',
        created_at__date=today,
    ).aggregate(total=Sum('amount'))['total'] or 0

    today_withdrawals = WalletTransaction.objects.filter(
        wallet__school=school,
        tx_type='withdrawal',
        created_at__date=today,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Pending collections (withdrawn by teacher, awaiting collection)
    pending_collections = WalletTransaction.objects.filter(
        wallet__school=school,
        status='pending_collection',
    ).select_related('wallet__student', 'withdrawn_by').order_by('-created_at')

    return render(request, 'dashboard/wallet/dashboard.html', {
        'total_balance': total_balance,
        'total_wallets': total_wallets,
        'active_wallets': active_wallets,
        'locked_wallets': locked_wallets,
        'recent_tx': recent_tx,
        'today_deposits': today_deposits,
        'today_withdrawals': today_withdrawals,
        'pending_collections': pending_collections,
        'is_accountant': True,
    })


@login_required
def wallet_list(request):
    """List all student wallets (accountant view)."""
    if not _accountant_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school
    qs = StudentWallet.objects.filter(school=school).select_related('student')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__admission_number__icontains=search)
        )

    class_filter = request.GET.get('class', '').strip()
    if class_filter:
        qs = qs.filter(student__class_level=class_filter)

    # Order by class + name
    qs = qs.order_by('student__class_level', 'student__first_name')

    classes = Student.objects.filter(
        school=school, is_active=True
    ).values_list('class_level', flat=True).distinct().exclude(class_level='')

    total = qs.aggregate(total=Sum('balance'))['total'] or 0

    return render(request, 'dashboard/wallet/wallet_list.html', {
        'wallets': qs,
        'search': search,
        'class_filter': class_filter,
        'classes': sorted(set(classes)),
        'total': total,
    })


@login_required
def wallet_detail(request, wallet_id):
    """View a specific student's wallet."""
    wallet = get_object_or_404(
        StudentWallet, id=wallet_id, school=request.user.school
    )

    if request.user.role not in ('accountant', 'school_admin', 'teacher'):
        return redirect('dashboard_home')

    transactions = wallet.transactions.select_related(
        'initiated_by', 'withdrawn_by'
    ).order_by('-created_at')[:100]

    return render(request, 'dashboard/wallet/wallet_detail.html', {
        'wallet': wallet,
        'transactions': transactions,
    })


# ============================================================
# TOP-UP (Accountant or Parent)
# ============================================================

@login_required
def wallet_topup(request, wallet_id):
    """Manually credit a wallet (cash, bank, or record M-Pesa)."""
    if not _accountant_required(request):
        return redirect('dashboard_home')

    wallet = get_object_or_404(
        StudentWallet, id=wallet_id, school=request.user.school
    )

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        source = request.POST.get('source', 'cash').strip()
        reference = request.POST.get('reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        try:
            amount = Decimal(amount)
            if amount <= 0:
                errors.append('Amount must be positive.')
        except Exception:
            errors.append('Invalid amount.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('wallet_topup', wallet_id=wallet.id)

        # Apply
        wallet.balance += amount
        wallet.save()

        # Record transaction
        tx = WalletTransaction.objects.create(
            wallet=wallet,
            tx_type='deposit',
            source=source,
            amount=amount,
            balance_after=wallet.balance,
            external_reference=reference,
            notes=notes,
            initiated_by=request.user,
            status='completed',
        )

        # Notify
        try:
            notify_wallet_topup(wallet, tx)
        except Exception:
            pass

        messages.success(
            request,
            f'KES {amount:,.0f} loaded. New balance: KES {wallet.balance:,.0f}'
        )
        return redirect('wallet_detail', wallet_id=wallet.id)

    return render(request, 'dashboard/wallet/wallet_topup.html', {
        'wallet': wallet,
    })


# ============================================================
# WITHDRAWAL (Accountant OR Class Teacher)
# ============================================================

@login_required
def wallet_withdraw(request, wallet_id):
    """Withdraw money from a student's wallet."""
    if request.user.role not in ('accountant', 'school_admin', 'teacher'):
        return redirect('dashboard_home')

    wallet = get_object_or_404(
        StudentWallet, id=wallet_id, school=request.user.school
    )

    # Teacher can only withdraw for their class students
    if request.user.role == 'teacher':
        teacher = getattr(request.user, 'teacher_profile', None)
        if not teacher or not teacher.current_class:
            messages.error(request, 'You are not a class teacher.')
            return redirect('dashboard_home')
        if wallet.student.class_level != teacher.current_class.name:
            messages.error(request, 'This student is not in your class.')
            return redirect('dashboard_home')

    if wallet.is_locked:
        messages.error(request, f'Wallet is locked: {wallet.locked_reason}')
        return redirect('wallet_detail', wallet_id=wallet.id)

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        purpose = request.POST.get('purpose', '').strip()
        collected_by = request.POST.get('collected_by', '').strip()
        notes = request.POST.get('notes', '').strip()
        mark_collected = 'mark_collected' in request.POST

        errors = []
        try:
            amount = Decimal(amount)
            if amount <= 0:
                errors.append('Amount must be positive.')
            elif amount > wallet.balance:
                errors.append(f'Insufficient balance. Available: KES {wallet.balance}')
            elif amount > wallet.daily_withdrawal_limit:
                errors.append(f'Exceeds daily limit of KES {wallet.daily_withdrawal_limit}')
        except Exception:
            errors.append('Invalid amount.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('wallet_withdraw', wallet_id=wallet.id)

        # Determine status
        status = 'collected' if mark_collected else 'pending_collection'

        # Apply
        wallet.balance -= amount
        wallet.save()

        # Record
        tx = WalletTransaction.objects.create(
            wallet=wallet,
            tx_type='withdrawal',
            source='cash',
            amount=amount,
            balance_after=wallet.balance,
            purpose=purpose,
            collected_by_name=collected_by or wallet.student.full_name,
            notes=notes,
            initiated_by=request.user,
            withdrawn_by=request.user,
            status=status,
            collected_at=timezone.now() if mark_collected else None,
        )

        # Notify
        try:
            notify_wallet_withdrawal(wallet, tx)
        except Exception:
            pass

        messages.success(
            request,
            f'KES {amount:,.0f} withdrawn from {wallet.student.full_name}. '
            f'New balance: KES {wallet.balance:,.0f}'
        )
        return redirect('wallet_detail', wallet_id=wallet.id)

    return render(request, 'dashboard/wallet/wallet_withdraw.html', {
        'wallet': wallet,
    })


@login_required
def wallet_mark_collected(request, tx_id):
    """Mark a pending withdrawal as collected."""
    if request.user.role not in ('accountant', 'school_admin', 'teacher'):
        return redirect('dashboard_home')

    tx = get_object_or_404(
        WalletTransaction, id=tx_id, wallet__school=request.user.school
    )

    if request.method == 'POST':
        tx.status = 'collected'
        tx.collected_at = timezone.now()
        tx.save()
        messages.success(request, 'Marked as collected.')
        return redirect('wallet_detail', wallet_id=tx.wallet.id)

    return render(request, 'dashboard/wallet/mark_collected.html', {'tx': tx})


# ============================================================
# CLASS TEACHER — Their Class Wallets
# ============================================================

@login_required
def teacher_wallets(request):
    """Class teacher's view of their class wallets."""
    if request.user.role != 'teacher':
        return redirect('dashboard_home')

    teacher = getattr(request.user, 'teacher_profile', None)
    if not teacher or not teacher.current_class:
        messages.error(request, 'You are not a class teacher.')
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school
    cls = teacher.current_class

    # Get or create wallets for all students in class
    students = Student.objects.filter(
        school=school, class_level=cls.name, is_active=True
    ).order_by('first_name', 'last_name')

    for s in students:
        _get_or_create_wallet(s)

    wallets = StudentWallet.objects.filter(
        student__in=students
    ).select_related('student').order_by('student__first_name')

    total_balance = sum(w.balance for w in wallets)

    return render(request, 'dashboard/wallet/teacher_wallets.html', {
        'wallets': wallets,
        'class_name': cls.name,
        'total_balance': total_balance,
        'student_count': students.count(),
    })


@login_required
def teacher_pending_collections(request):
    """Pending withdrawals for teacher's class."""
    if request.user.role != 'teacher':
        return redirect('dashboard_home')

    teacher = getattr(request.user, 'teacher_profile', None)
    if not teacher or not teacher.current_class:
        return redirect('dashboard_home')

    pending = WalletTransaction.objects.filter(
        wallet__school=request.user.school,
        wallet__student__class_level=teacher.current_class.name,
        status='pending_collection',
    ).select_related('wallet__student', 'withdrawn_by').order_by('-created_at')

    return render(request, 'dashboard/wallet/teacher_pending.html', {
        'pending': pending,
        'class_name': teacher.current_class.name,
    })


# ============================================================
# PARENT — View Children's Wallets
# ============================================================

@login_required
def parent_wallets(request):
    """Parent's view of their children's wallets."""
    if request.user.role != 'parent':
        return redirect('dashboard_home')

    from apps.parents.models import Parent

    parent = Parent.objects.filter(user=request.user).first()
    if not parent:
        messages.error(request, 'Parent profile not found.')
        return redirect('dashboard_home')

    children = parent.students.all()

    # Create wallets if missing
    for child in children:
        _get_or_create_wallet(child)

    wallets = StudentWallet.objects.filter(
        student__in=children
    ).select_related('student')

    return render(request, 'dashboard/wallet/parent_wallets.html', {
        'wallets': wallets,
        'children_count': children.count(),
    })


@login_required
def parent_child_wallet(request, wallet_id):
    """Parent views a specific child's wallet."""
    if request.user.role != 'parent':
        return redirect('dashboard_home')

    from apps.parents.models import Parent

    parent = Parent.objects.filter(user=request.user).first()
    wallet = get_object_or_404(StudentWallet, id=wallet_id)
    if not parent or wallet.student not in parent.students.all():
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    transactions = wallet.transactions.order_by('-created_at')[:50]

    return render(request, 'dashboard/wallet/parent_child_wallet.html', {
        'wallet': wallet,
        'transactions': transactions,
    })


# ============================================================
# STUDENT — View Own Wallet
# ============================================================

@login_required
def student_wallet(request):
    """Student's view of their own wallet."""
    if request.user.role != 'student':
        return redirect('dashboard_home')

    from apps.students.models import Student

    student = Student.objects.filter(user=request.user).first()
    if not student:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard_home')

    wallet = _get_or_create_wallet(student)
    transactions = wallet.transactions.order_by('-created_at')[:50]

    return render(request, 'dashboard/wallet/student_wallet.html', {
        'wallet': wallet,
        'transactions': transactions,
    })
    

# ============================================================
# PARENT — Load Money into Child's Wallet
# ============================================================

@login_required
def parent_wallet_topup(request, wallet_id):
    """Parent initiates M-Pesa top-up for their child's wallet."""
    if request.user.role != 'parent':
        return redirect('dashboard_home')

    from apps.parents.models import Parent

    parent = Parent.objects.filter(user=request.user).first()
    wallet = get_object_or_404(StudentWallet, id=wallet_id)

    # Authorization: only their own children
    if not parent or wallet.student not in parent.students.all():
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        phone = request.POST.get('phone', '').strip() or request.user.phone

        # Validate
        errors = []
        try:
            amount = Decimal(amount)
            if amount < 10:
                errors.append('Minimum top-up is KES 10.')
            if amount > 100000:
                errors.append('Maximum top-up is KES 100,000.')
        except Exception:
            errors.append('Invalid amount.')

        if not phone:
            errors.append('Phone number is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('parent_wallet_topup', wallet_id=wallet.id)

        # M-Pesa coming soon — politely notify
        messages.info(
            request,
            f'M-Pesa integration is coming soon. '
            f'Please pay KES {amount:,.0f} directly to the school '
            f'and share the confirmation code with the accountant. '
            f'They will credit {wallet.student.first_name}\'s wallet.'
        )

        # Optionally notify the accountant
        try:
            from apps.notifications.models import Notification
            from apps.accounts.models import User
            accountants = User.objects.filter(
                school=wallet.school, role='accountant', is_active=True
            )
            for acc in accountants:
                Notification.objects.create(
                    recipient=acc,
                    channel='in_app',
                    title=f'Wallet top-up request: {wallet.student.full_name}',
                    message=(
                        f'{request.user.get_full_name() or request.user.email} '
                        f'would like to load KES {amount:,.0f} into '
                        f'{wallet.student.full_name}\'s wallet ('
                        f'{wallet.student.admission_number}). '
                        f'Phone: {phone}. '
                        f'Kindly process once M-Pesa is configured.'
                    ),
                )
        except Exception:
            pass

        return redirect('parent_child_wallet', wallet_id=wallet.id)

    return render(request, 'dashboard/wallet/parent_wallet_topup.html', {
        'wallet': wallet,
        'default_phone': request.user.phone or '',
    })