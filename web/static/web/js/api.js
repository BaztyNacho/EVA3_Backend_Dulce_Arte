/*
 * Utilidades para llamar a la API de Dulce Arte desde el navegador.
 * Usa la misma sesión de Django (cookie) y envía el token CSRF en cada petición.
 */

function leerCookie(nombre) {
  const fila = document.cookie.split('; ').find((c) => c.startsWith(nombre + '='));
  return fila ? decodeURIComponent(fila.split('=')[1]) : null;
}

/**
 * Llama a la API.
 * opciones.json  -> envía un objeto como JSON
 * opciones.form  -> envía un FormData (para subir imágenes)
 * Devuelve { ok, status, datos }.
 */
async function llamarApi(url, { metodo = 'GET', json = null, form = null } = {}) {
  const cabeceras = { 'X-CSRFToken': leerCookie('csrftoken'), Accept: 'application/json' };
  let cuerpo = null;
  if (json !== null) {
    cabeceras['Content-Type'] = 'application/json';
    cuerpo = JSON.stringify(json);
  } else if (form !== null) {
    cuerpo = form;
  }
  try {
    const respuesta = await fetch(url, { method: metodo, headers: cabeceras, body: cuerpo, credentials: 'same-origin' });
    let datos = null;
    if (respuesta.status !== 204) {
      datos = await respuesta.json().catch(() => null);
    }
    return { ok: respuesta.ok, status: respuesta.status, datos };
  } catch (error) {
    return { ok: false, status: 0, datos: { detail: 'No hay conexión con el servidor. Revisa tu conexión e inténtalo de nuevo.' } };
  }
}

/** Convierte los errores de la API (DRF) en una lista de textos legibles. */
function textosDeError(datos) {
  if (!datos) return ['Ocurrió un error inesperado. Inténtalo de nuevo.'];
  if (typeof datos === 'string') return [datos];
  if (Array.isArray(datos)) return datos.flatMap(textosDeError);
  const textos = [];
  for (const [campo, valor] of Object.entries(datos)) {
    const mensajes = Array.isArray(valor) ? valor : [valor];
    for (const m of mensajes) {
      if (typeof m === 'object' && m !== null) {
        textos.push(...textosDeError(m));
      } else {
        textos.push(campo === 'detail' || campo === 'non_field_errors' ? String(m) : String(m));
      }
    }
  }
  return textos;
}

/** Muestra un aviso arriba de la página. tipo: success | error | warning | info */
function mostrarAviso(texto, tipo = 'info') {
  const contenedor = document.getElementById('avisos');
  if (!contenedor) return;
  const aviso = document.createElement('div');
  aviso.className = `mensaje mensaje--${tipo}`;
  aviso.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  aviso.textContent = texto;
  contenedor.replaceChildren(aviso);
  aviso.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/** Formatea pesos chilenos: 25000 -> $25.000 */
function clp(valor) {
  return '$' + Math.round(valor).toLocaleString('es-CL');
}
