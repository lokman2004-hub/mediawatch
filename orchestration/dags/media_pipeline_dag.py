from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import logging, sys, os

logger = logging.getLogger(__name__)

default_args = {
    "owner":            "architecture",
    "depends_on_past":  False,
    "start_date":       datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
}

def tache_scraping():
    sys.path.insert(0, "/opt/airflow/scraper")
    os.environ.setdefault("MINIO_ENDPOINT",   "minio:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "admin")
    os.environ.setdefault("MINIO_SECRET_KEY", "password123")
    from minio_uploader import pipeline_toutes_sources
    succes = pipeline_toutes_sources()
    if not succes:
        raise Exception("Echec du scraping")
    logger.info("Scraping termine avec succes")

def tache_bronze_silver():
    sys.path.insert(0, "/opt/airflow/transformation")
    os.environ.setdefault("MINIO_ENDPOINT",   "minio:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "admin")
    os.environ.setdefault("MINIO_SECRET_KEY", "password123")
    from bronze_to_silver import run
    run()
    logger.info("Bronze -> Silver termine")

def tache_silver_gold():
    sys.path.insert(0, "/opt/airflow/transformation")
    os.environ.setdefault("MINIO_ENDPOINT",   "minio:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "admin")
    os.environ.setdefault("MINIO_SECRET_KEY", "password123")
    from silver_to_gold import run
    run()
    logger.info("Silver -> Gold termine")

def tache_warehouse():
    sys.path.insert(0, "/opt/airflow/warehouse")
    os.environ.setdefault("MINIO_ENDPOINT",   "minio:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "admin")
    os.environ.setdefault("MINIO_SECRET_KEY", "password123")
    os.environ.setdefault("POSTGRES_HOST",     "postgres")
    os.environ.setdefault("POSTGRES_DB",       "mabd")
    os.environ.setdefault("POSTGRES_USER",     "airflow")
    os.environ.setdefault("POSTGRES_PASSWORD", "airflow")
    from load_warehouse import run
    run()
    logger.info("Warehouse charge avec succes")

def tache_notification(**context):
    execution_date = context.get("execution_date", datetime.now())
    logger.info(f"Pipeline architecture termine — {execution_date}")
    print(f"""
    Pipeline ARCHITECTURE termine
    Date      : {execution_date}
    Base      : mabd
    Tables    : publications, stats_quotidiennes, termes_frequents, executions
    Buckets   : media-bronze, media-silver, media-gold
    """)

with DAG(
    dag_id="media_pipeline",
    default_args=default_args,
    description="Pipeline Big Data — Agregation de flux actualites (projet architecture)",
    schedule_interval="@hourly",
    catchup=False,
    tags=["architecture", "media", "bigdata"],
) as dag:

    debut = BashOperator(
        task_id="debut",
        bash_command='echo "Pipeline media_pipeline demarre — $(date)"',
    )

    scraping = PythonOperator(
        task_id="scraping_toutes_sources",
        python_callable=tache_scraping,
    )

    bronze_silver = PythonOperator(
        task_id="bronze_vers_silver",
        python_callable=tache_bronze_silver,
    )

    silver_gold = PythonOperator(
        task_id="silver_vers_gold",
        python_callable=tache_silver_gold,
    )

    warehouse = PythonOperator(
        task_id="chargement_warehouse",
        python_callable=tache_warehouse,
    )

    notification = PythonOperator(
        task_id="notification",
        python_callable=tache_notification,
        provide_context=True,
    )

    fin = BashOperator(
        task_id="fin",
        bash_command='echo "Pipeline media_pipeline termine — $(date)"',
    )

    debut >> scraping >> bronze_silver >> silver_gold >> warehouse >> notification >> fin