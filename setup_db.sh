#!/usr/bin/env bash
# One-time Postgres setup for local or Codespaces use.
set -e

DB_USER="warhammer"
DB_PASS="warhammer"
DB_NAME="warhammer_leaks"

echo "Creating Postgres user and database..."
psql -U postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  psql -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "Done. DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
