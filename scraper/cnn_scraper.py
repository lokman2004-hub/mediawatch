# =============================================================================
# SCRAPER CNN — Projet : architecture
# =============================================================================
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time, os, hashlib, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CNNScraper:
    def __init__(self):
        self.base_url = "https://edition.cnn.com"
        self.sections = {
            "world":      "https://edition.cnn.com/world",
            "technology": "https://edition.cnn.com/business/tech",
            "health":     "https://edition.cnn.com/health",
            "business":   "https://edition.cnn.com/business",
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.delay = 2
        self.max_per_section = 8
        os.makedirs("data/bronze", exist_ok=True)
        logger.info("CNNScraper initialisé")

    def get_page(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.error(f"Erreur {url}: {e}")
            return None

    def get_links(self, section_url, category):
        html = self.get_page(section_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = self.base_url + href
            if ("edition.cnn.com" in href and "/20" in href
                    and "video" not in href and "gallery" not in href):
                if href not in links:
                    links.append(href)
        links = links[:self.max_per_section]
        logger.info(f"[CNN/{category}] {len(links)} liens trouvés")
        return links

    def scrape_article(self, url, category):
        time.sleep(self.delay)
        html = self.get_page(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        titre = None
        h1 = soup.find("h1")
        if h1:
            titre = h1.get_text(strip=True)
        if not titre:
            t = soup.find("title")
            if t:
                titre = t.get_text(strip=True).replace(" | CNN", "").replace(" - CNN", "")

        auteur = "CNN"
        by = soup.find(class_=lambda c: c and "byline" in c.lower())
        if by:
            auteur = by.get_text(strip=True)

        date_pub = datetime.now().isoformat()
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            date_pub = time_tag["datetime"]
        else:
            meta = soup.find("meta", attrs={"property": "article:published_time"})
            if meta:
                date_pub = meta.get("content", date_pub)

        paragraphes = []
        art = soup.find("article")
        if art:
            for p in art.find_all("p"):
                t = p.get_text(strip=True)
                if t and len(t) > 20:
                    paragraphes.append(t)
        else:
            for p in soup.find_all("p"):
                t = p.get_text(strip=True)
                if t and len(t) > 30:
                    paragraphes.append(t)
        contenu = " ".join(paragraphes)

        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        return {
            "id":               hashlib.md5(url.encode()).hexdigest()[:12],
            "titre":            titre or "Sans titre",
            "auteur":           auteur,
            "date_publication": date_pub,
            "categorie":        category,
            "description":      description,
            "contenu":          contenu,
            "source":           "CNN",
            "pays":             "USA",
            "url":              url,
            "langue":           "en",
            "date_collecte":    datetime.now().isoformat(),
            "nb_mots":          len(contenu.split()),
        }

    def valider(self, article):
        problemes = []
        if not article["titre"] or article["titre"] == "Sans titre":
            problemes.append("Titre manquant")
        if article["nb_mots"] < 100:
            problemes.append(f"Contenu trop court ({article['nb_mots']} mots)")
        if not article["url"]:
            problemes.append("URL manquante")
        return len(problemes) == 0, problemes

    def run(self):
        logger.info("=" * 55)
        logger.info("SCRAPER CNN")
        logger.info("=" * 55)
        valides = []
        for cat, url in self.sections.items():
            for lien in self.get_links(url, cat):
                art = self.scrape_article(lien, cat)
                if art:
                    ok, pb = self.valider(art)
                    if ok:
                        valides.append(art)
                    else:
                        logger.warning(f"Rejeté {pb}: {lien}")
        logger.info(f"CNN — {len(valides)} articles valides")
        return valides

if __name__ == "__main__":
    articles = CNNScraper().run()
    print(f"{len(articles)} articles collectés.")