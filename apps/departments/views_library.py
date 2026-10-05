"""
Library module views — books, issues, returns, overdue.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import Book, BookIssue, DepartmentChoices


def _librarian_required(request):
    """Librarian, School Admin, or Super Admin can manage the library."""
    return request.user.role in ('librarian', 'school_admin')


def _admin_required(request):
    """Only Librarian can manage books (full CRUD)."""
    return request.user.role == 'librarian'


# ============================================================
# LIBRARIAN DASHBOARD
# ============================================================

@login_required
def librarian_dashboard(request):
    """Librarian's main dashboard."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Stats
    total_books = Book.objects.filter(school=school, is_active=True).count()
    total_copies = Book.objects.filter(school=school, is_active=True).aggregate(
        t=Sum('total_copies')
    )['t'] or 0
    issued_count = BookIssue.objects.filter(school=school, status='issued').count()
    overdue_count = BookIssue.objects.filter(
        school=school, status='issued', due_date__lt=today
    ).count()

    # Recent issues
    recent_issues = BookIssue.objects.filter(
        school=school
    ).select_related('book', 'student').order_by('-created_at')[:10]

    # Overdue list
    overdue = BookIssue.objects.filter(
        school=school, status='issued', due_date__lt=today
    ).select_related('book', 'student').order_by('due_date')[:10]

    return render(request, 'departments/librarian/dashboard.html', {
        'total_books': total_books,
        'total_copies': total_copies,
        'issued_count': issued_count,
        'overdue_count': overdue_count,
        'recent_issues': recent_issues,
        'overdue': overdue,
        'today': today,
    })


# ============================================================
# BOOK CATALOG
# ============================================================

@login_required
def book_list(request):
    """List all books in the library."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = Book.objects.filter(school=school).order_by('title')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(author__icontains=search) |
            Q(isbn__icontains=search) |
            Q(category__icontains=search)
        )

    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(category=category)

    # Stats
    stats = {
        'total': qs.count(),
        'available': sum(1 for b in qs if b.is_available),
        'out_of_stock': sum(1 for b in qs if not b.is_available),
    }

    # Categories
    categories = Book.objects.filter(school=school, is_active=True).values_list(
        'category', flat=True
    ).distinct().exclude(category='')

    return render(request, 'departments/librarian/book_list.html', {
        'books': qs,
        'stats': stats,
        'search': search,
        'category_filter': category,
        'categories': categories,
    })


@login_required
def book_detail(request, book_id):
    """View a book + its issue history."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    book = get_object_or_404(Book, id=book_id, school=request.user.school)
    issues = book.issues.select_related('student').order_by('-issue_date')[:30]

    return render(request, 'departments/librarian/book_detail.html', {
        'book': book,
        'issues': issues,
    })


# ============================================================
# ISSUE / RETURN
# ============================================================

@login_required
def issue_book(request, book_id=None):
    """Issue a book to a student."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school

    book = None
    if book_id:
        book = get_object_or_404(Book, id=book_id, school=school)

    # Only books with available copies
    available_books = [b for b in Book.objects.filter(school=school, is_active=True) if b.is_available]
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')

    if request.method == 'POST':
        book_id_val = request.POST.get('book', '').strip()
        student_id_val = request.POST.get('student', '').strip()
        issue_date_val = request.POST.get('issue_date', '').strip()
        due_date_val = request.POST.get('due_date', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not book_id_val:
            errors.append('Book is required.')
        if not student_id_val:
            errors.append('Student is required.')
        if not issue_date_val:
            errors.append('Issue date is required.')
        if not due_date_val:
            errors.append('Due date is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/librarian/issue_form.html', {
                'book': book,
                'available_books': available_books,
                'students': students,
                'today': date.today(),
                'form_data': request.POST,
            })

        selected_book = get_object_or_404(Book, id=book_id_val, school=school)
        selected_student = get_object_or_404(Student, id=student_id_val, school=school)

        # Check availability
        if not selected_book.is_available:
            messages.error(request, f'"{selected_book.title}" has no available copies.')
            return redirect('issue_book')

        BookIssue.objects.create(
            school=school,
            book=selected_book,
            student=selected_student,
            issue_date=issue_date_val,
            due_date=due_date_val,
            status='issued',
            issued_by=request.user,
            notes=notes,
        )

        messages.success(request, f'"{selected_book.title}" issued to {selected_student.full_name}.')
        return redirect('librarian_dashboard')

    return render(request, 'departments/librarian/issue_form.html', {
        'book': book,
        'available_books': available_books,
        'students': students,
        'today': date.today(),
    })


@login_required
def return_book(request, issue_id):
    """Return a book."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    issue = get_object_or_404(
        BookIssue, id=issue_id, school=request.user.school
    )

    if request.method == 'POST':
        return_date_val = request.POST.get('return_date', date.today().isoformat())
        status = request.POST.get('status', 'returned')
        fine_kes = request.POST.get('fine_kes', '0').strip() or '0'
        notes = request.POST.get('notes', '').strip()

        issue.return_date = return_date_val
        issue.status = status
        issue.fine_kes = fine_kes
        issue.returned_to = request.user
        if notes:
            issue.notes = (issue.notes + '\n' + notes).strip()
        issue.save()

        messages.success(request, f'Book returned: {issue.book.title}')
        return redirect('book_issue_list')

    return render(request, 'departments/librarian/return_form.html', {
        'issue': issue,
        'today': date.today(),
    })


@login_required
def book_issue_list(request):
    """List all issues with filters."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = BookIssue.objects.filter(school=school).select_related('book', 'student').order_by('-issue_date')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(book__title__icontains=search) |
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search)
        )

    # Stats
    stats = {
        'all': BookIssue.objects.filter(school=school).count(),
        'issued': BookIssue.objects.filter(school=school, status='issued').count(),
        'returned': BookIssue.objects.filter(school=school, status='returned').count(),
        'overdue': BookIssue.objects.filter(
            school=school, status='issued', due_date__lt=date.today()
        ).count(),
    }

    return render(request, 'departments/librarian/issue_list.html', {
        'issues': qs,
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
        'today': date.today(),
    })


@login_required
def overdue_list(request):
    """List overdue books."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    overdue = BookIssue.objects.filter(
        school=school, status='issued', due_date__lt=today
    ).select_related('book', 'student').order_by('due_date')

    return render(request, 'departments/librarian/overdue_list.html', {
        'overdue': overdue,
        'today': today,
    })


# ============================================================
# SCHOOL ADMIN — Book CRUD
# ============================================================

@login_required
def book_form(request, book_id=None):
    """Add or edit a book (School Admin only)."""
    if not _admin_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    book = None
    if book_id:
        book = get_object_or_404(Book, id=book_id, school=school)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        author = request.POST.get('author', '').strip()
        isbn = request.POST.get('isbn', '').strip()
        category = request.POST.get('category', '').strip()
        publisher = request.POST.get('publisher', '').strip()
        edition = request.POST.get('edition', '').strip()
        year = request.POST.get('year') or None
        total_copies = request.POST.get('total_copies', '1').strip() or '1'
        shelf_location = request.POST.get('shelf_location', '').strip()
        notes = request.POST.get('notes', '').strip()
        cover = request.FILES.get('cover')
        is_active = 'is_active' in request.POST

        errors = []
        if not title:
            errors.append('Title is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/librarian/book_form.html', {
                'book': book,
                'form_data': request.POST,
            })

        if book:
            book.title = title
            book.author = author
            book.isbn = isbn
            book.category = category
            book.publisher = publisher
            book.edition = edition
            book.year = year
            book.total_copies = total_copies
            book.shelf_location = shelf_location
            book.notes = notes
            book.is_active = is_active
            if cover:
                book.cover = cover
            book.save()
            messages.success(request, f'Book "{title}" updated.')
        else:
            Book.objects.create(
                school=school, title=title, author=author, isbn=isbn,
                category=category, publisher=publisher, edition=edition,
                year=year, total_copies=total_copies,
                shelf_location=shelf_location, notes=notes,
                cover=cover, is_active=is_active,
            )
            messages.success(request, f'Book "{title}" added.')

        return redirect('book_list')

    return render(request, 'departments/librarian/book_form.html', {
        'book': book,
    })


@login_required
def book_delete(request, book_id):
    """Delete a book."""
    if not _admin_required(request):
        return redirect('dashboard_home')

    book = get_object_or_404(Book, id=book_id, school=request.user.school)

    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Book "{title}" deleted.')
        return redirect('book_list')

    return render(request, 'departments/librarian/confirm_delete.html', {
        'object_name': book.title,
        'object_type': 'Book',
        'cancel_url': 'book_list',
    })


# ============================================================
# REPORTS + PDF
# ============================================================

@login_required
def library_report_pdf(request):
    """PDF of book issues (with filters)."""
    if not _librarian_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    school = request.user.school
    qs = BookIssue.objects.filter(school=school).select_related('book', 'student').order_by('-issue_date')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    html_string = render_to_string('departments/librarian/issues_pdf.html', {
        'issues': qs,
        'school': school,
        'printed_at': timezone.now(),
        'status_filter': status_filter,
        'total': qs.count(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"library_issues_{date.today()}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa.CreatePDF(src=io.StringIO(html_string), dest=response, encoding='utf-8')
    return response