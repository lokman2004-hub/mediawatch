# =============================================================================
# KAFKA CONSUMER — Projet : architecture
# Écoute le topic Kafka et insère dans PostgreSQL
# Base : mabd | Table : publications
# =============================================================================
import json, signal, sys, logging
import psycopg
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KAFKA_BROKER = "kafka:29092"
KAFKA_TOPIC  = "media-articles"
KAFKA_GROUP  = "architecture-consumer-group"
PG_URL       = "postgresql://airflow:airflow@postgres:5432/mabd"

running = True

def signal_handler(sig, frame):
    global running
    print("\nArrêt du consumer...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def connecter_postgres():
    conn = psycopg.connect(PG_URL)
    logger.info("Connecté à PostgreSQL (mabd) !")
    return conn

def connecter_kafka():
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        consumer_timeout_ms=10000
    )
    logger.info("Connecté à Kafka !")
    return consumer

def inserer_publication(conn, art):
    """Insère un article dans la table 'publications' de mabd."""
    sql = """
        INSERT INTO publications (
            id, titre, auteur, date_publication,
            categorie, description, contenu,
            source, pays, url, langue, nb_mots, date_collecte
        ) VALUES (
            %(id)s, %(titre)s, %(auteur)s, %(date_publication)s,
            %(categorie)s, %(description)s, %(contenu)s,
            %(source)s, %(pays)s, %(url)s, %(langue)s,
            %(nb_mots)s, %(date_collecte)s
        )
        ON CONFLICT (id) DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {
            "id":               art.get("id", ""),
            "titre":            art.get("titre", ""),
            "auteur":           art.get("auteur", ""),
            "date_publication": art.get("date_publication"),
            "categorie":        art.get("categorie", ""),
            "description":      art.get("description", ""),
            "contenu":          art.get("contenu", ""),
            "source":           art.get("source", ""),
            "pays":             art.get("pays", ""),
            "url":              art.get("url", ""),
            "langue":           art.get("langue", "en"),
            "nb_mots":          art.get("nb_mots", 0),
            "date_collecte":    art.get("date_collecte"),
        })
    conn.commit()

def run():
    global running
    print("\n" + "=" * 55)
    print("  KAFKA CONSUMER — Projet : architecture")
    print("  Topic : media-articles | Base : mabd")
    print("  Table : publications")
    print("=" * 55)
    print("  Appuie sur Ctrl+C pour arrêter.\n")

    conn     = connecter_postgres()
    consumer = connecter_kafka()

    inseres  = 0
    doublons = 0

    print(f"Écoute du topic '{KAFKA_TOPIC}'...\n")

    try:
        for message in consumer:
            if not running:
                break
            art = message.value
            titre = art.get("titre", "Sans titre")[:60]
            try:
                inserer_publication(conn, art)
                inseres += 1
                print(f"  ✔ Inséré  : {titre}")
            except Exception:
                doublons += 1
                print(f"  ~ Doublon : {titre}")
    except Exception as e:
        logger.error(f"Erreur Kafka : {e}")
    finally:
        consumer.close()
        conn.close()

    print(f"\n{'=' * 55}")
    print(f"  Résumé :")
    print(f"    Publications insérées : {inseres}")
    print(f"    Doublons ignorés      : {doublons}")
    print(f"    Base : mabd | Table : publications")
    print(f"{'=' * 55}")

if __name__ == "__main__":
    run()