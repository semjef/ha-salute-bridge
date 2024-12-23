#!/usr/bin/with-contenv bashio

echo "token"
export SUPERVISOR_TOKEN="${__BASHIO_SUPERVISOR_API}"
python3 /app/main.py