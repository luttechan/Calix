"""Keep imported and user-owned tooltip text literal in Qt's rich-text view."""
from html import escape


def tooltip_text(value):
    value=str(value)
    if not any(char in value for char in '<>&'):return value
    return '<qt>'+escape(value).replace('\n','<br/>')+'</qt>'
