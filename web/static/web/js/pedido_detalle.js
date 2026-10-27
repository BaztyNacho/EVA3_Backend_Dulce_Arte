/*
 * Detalle del pedido: disponibilidad de stock, confirmar cotización,
 * subir imagen de referencia y cancelar. Todo mediante la API.
 */

const base = `/api/pedidos/${PEDIDO_ID}`;

function recargarConAviso(texto) {
  try { sessionStorage.setItem('aviso', texto); } catch (e) { /* sin almacenamiento: se omite el aviso */ }
  window.location.reload();
}

// Aviso guardado antes de recargar la página
try {
  const pendiente = sessionStorage.getItem('aviso');
  if (pendiente) {
    sessionStorage.removeItem('aviso');
    mostrarAviso(pendiente, pendiente.includes('no se pudo') ? 'warning' : 'success');
  } else if (new URLSearchParams(location.search).get('creado')) {
    mostrarAviso('Cotización guardada. Revisa el stock y confírmala cuando el cliente la apruebe.', 'success');
  }
} catch (e) { /* sin almacenamiento */ }

// ---------------------------------------------------------------
// Disponibilidad de insumos (solo cotizaciones)
// ---------------------------------------------------------------
async function revisarDisponibilidad() {
  const lista = document.getElementById('disponibilidad');
  const boton = document.getElementById('confirmar');
  const { ok, datos } = await llamarApi(`${base}/disponibilidad/`);
  lista.replaceChildren();
  if (!ok) {
    lista.innerHTML = '<li class="nota">No se pudo revisar el stock. Igual puedes intentar confirmar.</li>';
    boton.disabled = false;
    return;
  }
  for (const item of datos.insumos) {
    const necesario = Number(item.necesario);
    const disponible = Number(item.disponible);
    const li = document.createElement('li');
    const texto = document.createElement('div');
    texto.textContent = `${item.insumo}: necesita ${necesario.toLocaleString('es-CL')} ${item.unidad}, hay ${disponible.toLocaleString('es-CL')}`;
    const barra = document.createElement('div');
    barra.className = 'barra-stock' + (item.suficiente ? '' : ' barra-stock--falta');
    const relleno = document.createElement('span');
    relleno.style.width = `${Math.min(100, disponible > 0 ? (necesario / disponible) * 100 : 100)}%`;
    barra.append(relleno);
    li.append(texto, barra);
    lista.append(li);
  }
  if (!datos.insumos.length) {
    lista.innerHTML = '<li class="nota">Los productos no tienen receta registrada; no se descontarán insumos.</li>';
  }
  if (datos.hay_stock_suficiente) {
    boton.disabled = false;
  } else {
    const aviso = document.createElement('li');
    aviso.className = 'error-campo';
    aviso.textContent = 'Falta stock para confirmar. Repón los insumos en rojo o ajusta la cotización.';
    lista.append(aviso);
  }
}

if (ES_COTIZACION) {
  revisarDisponibilidad();

  document.getElementById('confirmar').addEventListener('click', async (evento) => {
    const boton = evento.currentTarget;
    boton.disabled = true;
    boton.textContent = 'Confirmando…';
    const { ok, datos } = await llamarApi(`${base}/confirmar/`, { metodo: 'POST' });
    if (ok) {
      recargarConAviso(`Pedido #${PEDIDO_ID} confirmado y enviado a cocina. Los insumos se descontaron de bodega.`);
    } else {
      mostrarAviso(textosDeError(datos).join(' '), 'error');
      boton.textContent = 'Confirmar y enviar a cocina';
      revisarDisponibilidad();
    }
  });

  const formImagen = document.getElementById('form-imagen');
  formImagen.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const archivo = document.getElementById('imagen').files[0];
    if (!archivo) { mostrarAviso('Elige una imagen antes de subirla.', 'error'); return; }
    const form = new FormData();
    form.append('imagen_referencia', archivo);
    const { ok, datos } = await llamarApi(`${base}/imagen-referencia/`, { metodo: 'POST', form });
    if (ok) recargarConAviso('Imagen de referencia actualizada.');
    else mostrarAviso(textosDeError(datos).join(' '), 'error');
  });
}

// ---------------------------------------------------------------
// Cancelar (solo Administrador)
// ---------------------------------------------------------------
const formCancelar = document.getElementById('form-cancelar');
if (formCancelar) {
  formCancelar.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const motivo = document.getElementById('motivo').value.trim();
    const { ok, datos } = await llamarApi(`${base}/cancelar/`, { metodo: 'POST', json: { motivo } });
    if (ok) recargarConAviso(`Pedido #${PEDIDO_ID} cancelado.`);
    else mostrarAviso(textosDeError(datos).join(' '), 'error');
  });
}
