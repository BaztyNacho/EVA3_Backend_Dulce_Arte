# Dulce Arte — Contexto del proyecto

## Qué es
Sistema de Trazabilidad y Pedidos para una Pastelería Artesanal.
Evaluación Parcial N°3 de Desarrollo Backend (INACAP). Proyecto individual.
Problema: falta de coordinación entre la toma de pedidos personalizados,
la disponibilidad de insumos en bodega y los tiempos de cocina.

## Requerimientos funcionales
1. Cotización y registro de pedidos personalizados (ingredientes, diseño, fecha/hora de entrega).
2. Tablero Kanban de cocina: Recibido → En Preparación → Horneado/Decorado → Control de Calidad → Listo.
3. Inventario de insumos con descuento automático mediante Lista de Materiales (BOM).
4. Rutas de despacho con confirmación por firma digital (canvas) o foto de comprobante.

## Roles
- Administrador: acceso total (Kanban, bodega, despachos, Django Admin).
- Atención y Ventas: cotiza, registra pedidos y consulta su estado. Sin acceso a cocina, bodega ni Admin.

## Stack técnico
- Python 3.14, Django 5.2 LTS, Django REST Framework.
- PostgreSQL 18 (local en desarrollo; en la instancia EC2 en producción).
- Frontend: templates de Django + HTML/CSS/JS. JavaScript con fetch a la API solo para Kanban y firma.
- Configuración sensible en `.env` mediante django-environ. Nunca escribir claves en el código.
- Despliegue: una sola instancia AWS EC2 (AWS Academy) con Gunicorn + Nginx + PostgreSQL.

## Entorno local (Windows 11)
- El entorno virtual está FUERA del proyecto: `C:\Users\bazty\venvs\dulce-arte`
- Activar: `& "$env:USERPROFILE\venvs\dulce-arte\Scripts\Activate.ps1"`
- No crear entornos virtuales dentro de la carpeta del proyecto (está en OneDrive).

## Identidad visual
Pastelería artesanal, elegante y cálida.
- Paleta: crema/vainilla (fondos), rosa frambuesa (principal), chocolate (textos), dorado caramelo (detalles).
- Tipografía: serif elegante para títulos, sans-serif limpia para el cuerpo.
- Animaciones suaves y con propósito; interfaz responsiva e intuitiva.

## Reglas de trabajo
- El estudiante está aprendiendo: explicar cada cambio de forma simple antes o después de hacerlo.
- Entregar siempre archivos completos al crear o modificar código, no fragmentos.
- Nombres de modelos, campos y vistas en español.
- Toda regla de negocio debe validarse en el backend, no solo en el frontend.
- Registrar los apoyos de IA para el archivo `prompts_ia.md` (entregable obligatorio).