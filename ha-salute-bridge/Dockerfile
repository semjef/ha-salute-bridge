ARG BUILD_FROM
FROM homeassistant/amd64-base:latest

RUN apk add --no-cache python3
RUN apk add --no-cache py3-pip gcc git

RUN pip3 install poetry==1.8.5

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

COPY rootfs /

WORKDIR /data

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --without-hashes -o /requirements.txt
RUN pip3 install --no-cache-dir -r /requirements.txt

RUN export SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN}

RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]