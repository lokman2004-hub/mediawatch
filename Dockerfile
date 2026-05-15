FROM apache/airflow:2.8.0

LABEL maintainer="Ryad Ghazaouni & Akram Mouhlal"
LABEL project="MediaWatch Big Data Pipeline"
LABEL version="1.0.0"

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV MINIO_ENDPOINT=minio:9000
ENV MINIO_ACCESS_KEY=admin
ENV MINIO_SECRET_KEY=password123
ENV POSTGRES_HOST=postgres
ENV POSTGRES_DB=mabd
ENV POSTGRES_USER=airflow
ENV POSTGRES_PASSWORD=airflow

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

COPY --chown=airflow:root scraper/        /opt/airflow/scraper/
COPY --chown=airflow:root transformation/ /opt/airflow/transformation/
COPY --chown=airflow:root warehouse/      /opt/airflow/warehouse/
COPY --chown=airflow:root dashboard/      /opt/airflow/dashboard/
COPY --chown=airflow:root orchestration/dags/ /opt/airflow/dags/

WORKDIR /opt/airflow

EXPOSE 8050