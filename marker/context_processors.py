from .models import Annotation,Rectangle
from django.core import serializers
import json

def rectangles_processor(request):
    rectangles = Rectangle.objects.filter(x1__gt = 0, y1__gt = 0, x2__gt = 0)
    return {'rectangles': rectangles}
