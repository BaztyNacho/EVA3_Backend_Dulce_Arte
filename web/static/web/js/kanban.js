/*
 * Tablero Kanban de cocina.
 * - Carga los pedidos desde GET /api/pedidos/kanban/
 * - Al soltar una comanda en la columna siguiente llama a POST /api/pedidos/<id>/avanzar/
 * - Al devolver una comanda de Control de Calidad a En Preparación llama a /rechazar-calidad/
 * Las reglas (no saltarse etapas, historial, etc.) las aplica el servidor.
 */

const ORDEN = ['recibido', 'en_preparacion', 'horneado_decorado', 'control_calidad', 'listo'];
const TITULOS = {
  recibido: 'Recibido',
  en_preparacion: 'En Preparación',
  horneado_decorado: 'Horneado/Decorado',
  control_calidad: 'Control de Calidad',
  listo: 'Listo',
};
let arrastrando = false;

const formatoHora = new Intl.DateTimeFormat('es-CL', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const formatoDia = new Intl.DateTimeFormat('es-CL', { weekday: 'short', day: 'numeric', month: 'short' });

function textoBotonAvanzar(pedido) {
  if (pedido.estado === 'listo') {
    return pedido.tipo_entrega === 'despacho' ? 'Enviar a despacho' : 'Entregado en tienda';
  }
  return `Pasar a ${TITULOS[ORDEN[ORDEN.indexOf(pedido.estado) + 1]]}`;
}

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
  avanzar.addEventListener('click', () => avanzarPedido(pedido.id, avanzar));
  acciones.append(avanzar);

  if (pedido.estado === 'control_calidad') {
    const rechazar = document.createElement('button');
    rechazar.type = 'button';
    rechazar.className = 'boton boton--chico boton--secundario';
    rechazar.textContent = 'Rechazar';
    rechazar.addEventListener('click', () => mostrarRechazo(tarjeta, pedido.id));
    acciones.append(rechazar);
  }

  tarjeta.append(cabecera, hora, dia, cliente, lineas, acciones);
  return tarjeta;
}

function mostrarRechazo(tarjeta, id) {
  if (tarjeta.querySelector('.rechazo')) return;
  const form = document.createElement('form');
  form.className = 'rechazo';
  form.innerHTML = `
    <label class="etiqueta" for="motivo-${id}">¿Qué hay que corregir?</label>
    <input type="text" id="motivo-${id}" maxlength="200" placeholder="Ej.: decoración dispareja">
    <div class="comanda__acciones">
      <button type="submit" class="boton boton--chico boton--peligro">Devolver a preparación</button>
      <button type="button" class="boton boton--chico boton--secundario">Cancelar</button>
    </div>`;
  form.querySelector('button[type=button]').addEventListener('click', () => form.remove());
  form.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const motivo = form.querySelector('input').value.trim();
    await rechazarPedido(id, motivo);
  });
  tarjeta.append(form);
  form.querySelector('input').focus();
}

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
  const { ok, datos } = await llamarApi(`/api/pedidos/${id}/rechazar-calidad/`, { metodo: 'POST', json: { motivo } });
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
  for (const columna of datos) {
    const lista = document.querySelector(`.columna__lista[data-estado="${columna.estado}"]`);
    lista.replaceChildren();
    if (!columna.pedidos.length) {
      const vacio = document.createElement('p');
      vacio.className = 'columna__vacia';
      vacio.textContent = 'Sin pedidos';
      lista.append(vacio);
    }
    for (const pedido of columna.pedidos) lista.append(crearTarjeta(pedido));
    document.querySelector(`[data-cuenta="${columna.estado}"]`).textContent = columna.pedidos.length;
  }
}

// Arrastrar y soltar: solo se permite pasar a la columna siguiente,
// o devolver de Control de Calidad a En Preparación.
function movimientoPermitido(desde, hacia) {
  const i = ORDEN.indexOf(desde);
  const j = ORDEN.indexOf(hacia);
  return j === i + 1 || (desde === 'control_calidad' && hacia === 'en_preparacion');
}

document.querySelectorAll('.columna__lista').forEach((lista) => {
  new Sortable(lista, {
    group: {
      name: 'cocina',
      put: (hacia, desde) => movimientoPermitido(desde.el.dataset.estado, hacia.el.dataset.estado),
    },
    sort: false,
    draggable: '.comanda--kanban',
    filter: 'button, a, input, .rechazo',
    preventOnFilter: false,
    animation: 180,
    easing: 'cubic-bezier(0.2, 0, 0, 1)',
    ghostClass: 'comanda--fantasma',
    dragClass: 'comanda--arrastrada',
    onStart: () => { arrastrando = true; },
    onEnd: async (evento) => {
      arrastrando = false;
      if (evento.from === evento.to) return;
      const id = evento.item.dataset.id;
      const desde = evento.from.dataset.estado;
      const hacia = evento.to.dataset.estado;
      if (desde === 'control_calidad' && hacia === 'en_preparacion') {
        await rechazarPedido(id, 'Rechazado en control de calidad');
      } else {
        await avanzarPedido(id);
      }
    },
  });
});

document.getElementById('actualizar').addEventListener('click', cargar);
setInterval(() => { if (!arrastrando && !document.querySelector('.rechazo')) cargar(); }, 60000);
cargar();
