/*
 * Despachos: crear rutas, asignar despachos y cambiar el estado de las rutas.
 * Usa /api/rutas/ y /api/despachos/.
 */

function recargarConAviso(texto) {
  try { sessionStorage.setItem('aviso', texto); } catch (e) { /* sin almacenamiento */ }
  window.location.reload();
}

try {
  const pendiente = sessionStorage.getItem('aviso');
  if (pendiente) {
    sessionStorage.removeItem('aviso');
    mostrarAviso(pendiente, 'success');
  }
} catch (e) { /* sin almacenamiento */ }

// Crear ruta
document.getElementById('form-ruta').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const nombre = document.getElementById('r-nombre').value.trim();
  const fecha = document.getElementById('r-fecha').value;
  if (!nombre || !fecha) { mostrarAviso('Indica el nombre y la fecha de la ruta.', 'error'); return; }
  const { ok, datos } = await llamarApi('/api/rutas/', { metodo: 'POST', json: { nombre, fecha } });
  if (ok) recargarConAviso(`Ruta "${datos.nombre}" creada.`);
  else mostrarAviso(textosDeError(datos).join(' '), 'error');
});

// Asignar un despacho a una ruta (queda al final de la ruta)
document.querySelectorAll('.parada__asignar').forEach((form) => {
  form.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const rutaId = Number(form.querySelector('select').value);
    const ruta = await llamarApi(`/api/rutas/${rutaId}/`);
    const orden = ruta.ok ? ruta.datos.despachos.length + 1 : 1;
    const { ok, datos } = await llamarApi(`/api/despachos/${form.dataset.despacho}/`, {
      metodo: 'PATCH',
      json: { ruta: rutaId, orden, estado: 'pendiente' },
    });
    if (ok) recargarConAviso(`Pedido #${datos.pedido} asignado a ${datos.ruta_nombre} como parada ${orden}.`);
    else mostrarAviso(textosDeError(datos).join(' '), 'error');
  });
});

// Quitar un despacho de su ruta
document.querySelectorAll('[data-quitar]').forEach((boton) => {
  boton.addEventListener('click', async () => {
    const { ok, datos } = await llamarApi(`/api/despachos/${boton.dataset.quitar}/`, {
      metodo: 'PATCH',
      json: { ruta: null, estado: 'pendiente' },
    });
    if (ok) recargarConAviso(`Pedido #${datos.pedido} volvió a "Por asignar".`);
    else mostrarAviso(textosDeError(datos).join(' '), 'error');
  });
});

// Iniciar o finalizar una ruta. Al iniciarla, sus despachos pendientes quedan "En camino".
document.querySelectorAll('[data-ruta-estado]').forEach((boton) => {
  boton.addEventListener('click', async () => {
    const id = boton.dataset.ruta;
    const nuevoEstado = boton.dataset.rutaEstado;
    boton.disabled = true;
    const { ok, datos } = await llamarApi(`/api/rutas/${id}/`, { metodo: 'PATCH', json: { estado: nuevoEstado } });
    if (!ok) { mostrarAviso(textosDeError(datos).join(' '), 'error'); boton.disabled = false; return; }
    if (nuevoEstado === 'en_curso') {
      for (const despacho of datos.despachos.filter((d) => d.estado === 'pendiente')) {
        await llamarApi(`/api/despachos/${despacho.id}/`, { metodo: 'PATCH', json: { estado: 'en_camino' } });
      }
      recargarConAviso(`${datos.nombre} iniciada. Sus despachos están en camino.`);
    } else {
      recargarConAviso(`${datos.nombre} finalizada.`);
    }
  });
});
