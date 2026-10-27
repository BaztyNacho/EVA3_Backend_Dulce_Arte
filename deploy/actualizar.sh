#!/usr/bin/env bash
# ---------------------------------------------------------------
# Actualiza Dulce Arte en el servidor AWS con los últimos cambios de GitHub.
# Uso (en el servidor):  bash ~/dulce-arte/deploy/actualizar.sh
# ---------------------------------------------------------------
set -e  # si un paso falla, el script se detiene

cd /home/ubuntu/dulce-arte

echo "1/5 Descargando cambios de GitHub..."
git pull

echo "2/5 Instalando librerías nuevas (si las hay)..."
source venv/bin/activate
pip install --quiet -r requirements.txt

echo "3/5 Aplicando migraciones de la base de datos..."
python manage.py migrate

echo "4/5 Reuniendo archivos estáticos..."
python manage.py collectstatic --noinput

echo "5/5 Reiniciando Gunicorn..."
sudo systemctl restart gunicorn

echo "Listo: Dulce Arte está actualizado."
