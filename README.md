docker-compose down

docker-compose down -v

docker logs airflow-webserver --tail 50
docker logs airflow-scheduler --tail 50

docker exec -it postgres psql -U airflow -d mabd

docker exec -it postgres psql -U airflow -d mabd \
  -c "TRUNCATE TABLE publications, stats_quotidiennes, termes_frequents, executions CASCADE;"

docker exec -it airflow-webserver bash -c \
  "python -c \"from minio import Minio; c=Minio('minio:9000',access_key='admin',secret_key='password123',secure=False); [print(b.name) for b in c.list_buckets()]\""# mediawatch
