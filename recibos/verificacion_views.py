from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .autenticidad import AVISO, emitir, estado_anulacion, integro, pdf_integro, verificar
from .models import AutenticidadRecibo
from .permisos import recibos_visibles

MAX_PDF = 5 * 1024 * 1024


class VerificacionForm(forms.Form):
    codigo = forms.RegexField(regex=r'^[A-F0-9]{32}$', max_length=32,
                              label='Código FORTEX (32 caracteres)')
    archivo = forms.FileField(label='PDF original recibido')

    def clean_archivo(self):
        f = self.cleaned_data['archivo']
        if f.size > MAX_PDF:
            raise forms.ValidationError('El PDF supera 5 MB.')
        return f


@login_required
@require_http_methods(['GET', 'POST'])
def verificar_recibo(request):
    if not request.user.is_active:
        raise PermissionDenied('Acceso interno FORTEX.')
    form = VerificacionForm(request.POST or None, request.FILES or None)
    resultado = None
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data['archivo'].read(MAX_PDF + 1)
        resultado = verificar(form.cleaned_data['codigo'], data) if len(data) <= MAX_PDF else 'NO_VERIFICABLE'
    response = render(request, 'recibos/verificar.html', {'form': form, 'resultado': resultado, 'aviso': AVISO})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@login_required
@require_POST
@csrf_protect
def emitir_pdf(request, recibo_id):
    get_object_or_404(recibos_visibles(request.user), pk=recibo_id)
    get_object_or_404(AutenticidadRecibo, recibo_id=recibo_id)
    try:
        emitir(recibo_id, usuario=request.user)
    except ValidationError:
        return HttpResponse('No se puede emitir: documento anulado o registro inconsistente.', status=409)
    return redirect('recibo_pdf', recibo_id=recibo_id)


def pdf_autenticado(registro):
    if not registro.fecha_emision:
        return HttpResponse('El documento todavía no fue emitido.', status=409, headers={'Cache-Control': 'no-store'})
    if not integro(registro) or not pdf_integro(registro) or estado_anulacion(registro):
        return HttpResponse('Documento anulado o registro inconsistente.', status=409,
                            headers={'Cache-Control': 'no-store'})
    response = HttpResponse(bytes(registro.pdf), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Recibo_{registro.recibo_id}.pdf"'
    response['Cache-Control'] = 'no-store'
    return response
