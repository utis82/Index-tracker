# Créez le fichier main/templatetags/dict_extras.py

from django import template

register = template.Library()

@register.filter
def lookup(dict_data, key):
    """Permet d'accéder à une clé de dictionnaire dans les templates"""
    if isinstance(dict_data, dict) and key in dict_data:
        return dict_data[key]
    return None

@register.filter
def sub(value, arg):
    """Soustraction dans les templates"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0