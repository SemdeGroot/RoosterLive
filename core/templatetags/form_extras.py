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
        val = d.get(key)
        # Als val None is, geef lege string terug. Anders de waarde.
        return val if val is not None else ""
    except Exception:
        return ""
    
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
