from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q

from .models import County, Constituency, Ward


@require_GET
def api_constituencies(request):
    county_param = request.GET.get('county', '').strip()
    if not county_param:
        return JsonResponse({'results': []})

    qs = Constituency.objects.all()
    
    # Accept ID, code, or name
    try:
        county_id = int(county_param)
        qs = qs.filter(county_id=county_id)
    except ValueError:
        qs = qs.filter(Q(county__code__iexact=county_param) | Q(county__name__iexact=county_param))

    results = [
        {'id': c.id, 'code': c.code, 'name': c.name.upper()}
        for c in qs.order_by('name')
    ]
    return JsonResponse({'results': results})


@require_GET
def api_wards(request):
    cons_param = request.GET.get('constituency', '').strip()
    if not cons_param:
        return JsonResponse({'results': []})

    qs = Ward.objects.all()
    
    try:
        cons_id = int(cons_param)
        qs = qs.filter(constituency_id=cons_id)
    except ValueError:
        qs = qs.filter(Q(constituency__code__iexact=cons_param) | Q(constituency__name__iexact=cons_param))

    results = [
        {'id': w.id, 'code': w.code, 'name': w.name.upper()}
        for w in qs.order_by('name')
    ]
    return JsonResponse({'results': results})