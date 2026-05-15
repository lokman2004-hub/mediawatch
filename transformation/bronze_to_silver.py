# =============================================================================
# TRANSFORMATION BRONZE → SILVER — Projet : architecture
# Buckets : media-bronze → media-silver
# =============================================================================
import json, re, io, logging
from datetime import datetime
from minio import Minio
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
MINIO_HOST    = "localhost:9000"
MINIO_ACCESS  = "admin"
MINIO_SECRET  = "password123"
BUCKET_BRONZE = "media-bronze"
BUCKET_SILVER = "media-silver"

STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","it","its","this","that","was","are","be","been","being","have",
    "has","had","he","she","they","we","you","i","by","as","from","up",
    "not","no","so","do","did","does","will","would","could","should","can",
    "le","la","les","un","une","des","de","du","et","en","au","aux","est",
    "qui","que","pour","par","sur","dans","avec","mais","ou","si","ne","pas",
    "il","elle","ils","elles","nous","vous","je","tu","se","ce","cet","cette",
}

def connecter_minio():
    client = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    logger.info("Connecté à MinIO !")
    return client

def lire_bronze(client):
    """Lit tous les fichiers du bucket media-bronze."""
    articles = []
    urls_vus = set()

    try:
        objets = list(client.list_objects(BUCKET_BRONZE, recursive=True))
    except Exception as e:
        logger.error(f"Erreur lecture bronze : {e}")
        return []

    for obj in objets:
        try:
            response = client.get_object(BUCKET_BRONZE, obj.object_name)
            data = json.loads(response.read().decode("utf-8"))

            # Gère format {metadata, articles} ou liste directe
            if isinstance(data, list):
                batch = data
            elif isinstance(data, dict) and "articles" in data:
                batch = data["articles"]
            else:
                continue

            for art in batch:
                url = art.get("url", "")
                if url and url not in urls_vus:
                    urls_vus.add(url)
                    articles.append(art)
                else:
                    logger.info(f"  Doublon ignoré : {url[:60]}...")

            logger.info(f"  Lecture : {obj.object_name} → {len(batch)} articles")
        except Exception as e:
            logger.error(f"  Erreur {obj.object_name} : {e}")

    return articles

def nettoyer_html(texte):
    """Supprime les balises HTML résiduelles."""
    if not texte:
        return ""
    texte = re.sub(r'<[^>]+>', ' ', texte)
    texte = re.sub(r'&nbsp;', ' ', texte)
    texte = re.sub(r'&amp;', '&', texte)
    texte = re.sub(r'&lt;', '<', texte)
    texte = re.sub(r'&gt;', '>', texte)
    texte = re.sub(r'\s+', ' ', texte)
    return texte.strip()

def detecter_langue(titre, contenu):
    """Détecte la langue : ar / fr / en."""
    texte = (titre or "") + " " + (contenu or "")
    arabic = sum(1 for c in texte if '\u0600' <= c <= '\u06FF')
    if arabic > len(texte) * 0.15:
        return "ar"
    mots_fr = {"le","la","les","de","du","et","en","un","une","des","pour","avec","sur","dans","est"}
    mots = set(texte.lower().split())
    if len(mots & mots_fr) >= 3:
        return "fr"
    return "en"

def valider_article(art):
    """Contrôle qualité — retourne (valide, liste_problemes)."""
    problemes = []
    if not art.get("titre") or art["titre"] == "Sans titre":
        problemes.append("Titre manquant")
    if not art.get("date_publication"):
        problemes.append("Date manquante")
    nb_mots = len((art.get("contenu") or "").split())
    if nb_mots < 50:
        problemes.append(f"Contenu trop court ({nb_mots} mots)")
    if not art.get("url"):
        problemes.append("URL manquante")
    if not art.get("source"):
        problemes.append("Source manquante")
    return len(problemes) == 0, problemes

def transformer_article(art):
    """Nettoie et enrichit un article."""
    contenu_propre = nettoyer_html(art.get("contenu", ""))
    titre_propre   = nettoyer_html(art.get("titre", ""))
    langue         = art.get("langue") or detecter_langue(titre_propre, contenu_propre)

    return {
        "id":               art.get("id", ""),
        "titre":            titre_propre,
        "auteur":           (art.get("auteur") or "Inconnu").strip(),
        "date_publication": art.get("date_publication", ""),
        "categorie":        (art.get("categorie") or "general").lower().strip(),
        "description":      nettoyer_html(art.get("description", "")),
        "contenu":          contenu_propre,
        "source":           art.get("source", ""),
        "pays":             art.get("pays", ""),
        "url":              art.get("url", ""),
        "langue":           langue,
        "date_collecte":    art.get("date_collecte", datetime.now().isoformat()),
        "nb_mots":          len(contenu_propre.split()),
        "date_silver":      datetime.now().isoformat(),
    }

def sauvegarder_silver(client, articles, source="all"):
    """Sauvegarde les articles Silver dans MinIO."""
    now = datetime.now()
    chemin = f"{source}/{now.strftime('%Y/%m/%d')}/silver_{now.strftime('%H%M%S')}.json"

    payload = {
        "metadata": {
            "source":       source,
            "date_silver":  now.isoformat(),
            "nb_articles":  len(articles),
            "projet":       "architecture",
        },
        "articles": articles
    }

    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        bucket_name=BUCKET_SILVER,
        object_name=chemin,
        data=io.BytesIO(json_bytes),
        length=len(json_bytes),
        content_type="application/json"
    )
    logger.info(f"Silver sauvegardé : s3://{BUCKET_SILVER}/{chemin}")
    return chemin

def run():
    print("\n" + "=" * 55)
    print("  TRANSFORMATION BRONZE → SILVER")
    print("  Projet : architecture | Buckets : media-*")
    print("=" * 55)

    client = connecter_minio()

    print("\nLecture du bucket 'media-bronze'...")
    articles_bruts = lire_bronze(client)
    print(f"Total articles Bronze lus : {len(articles_bruts)}")

    if not articles_bruts:
        print("Aucun article trouvé. Lance d'abord minio_uploader.py")
        return

    # ── Transformation avec pandas ────────────────────────────
    print("\nTransformation en cours...")
    df = pd.DataFrame(articles_bruts)

    articles_silver = []
    rejetes = 0
    problemes_counts = {}

    for _, row in df.iterrows():
        art = row.to_dict()
        art_propre = transformer_article(art)
        ok, problemes = valider_article(art_propre)

        if ok:
            articles_silver.append(art_propre)
        else:
            rejetes += 1
            for p in problemes:
                problemes_counts[p] = problemes_counts.get(p, 0) + 1

    # ── Stats avec pandas ─────────────────────────────────────
    df_silver = pd.DataFrame(articles_silver)

    print(f"\nRésultat :")
    print(f"  Articles valides   : {len(articles_silver)}")
    print(f"  Articles rejetés   : {rejetes}")

    if problemes_counts:
        print(f"  Raisons de rejet :")
        for p, n in problemes_counts.items():
            print(f"    - {p} : {n} fois")

    if not df_silver.empty:
        print(f"\nStats Silver (pandas) :")
        print(f"  Sources    : {df_silver['source'].value_counts().to_dict()}")
        print(f"  Langues    : {df_silver['langue'].value_counts().to_dict()}")
        print(f"  Moy. mots  : {df_silver['nb_mots'].mean():.0f} mots/article")

        # Sauvegarde Silver
        chemin = sauvegarder_silver(client, articles_silver)
        print(f"\nArticles Silver sauvegardés : {chemin}")
    else:
        print("Aucun article valide à sauvegarder.")

    print("\nLance maintenant : python silver_to_gold.py")
    print("=" * 55)

if __name__ == "__main__":
    run()