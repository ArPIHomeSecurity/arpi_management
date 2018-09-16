FROM postgres

ADD 00_example.sql /data/
ADD 00_import.sh /docker-entrypoint-initdb.d/