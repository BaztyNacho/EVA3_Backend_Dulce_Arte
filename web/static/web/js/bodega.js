/*
 * Bodega: registrar entradas y mermas con POST /api/movimientos-insumo/
 */

try {
  const pendiente = sessionStorage.getItem('aviso');
  if (pendiente) {
    sessionStorage.removeItem('aviso');
    mostrarAviso(pendiente, 'success');
  }
} catch (e) { /* sin almacenamiento */ }

document.getElementById('form-movimiento').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const insumo = document.getElementById('m-insumo');
  const cantidad = document.getElementById('m-cantidad');
  if (!insumo.value) { mostrarAviso('Elige el insumo.', 'error'); insumo.focus(); return; }
  if (!(Number(cantidad.value) > 0)) { mostrarAviso('Ingresa una cantidad mayor que cero.', 'error'); cantidad.focus(); return; }

  const boton = evento.submitter;
  boton.disabled = true;
  const { ok, datos } = await llamarApi('/api/movimientos-insumo/', {
    metodo: 'POST',
    json: {
      insumo: Number(insumo.value),
      tipo: document.getElementById('m-tipo').value,
      cantidad: cantidad.value,
      motivo: document.getElementById('m-motivo').value.trim(),
    },
  });
  boton.disabled = false;
  if (ok) {
    try { sessionStorage.setItem('aviso', `Movimiento registrado: ${datos.tipo_display}, ${datos.cantidad} de ${datos.insumo_nombre}.`); } catch (e) { /* sin almacenamiento */ }
    window.location.reload();
  } else {
    mostrarAviso(textosDeError(datos).join(' '), 'error');
  }
});
