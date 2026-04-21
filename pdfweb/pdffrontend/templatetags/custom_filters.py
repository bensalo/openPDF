from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Returns the value of the given key from a dictionary.
    """
    return dictionary.get(key, '')

@register.filter
def reverse_dict_items(value):
    """
    Custom filter to reverse dictionary items.
    """
    if isinstance(value, dict):
        return reversed(list(value.items()))
    return value