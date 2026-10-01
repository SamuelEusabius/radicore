from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Template filter to look up dict[key] in templates."""
    if not dictionary:
        return None
    return dictionary.get(str(key)) or dictionary.get(key)