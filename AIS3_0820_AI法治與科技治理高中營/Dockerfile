FROM python:3.12.13

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY app/ /srv/app/
COPY static/ /srv/static/
COPY scripts/ /srv/scripts/
COPY challenges.json /srv/challenges.json

RUN useradd --create-home --uid 10001 ctf \
    && mkdir -p /srv/data \
    && chown -R ctf:ctf /srv

USER ctf

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
