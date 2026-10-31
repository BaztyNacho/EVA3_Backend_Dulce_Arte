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

/* ---------- Ventana "Nueva ruta" (solo existe en la pantalla Despachos) ---------- */
const ventanaRuta = document.getElementById('ventana-ruta');
const errorRuta = document.getElementById('vr-error');
if (ventanaRuta) {

function mostrarErrorRuta(texto) {
  errorRuta.textContent = texto;
  errorRuta.hidden = !texto;
}

document.querySelectorAll('[data-abrir-ruta]').forEach((boton) => {
  boton.addEventListener('click', () => {
    mostrarErrorRuta('');
    ventanaRuta.showModal();
    document.getElementById('r-nombre').focus();
  });
});
ventanaRuta.querySelector('[data-cerrar]').addEventListener('click', () => ventanaRuta.close());
ventanaRuta.addEventListener('click', (evento) => { if (esClicFuera(evento, ventanaRuta)) ventanaRuta.close(); });

document.getElementById('form-ruta').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const nombre = document.getElementById('r-nombre').value.trim();
  const fecha = document.getElementById('r-fecha').value;
  if (!nombre || !fecha) { mostrarErrorRuta('Indica el nombre y la fecha de la ruta.'); return; }
  evento.submitter.disabled = true;
  const { ok, datos } = await llamarApi('/api/rutas/', { metodo: 'POST', json: { nombre, fecha } });
  evento.submitter.disabled = false;
  if (ok) recargarConAviso(`Ruta "${datos.nombre}" creada. Ahora agrégale pedidos desde "Por asignar".`);
  else mostrarErrorRuta(textosDeError(datos).join(' '));
});
}

/* ---------- Agregar un pedido a una ruta (queda como última parada) ---------- */
document.querySelectorAll('.tarjeta-despacho__asignar').forEach((form) => {
  form.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const select = form.querySelector('select');
    const rutaId = Number(select.value);
    // Si la ruta ya salió, el pedido queda directamente "En camino"
    const rutaEnCurso = select.selectedOptions[0].dataset.estado === 'en_curso';
    evento.submitter.disabled = true;
    const ruta = await llamarApi(`/api/rutas/${rutaId}/`);
    const orden = ruta.ok ? ruta.datos.despachos.length + 1 : 1;
    const { ok, datos } = await llamarApi(`/api/despachos/${form.dataset.despacho}/`, {
      metodo: 'PATCH',
      json: { ruta: rutaId, orden, estado: rutaEnCurso ? 'en_camino' : 'pendiente' },
    });
    evento.submitter.disabled = false;
    if (ok) recargarConAviso(`Pedido #${datos.pedido} agregado a ${datos.ruta_nombre} como parada ${orden}.`);
    else mostrarAviso(textosDeError(datos).join(' '), 'error');
  });
});

/* ---------- Quitar un pedido de su ruta ---------- */
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

/* ---------- Iniciar o finalizar una ruta ----------
 * Al iniciarla, sus despachos pendientes quedan "En camino". */
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
      recargarConAviso(`${datos.nombre} iniciada. Entrega cada parada con el botón "Entregar".`);
    } else {
      recargarConAviso(`${datos.nombre} finalizada. ¡Buen trabajo!`);
    }
  });
});
