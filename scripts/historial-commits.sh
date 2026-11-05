#!/usr/bin/env bash
# Reconstruye el historial de commits del proyecto (10 commits, en el orden de
# prioridad del enunciado: modelo y carga -> API -> interfaz -> ejecución).
# El detalle requisito -> commit está en TRAZABILIDAD.md.
#
# Uso:  bash scripts/historial-commits.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -d .git ]; then
  echo "Ya hay un repositorio git en $(pwd); no se toca."
  echo "Para rehacer el historial: rm -rf .git && bash scripts/historial-commits.sh"
  echo
  git --no-pager log --oneline --reverse || true
  exit 0
fi

git init -q
git symbolic-ref HEAD refs/heads/main

if ! git config user.email >/dev/null 2>&1; then
  git config user.email "dev@example.com"
  git config user.name "Desarrollador"
  echo "Aviso: no había identidad de git configurada; se usó una local a este repo."
fi

add_paths() {
  for path in "$@"; do
    if [ -e "$path" ]; then
      git add -- "$path"
    fi
  done
}

commit() {
  message="$1"
  shift
  add_paths "$@"
  git commit -q -m "$message"
  git --no-pager log -1 --pretty='%h %s'
}

commit "docs: enunciado de la prueba, datos de ejemplo y .gitignore" \
  .gitignore README.md data assets

commit "feat(db): esquema PostgreSQL y conexión" \
  backend/requirements.txt backend/app/__init__.py backend/app/config.py \
  backend/app/db.py backend/app/schema.sql

commit "feat(ingesta): reglas del proveedor y descartes por motivo" \
  backend/app/normalize.py

commit "feat(ingesta): cargador idempotente con resumen de descartes" \
  backend/app/load.py

commit "feat(api): sesiones de 10 minutos y días en America/Santiago" \
  backend/app/sessions.py

commit "feat(api): dispositivos, resumen diario y track GeoJSON" \
  backend/app/api.py

commit "feat(web): pantalla con filtros, sesiones y mapa Leaflet" \
  frontend

commit "feat(infra): servicio api en docker compose y Dockerfile" \
  docker-compose.yml backend/Dockerfile .env.example .dockerignore

commit "test: reglas de ingesta y cortes de sesión" \
  backend/tests backend/pytest.ini backend/requirements-dev.txt

commit "docs: decisiones, trazabilidad y reconstrucción del historial" \
  DECISIONES.md TRAZABILIDAD.md scripts

echo
echo "Historial (más antiguo primero):"
git --no-pager log --oneline --reverse
echo
if [ -n "$(git status --porcelain)" ]; then
  echo "Quedaron archivos sin trazabilidad:"
  git status --short
else
  echo "Árbol limpio: todos los archivos del proyecto están en algún commit."
fi
