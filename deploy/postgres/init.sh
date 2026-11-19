#!/bin/sh
# Creates one database and one role per service on first start. Passwords come from the environment, never from this file.
set -eu
for svc in identity accounting intelligence marketplace billing advisory notification audit keycloak; do
  eval "pw=\${DB_PASSWORD_$(echo $svc | tr a-z A-Z)}"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" <<SQL
CREATE ROLE ${svc}_owner LOGIN PASSWORD '${pw}';
CREATE DATABASE credsort_${svc} OWNER ${svc}_owner;
SQL
done
