const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('AP limpia y deshabilita vehículo; automotor y moto recuperan el selector', () => {
  const inputs = [{}, {}, {}];
  let changed;
  const tipo = {value: 'Automotor', addEventListener: (_, fn) => changed = fn};
  const vehiculo = {value: '123'};
  const datos = {querySelectorAll: () => inputs};
  const riesgo = {};
  const cobertura = {};
  const document = {
    querySelector: (selector) => selector.includes('tipo_seguro') ? tipo : selector.includes('vehiculo') ? vehiculo : cobertura,
    getElementById: (id) => id === 'datos-ap' ? datos : riesgo,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../principal/static/principal/js/poliza_ap.js'), 'utf8'), { document });
  assert.equal(vehiculo.value, '123');
  assert.equal(vehiculo.disabled, false);
  tipo.value = 'Accidentes Personales';
  changed();
  assert.equal(vehiculo.value, '');
  assert.equal(vehiculo.disabled, true);
  assert.equal(riesgo.hidden, true);
  assert.equal(datos.hidden, false);
  assert.equal(cobertura.required, true);
  assert.ok(inputs.every(input => input.required && !input.disabled));
  tipo.value = 'Moto';
  changed();
  assert.equal(vehiculo.disabled, false);
  assert.equal(riesgo.hidden, false);
  assert.equal(datos.hidden, true);
  assert.ok(inputs.every(input => !input.required && input.disabled));
});
