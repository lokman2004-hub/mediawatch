import json, logging, time
from datetime import datetime
from minio import Minio
import psycopg

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MINIO_HOST    = "minio:9000"
MINIO_ACCESS  = "admin"
MINIO_SECRET  = "password123"
BUCKET_SILVER = "media-silver"
BUCKET_GOLD   = "media-gold"
PG_URL        = "postgresql://airflow:airflow@postgres:5432/mabd"

def nettoyer_texte(valeur):
    if not isinstance(valeur, str):
        return valeur
    try:
        return valeur.encode('utf-8', errors='ignore').decode('utf-8')
    except Exception:
        return valeur.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')

def decoder_bytes(raw_bytes):
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']:
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return raw_bytes.decode('utf-8', errors='ignore')

def connecter_minio():
    client = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    logger.info("Connecte a MinIO !")
    return client

def connecter_postgres():
    conn = psycopg.connect(PG_URL)
    logger.info("Connecte a PostgreSQL (mabd) !")
    return conn

def lire_silver(client):
    articles = []
    try:
        for obj in client.list_objects(BUCKET_SILVER, recursive=True):
            response = client.get_object(BUCKET_SILVER, obj.object_name)
            raw = response.read()
            texte = decoder_bytes(raw)
            data = json.loads(texte)
            batch = data.get("articles", data) if isinstance(data, dict) else data
            # Nettoyer chaque article
            batch_clean = []
            for art in batch:
                art_clean = {k: nettoyer_texte(v) if isinstance(v, str) else v for k, v in art.items()}
                batch_clean.append(art_clean)
            articles.extend(batch_clean)
            logger.info(f"  Silver lu : {obj.object_name} ({len(batch_clean)} articles)")
    except Exception as e:
        logger.error(f"Erreur lecture Silver : {e}")
    return articles

def lire_gold(client):
    rapports = []
    try:
        for obj in client.list_objects(BUCKET_GOLD, recursive=True):
            response = client.get_object(BUCKET_GOLD, obj.object_name)
            raw = response.read()
            texte = decoder_bytes(raw)
            data = json.loads(texte)
            rapports.append(data)
            logger.info(f"  Gold lu : {obj.object_name}")
    except Exception as e:
        logger.error(f"Erreur lecture Gold : {e}")
    return rapports

def charger_publications(conn, articles):
    inseres = 0
    doublons = 0
    sql = """
        INSERT INTO publications (
            id, titre, auteur, date_publication, categorie,
            description, contenu, source, pays, url,
            langue, nb_mots, date_collecte
        ) VALUES (
            %(id)s, %(titre)s, %(auteur)s, %(date_publication)s, %(categorie)s,
            %(description)s, %(contenu)s, %(source)s, %(pays)s, %(url)s,
            %(langue)s, %(nb_mots)s, %(date_collecte)s
        )
        ON CONFLICT (id) DO NOTHING;
    """
    with conn.cursor() as cur:
        for art in articles:
            try:
                cur.execute(sql, {
                    "id":               art.get("id", ""),
                    "titre":            art.get("titre", ""),
                    "auteur":           art.get("auteur", "Inconnu"),
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
                inseres += 1
            except Exception:
                doublons += 1
    conn.commit()
    return inseres, doublons

def charger_stats(conn, rapports):
    today = datetime.now().date()
    with conn.cursor() as cur:
        for rapport in rapports:
            for row in rapport.get("par_source", []):
                try:
                    cur.execute("""
                        INSERT INTO stats_quotidiennes
                            (date_rapport, source, pays, langue, nb_publications, moy_mots)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (
                        today,
                        nettoyer_texte(row.get("source", "")),
                        "",
                        "",
                        row.get("nb_articles", 0),
                        row.get("moy_mots", 0),
                    ))
                except Exception:
                    pass

            for item in rapport.get("top_mots", []):
                try:
                    cur.execute("""
                        INSERT INTO termes_frequents (date_rapport, terme, occurrences)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (today, nettoyer_texte(item.get("mot", "")), item.get("occurrences", 0)))
                except Exception:
                    pass

    conn.commit()
    logger.info("Stats et termes inseres.")

def enregistrer_execution(conn, etape, statut, nb_articles, duree, message=""):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO executions (etape, statut, nb_articles, duree_secondes, message)
            VALUES (%s, %s, %s, %s, %s);
        """, (etape, statut, nb_articles, duree, message))
    conn.commit()

def afficher_resume(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM publications;")
        total = cur.fetchone()[0]
        cur.execute("SELECT source, COUNT(*) as nb FROM publications GROUP BY source ORDER BY nb DESC;")
        par_source = cur.fetchall()
        cur.execute("SELECT langue, COUNT(*) as nb FROM publications GROUP BY langue ORDER BY nb DESC;")
        par_langue = cur.fetchall()
        cur.execute("""
            SELECT terme, occurrences FROM termes_frequents
            WHERE date_rapport = CURRENT_DATE
            ORDER BY occurrences DESC LIMIT 5;
        """)
        top_termes = cur.fetchall()

    print(f"\n{'=' * 50}")
    print(f"  RESUME DATA WAREHOUSE — mabd")
    print(f"{'=' * 50}")
    print(f"  Table publications : {total} articles")
    print(f"\n  Par source :")
    for src, nb in par_source:
        print(f"    {src:<20} : {nb}")
    print(f"\n  Par langue :")
    for lang, nb in par_langue:
        print(f"    {lang:<10} : {nb}")
    if top_termes:
        print(f"\n  Top 5 termes du jour :")
        for terme, nb in top_termes:
            print(f"    {terme:<20} : {nb} fois")
    print(f"{'=' * 50}")
    print(f"  Data Warehouse mis a jour avec succes !")
    print(f"{'=' * 50}")

def run():
    debut = time.time()
    print("\n" + "=" * 55)
    print("  DATA WAREHOUSE — Projet : architecture")
    print("  Base : mabd")
    print("=" * 55)

    client = connecter_minio()
    conn   = connecter_postgres()

    print("\nChargement Silver → table publications...")
    articles = lire_silver(client)
    inseres, doublons = charger_publications(conn, articles)
    print(f"  Inseres  : {inseres}")
    print(f"  Doublons : {doublons}")

    print("\nChargement Gold → tables analytiques...")
    rapports = lire_gold(client)
    charger_stats(conn, rapports)
    print(f"  {len(rapports)} rapport(s) Gold charge(s).")

    duree = round(time.time() - debut, 2)
    enregistrer_execution(conn, "load_warehouse", "success", inseres, duree)

    afficher_resume(conn)
    conn.close()

if __name__ == "__main__":
    run()