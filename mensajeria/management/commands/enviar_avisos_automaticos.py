from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from polizas.models import Poliza
from principal.models import MovimientoCliente
from principal.whatsapp import (
    enviar_recordatorio_vencimiento,
    enviar_cuota_vencida,
    obtener_importe_referencia,
)


class Command(BaseCommand):
    help = "Envía avisos automáticos D-1 y D+1 por WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Muestra los avisos sin enviarlos.",
        )

        parser.add_argument(
            "--poliza",
            type=int,
            help="Procesa solamente una póliza específica.",
        )

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        ayer = hoy - timedelta(days=1)

        simular = options["simular"]
        poliza_id = options.get("poliza")

        polizas = (
            Poliza.objects
            .select_related("cliente", "vehiculo")
            .filter(
                fecha_vencimiento__in=[ayer, manana]
            )
            .exclude(estado="Anulada")
        )

        if poliza_id:
            polizas = polizas.filter(id=poliza_id)

        self.stdout.write(
            f"FORTEX - Avisos automáticos {hoy:%d/%m/%Y}"
        )

        self.stdout.write(
            f"Pólizas encontradas: {polizas.count()}"
        )

        enviados = 0
        omitidos = 0
        errores = 0

        for poliza in polizas:
            cliente = poliza.cliente

            if not cliente.whatsapp:
                self.stdout.write(
                    self.style.WARNING(
                        f"Póliza {poliza.id}: cliente sin WhatsApp."
                    )
                )
                omitidos += 1
                continue

            if not poliza.vehiculo or not poliza.vehiculo.patente:
                self.stdout.write(
                    self.style.WARNING(
                        f"Póliza {poliza.id}: sin vehículo o patente."
                    )
                )
                omitidos += 1
                continue

            if poliza.fecha_vencimiento == manana:
                tipo = "recordatorio"
                titulo = (
                    "WhatsApp automático - "
                    "recordatorio vencimiento"
                )
            elif poliza.fecha_vencimiento == ayer:
                tipo = "cuota_vencida"
                titulo = (
                    "WhatsApp automático - cuota vencida"
                )
            else:
                continue

            clave = (
                f"POLIZA_ID={poliza.id}; "
                f"VENCIMIENTO={poliza.fecha_vencimiento.isoformat()}"
            )

            ya_enviado = MovimientoCliente.objects.filter(
                cliente=cliente,
                tipo="whatsapp",
                titulo=titulo,
                descripcion__contains=clave,
            ).exists()

            if ya_enviado:
                self.stdout.write(
                    self.style.WARNING(
                        f"Póliza {poliza.id}: aviso ya enviado."
                    )
                )
                omitidos += 1
                continue

            numero = str(cliente.whatsapp or "")
            numero = "".join(
                caracter
                for caracter in numero
                if caracter.isdigit()
            )

            if numero.startswith("0"):
                numero = numero[1:]

            if numero.startswith("54"):
                destinatario = numero
            else:
                destinatario = "549" + numero

            nombre = cliente.nombre.strip()
            patente = poliza.vehiculo.patente.strip()

            fecha = (
                poliza.fecha_vencimiento
                .strftime("%d/%m/%Y")
            )

            importe = obtener_importe_referencia(poliza)

            if importe is None:
                importe_texto = "Consultar con su asesor"
            else:
                importe_texto = (
                    f"{importe:,.0f}"
                    .replace(",", ".")
                )

            self.stdout.write(
                f"Póliza {poliza.id} | "
                f"{cliente.apellido}, {cliente.nombre} | "
                f"{tipo} | "
                f"{fecha}"
            )

            if simular:
                continue

            try:
                if tipo == "cuota_vencida":
                    respuesta = enviar_cuota_vencida(
                        destinatario=destinatario,
                        nombre=nombre,
                        patente=patente,
                        fecha_vencimiento=fecha,
                        importe=importe_texto,
                    )
                else:
                    respuesta = enviar_recordatorio_vencimiento(
                        destinatario=destinatario,
                        nombre=nombre,
                        patente=patente,
                        fecha_vencimiento=fecha,
                        importe=importe_texto,
                    )

                if respuesta.ok:
                    MovimientoCliente.objects.create(
                        cliente=cliente,
                        tipo="whatsapp",
                        titulo=titulo,
                        descripcion=(
                            f"{clave}; "
                            f"DESTINATARIO={destinatario}; "
                            f"TIPO={tipo}; "
                            f"ESTADO=ENVIADO"
                        ),
                        usuario=None,
                    )

                    enviados += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Póliza {poliza.id}: enviado correctamente."
                        )
                    )
                else:
                    errores += 1

                    self.stdout.write(
                        self.style.ERROR(
                            f"Póliza {poliza.id}: "
                            f"Meta rechazó el envío: "
                            f"{respuesta.text}"
                        )
                    )

            except Exception as error:
                errores += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"Póliza {poliza.id}: error: {error}"
                    )
                )

        self.stdout.write("")

        if simular:
            self.stdout.write(
                self.style.WARNING(
                    "MODO SIMULACIÓN: no se envió ningún mensaje."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enviados: {enviados}"
                )
            )

        self.stdout.write(
            f"Omitidos: {omitidos} | Errores: {errores}"
        )