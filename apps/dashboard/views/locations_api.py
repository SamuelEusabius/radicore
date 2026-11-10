from django.http import JsonResponse
from kenyan_counties.models import Constituency, Ward

def get_constituencies(request):
    # Accept both 'county' and 'county_id' to support different HTML pages
    county_code = request.GET.get('county') or request.GET.get('county_id')
    if not county_code:
        return JsonResponse([], safe=False)
    
    qs = Constituency.objects.filter(county__code=county_code).values('id', 'name').order_by('name')
    return JsonResponse(list(qs), safe=False)

def get_wards(request):
    # Accept both 'constituency' and 'constituency_id' to support different HTML pages
    constituency_id = request.GET.get('constituency') or request.GET.get('constituency_id')
    if not constituency_id:
        return JsonResponse([], safe=False)
    
    qs = Ward.objects.filter(constituency_id=constituency_id).values('id', 'name').order_by('name')
    return JsonResponse(list(qs), safe=False)