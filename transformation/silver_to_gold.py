# =============================================================================
# TRANSFORMATION SILVER → GOLD — Projet : architecture
# Buckets : media-silver → media-gold
# Tables cibles : stats_quotidiennes, termes_frequents
# =============================================================================
import json, io, re, logging
from datetime import datetime
from collections import Counter
from minio import Minio
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MINIO_HOST    = "localhost:9000"
MINIO_ACCESS  = "admin"
MINIO_SECRET  = "password123"
BUCKET_SILVER = "media-silver"
BUCKET_GOLD   = "media-gold"

STOPWORDS = {
    # Anglais
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","it","its","this","that","was","are","be","been","being","have",
    "has","had","he","she","they","we","you","i","by","as","from","up",
    "not","no","so","do","did","does","will","would","could","should","can",
    "said","also","about","after","before","more","over","their","which",
    "who","what","when","where","how","all","one","two","new","just","than",
    # Français
    "le","la","les","un","une","des","de","du","et","en","au","aux","est",
    "qui","que","pour","par","sur","dans","avec","mais","ou","si","ne","pas",
    "il","elle","ils","elles","nous","vous","je","tu","se","ce","cet","cette",
    "son","sa","ses","mon","ma","mes","ton","ta","tes","leur","leurs","plus",
    "tout","tous","toute","toutes","très","bien","aussi","comme","même",
    # Communs
    "s","t","d","l","m","j","n","y","c",
}

def connecter_minio():
    client = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    logger.info("Connecté à MinIO !")
    return client

def lire_silver(client):
    articles = []
    try:
        objets = list(client.list_objects(BUCKET_SILVER, recursive=True))
    except Exception as e:
        logger.error(f"Erreur lecture silver : {e}")
        return []

    for obj in objets:
        try:
            response = client.get_object(BUCKET_SILVER, obj.object_name)
            data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list):
                articles.extend(data)
            elif isinstance(data, dict) and "articles" in data:
                articles.extend(data["articles"])
            logger.info(f"  Lecture : {obj.object_name}")
        except Exception as e:
            logger.error(f"  Erreur {obj.object_name} : {e}")
    return articles

def extraire_mots(texte):
    """Extrait les mots significatifs d'un texte."""
    if not texte:
        return []
    mots = re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', texte.lower())
    return [m for m in mots if m not in STOPWORDS]

def sauvegarder_gold(client, rapport, nom_fichier):
    """Sauvegarde un rapport Gold dans MinIO."""
    now = datetime.now()
    chemin = f"rapports/{now.strftime('%Y/%m/%d')}/{nom_fichier}_{now.strftime('%H%M%S')}.json"
    json_bytes = json.dumps(rapport, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        bucket_name=BUCKET_GOLD,
        object_name=chemin,
        data=io.BytesIO(json_bytes),
        length=len(json_bytes),
        content_type="application/json"
    )
    logger.info(f"Gold sauvegardé : s3://{BUCKET_GOLD}/{chemin}")
    return chemin

def run():
    print("\n" + "=" * 55)
    print("  TRANSFORMATION SILVER → GOLD")
    print("  Projet : architecture | Buckets : media-*")
    print("=" * 55)

    client = connecter_minio()

    print("\nLecture du bucket 'media-silver'...")
    articles = lire_silver(client)
    print(f"Total articles Silver lus : {len(articles)}")

    if not articles:
        print("Aucun article trouvé. Lance d'abord bronze_to_silver.py")
        return

    # ── DataFrame pandas ──────────────────────────────────────
    df = pd.DataFrame(articles)

    # Nettoyage colonnes
    df["date_publication"] = pd.to_datetime(df["date_publication"], errors="coerce", utc=True)
    df["date_jour"]        = df["date_publication"].dt.date.astype(str)
    df["nb_mots"]          = pd.to_numeric(df["nb_mots"], errors="coerce").fillna(0).astype(int)

    today = datetime.now().strftime("%Y-%m-%d")

    # ── RAPPORT 1 : Articles par source ───────────────────────
    par_source = df.groupby("source").agg(
        nb_articles=("id", "count"),
        moy_mots=("nb_mots", "mean"),
    ).reset_index()
    par_source["moy_mots"] = par_source["moy_mots"].round(0).astype(int)

    # ── RAPPORT 2 : Articles par langue ───────────────────────
    par_langue = df.groupby("langue").agg(
        nb_articles=("id", "count")
    ).reset_index()

    # ── RAPPORT 3 : Articles par catégorie ────────────────────
    par_categorie = df.groupby("categorie").agg(
        nb_articles=("id", "count")
    ).reset_index().sort_values("nb_articles", ascending=False)

    # ── RAPPORT 4 : Articles par pays ─────────────────────────
    par_pays = df.groupby("pays").agg(
        nb_articles=("id", "count")
    ).reset_index().sort_values("nb_articles", ascending=False)

    # ── RAPPORT 5 : Top mots fréquents ────────────────────────
    tous_mots = []
    for _, row in df.iterrows():
        tous_mots.extend(extraire_mots(row.get("contenu", "")))
        tous_mots.extend(extraire_mots(row.get("titre", "")))

    top_mots = Counter(tous_mots).most_common(30)

    # ── RAPPORT 6 : Qualité des données ───────────────────────
    qualite = {
        "total_articles":      len(df),
        "articles_avec_titre": int(df["titre"].notna().sum()),
        "articles_avec_date":  int(df["date_publication"].notna().sum()),
        "articles_avec_auteur":int((df["auteur"] != "Inconnu").sum()),
        "articles_courts":     int((df["nb_mots"] < 100).sum()),
        "moy_mots_global":     int(df["nb_mots"].mean()),
        "completude_titre":    round(df["titre"].notna().mean() * 100, 1),
        "completude_date":     round(df["date_publication"].notna().mean() * 100, 1),
        "completude_auteur":   round((df["auteur"] != "Inconnu").mean() * 100, 1),
    }

    # ── Assemblage du rapport Gold ─────────────────────────────
    rapport_gold = {
        "metadata": {
            "date_generation": datetime.now().isoformat(),
            "nb_articles":     len(df),
            "projet":          "architecture",
            "base_donnees":    "mabd",
        },
        "par_source":    par_source.to_dict(orient="records"),
        "par_langue":    par_langue.to_dict(orient="records"),
        "par_categorie": par_categorie.to_dict(orient="records"),
        "par_pays":      par_pays.to_dict(orient="records"),
        "top_mots":      [{"mot": m, "occurrences": n} for m, n in top_mots],
        "qualite":       qualite,
    }

    # ── Sauvegarde Gold ───────────────────────────────────────
    sauvegarder_gold(client, rapport_gold, "rapport_gold")

    # ── Affichage résumé ──────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"  RAPPORT GOLD — {today}")
    print(f"{'=' * 55}")
    print(f"\n  Articles par source :")
    for _, row in par_source.iterrows():
        print(f"    {row['source']:<20} : {row['nb_articles']} articles (moy. {row['moy_mots']} mots)")

    print(f"\n  Articles par langue :")
    for _, row in par_langue.iterrows():
        print(f"    {row['langue']:<10} : {row['nb_articles']} articles")

    print(f"\n  Articles par pays :")
    for _, row in par_pays.iterrows():
        print(f"    {row['pays']:<15} : {row['nb_articles']} articles")

    print(f"\n  Top 10 mots fréquents :")
    for mot, nb in top_mots[:10]:
        print(f"    {mot:<20} : {nb} fois")

    print(f"\n  Qualité des données :")
    print(f"    Complétude titre  : {qualite['completude_titre']}%")
    print(f"    Complétude date   : {qualite['completude_date']}%")
    print(f"    Complétude auteur : {qualite['completude_auteur']}%")
    print(f"    Articles courts   : {qualite['articles_courts']}")

    print(f"\n  Rapport Gold sauvegardé dans media-gold/")
    print(f"  Prochaine étape : python load_warehouse.py")
    print(f"{'=' * 55}")

if __name__ == "__main__":
    run()