ARG BUILD_FROM
FROM python:3.12 as builder

WORKDIR /tmp
COPY pyproject.toml poetry.lock /tmp/

RUN pip install poetry==1.8.5

RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM $BUILD_FROM

COPY  rootfs /

WORKDIR /

RUN apk add --no-cache git

COPY --from=builder /tmp/requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir -r /requirements.txt

WORKDIR /data
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]