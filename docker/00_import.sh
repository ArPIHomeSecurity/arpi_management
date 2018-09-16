psql -c "CREATE USER argus WITH PASSWORD 'argus';"
createdb -E UTF8 -e argus
psql argus < /data/00_example.sql