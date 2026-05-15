# =============================================================================
# MINIO UPLOADER — Projet : architecture
# Lance les 5 scrapers et envoie vers MinIO (media-bronze)
# Buckets : media-bronze / media-silver / media-gold
# Base de données : mabd
# Tables : publications, stats_quotidiennes, termes_frequents, executions
# =============================================================================
from minio import Minio
from minio.error import S3Error
import json, io, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Buckets du projet architecture ────────────────────────────
BUCKET_BRONZE = "media-bronze"
BUCKET_SILVER = "media-silver"
BUCKET_GOLD   = "media-gold"

class MinIOUploader:
    def __init__(self):
        self.endpoint   = os.getenv("MINIO_ENDPOINT",   "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "admin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "password123")
        self.client = None

    def connect(self):
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=False
            )
            self.client.list_buckets()
            logger.info("Connecté à MinIO !")
            return True
        except Exception as e:
            logger.error(f"Erreur MinIO : {e}")
            return False

    def creer_buckets(self):
        for bucket in [BUCKET_BRONZE, BUCKET_SILVER, BUCKET_GOLD]:
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Bucket créé : {bucket}")
                else:
                    logger.info(f"Bucket existant : {bucket}")
            except S3Error as e:
                logger.error(f"Erreur bucket {bucket} : {e}")

    def construire_chemin(self, source, type_fichier="articles"):
        now = datetime.now()
        return (
            f"{source.lower()}/"
            f"{now.strftime('%Y/%m/%d')}/"
            f"{type_fichier}_{now.strftime('%H%M%S')}.json"
        )

    def envoyer_articles(self, articles, source):
        if not articles:
            logger.warning(f"[{source}] Aucun article à envoyer")
            return None
        payload = {
            "metadata": {
                "source":        source,
                "date_collecte": datetime.now().isoformat(),
                "nb_articles":   len(articles),
                "version":       "1.0",
                "projet":        "architecture",
            },
            "articles": articles
        }
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        chemin = self.construire_chemin(source)
        try:
            self.client.put_object(
                bucket_name=BUCKET_BRONZE,
                object_name=chemin,
                data=io.BytesIO(json_bytes),
                length=len(json_bytes),
                content_type="application/json"
            )
            logger.info(f"[{source}] {len(articles)} articles → s3://{BUCKET_BRONZE}/{chemin}")
            return chemin
        except S3Error as e:
            logger.error(f"[{source}] Erreur upload : {e}")
            return None


def pipeline_toutes_sources():
    print("\n" + "█" * 60)
    print("  PROJET : architecture")
    print("  PIPELINE — TOUTES SOURCES")
    print(f"  Démarré à : {datetime.now().strftime('%H:%M:%S')}")
    print("█" * 60)

    uploader = MinIOUploader()
    if not uploader.connect():
        print("Arrêt : impossible de se connecter à MinIO")
        return False
    uploader.creer_buckets()

    sources = []

    try:
        from bbc_scraper import BBCScraper
        sources.append(("bbc", BBCScraper()))
        print("✔ BBC News chargé")
    except Exception as e:
        print(f"✘ BBC News : {e}")

    try:
        from cnn_scraper import CNNScraper
        sources.append(("cnn", CNNScraper()))
        print("✔ CNN chargé")
    except Exception as e:
        print(f"✘ CNN : {e}")

    try:
        from aljazeera_scraper import AlJazeeraScraper
        sources.append(("aljazeera", AlJazeeraScraper()))
        print("✔ Al Jazeera chargé")
    except Exception as e:
        print(f"✘ Al Jazeera : {e}")

    try:
        from hespress_scraper import HespressScraper
        sources.append(("hespress", HespressScraper()))
        print("✔ Hespress chargé")
    except Exception as e:
        print(f"✘ Hespress : {e}")

    try:
        from akhbarona_scraper import AkhbaronaScraper
        sources.append(("akhbarona", AkhbaronaScraper()))
        print("✔ Akhbarona chargé")
    except Exception as e:
        print(f"✘ Akhbarona : {e}")

    resultats = {}
    total = 0

    for source_id, scraper in sources:
        print(f"\n{'=' * 60}")
        print(f"  SCRAPING : {source_id.upper()}")
        print(f"{'=' * 60}")
        try:
            articles = scraper.run()
            uploader.envoyer_articles(articles, source=source_id)
            resultats[source_id] = len(articles)
            total += len(articles)
        except Exception as e:
            logger.error(f"[{source_id}] Erreur : {e}")
            resultats[source_id] = 0

    print("\n" + "█" * 60)
    print("  RÉSUMÉ FINAL")
    print("█" * 60)
    for src, nb in resultats.items():
        print(f"  {src.upper():<15} : {nb} articles")
    print(f"  {'TOTAL':<15} : {total} articles")
    print(f"\n  Buckets MinIO : {BUCKET_BRONZE} / {BUCKET_SILVER} / {BUCKET_GOLD}")
    print(f"  Ouvre http://localhost:9001 pour vérifier.")
    print("█" * 60)
    return True


if __name__ == "__main__":
    pipeline_toutes_sources()