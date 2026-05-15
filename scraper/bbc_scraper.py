# =============================================================================
# SCRAPER BBC NEWS — Projet : architecture
# =============================================================================
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time, os, hashlib, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BBCScraper:
    def __init__(self):
        self.base_url = "https://www.bbc.com"
        self.sections = {
            "world":      "https://www.bbc.com/news/world",
            "technology": "https://www.bbc.com/news/technology",
            "science":    "https://www.bbc.com/news/science_and_environment",
            "business":   "https://www.bbc.com/news/business",
            "health":     "https://www.bbc.com/news/health",
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.delay = 2
        self.max_per_section = 10
        os.makedirs("data/bronze", exist_ok=True)
        logger.info("BBCScraper initialisé")

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
            if (href.startswith("/news/") and "-" in href
                    and not href.startswith("/news/live")
                    and not href.startswith("/news/topics")
                    and not href.startswith("/news/av")):
                full = self.base_url + href
                if full not in links:
                    links.append(full)
        links = links[:self.max_per_section]
        logger.info(f"[BBC/{category}] {len(links)} liens trouvés")
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
                titre = t.get_text(strip=True).replace(" - BBC News", "")

        auteur = "BBC News"
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            auteur = meta_author["content"]

        date_pub = datetime.now().isoformat()
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            date_pub = time_tag["datetime"]

        paragraphes = []
        blocks = soup.find_all("div", attrs={"data-component": "text-block"})
        if blocks:
            for b in blocks:
                for p in b.find_all("p"):
                    t = p.get_text(strip=True)
                    if t and len(t) > 20:
                        paragraphes.append(t)
        else:
            art = soup.find("article")
            if art:
                for p in art.find_all("p"):
                    t = p.get_text(strip=True)
                    if t and len(t) > 20:
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
            "source":           "BBC News",
            "pays":             "UK",
            "url":              url,
            "langue":           "en",
            "date_collecte":    datetime.now().isoformat(),
            "nb_mots":          len(contenu.split()),
        }

    def valider(self, article):
        problemes = []
        if not article["titre"] or article["titre"] == "Sans titre":
            problemes.append("Titre manquant")
        if not article["date_publication"]:
            problemes.append("Date manquante")
        if article["nb_mots"] < 100:
            problemes.append(f"Contenu trop court ({article['nb_mots']} mots)")
        if not article["url"]:
            problemes.append("URL manquante")
        return len(problemes) == 0, problemes

    def run(self):
        logger.info("=" * 55)
        logger.info("SCRAPER BBC NEWS")
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
        logger.info(f"BBC — {len(valides)} articles valides")
        return valides

if __name__ == "__main__":
    articles = BBCScraper().run()
    print(f"{len(articles)} articles collectés.")