/*
 * Tablero Kanban de cocina.
 * - Carga los pedidos desde GET /api/pedidos/kanban/
 * - Cada cambio de etapa (arrastrando o con los botones) se confirma primero
 *   en una ventana que detalla el pedido y la etapa nueva.
 * - Avanzar: POST /api/pedidos/<id>/avanzar/
 * - Rechazar en Control de Calidad: POST /api/pedidos/<id>/rechazar-calidad/
 * Las reglas (no saltarse etapas, historial, etc.) las aplica el servidor.
 */

const ORDEN = ['recibido', 'en_preparacion', 'horneado_decorado', 'control_calidad', 'listo'];
const TITULOS = {
  recibido: 'Recibido',
  en_preparacion: 'En Preparación',
  horneado_decorado: 'Horneado/Decorado',
  control_calidad: 'Control de Calidad',
  listo: 'Listo',
  en_despacho: 'En Despacho',
  entregado: 'Entregado',
};
// Qué significa llegar a cada etapa (se muestra en la ventana de confirmación)
const EXPLICACIONES = {
  en_preparacion: 'La cocina comienza a preparar el pedido.',
  horneado_decorado: 'El pedido pasa a horneado y decoración.',
  control_calidad: 'El pedido queda listo para revisar su calidad.',
  listo: 'El pedido aprobó el control de calidad y queda listo para entregar.',
  en_despacho: 'Se crea el despacho y el pedido aparecerá en Despachos para asignarle una ruta.',
  entregado: 'El pedido se marca como entregado al cliente en la tienda. Esta acción no se puede deshacer.',
  rechazo: 'El pedido vuelve a En Preparación y el motivo queda registrado en su historial.',
};

// Sello de la etapa: usa los dibujos SVG de web/_sellos.html (cargados en base.html).
function crearSello(estado) {
  const sello = document.createElement('span');
  sello.className = `comanda__sello sello--${estado}`;
  sello.setAttribute('aria-hidden', 'true');   // es decorativo: la etapa ya la indica la columna
  sello.innerHTML = `<svg viewBox="0 0 100 100"><use href="#sello-${estado}"/></svg>`;
  return sello;
}

const pedidos = new Map();   // id -> datos del pedido (para la ventana de confirmación)
let arrastrando = false;

const formatoHora = new Intl.DateTimeFormat('es-CL', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const formatoDia = new Intl.DateTimeFormat('es-CL', { weekday: 'short', day: 'numeric', month: 'short' });
const formatoCompleto = new Intl.DateTimeFormat('es-CL', {
  weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

/** Etapa a la que llega un pedido al avanzar. */
function etapaSiguiente(pedido) {
  if (pedido.estado === 'listo') return pedido.tipo_entrega === 'despacho' ? 'en_despacho' : 'entregado';
  return ORDEN[ORDEN.indexOf(pedido.estado) + 1];
}

function textoBotonAvanzar(pedido) {
  if (pedido.estado === 'listo') {
    return pedido.tipo_entrega === 'despacho' ? 'Enviar a despacho' : 'Entregado en tienda';
  }
  return `Pasar a ${TITULOS[etapaSiguiente(pedido)]}`;
}

/* ---------------- Ventana de confirmación ---------------- */
const ventana = document.getElementById('ventana-confirmar');
const formConfirmar = document.getElementById('form-confirmar');
const campoMotivo = document.getElementById('vc-campo-motivo');
const inputMotivo = document.getElementById('vc-motivo');
let responder = null;   // resuelve la promesa de confirmarCambio()

/**
 * Muestra la ventana y espera la respuesta del usuario.
 * Devuelve { confirmado: true|false, motivo }.
 */
function confirmarCambio(pedido, hacia, { rechazo = false } = {}) {
  const desde = document.getElementById('vc-desde');
  const destino = document.getElementById('vc-hacia');
  desde.className = `estado estado--${pedido.estado}`;
  desde.textContent = TITULOS[pedido.estado];
  destino.className = `estado estado--${hacia}`;
  destino.textContent = TITULOS[hacia];

  document.getElementById('vc-titulo').textContent = rechazo ? '¿Rechazar en Control de Calidad?' : '¿Confirmar cambio de etapa?';
  document.getElementById('vc-explicacion').textContent = rechazo ? EXPLICACIONES.rechazo : EXPLICACIONES[hacia];
  document.getElementById('vc-pedido').textContent = `#${pedido.id} · ${pedido.tipo_entrega === 'despacho' ? 'Despacho a domicilio' : 'Retiro en tienda'}`;
  document.getElementById('vc-cliente').textContent = pedido.cliente_nombre;
  document.getElementById('vc-entrega').textContent = formatoCompleto.format(new Date(pedido.fecha_entrega));
  const lista = document.getElementById('vc-productos');
  lista.replaceChildren(...pedido.productos.map((texto) => {
    const li = document.createElement('li');
    li.textContent = texto;
    return li;
  }));

  const botonConfirmar = document.getElementById('vc-confirmar');
  botonConfirmar.textContent = rechazo ? 'Devolver a preparación' : 'Confirmar';
  botonConfirmar.classList.toggle('boton--peligro', rechazo || hacia === 'entregado');
  campoMotivo.hidden = !rechazo;
  inputMotivo.value = '';

  ventana.showModal();
  (rechazo ? inputMotivo : botonConfirmar).focus();

  return new Promise((resolver) => { responder = resolver; });
}

function cerrarVentana(confirmado) {
  if (!ventana.open) return;
  const motivo = inputMotivo.value.trim();
  ventana.close();
  if (responder) {
    responder({ confirmado, motivo });
    responder = null;
  }
}

formConfirmar.addEventListener('submit', (evento) => { evento.preventDefault(); cerrarVentana(true); });
ventana.querySelector('[data-cerrar]').addEventListener('click', () => cerrarVentana(false));
// Escape: el navegador cierra el <dialog>; lo tratamos como "Cancelar"
ventana.addEventListener('cancel', (evento) => { evento.preventDefault(); cerrarVentana(false); });
// Clic en el fondo oscuro (fuera de la ventana) también cancela
ventana.addEventListener('click', (evento) => { if (evento.target === ventana) cerrarVentana(false); });

/* ---------------- Tarjetas ---------------- */
function crearTarjeta(pedido) {
  const entrega = new Date(pedido.fecha_entrega);
  const urgente = entrega - Date.now() < 3 * 3600 * 1000;

  const tarjeta = document.createElement('article');
  tarjeta.className = 'comanda comanda--kanban' + (urgente ? ' comanda--urgente' : '');
  tarjeta.dataset.id = pedido.id;
  tarjeta.dataset.estado = pedido.estado;
  tarjeta.setAttribute('aria-label', `Pedido ${pedido.id} de ${pedido.cliente_nombre}`);

  const cabecera = document.createElement('div');
  cabecera.className = 'comanda__cabecera';
  const numero = document.createElement('a');
  numero.className = 'comanda__numero';
  numero.href = URL_DETALLE.replace('/0/', `/${pedido.id}/`);
  numero.textContent = `Pedido #${pedido.id}`;
  const tipo = document.createElement('span');
  tipo.className = 'nota';
  tipo.textContent = pedido.tipo_entrega === 'despacho' ? 'Despacho' : 'Retiro';
  cabecera.append(numero, tipo);

  const hora = document.createElement('div');
  hora.className = 'comanda__hora';
  hora.textContent = formatoHora.format(entrega);
  const dia = document.createElement('div');
  dia.className = 'comanda__fecha';
  dia.textContent = formatoDia.format(entrega) + (urgente ? ', entrega en menos de 3 horas' : '');

  const cliente = document.createElement('div');
  cliente.className = 'comanda__cliente';
  cliente.textContent = pedido.cliente_nombre;

  const lineas = document.createElement('ul');
  lineas.className = 'comanda__lineas';
  for (const producto of pedido.productos) {
    const li = document.createElement('li');
    li.textContent = producto;
    lineas.append(li);
  }
  if (pedido.diseno) {
    const li = document.createElement('li');
    li.className = 'nota';
    li.textContent = pedido.diseno.length > 90 ? pedido.diseno.slice(0, 90) + '…' : pedido.diseno;
    lineas.append(li);
  }

  const acciones = document.createElement('div');
  acciones.className = 'comanda__acciones';
  const avanzar = document.createElement('button');
  avanzar.type = 'button';
  avanzar.className = 'boton boton--chico';
  avanzar.textContent = textoBotonAvanzar(pedido);
  avanzar.addEventListener('click', async () => {
    const { confirmado } = await confirmarCambio(pedido, etapaSiguiente(pedido));
    if (confirmado) await avanzarPedido(pedido.id, avanzar);
  });
  acciones.append(avanzar);

  if (pedido.estado === 'control_calidad') {
    const rechazar = document.createElement('button');
    rechazar.type = 'button';
    rechazar.className = 'boton boton--chico boton--secundario';
    rechazar.textContent = 'Rechazar';
    rechazar.addEventListener('click', async () => {
      const { confirmado, motivo } = await confirmarCambio(pedido, 'en_preparacion', { rechazo: true });
      if (confirmado) await rechazarPedido(pedido.id, motivo);
    });
    acciones.append(rechazar);
  }

  tarjeta.append(crearSello(pedido.estado), cabecera, hora, dia, cliente, lineas, acciones);
  return tarjeta;
}

/* ---------------- Llamadas a la API ---------------- */
async function avanzarPedido(id, boton) {
  if (boton) boton.disabled = true;
  const { ok, datos } = await llamarApi(`/api/pedidos/${id}/avanzar/`, { metodo: 'POST' });
  if (ok) {
    const destino = datos.estado === 'en_despacho' ? 'enviado a despacho'
      : datos.estado === 'entregado' ? 'marcado como entregado'
      : `ahora está en ${TITULOS[datos.estado]}`;
    mostrarAviso(`Pedido #${id} ${destino}.`, 'success');
  } else {
    mostrarAviso(textosDeError(datos).join(' '), 'error');
  }
  await cargar();
}

async function rechazarPedido(id, motivo) {
  const { ok, datos } = await llamarApi(`/api/pedidos/${id}/rechazar-calidad/`, {
    metodo: 'POST',
    json: { motivo: motivo || 'Rechazado en control de calidad' },
  });
  if (ok) mostrarAviso(`Pedido #${id} devuelto a En Preparación.`, 'warning');
  else mostrarAviso(textosDeError(datos).join(' '), 'error');
  await cargar();
}

async function cargar() {
  const tablero = document.getElementById('tablero');
  const { ok, datos } = await llamarApi('/api/pedidos/kanban/');
  tablero.setAttribute('aria-busy', 'false');
  if (!ok) {
    mostrarAviso('No se pudo cargar el tablero. ' + textosDeError(datos).join(' '), 'error');
    return;
  }
  pedidos.clear();
  for (const columna of datos) {
    const lista = document.querySelector(`.columna__lista[data-estado="${columna.estado}"]`);
    lista.replaceChildren();
    if (!columna.pedidos.length) {
      const vacio = document.createElement('p');
      vacio.className = 'columna__vacia';
      vacio.textContent = 'Sin pedidos';
      lista.append(vacio);
    }
    for (const pedido of columna.pedidos) {
      pedidos.set(String(pedido.id), pedido);
      lista.append(crearTarjeta(pedido));
    }
    document.querySelector(`[data-cuenta="${columna.estado}"]`).textContent = columna.pedidos.length;
  }
}

/* ---------------- Arrastrar y soltar ----------------
 * Solo se permite pasar a la columna siguiente,
 * o devolver de Control de Calidad a En Preparación (rechazo). */
function movimientoPermitido(desde, hacia) {
  const i = ORDEN.indexOf(desde);
  const j = ORDEN.indexOf(hacia);
  return j === i + 1 || (desde === 'control_calidad' && hacia === 'en_preparacion');
}

/** Devuelve la tarjeta a su columna original (cuando se cancela). */
function devolverTarjeta(evento) {
  const referencia = evento.from.children[evento.oldIndex] || null;
  evento.from.insertBefore(evento.item, referencia);
}

document.querySelectorAll('.columna__lista').forEach((lista) => {
  new Sortable(lista, {
    group: {
      name: 'cocina',
      put: (hacia, desde) => movimientoPermitido(desde.el.dataset.estado, hacia.el.dataset.estado),
    },
    sort: false,
    draggable: '.comanda--kanban',
    filter: 'button, a, input',
    preventOnFilter: false,
    animation: 180,
    easing: 'cubic-bezier(0.2, 0, 0, 1)',
    ghostClass: 'comanda--fantasma',
    dragClass: 'comanda--arrastrada',
    onStart: () => { arrastrando = true; },
    onEnd: async (evento) => {
      arrastrando = false;
      if (evento.from === evento.to) return;
      const pedido = pedidos.get(evento.item.dataset.id);
      const desde = evento.from.dataset.estado;
      const hacia = evento.to.dataset.estado;
      const rechazo = desde === 'control_calidad' && hacia === 'en_preparacion';

      const { confirmado, motivo } = await confirmarCambio(pedido, rechazo ? 'en_preparacion' : etapaSiguiente(pedido), { rechazo });
      if (!confirmado) {
        devolverTarjeta(evento);
        return;
      }
      if (rechazo) await rechazarPedido(pedido.id, motivo);
      else await avanzarPedido(pedido.id);
    },
  });
});

document.getElementById('actualizar').addEventListener('click', cargar);
// Recarga automática cada minuto, salvo mientras se arrastra o se está confirmando
setInterval(() => { if (!arrastrando && !ventana.open) cargar(); }, 60000);
cargar();
