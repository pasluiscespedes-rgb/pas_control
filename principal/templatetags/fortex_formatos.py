from django import template

register = template.Library()


@register.filter
def fecha_ar(value):
    if not value:
        return ""

    return value.strftime("%d/%m/%Y")


@register.filter
def dinero_ar(value):
    if value is None:
        return "$ 0"

    valor = int(round(value))

    return "$ " + f"{valor:,}".replace(",", ".")