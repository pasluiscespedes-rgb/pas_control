from django.urls import path
from . import views

app_name = "cobros"

urlpatterns = [
    path("", views.historial_cobros, name="historial_cobros"),
    path("anular/<int:cobro_id>/", views.anular_cobro, name="anular_cobro"),
]