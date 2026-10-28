/*
 * Bodega: registrar entradas y mermas con POST /api/movimientos-insumo/
 * Dos formas de hacerlo:
 *   1. Botón "Añadir" de cada tarjeta: abre una ventana con el insumo ya elegido.
 *   2. Formulario lateral (acceso rápido): se elige el insumo de la lista.
 * El servidor valida todo (por ejemplo, que una merma no deje el stock negativo).
 */

// Aviso pendiente después de recargar la página
try {
  const pendiente = sessionStorage.getItem('aviso');
  if (pendiente) {
    sessionStorage.removeItem('aviso');
    mostrarAviso(pendiente, 'success');
  }
} catch (e) { /* sin almacenamiento */ }

/** Envía el movimiento a la API. Si sale bien, recarga para ver el stock nuevo. */
async function registrarMovimiento({ insumo, tipo, cantidad, motivo }, boton) {
  boton.disabled = true;
  const { ok, datos } = await llamarApi('/api/movimientos-insumo/', {
    metodo: 'POST',
    json: { insumo: Number(insumo), tipo, cantidad, motivo },
  });
  boton.disabled = false;
  if (ok) {
    try { sessionStorage.setItem('aviso', `Movimiento registrado: ${datos.tipo_display}, ${Number(datos.cantidad).toLocaleString('es-CL')} de ${datos.insumo_nombre}.`); } catch (e) { /* sin almacenamiento */ }
    window.location.reload();
    return null;
  }
  return textosDeError(datos).join(' ');
}

const EJEMPLOS_MOTIVO = { entrada: 'Ej.: compra a proveedor', ajuste: 'Ej.: producto vencido' };

/* ---------- 1. Ventana del botón "Añadir" ---------- */
const ventana = document.getElementById('ventana-movimiento');
const formVentana = document.getElementById('form-ventana');
const vmTipo = document.getElementById('vm-tipo');
const vmCantidad = document.getElementById('vm-cantidad');
const vmMotivo = document.getElementById('vm-motivo');
const vmError = document.getElementById('vm-error');
let insumoElegido = null;

function mostrarErrorVentana(texto) {
  vmError.textContent = texto;
  vmError.hidden = !texto;
}

document.querySelectorAll('[data-abrir-movimiento]').forEach((boton) => {
  boton.addEventListener('click', () => {
    insumoElegido = boton.dataset.insumo;
    document.getElementById('vm-titulo').textContent = boton.dataset.nombre;
    document.getElementById('vm-detalle').textContent = `Stock actual: ${boton.dataset.stock} ${boton.dataset.unidad}`;
    document.getElementById('vm-unidad').textContent = boton.dataset.unidad;
    formVentana.reset();
    vmMotivo.placeholder = EJEMPLOS_MOTIVO.entrada;
    mostrarErrorVentana('');
    ventana.showModal();          // <dialog> nativo: foco dentro y Escape para cerrar
    vmCantidad.focus();
  });
});

vmTipo.addEventListener('change', () => { vmMotivo.placeholder = EJEMPLOS_MOTIVO[vmTipo.value]; });
ventana.querySelector('[data-cerrar]').addEventListener('click', () => ventana.close());
// Clic fuera de la ventana (en el fondo oscuro) también la cierra
ventana.addEventListener('click', (evento) => { if (evento.target === ventana) ventana.close(); });

formVentana.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  if (!(Number(vmCantidad.value) > 0)) {
    mostrarErrorVentana('Ingresa una cantidad mayor que cero.');
    vmCantidad.focus();
    return;
  }
  const error = await registrarMovimiento({
    insumo: insumoElegido,
    tipo: vmTipo.value,
    cantidad: vmCantidad.value,
    motivo: vmMotivo.value.trim(),
  }, evento.submitter);
  if (error) mostrarErrorVentana(error);   // el error se muestra dentro de la ventana
});

/* ---------- 2. Formulario lateral (acceso rápido) ---------- */
const mTipo = document.getElementById('m-tipo');
mTipo.addEventListener('change', () => { document.getElementById('m-motivo').placeholder = EJEMPLOS_MOTIVO[mTipo.value]; });

document.getElementById('form-movimiento').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const insumo = document.getElementById('m-insumo');
  const cantidad = document.getElementById('m-cantidad');
  if (!insumo.value) { mostrarAviso('Elige el insumo.', 'error'); insumo.focus(); return; }
  if (!(Number(cantidad.value) > 0)) { mostrarAviso('Ingresa una cantidad mayor que cero.', 'error'); cantidad.focus(); return; }

  const error = await registrarMovimiento({
    insumo: insumo.value,
    tipo: mTipo.value,
    cantidad: cantidad.value,
    motivo: document.getElementById('m-motivo').value.trim(),
  }, evento.submitter);
  if (error) mostrarAviso(error, 'error');
});
