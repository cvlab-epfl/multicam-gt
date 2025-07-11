from django import template
from marker.models import *
from django.utils import timezone
import json
from django.core import serializers

register = template.Library()

@register.filter(name='next')
def next(value):
    return int(value)+1

@register.filter(name='prev')
def prev(value):
    f = int(value)
    if f > 0:
        return f-1
    else:
         return f

@register.filter(name='toJSON')
def toJSON(value):
    return serializers.serialize("json",value)
