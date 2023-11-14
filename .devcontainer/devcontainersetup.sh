#!/bin/bash
# This script is to be executed on creation of the dev container in order to create a working development enviornment

# 1. setup the python enviornment
pip3 install --upgrade poetry 
poetry run pip install --upgrade pip poetry 
poetry install

# 2. create minimalistic secret files for all the modules. 
# 2.1 Neo4j
UNS_graphdb__username=neo4j
UNS_graphdb__password=$(openssl rand -base64 32 | tr -dc '[:alnum:]')
echo "graphdb:
  username: "${UNS_graphdb__username}"
  password: "${UNS_graphdb__password}"
dynaconf_merge: true
" > ./03_uns_graphdb/conf/.secrets.yaml

# 2.2 Timescale DB
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc '[:alnum:]')
UNS_historian__username=uns_dbuser
UNS_historian__password=$(openssl rand -base64 32 | tr -dc '[:alnum:]')

UNS_historian__database=uns_historian
UNS_historian__table=UnifiedNamespace

echo "historian:
  username: "${UNS_historian__username}"
  password: "${UNS_historian__password}"
dynaconf_merge: true
# This password is for your reference if you ever need to login as postgres user
# POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
" > ./04_uns_historian/conf/.secrets.yaml

# 3. Install the docker files needed for testing the environment. 
# 3.1 MQTT used by all modules 
docker run \
    --name uns_emqx_mqtt \
    -p1883:1883 -p18083:18083 \
    -d \
    emqx/emqx:latest
# 3.2 Graph DB used by 03_uns_graphdb
docker run \
    --name  uns_graphdb \
    -p7474:7474 -p7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/plugins:/plugins \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    --env NEO4J_AUTH=${UNS_graphdb__username}/${UNS_graphdb__password} \
    --env apoc.export.file.enabled=true \
    --env apoc.import.file.enabled=true \
    --env apoc.import.file.use_neo4j_config=true \
    --env NEO4J_PLUGINS=\[\"apoc\"\] \
    neo4j:latest

# 3.3 Historian DB used by 04_uns_historian
docker run \
    --name uns_timescaledb  \
    -p 5432:5432  \
    -v $HOME/timescaledb/data:/var/lib/postgresql/data \
    -d \
    -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
    timescale/timescaledb:latest-pg14

# 3.4 Kafka used by 06_uns_kafka

docker run \
    --name uns_kafka \
    --env KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://localhost:9092" \
    --env ALLOW_PLAINTEXT_LISTENER="yes" \
    --env KAFKA_CFG_NODE_ID="0" \
    --env KAFKA_CFG_PROCESS_ROLES="controller,broker" \
    --env KAFKA_CFG_LISTENERS="PLAINTEXT://:9092,CONTROLLER://:9093" \
    --env KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP="CONTROLLER:PLAINTEXT, PLAINTEXT:PLAINTEXT" \
    --env KAFKA_CFG_CONTROLLER_QUORUM_VOTERS="0@localhost:9093" \
    --env KAFKA_CFG_CONTROLLER_LISTENER_NAMES="CONTROLLER" \
    -p 9092:9092 \
    -d \
    bitnami/kafka:latest

# 3.5 wait for docker to be up and running
# first wait for the database to be running
# Function to check if PostgreSQL is ready
check_postgres_ready() {
    docker exec uns_timescaledb pg_isready -q
}
# loop to check 
echo "Waiting for  timescaledb to start ."
while [ "True" ] ; do
  if check_postgres_ready; then
    break;
  else
    echo -n .;
    sleep 1
  fi
done

# 3.6 basic database setup needed for the historian ( create users, database, timeseries extension etc.)

docker exec \
  -e PGPASSWORD=${POSTGRES_PASSWORD} \
  -e UNS_historian__database=${UNS_historian__database} \
  -e UNS_historian__username=${UNS_historian__username} \
  -e UNS_historian__password=${UNS_historian__password} \
  -e UNS_historian__table=${UNS_historian__table} \
  -it uns_timescaledb \
  bash -c "
  PGPASSWORD=${PGPASSWORD} psql -U postgres -p 5432 -c '
    CREATE DATABASE ${UNS_historian__database};'
  PGPASSWORD=${PGPASSWORD} psql -U postgres -p 5432 -d ${UNS_historian__database} -c '
    CREATE EXTENSION IF NOT EXISTS timescaledb;
    CREATE ROLE ${UNS_historian__username} LOGIN PASSWORD '\''${UNS_historian__password}'\'';'

  PGPASSWORD=${UNS_historian__password} psql -U ${UNS_historian__username} -p 5432 -d ${UNS_historian__database} -c'
    CREATE TABLE ${UNS_historian__table} (time TIMESTAMPTZ NOT NULL, topic TEXT NOT NULL, client_id TEXT, mqtt_msg JSONB);
    SELECT create_hypertable('\''${UNS_historian__table}'\'', '\''time'\'');'
  "
