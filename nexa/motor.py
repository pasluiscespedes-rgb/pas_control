import unicodedata
import re
from datetime import datetime, timedelta

from django.utils import timezone
from clientes.models import Cliente
from vehiculos.models import Vehiculo

from .models import InteraccionNexa
from .servicios import obtener_contexto_cliente


def _normalizar(texto):
    texto = (texto or "").lower().strip()

    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )

def _solo_digitos(valor):
    return "".join(
        caracter
        for caracter in str(valor or "")
        if caracter.isdigit()
    )


def _normalizar_patente(valor):
    return "".join(
        caracter
        for caracter in str(valor or "").upper()
        if caracter.isalnum()
    )

def _extraer_datos_verificacion(texto):
    texto = str(texto or "").upper()

    coincidencia_dni = re.search(
        r"\bDNI\s*[:\-]?\s*(\d{7,8})\b",
        texto,
    )

    coincidencia_patente = re.search(
        r"\bPATENTE\s*[:\-]?\s*([A-Z0-9]{6,7})\b",
        texto,
    )

    if (
        coincidencia_dni is None
        or coincidencia_patente is None
    ):
        return None, None

    return (
        coincidencia_dni.group(1),
        coincidencia_patente.group(1),
    )


def _verificar_cliente_por_dni_patente(
    dni,
    patente,
):
    dni_limpio = _solo_digitos(dni)
    patente_limpia = _normalizar_patente(patente)

    if not dni_limpio or not patente_limpia:
        return None

    cliente = Cliente.objects.filter(
        dni=dni_limpio,
    ).first()

    if cliente is None:
        return None

    vehiculos = Vehiculo.objects.filter(
        cliente=cliente,
    )

    for vehiculo in vehiculos:
        if (
            _normalizar_patente(vehiculo.patente)
            == patente_limpia
        ):
            return cliente

    return None

def _seleccionar_poliza(polizas, texto):
    """
    Selecciona una póliza cuando el cliente tiene varias.

    Puede identificarla por:
    - número de póliza
    - patente del vehículo
    """

    if not polizas:
        return None

    if len(polizas) == 1:
        return polizas[0]

    texto_normalizado = _normalizar(texto)
    texto_compacto = (
        texto_normalizado
        .replace(" ", "")
        .replace("-", "")
    )

    for poliza in polizas:
        numero_poliza = _normalizar(
            poliza.get("numero_poliza") or ""
        )

        numero_compacto = (
            numero_poliza
            .replace(" ", "")
            .replace("-", "")
        )

        vehiculo = poliza.get("vehiculo") or {}

        patente = _normalizar(
            vehiculo.get("patente") or ""
        )

        patente_compacta = (
            patente
            .replace(" ", "")
            .replace("-", "")
        )

        if (
            numero_compacto
            and numero_compacto in texto_compacto
        ):
            return poliza

        if (
            patente_compacta
            and patente_compacta in texto_compacto
        ):
            return poliza

    return None

def _obtener_interaccion_pendiente(
    cliente,
    conversacion=None,
):
    pendientes = InteraccionNexa.objects.filter(
        estado="pendiente",
        motivo_escalamiento=(
            "Esperando identificación de póliza."
        ),
    )

    if conversacion is not None:
        pendientes = pendientes.filter(
            conversacion_whatsapp=conversacion,
        )
    else:
        pendientes = pendientes.filter(
            canal="interno",
            datos_consultados__cliente_id=cliente.id,
        )

    return pendientes.order_by(
        "-creada_en"
    ).first()

def _obtener_verificacion_identidad_pendiente(
    conversacion,
):
    if conversacion is None:
        return None

    return (
        InteraccionNexa.objects
        .filter(
            estado="pendiente",
            motivo_escalamiento=(
                "Esperando verificación de identidad."
            ),
            conversacion_whatsapp=conversacion,
            tipo_interlocutor="cliente_no_verificado",
        )
        .order_by("-creada_en")
        .first()
    )

def _obtener_cliente_verificado_temporal(
    conversacion,
):
    if conversacion is None:
        return None

    limite = timezone.now() - timedelta(
        minutes=30
    )

    interaccion = (
        InteraccionNexa.objects
        .filter(
            conversacion_whatsapp=conversacion,
            tipo_interlocutor="cliente",
            identidad_verificada=True,
            creada_en__gte=limite,
        )
        .order_by("-creada_en")
        .first()
    )

    if interaccion is None:
        return None

    cliente_id = (
        interaccion.datos_consultados
        or {}
    ).get("cliente_id")

    if not cliente_id:
        return None

    return Cliente.objects.filter(
        id=cliente_id,
    ).first()

def _obtener_viaje_pendiente(
    cliente,
    conversacion=None,
):
    pendientes = InteraccionNexa.objects.filter(
        estado="pendiente",
        motivo_escalamiento="Esperando destino de viaje.",
    )

    if conversacion is not None:
        pendientes = pendientes.filter(
            conversacion_whatsapp=conversacion,
        )
    else:
        pendientes = pendientes.filter(
            canal="interno",
            datos_consultados__cliente_id=cliente.id,
        )

    return pendientes.order_by(
        "-creada_en"
    ).first()


def _fecha_argentina(fecha_iso):
    if not fecha_iso:
        return None

    fecha = datetime.fromisoformat(fecha_iso)

    return fecha.strftime("%d/%m/%Y")


def _importe_argentino(valor):
    if valor in (None, ""):
        return None

    numero = float(valor)

    return (
        f"${numero:,.0f}"
        .replace(",", ".")
    )


def _guardar_interaccion(
    cliente,
    consulta,
    respuesta,
    estado="respondida",
    requiere_revision=False,
    motivo="",
    conversacion=None,
    datos_extra=None,
    tipo_interlocutor="desconocido",
    identidad_verificada=False,
    respuesta_bloqueada_privacidad=False,
    motivo_bloqueo_privacidad="",
):
    if (
        tipo_interlocutor == "desconocido"
        and cliente is not None
        and conversacion is not None
    ):
        tipo_interlocutor = "cliente"
        identidad_verificada = True
    datos = {}

    if cliente is not None:
        datos["cliente_id"] = cliente.id

    if datos_extra:
        datos.update(datos_extra)

    return InteraccionNexa.objects.create(
        canal=(
            "whatsapp"
            if conversacion
            else "interno"
        ),
        conversacion_whatsapp=conversacion,
        consulta=consulta,
        respuesta=respuesta,
        estado=estado,
        tipo_interlocutor=tipo_interlocutor,
        identidad_verificada=identidad_verificada,
        respuesta_bloqueada_privacidad=(
            respuesta_bloqueada_privacidad
        ),
        motivo_bloqueo_privacidad=(
            motivo_bloqueo_privacidad
        ),
        requiere_revision_humana=requiere_revision,
        motivo_escalamiento=motivo,
        datos_consultados=datos,
        respondida_en=timezone.now(),
    )

def responder_consulta_no_vinculada(
    consulta,
    conversacion=None,
):
    texto = _normalizar(consulta)

    cliente_temporal = (
        _obtener_cliente_verificado_temporal(
            conversacion
        )
    )

    if cliente_temporal is not None:
        return responder_consulta_cliente(
            cliente=cliente_temporal,
            consulta=consulta,
            conversacion=conversacion,
        )

    pendiente_verificacion = (
        _obtener_verificacion_identidad_pendiente(
        conversacion
        )
    )

    if pendiente_verificacion is not None:
        dni, patente = _extraer_datos_verificacion(
            consulta
        )

        if not dni or not patente:
            respuesta = (
                "Para verificar tu identidad necesito que "
                "indiques ambos datos con este formato: "
                "DNI 12345678 PATENTE AB123CD."
            )

            _guardar_interaccion(
                cliente=None,
                consulta="Verificación de identidad incompleta.",
                respuesta=respuesta,
                estado="pendiente",
                motivo="Esperando verificación de identidad.",
                conversacion=conversacion,
                tipo_interlocutor="cliente_no_verificado",
                identidad_verificada=False,
            )

            return respuesta

        cliente_verificado = (
            _verificar_cliente_por_dni_patente(
                dni,
                patente,
            )
        )

        if cliente_verificado is None:
            respuesta = (
                "No pude verificar la identidad con los "
                "datos ingresados. Revisalos e intentá "
                "nuevamente. Por seguridad no puedo "
                "confirmar cuál de los datos no coincide."
            )

            _guardar_interaccion(
                cliente=None,
                consulta="Intento de verificación de identidad.",
                respuesta=respuesta,
                estado="pendiente",
                motivo="Esperando verificación de identidad.",
                conversacion=conversacion,
                tipo_interlocutor="cliente_no_verificado",
                identidad_verificada=False,
            )

            return respuesta

        pendiente_verificacion.estado = "respondida"
        pendiente_verificacion.respondida_en = timezone.now()
        pendiente_verificacion.save(
            update_fields=[
                "estado",
                "respondida_en",
            ]
        )

        respuesta = (
            "Identidad verificada correctamente. "
            "Ya puedo continuar atendiéndote como "
            "cliente de FORTEX."
        )

        _guardar_interaccion(
            cliente=cliente_verificado,
            consulta="Verificación de identidad completada.",
            respuesta=respuesta,
            estado="respondida",
            conversacion=conversacion,
            tipo_interlocutor="cliente",
            identidad_verificada=True,
        )

        return respuesta

    frases_tercero = (
        "soy tercero",
        "soy un tercero",
        "me choco un asegurado",
        "me choco uno de sus asegurados",
        "tuve un accidente con un asegurado",
        "tuve un siniestro con un asegurado",
    )

    frases_cliente = (
        "soy asegurado",
        "soy cliente",
        "tengo una poliza",
        "mi poliza",
        "soy asegurado de fortex",
    )

    if any(
        frase in texto
        for frase in frases_tercero
    ):
        tipo_interlocutor = "tercero"
        motivo = "Esperando datos de siniestro de tercero."

        respuesta = (
            "Hola. Soy NEXA, asistente de FORTEX. "
            "Puedo ayudarte como tercero involucrado "
            "en un siniestro. "
            "Para iniciar la gestión, indicame tu "
            "nombre y apellido, la fecha del hecho, "
            "la patente del vehículo asegurado si la "
            "conocés y una breve descripción de lo "
            "ocurrido. "
            "Por seguridad, no brindaré datos "
            "personales ni información privada de "
            "nuestros asegurados."
        )

    elif any(
        frase in texto
        for frase in frases_cliente
    ):
        tipo_interlocutor = "cliente_no_verificado"
        motivo = "Esperando verificación de identidad."

        respuesta = (
            "Hola. Soy NEXA, asistente de FORTEX. "
            "Este número no está asociado actualmente "
            "a un cliente registrado. "
            "Si sos asegurado nuestro, puedo ayudarte. "
            "Para localizar tu registro y verificar "
            "tu identidad, indicame tu DNI y la patente "
            "del vehículo asegurado. "
            "No voy a mostrar ni confirmar datos "
            "privados hasta completar la verificación."
        )

    else:
        tipo_interlocutor = "desconocido"
        motivo = "Esperando identificación de interlocutor."

        respuesta = (
            "Hola. Soy NEXA, asistente de FORTEX. "
            "No tengo este número asociado a un cliente "
            "registrado. Para poder ayudarte, indicame "
            "si sos asegurado nuestro, un tercero "
            "involucrado en un siniestro o si realizás "
            "otra consulta."
        )

    _guardar_interaccion(
        cliente=None,
        consulta=consulta,
        respuesta=respuesta,
        estado="pendiente",
        motivo=motivo,
        conversacion=conversacion,
        tipo_interlocutor=tipo_interlocutor,
        identidad_verificada=False,
    )

    return respuesta

def responder_consulta_cliente(
    cliente,
    consulta,
    conversacion=None,
):
    """
    Primer motor seguro de NEXA.

    NEXA solamente responde con información
    encontrada realmente en FORTEX.

    Si no tiene certeza, deriva.
    """

    contexto = obtener_contexto_cliente(cliente)

    polizas = contexto["polizas"]

    texto = _normalizar(consulta)

    if not polizas:
        respuesta = (
            "No encuentro una póliza activa registrada "
            "a su nombre en FORTEX. "
            "Voy a derivar la consulta a un operador."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            estado="derivada",
            requiere_revision=True,
            motivo="Cliente sin póliza activa disponible.",
            conversacion=conversacion,
        )

        return respuesta

    poliza = _seleccionar_poliza(
        polizas,
        consulta,
    )

    viaje_pendiente = _obtener_viaje_pendiente(
    cliente,
    conversacion,
    )

    paises = [
        "bolivia",
        "brasil",
        "chile",
        "paraguay",
        "peru",
        "uruguay",
    ]

    if (
        poliza is None
        and viaje_pendiente is not None
        and any(pais in texto for pais in paises)
    ):
        datos_viaje = (
            viaje_pendiente.datos_consultados
            or {}
        )

        poliza_id = datos_viaje.get(
            "poliza_id"
        )

        poliza = next(
            (
                item
                for item in polizas
                if item["id"] == poliza_id
            ),
            None,
        )

        if poliza is not None:
            viaje_pendiente.estado = "respondida"
            viaje_pendiente.respondida_en = timezone.now()

            viaje_pendiente.save(
                update_fields=[
                    "estado",
                    "respondida_en",
                ]
            )

    pendiente = _obtener_interaccion_pendiente(
    cliente,
    conversacion,
    )

    if poliza is not None and pendiente is not None:

        consulta_contextual = (
            f"{pendiente.consulta} {consulta}"
        )

        texto = _normalizar(
            consulta_contextual
        )

        datos_pendientes = dict(
            pendiente.datos_consultados or {}
        )

        datos_pendientes["poliza_id"] = poliza["id"]
        pendiente.datos_consultados = datos_pendientes
        pendiente.estado = "respondida"
        pendiente.respondida_en = timezone.now()

        pendiente.save(
            update_fields=[
                "datos_consultados",
                "estado",
                "respondida_en",
            ]
        )

    if poliza is None:
        opciones = []

        for item in polizas:
            vehiculo = item.get("vehiculo") or {}

            patente = (
                vehiculo.get("patente")
                or "SIN PATENTE"
            )

            numero = (
                item.get("numero_poliza")
                or "SIN NÚMERO"
            )

            opciones.append(
                f"{patente} - póliza {numero}"
            )

        respuesta = (
            "Tiene más de una póliza registrada en FORTEX. "
            "Indíqueme la patente del vehículo o el número "
            "de póliza sobre el que desea consultar. "
            "Opciones: "
            + "; ".join(opciones)
            + "."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            estado="pendiente",
            requiere_revision=False,
            motivo="Esperando identificación de póliza.",
            conversacion=conversacion,
        )

        return respuesta

    numero_poliza = (
        poliza["numero_poliza"]
        or "sin número registrado"
    )

    compania = (
        poliza["compania"]
        or "sin compañía registrada"
    )

    # ==========================================
    # COBERTURA
    # ==========================================

    if any(
        palabra in texto
        for palabra in [
            "cobertura",
            "que cubre",
            "estoy cubierto",
            "seguro tengo",
        ]
    ):
        cobertura = poliza["cobertura"]

        if cobertura:
            respuesta = (
                f"Su póliza {numero_poliza}, "
                f"de {compania}, tiene registrada "
                f"la cobertura: {cobertura}."
            )

            _guardar_interaccion(
                cliente,
                consulta,
                respuesta,
                conversacion=conversacion,
            )

            return respuesta

        respuesta = (
            "La póliza está registrada en FORTEX, "
            "pero todavía no tiene cargado el detalle "
            "de cobertura. Voy a derivar la consulta "
            "a un operador para evitar darle información "
            "incorrecta."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            estado="derivada",
            requiere_revision=True,
            motivo="Cobertura no cargada.",
            conversacion=conversacion,
        )

        return respuesta

    # ==========================================
    # CUOTA / VENCIMIENTO / PAGO
    # ==========================================

    if any(
        palabra in texto
        for palabra in [
            "cuota",
            "pagar",
            "pago",
            "vence",
            "vencimiento",
            "debo",
        ]
    ):
        cuota = poliza["proxima_cuota"]

        vencimiento = _fecha_argentina(
            poliza["proximo_vencimiento"]
        )

        importe = _importe_argentino(
            poliza["importe_cuota"]
        )

        if cuota is None:
            respuesta = (
                f"La póliza {numero_poliza} no tiene "
                "cuotas pendientes registradas en FORTEX."
            )

        else:
            partes = [
                f"La próxima cuota registrada es la Nº {cuota}."
            ]

            if vencimiento:
                partes.append(
                    f"Vence el {vencimiento}."
                )

            if importe:
                partes.append(
                    f"El importe registrado es {importe}."
                )

            respuesta = " ".join(partes)

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            conversacion=conversacion,
        )

        return respuesta

    # ==========================================
    # RENOVACIÓN
    # ==========================================

    if any(
        palabra in texto
        for palabra in [
            "renovacion",
            "renovar",
            "vigencia",
            "cuando termina",
        ]
    ):
        fecha_fin = _fecha_argentina(
            poliza["fecha_fin_vigencia"]
        )

        if fecha_fin:
            respuesta = (
                f"La vigencia registrada de la póliza "
                f"{numero_poliza} finaliza el "
                f"{fecha_fin}. "
                "FORTEX puede revisar su renovación "
                "antes de esa fecha."
            )

        else:
            respuesta = (
                "No encuentro una fecha de fin de vigencia "
                "confiable para esta póliza. "
                "Voy a derivar la consulta a un operador."
            )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            estado=(
                "respondida"
                if fecha_fin
                else "derivada"
            ),
            requiere_revision=not bool(fecha_fin),
            motivo=(
                ""
                if fecha_fin
                else "Falta fecha de fin de vigencia."
            ),
            conversacion=conversacion,
        )

        return respuesta

    # ==========================================
    # VIAJES / COBERTURA MERCOSUR
    # ==========================================

    if any(
        frase in texto
        for frase in [
            "viajar",
            "viaje",
            "mercosur",
            "cruzar la frontera",
            "salir del pais",
            "bolivia",
            "brasil",
            "chile",
            "paraguay",
            "peru",
            "uruguay",
        ]
    ):
        tipo_seguro = _normalizar(
            poliza["tipo_seguro"]
        )

        compania_normalizada = _normalizar(
            poliza["compania"]
        )

        if tipo_seguro not in [
            "automotor",
            "moto",
        ]:
            respuesta = (
                "La cobertura Mercosur corresponde a pólizas "
                "de Automotor o Moto. Voy a derivar su consulta "
                "para verificar su caso."
            )

            _guardar_interaccion(
                cliente,
                consulta,
                respuesta,
                estado="derivada",
                requiere_revision=True,
                motivo="Consulta Mercosur fuera de Automotor/Moto.",
                conversacion=conversacion,
            )

            return respuesta

        paises_por_compania = {}

        if "mercantil" in compania_normalizada:
            paises_por_compania = {
                "brasil",
                "paraguay",
                "uruguay",
            }

        elif "providencia" in compania_normalizada:
            paises_por_compania = {
                "bolivia",
                "brasil",
                "chile",
                "paraguay",
                "uruguay",
            }

        elif "san cristobal" in compania_normalizada:
            paises_por_compania = {
                "bolivia",
                "brasil",
                "chile",
                "paraguay",
                "peru",
                "uruguay",
            }

        destino = None

        for pais in [
            "argentina",
            "bolivia",
            "brasil",
            "chile",
            "paraguay",
            "peru",
            "uruguay",
        ]:
            if pais in texto:
                destino = pais
                break

        if not paises_por_compania:
            respuesta = (
                "La póliza corresponde a Automotor o Moto, "
                "pero todavía no tengo configurados en NEXA "
                "los países de cobertura Mercosur para esta compañía. "
                "Voy a derivar la consulta para verificarlo."
            )

            _guardar_interaccion(
                cliente,
                consulta,
                respuesta,
                estado="derivada",
                requiere_revision=True,
                motivo="Compañía sin tabla Mercosur configurada.",
                conversacion=conversacion,
            )

            return respuesta

        if not destino:
            respuesta = (
                "Su póliza cuenta con cobertura Mercosur. "
                "Indíqueme a qué país desea viajar para poder "
                "confirmarle si figura dentro de la cobertura."
            )

            _guardar_interaccion(
                cliente,
                consulta,
                respuesta,
                estado="pendiente",
                requiere_revision=False,
                motivo="Esperando destino de viaje.",
                conversacion=conversacion,
                datos_extra={
                    "poliza_id": poliza["id"],
                },
            )

            return respuesta

        if destino in paises_por_compania:
            respuesta = (
                f"Sí, puede viajar a {destino.title()}. "
                "Ese país figura dentro de la cobertura Mercosur "
                "registrada para su aseguradora. "
                "Voy a derivar la consulta para que podamos enviarle "
                "una copia del certificado y así lo tenga disponible "
                "al momento de cruzar la frontera."
            )

            _guardar_interaccion(
                cliente,
                consulta,
                respuesta,
                estado="derivada",
                requiere_revision=True,
                motivo="Enviar certificado Mercosur al asegurado.",
                conversacion=conversacion,
            )

            return respuesta

        respuesta = (
            f"No tengo registrado a {destino.title()} dentro de "
            "los países que figuran en la constancia Mercosur "
            "de esta aseguradora. Voy a derivar la consulta "
            "para verificarlo antes de darle una respuesta definitiva."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            estado="derivada",
            requiere_revision=True,
            motivo="Destino no incluido en tabla Mercosur configurada.",
            conversacion=conversacion,
        )

        return respuesta
    
    # ==========================================
    # DOCUMENTACIÓN PARA CARGAR SINIESTRO
    # ==========================================

    if any(
        frase in texto
        for frase in [
            "documentacion",
            "documentos",
            "que tengo que enviar",
            "que debo enviar",
            "que necesito para cargar",
            "cargar el siniestro",
            "presentar el siniestro",
        ]
    ):
        respuesta = (
            "Para cargar un siniestro automotor en FORTEX "
            "debe enviarnos: cédula verde frente y dorso; "
            "DNI del titular; registro de conducir frente y dorso; "
            "fotos de los daños donde se vea claramente la patente; "
            "presupuesto de reparación; y croquis del siniestro. "
            "Si quien conducía no era el asegurado, también debe enviar "
            "el DNI y el carnet de conducir de esa persona. "
            "Si hubo lesionados o robo, debe incluir la denuncia policial "
            "y los datos del juzgado o fiscalía interviniente. "
            "El siniestro debe denunciarse dentro de los 3 días "
            "de conocido el hecho."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            conversacion=conversacion,
        )

        return respuesta

    # ==========================================
    # QUÉ HACER EN EL MOMENTO DEL SINIESTRO
    # ==========================================

    if any(
        palabra in texto
        for palabra in [
            "siniestro",
            "choque",
            "accidente",
            "me chocaron",
            "choque a",
            "robo",
            "que hago",
        ]
    ):
        respuesta = (
            "Si acaba de tener un accidente, procure obtener "
            "en el lugar los siguientes datos: "
            "del conductor, nombre, dirección, teléfono y registro; "
            "del vehículo, marca, patente, propietario y teléfono; "
            "y de los terceros involucrados, nombre, dirección y teléfono. "
            "También es importante realizar la denuncia policial "
            "a la brevedad. "
            "No realice acuerdos ni transacciones con terceros. "
            "Luego comuníquese con FORTEX para continuar "
            "con la gestión del siniestro."
        )

        _guardar_interaccion(
            cliente,
            consulta,
            respuesta,
            conversacion=conversacion,
        )

        return respuesta

    # ==========================================
    # NO SABE / ESCALAMIENTO
    # ==========================================

    respuesta = (
        "No tengo información suficiente para responder "
        "esa consulta con seguridad. "
        "La voy a derivar para revisión."
    )

    _guardar_interaccion(
        cliente,
        consulta,
        respuesta,
        estado="escalada",
        requiere_revision=True,
        motivo="Consulta no reconocida por NEXA.",
        conversacion=conversacion,
    )

    return respuesta