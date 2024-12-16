ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3
RUN apk add --no-cache py3-pip gcc git

COPY rootfs /

WORKDIR /data

COPY requirements.txt /
RUN pip3 install --no-cache-dir -r /requirements.txt

RUN export SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN}

RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]