(() => {
    const tipo = document.querySelector('[name="tipo_seguro"]');
    const vehiculo = document.querySelector('[name="vehiculo"]');
    const datos = document.getElementById('datos-ap');
    function actualizar() {
        const ap = tipo.value.toLowerCase() === 'accidentes personales';
        document.getElementById('riesgo-vehiculo').hidden = ap;
        vehiculo.disabled = ap;
        if (ap) vehiculo.value = '';
        datos.hidden = !ap;
        datos.querySelectorAll('input').forEach(input => {
            input.disabled = !ap;
            input.required = ap;
        });
        document.querySelector('[name="cobertura"]').required = ap;
    }
    tipo.addEventListener('change', actualizar);
    actualizar();
})();
