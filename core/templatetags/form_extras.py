# core/templatetags/form_extras.py
from django import template
register = template.Library()

@register.filter
def has_key(d, key):
    try:
        return key in d
    except Exception:
        return False

@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def field(form, name):
    """
    Haal een BoundField op: form[name].
    Retourneert None als het veld er niet is.
    """
    try:
        return form[name]
    except Exception:
        return None
