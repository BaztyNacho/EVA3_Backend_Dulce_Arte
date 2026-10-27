/*
 * Firma digital en pantalla y confirmación de entrega.
 * La firma se dibuja en un <canvas> (mouse, dedo o lápiz) y se envía a la API
 * como imagen PNG en base64 junto con la foto del comprobante:
 *   POST /api/despachos/<id>/confirmar-entrega/
 */

const lienzo = document.getElementById('firma');

if (lienzo) {
  const ctx = lienzo.getContext('2d');
  let dibujando = false;
  let hayFirma = false;
  let ultimo = null;

  // Ajusta el tamaño real del lienzo a la pantalla (nítido en celulares).
  function ajustarTamano() {
    const escala = window.devicePixelRatio || 1;
    const ancho = lienzo.clientWidth;
    const alto = lienzo.clientHeight;
    lienzo.width = ancho * escala;
    lienzo.height = alto * escala;
    ctx.scale(escala, escala);
    ctx.lineWidth = 2.4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#3B2420';
    hayFirma = false;
  }

  function punto(evento) {
    const caja = lienzo.getBoundingClientRect();
    return { x: evento.clientX - caja.left, y: evento.clientY - caja.top };
  }

  lienzo.addEventListener('pointerdown', (evento) => {
    evento.preventDefault();
    lienzo.setPointerCapture(evento.pointerId);
    dibujando = true;
    ultimo = punto(evento);
    ctx.beginPath();
    ctx.arc(ultimo.x, ultimo.y, 1.2, 0, Math.PI * 2);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fill();
    hayFirma = true;
  });

  lienzo.addEventListener('pointermove', (evento) => {
    if (!dibujando) return;
    const actual = punto(evento);
    // Curva suave entre el punto anterior y el actual
    const medio = { x: (ultimo.x + actual.x) / 2, y: (ultimo.y + actual.y) / 2 };
    ctx.beginPath();
    ctx.moveTo(ultimo.x, ultimo.y);
    ctx.quadraticCurveTo(ultimo.x, ultimo.y, medio.x, medio.y);
    ctx.lineTo(actual.x, actual.y);
    ctx.stroke();
    ultimo = actual;
    hayFirma = true;
  });

  const terminar = () => { dibujando = false; };
  lienzo.addEventListener('pointerup', terminar);
  lienzo.addEventListener('pointercancel', terminar);

  document.getElementById('borrar-firma').addEventListener('click', () => {
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    hayFirma = false;
  });

  ajustarTamano();
  window.addEventListener('resize', () => { if (!hayFirma) ajustarTamano(); });

  // Confirmar entrega
  document.getElementById('form-entrega').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const receptor = document.getElementById('receptor').value.trim();
    const foto = document.getElementById('comprobante').files[0];
    if (!receptor) { mostrarAviso('Escribe el nombre de quien recibe.', 'error'); return; }
    if (!hayFirma && !foto) { mostrarAviso('Pide la firma del cliente o toma una foto del comprobante.', 'error'); return; }

    const form = new FormData();
    form.append('nombre_receptor', receptor);
    form.append('observaciones', document.getElementById('obs').value.trim());
    if (hayFirma) form.append('firma', lienzo.toDataURL('image/png'));
    if (foto) form.append('comprobante', foto);

    const boton = evento.submitter;
    boton.disabled = true;
    boton.textContent = 'Confirmando…';
    const { ok, datos } = await llamarApi(`/api/despachos/${DESPACHO_ID}/confirmar-entrega/`, { metodo: 'POST', form });
    if (ok) {
      try { sessionStorage.setItem('aviso', `Pedido #${datos.pedido} entregado a ${datos.nombre_receptor}.`); } catch (e) { /* sin almacenamiento */ }
      window.location.href = URL_DESPACHOS;
    } else {
      mostrarAviso(textosDeError(datos).join(' '), 'error');
      boton.disabled = false;
      boton.textContent = 'Confirmar entrega';
    }
  });

  // Intento fallido
  document.getElementById('form-fallido').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const motivo = document.getElementById('motivo-fallido').value.trim();
    if (!motivo) { mostrarAviso('Cuenta qué pasó con la entrega.', 'error'); return; }
    const { ok, datos } = await llamarApi(`/api/despachos/${DESPACHO_ID}/`, {
      metodo: 'PATCH',
      json: { estado: 'fallido', observaciones: motivo, ruta: null },
    });
    if (ok) {
      try { sessionStorage.setItem('aviso', `Intento fallido registrado para el pedido #${datos.pedido}. Quedó en "Por asignar" para reintentar.`); } catch (e) { /* sin almacenamiento */ }
      window.location.href = URL_DESPACHOS;
    } else {
      mostrarAviso(textosDeError(datos).join(' '), 'error');
    }
  });
}
