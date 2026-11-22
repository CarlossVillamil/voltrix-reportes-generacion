# API de Reportes de Generación (Equipo 4)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencias primero, para reutilizar la capa si solo cambia el código
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY openapi.yaml .

# Usuario sin privilegios
RUN useradd --create-home --uid 1000 voltrix && chown -R voltrix /srv
USER voltrix

EXPOSE 8000
# Un solo proceso de uvicorn: la instancia tiene 1 GiB y el paralelismo lo pone
# el ProcessPoolExecutor del Map-Reduce, no uvicorn.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
