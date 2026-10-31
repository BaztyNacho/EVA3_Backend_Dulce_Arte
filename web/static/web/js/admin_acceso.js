/*
 * Administración: antes de ir al panel (Django Admin) se pide la contraseña en una ventana.
 * La ventana envía el formulario a /administracion/verificar/; el servidor la valida
 * (si alguien escribe /admin/ directo, el servidor también la pide).
 */
const ventanaAdmin = document.getElementById('ventana-admin');

if (ventanaAdmin) {
  document.querySelectorAll('[data-abrir-admin]').forEach((enlace) => {
    enlace.addEventListener('click', (evento) => {
      evento.preventDefault();
      ventanaAdmin.showModal();
      document.getElementById('ventana-admin-password').focus();
    });
  });
  ventanaAdmin.querySelector('[data-cerrar]').addEventListener('click', () => ventanaAdmin.close());
  ventanaAdmin.addEventListener('click', (evento) => { if (esClicFuera(evento, ventanaAdmin)) ventanaAdmin.close(); });
}
