"""
PDF utility — converts HTML string to a PDF bytes response.
Uses xhtml2pdf (pure Python, no GTK needed on Windows).
"""

from io import BytesIO
from django.http import HttpResponse
from xhtml2pdf import pisa


def html_to_pdf_response(html_string: str, filename: str) -> HttpResponse:
    """
    Convert an HTML string to a PDF and return it as an HTTP response.

    Args:
        html_string: full HTML with <style> etc.
        filename:    e.g. 'receipt_INV123.pdf'

    Returns:
        HttpResponse with content_type application/pdf
    """
    buffer = BytesIO()

    pisa_status = pisa.CreatePDF(
        src=html_string,
        dest=buffer,
        encoding='utf-8',
    )

    if pisa_status.err:
        return HttpResponse(
            f'<h1>PDF generation error</h1><p>Code: {pisa_status.err}</p>',
            status=500
        )

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response