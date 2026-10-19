"""
Global search — cross-model, tenant-scoped.

Searches everything relevant to the current user's role:
  - Students (name, admission number, UPI)
  - Staff (name, email, phone)
  - Visitors (name, phone, org, host)
  - Invoices (number, student name)
  - Books (title, author, ISBN)
  - Incidents (reference, title)
  - Correspondence (reference, subject)
  - Admission applications (ref, applicant)

Results are grouped by category for the search results page.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render


def _school(request):
    school = getattr(request, 'school', None)
    if not school:
        school = getattr(request.user, 'school', None)
    return school


# Roles that can see each category
ROLE_VISIBILITY = {
    'students':     None,  # None = all roles
    'staff':        None,
    'visitors':     ('security_officer', 'secretary', 'principal', 'deputy_admin'),
    'invoices':     ('accountant', 'principal', 'deputy_admin'),
    'books':        ('librarian', 'principal', 'deputy_admin', 'teacher', 'class_teacher', 'student'),
    'incidents':    ('security_officer', 'principal', 'deputy_admin', 'secretary'),
    'correspondence': ('secretary', 'principal'),
    'applications': ('secretary', 'principal', 'deputy_admin'),
}


def _can_search(role: str, category: str) -> bool:
    allowed = ROLE_VISIBILITY.get(category)
    if allowed is None:
        return True
    return role in allowed


@login_required
def global_search(request):
    """
    Global search across all models the current user can access.
    """
    school = _school(request)
    if not school:
        return render(request, 'dashboard/search_results.html', {
            'query': '',
            'total': 0,
            'groups': [],
        })

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return render(request, 'dashboard/search_results.html', {
            'query': q,
            'total': 0,
            'groups': [],
            'too_short': len(q) == 1,
        })

    role = getattr(request.user, 'role', '')
    groups = []
    total = 0

    # ==========================================================
    # STUDENTS
    # ==========================================================
    if _can_search(role, 'students'):
        try:
            from apps.students.models import Student
            students = Student.objects.filter(
                school=school,
            ).filter(
                Q(first_name__icontains=q)
                | Q(middle_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(admission_number__icontains=q)
                | Q(upi__icontains=q)
            ).order_by('first_name', 'last_name')[:20]

            if students:
                items = []
                for s in students:
                    items.append({
                        'title': f"{s.first_name} {s.middle_name} {s.last_name}".strip(),
                        'subtitle': f"Adm: {s.admission_number} · Class: {s.class_level or s.cbc_level or '—'}",
                        'url': f"/dashboard/students/{s.id}/" if hasattr(s, 'id') else None,
                        'icon': 'graduation-cap',
                    })
                groups.append({'label': 'Students', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # STAFF
    # ==========================================================
    if _can_search(role, 'staff'):
        try:
            from apps.accounts.models import User
            staff = User.objects.filter(
                school=school,
            ).exclude(role__in=('student', 'parent')).filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            ).order_by('first_name', 'last_name')[:15]

            if staff:
                items = []
                for u in staff:
                    items.append({
                        'title': u.get_full_name() or u.email,
                        'subtitle': f"{u.get_role_display()} · {u.email}",
                        'url': f"/dashboard/users/{u.id}/" if hasattr(u, 'id') else None,
                        'icon': 'user',
                    })
                groups.append({'label': 'Staff', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # VISITORS
    # ==========================================================
    if _can_search(role, 'visitors'):
        try:
            from apps.security.models import Visitor
            visitors = Visitor.objects.filter(
                school=school,
            ).filter(
                Q(full_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(organisation__icontains=q)
                | Q(host_name__icontains=q)
            ).order_by('-time_in')[:15]

            if visitors:
                items = []
                for v in visitors:
                    items.append({
                        'title': v.full_name,
                        'subtitle': f"{v.get_purpose_display()} · {v.time_in:%d %b %H:%M}",
                        'url': f"/dashboard/security/visitors/{v.id}/",
                        'icon': 'users',
                    })
                groups.append({'label': 'Visitors', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # INVOICES
    # ==========================================================
    if _can_search(role, 'invoices'):
        try:
            from apps.finance.models import Invoice
            invoices = Invoice.objects.filter(
                student__school=school,
            ).filter(
                Q(invoice_number__icontains=q)
                | Q(student__first_name__icontains=q)
                | Q(student__last_name__icontains=q)
            ).select_related('student')[:15]

            if invoices:
                items = []
                for inv in invoices:
                    items.append({
                        'title': f"Invoice {inv.invoice_number}",
                        'subtitle': f"{inv.student.first_name} {inv.student.last_name} · KES {inv.total_amount|default:0}",
                        'url': f"/dashboard/finance/invoices/{inv.id}/",
                        'icon': 'file-text',
                    })
                groups.append({'label': 'Invoices', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # BOOKS (library)
    # ==========================================================
    if _can_search(role, 'books'):
        try:
            from apps.departments.models import Book
            books = Book.objects.filter(
                school=school,
            ).filter(
                Q(title__icontains=q)
                | Q(author__icontains=q)
                | Q(isbn__icontains=q)
            ).order_by('title')[:15]

            if books:
                items = []
                for b in books:
                    items.append({
                        'title': b.title,
                        'subtitle': f"by {b.author or '—'} · {getattr(b, 'copies_available', '—')} available",
                        'url': f"/dashboard/library/books/{b.id}/",
                        'icon': 'book',
                    })
                groups.append({'label': 'Books', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # INCIDENTS
    # ==========================================================
    if _can_search(role, 'incidents'):
        try:
            from apps.security.models import Incident
            incidents = Incident.objects.filter(
                school=school,
            ).filter(
                Q(reference__icontains=q)
                | Q(title__icontains=q)
                | Q(description__icontains=q)
            ).order_by('-occurred_at')[:15]

            if incidents:
                items = []
                for inc in incidents:
                    items.append({
                        'title': f"{inc.reference} — {inc.title}",
                        'subtitle': f"{inc.get_severity_display()} · {inc.occurred_at:%d %b %H:%M}",
                        'url': f"/dashboard/security/incidents/{inc.id}/",
                        'icon': 'alert-triangle',
                    })
                groups.append({'label': 'Incidents', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # CORRESPONDENCE
    # ==========================================================
    if _can_search(role, 'correspondence'):
        try:
            from apps.secretary.models import Correspondence
            letters = Correspondence.objects.filter(
                school=school,
            ).filter(
                Q(reference_number__icontains=q)
                | Q(subject__icontains=q)
                | Q(correspondent_name__icontains=q)
            ).order_by('-created_at')[:15]

            if letters:
                items = []
                for c in letters:
                    items.append({
                        'title': c.subject,
                        'subtitle': f"{c.reference_number} · {c.get_direction_display()} · {c.correspondent_name}",
                        'url': f"/dashboard/secretary/correspondence/{c.id}/",
                        'icon': 'mail',
                    })
                groups.append({'label': 'Correspondence', 'items': items})
                total += len(items)
        except Exception:
            pass

    # ==========================================================
    # ADMISSION APPLICATIONS
    # ==========================================================
    if _can_search(role, 'applications'):
        try:
            from apps.secretary.models import AdmissionApplication
            apps_qs = AdmissionApplication.objects.filter(
                school=school,
            ).filter(
                Q(reference_number__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(guardian_name__icontains=q)
            ).order_by('-created_at')[:15]

            if apps_qs:
                items = []
                for a in apps_qs:
                    items.append({
                        'title': f"{a.first_name} {a.last_name}",
                        'subtitle': f"{a.reference_number} · {a.get_status_display()}",
                        'url': f"/dashboard/secretary/admissions/{a.id}/",
                        'icon': 'file-plus',
                    })
                groups.append({'label': 'Admission Applications', 'items': items})
                total += len(items)
        except Exception:
            pass

    context = {
        'query': q,
        'total': total,
        'groups': groups,
    }
    return render(request, 'dashboard/search_results.html', context)