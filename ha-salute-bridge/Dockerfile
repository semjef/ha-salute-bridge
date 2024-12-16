ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3

RUN pip3 install poetry==1.8.5

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache


COPY rootfs /

WORKDIR /data

COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --without test --no-root && rm -rf ${POETRY_CACHE_DIR}

RUN export SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN}

RUN chmod a+x /run.sh

CMD [ "/app/run.sh" ]