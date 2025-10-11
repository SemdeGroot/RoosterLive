# core/views/misc.py
from django.http import HttpResponse

def hash_endpoint(request):
    return HttpResponse("", content_type="text/plain")
