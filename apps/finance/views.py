from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.http import HttpResponseForbidden


from .models import FeeStructure, Invoice, Payment
from .serializers import FeeStructureSerializer, InvoiceSerializer, PaymentSerializer
from .services.mpesa import stk_push
from apps.accounts.permissions import IsAccountant
from apps.core.pdf_utils import build_pdf_context


class FeeStructureViewSet(viewsets.ModelViewSet):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAccountant]

    def get_queryset(self):
        user = self.request.user
        qs = FeeStructure.objects.all()
        return qs if user.is_super_admin else qs.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAccountant]

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('student', 'fee_structure')
        if user.is_super_admin:
            return qs
        return qs.filter(student__school=user.school)

    @action(detail=True, methods=['post'])
    def pay_mpesa(self, request, pk=None):
        invoice = self.get_object()
        phone = request.data.get('phone')
        if not phone:
            return Response({'error': 'Phone required'}, status=400)
        try:
            result = stk_push(phone, float(invoice.balance), invoice.id)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@api_view(['POST'])
@permission_classes([])
def mpesa_callback(request):
    data = request.data
    try:
        stk = data['Body']['stkCallback']
        if stk['ResultCode'] != 0:
            return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        meta = {item['Name']: item.get('Value')
                for item in stk['CallbackMetadata']['Item']}
        receipt = meta.get('MpesaReceiptNumber')
        amount = meta.get('Amount')

        account_ref = stk.get('AccountReference', '')
        invoice_id = int(account_ref.replace('INV', '')) if account_ref.startswith('INV') else None

        if invoice_id and receipt:
            invoice = Invoice.objects.get(id=invoice_id)
            Payment.objects.get_or_create(
                reference=receipt,
                defaults={
                    'invoice': invoice,
                    'amount_kes': amount,
                    'method': Payment.Method.MPESA,
                }
            )
    except Exception as e:
        print('M-Pesa callback error:', e)

    return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})
# ==========================================================
# PDF RECEIPT
# ==========================================================

# ==========================================================
# FEE STATEMENT PDF (A5)
# ==========================================================

@login_required
def fee_statement_pdf(request, student_id):
    """Generate a fee statement PDF for a student."""
    from apps.students.models import Student
    from .models import Invoice, Payment
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    # Security — parents only see their own children
    if request.user.role == 'parent':
        try:
            student = request.user.parent_profile.students.get(id=student_id)
        except Exception:
            return HttpResponse('Student not found', status=404)
    else:
        if request.user.is_super_admin:
            student = get_object_or_404(Student, id=student_id)
        else:
            student = get_object_or_404(Student, id=student_id, school=request.user.school)

    invoices = Invoice.objects.filter(
        student=student
    ).select_related('fee_structure').order_by('due_date')

    invoice_ids = list(invoices.values_list('id', flat=True))
    payments = Payment.objects.filter(
        invoice_id__in=invoice_ids
    ).select_related('invoice').order_by('-paid_at')

    total_invoiced = sum(i.amount_due for i in invoices)
    total_paid = sum(i.amount_paid for i in invoices)
    total_balance = total_invoiced - total_paid
    outstanding_invoices = [i for i in invoices if i.balance > 0]

    html_string = render_to_string('pdf/fee_statement.html',
        build_pdf_context(
            school=student.school,
            generated_by=request.user,
            student=student,
            invoices=invoices,
            payments=payments,
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            total_balance=total_balance,
            outstanding_invoices=outstanding_invoices,
        )
    )

    filename = f'fee_statement_{student.admission_number}.pdf'
    return html_to_pdf_response(html_string, filename)
# ==========================================================
# RECEIPT PDF (A5)
# ==========================================================

@login_required
def receipt_pdf(request, payment_id):
    """Generate an A5 receipt PDF for a payment.
    Accessible to: Accountants, Principals, and Parents (only their own child).
    """
    from .models import Payment, Invoice
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    role = getattr(user, 'role', None)

    # -------------------------------
    # ROLE-BASED ACCESS
    # -------------------------------
    if role in ('accountant', 'principal', 'bursar', 'super_admin'):
        # Staff: they can see any receipt for their own school
        payment = get_object_or_404(Payment, id=payment_id)

        # Ensure the payment belongs to the staff member's school
        if role != 'super_admin':
            if not user.school or payment.invoice.student.school != user.school:
                return HttpResponseForbidden("Access denied.")

    elif role == 'parent':
        # Parents: can only download receipts for their own children
        try:
            parent = user.parent_profile
            child_ids = parent.students.values_list('id', flat=True)
        except Exception:
            return HttpResponseForbidden("Parent profile not found.")

        payment = get_object_or_404(Payment, id=payment_id)

        if payment.invoice.student_id not in child_ids:
            return HttpResponseForbidden("You can only download receipts for your own child.")

    else:
        return HttpResponseForbidden("You do not have permission to view this receipt.")

    # -------------------------------
    # BUILD PDF
    # -------------------------------
    invoice = Invoice.objects.get(id=payment.invoice_id)
    student = invoice.student
    school = student.school

    html_string = render_to_string('pdf/receipt.html',
        build_pdf_context(
            school=school,
            generated_by=user,
            payment=payment,
            invoice=invoice,
            student=student,
            user=user,
        )
    )
    filename = f'receipt_{payment.reference or payment.id}.pdf'
    return html_to_pdf_response(html_string, filename)

# ==========================================================
# FEE STATEMENT PDF (A5)
# ==========================================================

@login_required
def fee_statement_pdf(request, student_id):
    """Generate an A5 fee statement PDF for a student."""
    from apps.students.models import Student
    from .models import Invoice, Payment
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    # Security — parents only see their own children
    if request.user.role == 'parent':
        try:
            student = request.user.parent_profile.students.get(id=student_id)
        except Exception:
            return HttpResponse('Student not found', status=404)
    else:
        if request.user.is_super_admin:
            student = get_object_or_404(Student, id=student_id)
        else:
            student = get_object_or_404(Student, id=student_id, school=request.user.school)

    invoices = Invoice.objects.filter(
        student=student
    ).select_related('fee_structure').order_by('due_date')

    invoice_ids = list(invoices.values_list('id', flat=True))
    payments = Payment.objects.filter(
        invoice_id__in=invoice_ids
    ).select_related('invoice').order_by('-paid_at')

    total_invoiced = sum(i.amount_due for i in invoices)
    total_paid = sum(i.amount_paid for i in invoices)
    total_balance = total_invoiced - total_paid
    outstanding_invoices = [i for i in invoices if i.balance > 0]

    html_string = render_to_string('pdf/fee_statement.html',
        build_pdf_context(
            school=student.school,
            generated_by=request.user,
            student=student,
            invoices=invoices,
            payments=payments,
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            total_balance=total_balance,
            outstanding_invoices=outstanding_invoices,
        )
    )

    filename = f'fee_statement_{student.admission_number}.pdf'
    return html_to_pdf_response(html_string, filename)