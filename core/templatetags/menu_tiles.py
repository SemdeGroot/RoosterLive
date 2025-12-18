from django import template
from core.tiles import build_tiles, build_nav_tree_recursive

register = template.Library()

@register.simple_tag(takes_context=True)
def user_tiles(context, group="home"):
    request = context["request"]
    return build_tiles(request.user, group=group)

@register.simple_tag(takes_context=True)
def user_nav_tree(context, root_group="home"):
    request = context["request"]
    return build_nav_tree_recursive(request.user, root_group=root_group, max_depth=10)