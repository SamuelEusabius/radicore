"""
AJAX endpoints for cascading dropdowns.

GET /api/locations/constituencies/?county=<county_id>     → list of constituencies
GET /api/locations/wards/?constituency=<constituency_id>   → list of wards
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import County, Constituency, Ward


@require_GET
def api_constituencies(request):
    """
    Returns constituencies for the given county.
    Query param: county (County ID or code)
    """
    county_param = request.GET.get('county', '').strip()
    if not county_param:
        return JsonResponse({'results': []})

    qs = Constituency.objects.all()
    # Accept either ID or code
    try:
        county_id = int(county_param)
        qs = qs.filter(county_id=county_id)
    except ValueError:
        qs = qs.filter(county__code=county_param)

    results = [
        {'id': c.id, 'code': c.code, 'name': c.name}
        for c in qs.order_by('name')
    ]
    return JsonResponse({'results': results})


@require_GET
def api_wards(request):
    """
    Returns wards for the given constituency.
    Query param: constituency (Constituency ID or code)
    """
    cons_param = request.GET.get('constituency', '').strip()
    if not cons_param:
        return JsonResponse({'results': []})

    qs = Ward.objects.all()
    try:
        cons_id = int(cons_param)
        qs = qs.filter(constituency_id=cons_id)
    except ValueError:
        qs = qs.filter(constituency__code=cons_param)

    results = [
        {'id': w.id, 'code': w.code, 'name': w.name}
        for w in qs.order_by('name')
    ]
    return JsonResponse({'results': results})