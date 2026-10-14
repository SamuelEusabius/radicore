"""
PDF utility — converts HTML string to a PDF bytes response.
Uses xhtml2pdf (pure Python, no GTK needed on Windows).
"""

from io import BytesIO
import base64
import os

from django.http import HttpResponse
from xhtml2pdf import pisa


def html_to_pdf_response(html_string: str, filename: str) -> HttpResponse:
    """Convert an HTML string to a PDF and return it as an HTTP response."""
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


def image_to_base64(image_field, max_width=180):
    """
    Convert a Django ImageField to a base64 data URI for embedding in PDFs.
    Resizes the image to keep the PDF small enough for xhtml2pdf.
    """
    if not image_field:
        return None

    try:
        path = image_field.path
    except (ValueError, AttributeError):
        return None

    if not os.path.exists(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        '.jpg':  'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png':  'image/png',
        '.gif':  'image/gif',
        '.webp': 'image/webp',
    }
    mime = mime_map.get(ext, 'image/jpeg')

    # Try to resize with PIL for smaller payloads
    try:
        from PIL import Image

        img = Image.open(path)

        # Convert to RGB (drop alpha for JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            try:
                background.paste(img, mask=img.split()[-1])
            except Exception:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if wider than max_width
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=80, optimize=True)
        data = base64.b64encode(buffer.getvalue()).decode('ascii')
        buffer.close()

        return f'data:image/jpeg;base64,{data}'

    except ImportError:
        # Fallback: raw file
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f'data:{mime};base64,{data}'
    except Exception:
        return None
    
    

def get_school_logo_data_uri(school, max_width=180):
    """
    Base64 data URI for the school logo, with fallback chain:
      1. school.logo (uploaded image)
      2. static/images/coat_of_arms.png
      3. static/images/graduation-cap-books.png
      4. None

    xhtml2pdf cannot fetch /media/ URLs, so data URIs are required.
    """
    if school is None:
        return None

    # 1. Try uploaded logo
    logo = getattr(school, 'logo', None)
    if logo and getattr(logo, 'name', ''):
        uri = image_to_base64(logo, max_width=max_width)
        if uri:
            return uri

    # 2/3. Static fallbacks
    from django.conf import settings
    for filename in ('coat_of_arms.png', 'graduation-cap-books.png'):
        path = os.path.join(settings.BASE_DIR, 'static', 'images', filename)
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
                data = base64.b64encode(raw).decode('ascii')
                return f'data:image/png;base64,{data}'
            except Exception:
                continue

    return None


def build_pdf_context(school, generated_by=None, **extra):
    """
    Build a standard PDF context dict with logo, school, and metadata.

    Usage in a view:
        context = build_pdf_context(request.user.school, request.user,
                                    student=student, invoice=invoice)
        html = render_to_string('pdf/foo.html', context)

    Automatically adds:
        school, logo_data_uri, generated_by, generated_on

    Pass any additional keys via **extra.
    """
    from django.utils import timezone

    ctx = {
        'school': school,
        'logo_data_uri': get_school_logo_data_uri(school),
        'generated_by': generated_by,
        'generated_on': timezone.now(),
    }
    ctx.update(extra)
    return ctx