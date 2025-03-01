#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."

until pg_isready -h postgres -p 5432 -U postgres; do
  sleep 2
done

echo "Waiting for RabbitMQ..."

until nc -z rabbitmq 5672; do
  sleep 2
done

echo "Dependencies are ready, starting app..."
exec "$@"
