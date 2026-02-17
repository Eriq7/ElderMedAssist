import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .serializers import serialize_careplan
from . import services


def index(request):
    return render(request, 'careplan/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def generate_careplan(request):
    data = json.loads(request.body)
    result = services.create_careplan(data)
    return JsonResponse(result, status=202)


@require_http_methods(["GET"])
def list_careplans(request):
    q = request.GET.get('q', '').strip()
    plans = services.list_careplans(query=q)
    return JsonResponse([serialize_careplan(p) for p in plans], safe=False)


@require_http_methods(["GET"])
def careplan_status(request, pk):
    plan = services.get_careplan(pk)
    return JsonResponse(serialize_careplan(plan))


@require_http_methods(["GET"])
def download_careplan(request, pk):
    plan = services.get_careplan(pk)
    content = services.format_careplan_download(plan)

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="careplan_{plan.id}.txt"'
    return response
