#!/usr/bin/with-contenv bashio

echo "token"
echo ${SUPERVISOR_TOKEN}
echo ${__BASHIO_SUPERVISOR_API}
export SUPERVISOR_TOKEN="${__BASHIO_SUPERVISOR_API}"

python3 /app/main.py