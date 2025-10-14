# core/templatetags/menu_tiles.py
from django import template
from core.tiles import build_tiles

register = template.Library()

@register.simple_tag(takes_context=True)
def user_tiles(context):
    request = context["request"]
    return build_tiles(request.user)