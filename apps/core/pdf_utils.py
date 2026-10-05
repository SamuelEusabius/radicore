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