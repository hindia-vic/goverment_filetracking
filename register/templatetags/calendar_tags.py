from django import template

register = template.Library()

@register.simple_tag
def get_item(dictionary, key):
    """Access dictionary item by key"""
    return dictionary.get(key, [])