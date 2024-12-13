ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3


COPY rootfs /

WORKDIR /data

RUN export SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN}

RUN chmod a+x /run.sh

CMD [ "/app/run.sh" ]