"""
Protección extra para el panel de Administración (Django Admin).

Aunque el usuario ya inició sesión, para entrar a /admin/ debe volver a escribir su
contraseña. La verificación dura 10 minutos y se renueva mientras siga usando el panel;
si sale y vuelve más tarde, se le pide de nuevo.
"""

import time

from django.shortcuts import redirect
from django.urls import reverse

CLAVE_SESION = 'admin_verificado_hasta'
DURACION_SEGUNDOS = 10 * 60


class VerificarAccesoAdmin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefijo_admin = reverse('admin:index')               # "/admin/"
        exentas = (reverse('admin:login'), reverse('admin:logout'))
        if (
            request.path.startswith(prefijo_admin)
            and request.path not in exentas
            and request.user.is_authenticated
        ):
            ahora = time.time()
            if request.session.get(CLAVE_SESION, 0) < ahora:
                return redirect(f"{reverse('verificar_admin')}?next={request.get_full_path()}")
            # Mientras siga trabajando en el panel, la verificación se renueva
            request.session[CLAVE_SESION] = ahora + DURACION_SEGUNDOS
        return self.get_response(request)
