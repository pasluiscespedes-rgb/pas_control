/* FORTEX Catálogo Maestro: selector progresivo y propuestas OCR, sin guardado automático. */
(() => {
  "use strict";
  const marca = document.getElementById("marca");
  const modelo = document.getElementById("modelo");
  const tipo = document.getElementById("tipo_vehiculo");
  const riesgo = document.getElementById("tipo_riesgo");
  const marcaManual = document.getElementById("marca_manual");
  const modeloManual = document.getElementById("modelo_manual");
  const buscar = document.getElementById("catalogo_buscar_modelo");
  const aviso = document.getElementById("catalogo_estado");
  const propuesta = document.getElementById("catalogo_propuesta_ocr");
  const modeloId = document.getElementById("modelo_catalogo_id");
  if (![marca, modelo, tipo, riesgo, marcaManual, modeloManual, buscar, aviso, propuesta, modeloId].every(Boolean)) return;

  let secuencia = 0;
  let temporizador;
  const normal = value => String(value || "").normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const opcion = (valor, texto, id = "") => {
    const o = new Option(texto, valor);
    if (id) o.dataset.catalogoId = String(id);
    return o;
  };
  const estado = mensaje => { aviso.textContent = mensaje; };
  const vaciar = () => {
    secuencia += 1;
    modelo.replaceChildren(opcion("", "Seleccione un modelo"), opcion("OTRO", "➕ Otro modelo / escribir manualmente"));
    modelo.value = "";
    modeloId.value = "";
    actualizarModeloManual();
  };
  function actualizarModeloManual() {
    const manual = modelo.value === "OTRO";
    modeloManual.style.display = manual ? "block" : "none";
    modeloManual.required = manual;
    if (!manual) modeloManual.value = "";
    modeloId.value = !manual ? (modelo.selectedOptions[0]?.dataset.catalogoId || "") : "";
  }
  function actualizarMarcaManual() {
    const manual = marca.value === "OTRA";
    marcaManual.style.display = manual ? "block" : "none";
    marcaManual.required = manual;
    if (!manual) marcaManual.value = "";
    buscar.disabled = !marca.value || manual;
  }
  function tipoDesdeDocumento(clase) {
    const v = normal(clase);
    if (v.includes("MOTO") || v.includes("SCOOTER") || v.includes("CICLOMOTOR")) return "Moto";
    if (v.includes("SEMIRREMOLQUE") || v.includes("ACOPLADO")) return "Acoplado";
    if (v.includes("TRAILER") || v.includes("REMOLQUE")) return "Tráiler";
    if (v.includes("CAMIONETA") || v.includes("PICKUP")) return "Camioneta";
    if (v.includes("FURGON") || v.includes("FURGONETA")) return "Furgón";
    if (v.includes("CAMION") || v.includes("TRACTOCAMION")) return "Camión";
    if (v.includes("AUTO") || v.includes("SEDAN") || v.includes("SUV")) return "Auto";
    return null;
  }
  function actualizarMarcasPorTipo() {
    if (riesgo.value === "Motocicleta") tipo.value = "Moto";
    else if (riesgo.value === "Automotor" && tipo.value === "Moto") tipo.value = "Auto";
    actualizarMarcaManual();
    vaciar();
    buscar.value = "";
    estado("Escribí al menos dos caracteres del modelo. También podés cargarlo manualmente.");
  }
  async function buscarModelos() {
    clearTimeout(temporizador);
    const esta = ++secuencia;
    const q = buscar.value.trim();
    vaciar();
    // vaciar() cambia el contador para invalidar peticiones previas.
    const token = secuencia;
    if (q.length < 2 || buscar.disabled) {
      estado("Escribí al menos dos caracteres para buscar.");
      return;
    }
    estado("Buscando modelos...");
    const url = new URL("/vehiculos/catalogo/buscar/", location.origin);
    url.searchParams.set("q", q);
    url.searchParams.set("marca", marca.value);
    url.searchParams.set("tipo", tipo.value);
    try {
      const respuesta = await fetch(url, {credentials: "same-origin", cache: "no-store"});
      if (!respuesta.ok) throw new Error("No se pudo consultar el catálogo");
      const data = await respuesta.json();
      if (token !== secuencia) return;
      for (const m of data.resultados || []) modelo.insertBefore(
        opcion(m.modelo, m.modelo + (m.anio_desde ? " (" + m.anio_desde + "–" + (m.anio_hasta || "?") + ")" : ""), m.id),
        modelo.options[modelo.options.length - 1]
      );
      estado(data.resultados?.length
        ? "Elegí el modelo de la lista. Si falta, usá «Otro modelo»."
        : "No encontramos ese modelo. Podés escribirlo manualmente sin bloquear el alta.");
    } catch (err) {
      if (token === secuencia) estado("Catálogo no disponible. Podés elegir «Otro modelo» y seguir.");
    }
  }
  function elegirModelo(m) {
    const marcaEncontrada = Array.from(marca.options).find(o => normal(o.value) === normal(m.marca));
    marca.value = marcaEncontrada?.value || "OTRA";
    actualizarMarcaManual();
    if (!marcaEncontrada) marcaManual.value = m.marca;
    if (Array.from(tipo.options).some(o => o.value === m.tipo)) tipo.value = m.tipo;
    buscar.disabled = !marcaEncontrada;
    buscar.value = m.modelo;
    vaciar();
    modelo.insertBefore(opcion(m.modelo, m.modelo, m.modelo_id || m.id), modelo.lastElementChild);
    modelo.value = m.modelo;
    actualizarModeloManual();
    propuesta.replaceChildren();
    estado("Modelo aplicado a la ficha. Revisá los datos antes de guardar.");
  }
  function proponer(mensaje, alternativas = []) {
    propuesta.replaceChildren();
    const p = document.createElement("p");
    p.textContent = mensaje;
    propuesta.appendChild(p);
    for (const item of alternativas.slice(0, 5)) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn-outline-primary btn-sm me-2 mb-2";
      b.textContent = "Confirmar " + item.marca + " " + item.modelo + " (" + item.tipo + ")";
      b.addEventListener("click", () => elegirModelo(item));
      propuesta.appendChild(b);
    }
  }
  async function fortexProponerOCR(datos) {
    const t = tipoDesdeDocumento(datos.tipo);
    if (t) {
      tipo.value = t;
      if (t === "Moto") riesgo.value = "Motocicleta";
      actualizarMarcasPorTipo();
      tipo.value = t;
    }
    const m = Array.from(marca.options).find(o => normal(o.value) === normal(datos.marca));
    marca.value = m?.value || "OTRA";
    actualizarMarcaManual();
    if (!m) marcaManual.value = datos.marca || "";
    buscar.value = String(datos.modelo || "");
    vaciar();
    // Conservar siempre un camino manual y editable para lo leído.
    modelo.value = "OTRO";
    actualizarModeloManual();
    modeloManual.value = datos.modelo || "";
    if (!datos.marca || !datos.modelo) {
      proponer("OCR incompleto: revisá marca y modelo manualmente.");
      return;
    }
    const url = new URL("/vehiculos/catalogo/sugerencias/", location.origin);
    url.searchParams.set("marca", datos.marca);
    url.searchParams.set("modelo", datos.modelo);
    if (t) url.searchParams.set("tipo", t);
    if (datos.anio) url.searchParams.set("anio", datos.anio);
    try {
      const response = await fetch(url, {credentials: "same-origin", cache: "no-store"});
      if (!response.ok) throw new Error("OCR sin verificación de catálogo");
      const d = await response.json();
      if (d.estado === "COINCIDENCIA") {
        proponer("El catálogo encontró una coincidencia exacta. Confirmá que coincida con la cédula.", d.opciones);
      } else {
        proponer("REVISAR: " + (d.motivo || "Sin coincidencia segura") + ". Podés confirmar una opción o mantener la carga manual.", d.opciones || []);
      }
    } catch (_) {
      proponer("REVISAR: no se pudo consultar el catálogo. El texto OCR quedó editable para revisión.");
    }
  }
  marca.addEventListener("change", () => {
    actualizarMarcaManual(); vaciar(); buscar.value = "";
  });
  riesgo.addEventListener("change", actualizarMarcasPorTipo);
  tipo.addEventListener("change", () => { vaciar(); buscar.value = ""; });
  modelo.addEventListener("change", actualizarModeloManual);
  buscar.addEventListener("input", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(buscarModelos, 250);
  });
  // Restauración de un formulario que volvió por errores de validación.
  const marcaPrevia = marca.dataset.previo;
  const modeloPrevio = modelo.dataset.previo;
  if (marcaPrevia) {
    const m = Array.from(marca.options).find(o => o.value === marcaPrevia);
    marca.value = m ? m.value : "OTRA";
    actualizarMarcaManual();
    if (!m) marcaManual.value = marcaPrevia;
  } else actualizarMarcaManual();
  vaciar();
  if (modeloPrevio) {
    modelo.value = "OTRO";
    actualizarModeloManual();
    modeloManual.value = modeloPrevio;
    buscar.value = modeloPrevio;
  }
  window.fortexProponerOCR = fortexProponerOCR;
})();