/*
 * Cotizador de Dulce Arte.
 * Arma la cotización en el navegador y la guarda llamando a la API:
 *   1. (si es cliente nuevo) POST /api/clientes/
 *   2. POST /api/pedidos/  con productos y personalizaciones
 *   3. (si hay imagen)     POST /api/pedidos/<id>/imagen-referencia/
 */

const PRODUCTOS = JSON.parse(document.getElementById('datos-productos').textContent);
const OPCIONES = JSON.parse(document.getElementById('datos-opciones').textContent);

const estado = {
  cliente: null, // { id, nombre, telefono, direccion }
  lineas: [],    // { uid, producto, cantidad, comentario, extras: { opcionId: porciones } }
};
let siguienteUid = 1;

const $ = (selector) => document.querySelector(selector);

// ---------------------------------------------------------------
// Catálogo de productos
// ---------------------------------------------------------------
function dibujarCatalogo() {
  const catalogo = $('#catalogo');
  if (!PRODUCTOS.length) {
    catalogo.innerHTML = '<p class="nota">No hay productos activos. Un administrador debe crearlos en el panel de administración.</p>';
    return;
  }
  for (const producto of PRODUCTOS) {
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'producto';
    boton.setAttribute('aria-label', `Agregar ${producto.nombre}`);
    if (producto.imagen) {
      const img = document.createElement('img');
      img.src = producto.imagen;
      img.alt = '';
      boton.append(img);
    }
    const nombre = document.createElement('span');
    nombre.className = 'producto__nombre';
    nombre.textContent = producto.nombre;
    const precio = document.createElement('span');
    precio.className = 'producto__precio';
    precio.textContent = `${producto.categoria}, ${clp(producto.precio)}`;
    boton.append(nombre, precio);
    boton.addEventListener('click', () => agregarLinea(producto));
    catalogo.append(boton);
  }
}

function agregarLinea(producto) {
  estado.lineas.push({ uid: siguienteUid++, producto, cantidad: 1, comentario: '', extras: {} });
  limpiarError('detalles');
  dibujarLineas(true);
}

// ---------------------------------------------------------------
// Líneas del pedido (cantidad, extras y comentario)
// ---------------------------------------------------------------
function crearContador(valor, min, max, alCambiar, etiqueta) {
  const contenedor = document.createElement('span');
  contenedor.className = 'contador';
  const menos = document.createElement('button');
  menos.type = 'button';
  menos.textContent = '−';
  menos.setAttribute('aria-label', `Disminuir ${etiqueta}`);
  const salida = document.createElement('output');
  salida.textContent = valor > 0 && min < 0 ? `+${valor}` : valor;
  salida.setAttribute('aria-live', 'polite');
  const mas = document.createElement('button');
  mas.type = 'button';
  mas.textContent = '+';
  mas.setAttribute('aria-label', `Aumentar ${etiqueta}`);
  menos.addEventListener('click', () => valor > min && alCambiar(valor - 1));
  mas.addEventListener('click', () => valor < max && alCambiar(valor + 1));
  contenedor.append(menos, salida, mas);
  return contenedor;
}

function dibujarLineas(hayNueva = false) {
  const contenedor = $('#lineas');
  contenedor.replaceChildren();

  estado.lineas.forEach((linea, indice) => {
    const caja = document.createElement('div');
    caja.className = 'linea-pedido' + (hayNueva && indice === estado.lineas.length - 1 ? ' nueva' : '');

    const cabecera = document.createElement('div');
    cabecera.className = 'linea-pedido__cabecera';
    const nombre = document.createElement('span');
    nombre.className = 'linea-pedido__nombre';
    nombre.textContent = `${linea.producto.nombre} (${clp(linea.producto.precio)} c/u)`;
    const quitar = document.createElement('button');
    quitar.type = 'button';
    quitar.className = 'quitar';
    quitar.textContent = 'Quitar';
    quitar.addEventListener('click', () => {
      estado.lineas = estado.lineas.filter((l) => l.uid !== linea.uid);
      dibujarLineas();
    });
    cabecera.append(
      nombre,
      crearContador(linea.cantidad, 1, 50, (v) => { linea.cantidad = v; dibujarLineas(); }, `cantidad de ${linea.producto.nombre}`),
      quitar,
    );
    caja.append(cabecera);

    // Solo los extras que se ofrecen para este producto
    const opcionesProducto = OPCIONES.filter((o) => linea.producto.opciones.includes(o.id));
    if (opcionesProducto.length) {
      const lista = document.createElement('div');
      lista.className = 'personalizaciones';
      const titulo = document.createElement('span');
      titulo.className = 'etiqueta';
      titulo.textContent = 'Extras';
      lista.append(titulo);
      for (const opcion of opcionesProducto) {
        const porciones = linea.extras[opcion.id] || 0;
        const fila = document.createElement('div');
        fila.className = 'personalizacion';
        const texto = document.createElement('span');
        let nota = 'Normal';
        if (porciones > 0) nota = `${porciones} porción${porciones > 1 ? 'es' : ''} extra, ${clp(porciones * opcion.precio)} por unidad`;
        if (porciones < 0) nota = `Menos cantidad (${porciones}), sin costo`;
        texto.innerHTML = `${opcion.nombre}<br><span class="personalizacion__nota"></span>`;
        texto.querySelector('.personalizacion__nota').textContent = nota;
        fila.append(texto, crearContador(porciones, -5, 5, (v) => {
          if (v === 0) delete linea.extras[opcion.id];
          else linea.extras[opcion.id] = v;
          dibujarLineas();
        }, opcion.nombre));
        lista.append(fila);
      }
      caja.append(lista);
    }

    const campo = document.createElement('div');
    campo.className = 'campo';
    campo.classList.add('comentario-linea');
    const idComentario = `comentario-${linea.uid}`;
    campo.innerHTML = `<label for="${idComentario}">Comentario o añadido extra</label>`;
    const comentario = document.createElement('textarea');
    comentario.id = idComentario;
    comentario.rows = 2;
    comentario.placeholder = 'Ej.: escribir "Feliz cumpleaños, Sofía"';
    comentario.value = linea.comentario;
    comentario.addEventListener('input', () => { linea.comentario = comentario.value; });
    campo.append(comentario);
    caja.append(campo);

    contenedor.append(caja);
  });

  dibujarResumen();
}

function subtotalLinea(linea) {
  let total = linea.producto.precio * linea.cantidad;
  for (const [opcionId, porciones] of Object.entries(linea.extras)) {
    const opcion = OPCIONES.find((o) => o.id === Number(opcionId));
    if (opcion && porciones > 0) total += porciones * opcion.precio * linea.cantidad;
  }
  return total;
}

function dibujarResumen() {
  const lista = $('#resumen-lineas');
  lista.replaceChildren();
  if (!estado.lineas.length) {
    lista.innerHTML = '<li><span class="nota">Aún no agregas productos.</span></li>';
  }
  let total = 0;
  for (const linea of estado.lineas) {
    const subtotal = subtotalLinea(linea);
    total += subtotal;
    const item = document.createElement('li');
    const texto = document.createElement('span');
    texto.textContent = `${linea.cantidad} × ${linea.producto.nombre}`;
    const valor = document.createElement('span');
    valor.textContent = clp(subtotal);
    item.append(texto, valor);
    lista.append(item);
  }
  $('#resumen-total').textContent = clp(total);
}

// ---------------------------------------------------------------
// Cliente: búsqueda o cliente nuevo
// ---------------------------------------------------------------
let temporizador = null;
$('#busqueda-cliente').addEventListener('input', (evento) => {
  clearTimeout(temporizador);
  const texto = evento.target.value.trim();
  const sugerencias = $('#sugerencias');
  if (texto.length < 2) { sugerencias.hidden = true; return; }
  temporizador = setTimeout(async () => {
    const { ok, datos } = await llamarApi(`/api/clientes/?q=${encodeURIComponent(texto)}`);
    sugerencias.replaceChildren();
    if (!ok || !datos.length) {
      sugerencias.innerHTML = '<li class="nota sugerencias__vacio">Sin resultados. Regístralo como cliente nuevo.</li>';
    } else {
      for (const cliente of datos.slice(0, 8)) {
        const item = document.createElement('li');
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.textContent = `${cliente.nombre} (${cliente.telefono})`;
        boton.addEventListener('click', () => elegirCliente(cliente));
        item.append(boton);
        sugerencias.append(item);
      }
    }
    sugerencias.hidden = false;
  }, 250);
});

function elegirCliente(cliente) {
  estado.cliente = cliente;
  limpiarError('cliente');
  $('#cliente-elegido-texto').textContent = `${cliente.nombre} (${cliente.telefono})`;
  $('#cliente-elegido').hidden = false;
  $('#buscar-cliente').hidden = true;
  $('#sugerencias').hidden = true;
  const direccion = $('#direccion-entrega');
  if (!direccion.value && cliente.direccion) direccion.value = cliente.direccion;
}

$('#cambiar-cliente').addEventListener('click', () => {
  estado.cliente = null;
  $('#cliente-elegido').hidden = true;
  $('#buscar-cliente').hidden = false;
  $('#busqueda-cliente').value = '';
  $('#busqueda-cliente').focus();
});

// ---------------------------------------------------------------
// Tipo de entrega
// ---------------------------------------------------------------
document.querySelectorAll('input[name="tipo_entrega"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    $('#campo-direccion').hidden = tipoEntrega() !== 'despacho';
  });
});
const tipoEntrega = () => document.querySelector('input[name="tipo_entrega"]:checked').value;

// ---------------------------------------------------------------
// Guardar
// ---------------------------------------------------------------
function limpiarErrores() {
  document.querySelectorAll('[data-error]').forEach((el) => { el.textContent = ''; });
  document.getElementById('avisos').replaceChildren();
}

function limpiarError(campo) {
  const destino = document.querySelector(`[data-error="${campo}"]`);
  if (destino) destino.textContent = '';
}

// Al corregir un campo, su mensaje de error desaparece.
$('#fecha-entrega').addEventListener('input', () => limpiarError('fecha_entrega'));
$('#direccion-entrega').addEventListener('input', () => limpiarError('direccion_entrega'));
['#c-nombre', '#c-telefono'].forEach((id) => $(id).addEventListener('input', () => limpiarError('cliente')));

function mostrarErrores(datos) {
  let general = [];
  if (datos && typeof datos === 'object' && !Array.isArray(datos)) {
    for (const [campo, valor] of Object.entries(datos)) {
      const destino = document.querySelector(`[data-error="${campo}"]`);
      if (destino) destino.textContent = textosDeError(valor).join(' ');
      else general = general.concat(textosDeError(valor));
    }
  } else {
    general = textosDeError(datos);
  }
  mostrarAviso(general.length ? general.join(' ') : 'Revisa los campos marcados en rojo.', 'error');
}

$('#cotizador').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  limpiarErrores();

  // Validaciones rápidas antes de llamar a la API
  const errores = {};
  const nuevo = {
    nombre: $('#c-nombre').value.trim(),
    telefono: $('#c-telefono').value.trim(),
    email: $('#c-email').value.trim(),
    direccion: $('#c-direccion').value.trim(),
  };
  if (!estado.cliente && !(nuevo.nombre && nuevo.telefono)) {
    errores.cliente = 'Elige un cliente o ingresa nombre y teléfono del cliente nuevo.';
  }
  if (!$('#fecha-entrega').value) errores.fecha_entrega = 'Indica la fecha y hora de entrega.';
  if (!estado.lineas.length) errores.detalles = 'Agrega al menos un producto.';
  if (tipoEntrega() === 'despacho' && !$('#direccion-entrega').value.trim()) {
    errores.direccion_entrega = 'Indica la dirección de entrega.';
  }
  if (Object.keys(errores).length) { mostrarErrores(errores); return; }

  const boton = $('#guardar');
  boton.disabled = true;
  boton.textContent = 'Guardando…';

  try {
    // 1. Cliente nuevo
    if (!estado.cliente) {
      const r = await llamarApi('/api/clientes/', { metodo: 'POST', json: nuevo });
      if (!r.ok) { mostrarErrores({ cliente: textosDeError(r.datos).join(' ') }); return; }
      elegirCliente(r.datos);
    }

    // 2. Cotización
    const cuerpo = {
      cliente: estado.cliente.id,
      fecha_entrega: $('#fecha-entrega').value,
      tipo_entrega: tipoEntrega(),
      direccion_entrega: tipoEntrega() === 'despacho' ? $('#direccion-entrega').value.trim() : '',
      diseno: $('#diseno').value.trim(),
      observaciones: $('#observaciones').value.trim(),
      detalles: estado.lineas.map((linea) => ({
        producto: linea.producto.id,
        cantidad: linea.cantidad,
        comentario: linea.comentario.trim(),
        personalizaciones: Object.entries(linea.extras).map(([opcion, porciones]) => ({
          opcion: Number(opcion),
          porciones,
        })),
      })),
    };
    const r = await llamarApi('/api/pedidos/', { metodo: 'POST', json: cuerpo });
    if (!r.ok) { mostrarErrores(r.datos); return; }
    const pedido = r.datos;

    // 3. Imagen de referencia
    const archivo = $('#imagen').files[0];
    if (archivo) {
      const form = new FormData();
      form.append('imagen_referencia', archivo);
      const ri = await llamarApi(`/api/pedidos/${pedido.id}/imagen-referencia/`, { metodo: 'POST', form });
      if (!ri.ok) {
        try {
          sessionStorage.setItem('aviso', 'La cotización se guardó, pero la imagen no se pudo subir. Puedes subirla desde aquí.');
        } catch (e) { /* sin almacenamiento: se omite el aviso */ }
      }
    }
    window.location.href = URL_DETALLE.replace('/0/', `/${pedido.id}/`) + '?creado=1';
  } finally {
    boton.disabled = false;
    boton.textContent = 'Guardar cotización';
  }
});

dibujarCatalogo();
dibujarResumen();

// Si se llega desde el Catálogo con ?producto=<id>, ese producto queda agregado.
const productoInicial = Number(new URLSearchParams(window.location.search).get('producto'));
const encontrado = PRODUCTOS.find((p) => p.id === productoInicial);
if (encontrado) agregarLinea(encontrado);
