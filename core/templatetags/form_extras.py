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

@register.filter
def dutch_name(user):
    """
    Formatteert de naam van een User object.
    Eerste en laatste woord met hoofdletter.
    """
    if not user:
        return "-"
    
    # Haal voor- en achternaam op
    full_name = f"{user.first_name} {user.last_name}".strip()
    
    # Fallback als er geen naam is ingevuld
    if not full_name:
        return user.username

    parts = full_name.split()
    if not parts:
        return full_name
        
    # Eerste woord Capitalizen
    parts[0] = parts[0].capitalize()
    
    # Laatste woord Capitalizen (als er meer dan 1 woord is)
    if len(parts) > 1:
        parts[-1] = parts[-1].capitalize()
        
    return " ".join(parts)

@register.filter
def vaste_werkdagen_short(profile):
    """
    Korte weergave vaste werkdagen voor 'vast' dienstverband:
    - o = ochtend
    - m = middag
    - o/m = beide
    Voorbeeld: "Ma o/m, Di m, Vr o"
    """
    if not profile or getattr(profile, "dienstverband", "") != "vast":
        return ""

    days = [
        ("Ma", profile.work_mon_am, profile.work_mon_pm),
        ("Di", profile.work_tue_am, profile.work_tue_pm),
        ("Wo", profile.work_wed_am, profile.work_wed_pm),
        ("Do", profile.work_thu_am, profile.work_thu_pm),
        ("Vr", profile.work_fri_am, profile.work_fri_pm),
    ]

    out = []
    for d, am, pm in days:
        if am and pm:
            out.append(f"{d} Och/Mid")
        elif am:
            out.append(f"{d} Och")
        elif pm:
            out.append(f"{d} Mid")

    return ", ".join(out) if out else "—"