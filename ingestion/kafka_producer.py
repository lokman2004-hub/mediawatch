# =============================================================================
# KAFKA PRODUCER — Projet : architecture
# Lit les articles depuis media-bronze et envoie vers Kafka
# Topic : media-articles
# =============================================================================
import json, time, logging
from minio import Minio
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MINIO_HOST    = "minio:9000"
MINIO_ACCESS  = "admin"
MINIO_SECRET  = "password123"
BUCKET_BRONZE = "media-bronze"
KAFKA_BROKER  = "kafka:29092"
KAFKA_TOPIC   = "media-articles"

def connecter_minio():
    client = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    logger.info("Connecté à MinIO !")
    return client

def connecter_kafka():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        acks="all",
        retries=3
    )
    logger.info("Connecté à Kafka !")
    return producer

def lire_articles(client):
    articles = []
    urls_vus = set()
    objets = client.list_objects(BUCKET_BRONZE, recursive=True)
    for obj in objets:
        try:
            response = client.get_object(BUCKET_BRONZE, obj.object_name)
            data = json.loads(response.read().decode("utf-8"))
            batch = data.get("articles", data) if isinstance(data, dict) else data
            for art in batch:
                url = art.get("url", "")
                if url and url not in urls_vus:
                    urls_vus.add(url)
                    articles.append(art)
        except Exception as e:
            logger.error(f"Erreur {obj.object_name} : {e}")
    return articles

def run():
    print("\n" + "=" * 55)
    print("  KAFKA PRODUCER — Projet : architecture")
    print("  Topic : media-articles")
    print("=" * 55)

    client   = connecter_minio()
    producer = connecter_kafka()

    print(f"\nLecture de '{BUCKET_BRONZE}'...")
    articles = lire_articles(client)
    print(f"  {len(articles)} articles trouvés.")

    if not articles:
        print("Aucun article. Lance d'abord minio_uploader.py")
        return

    print(f"\nEnvoi vers le topic '{KAFKA_TOPIC}'...")
    envoyes = 0
    for art in articles:
        try:
            producer.send(KAFKA_TOPIC, value=art)
            envoyes += 1
            print(f"  ✔ Envoyé : {art.get('titre', 'Sans titre')[:60]}")
            time.sleep(0.1)
        except Exception as e:
            print(f"  ✘ Erreur : {e}")

    producer.flush()
    producer.close()

    print(f"\n{'=' * 55}")
    print(f"  {envoyes} articles envoyés dans Kafka !")
    print(f"  Lance maintenant : python kafka_consumer.py")
    print(f"{'=' * 55}")

if __name__ == "__main__":
    run()