import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')

@register.filter
def render_links(value):
    """Convert markdown links [text](url) to HTML anchor tags."""
    if not value:
        return value
    escaped = escape(value)
    result = MARKDOWN_LINK_RE.sub(
        r'<a href="\2" target="_blank" rel="noopener noreferrer" style="color:var(--muted); text-decoration:underline;">\1</a>',
        escaped
    )
    return mark_safe(result)