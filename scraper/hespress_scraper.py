# =============================================================================
# SCRAPER HESPRESS — Projet : architecture
# =============================================================================
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time, os, hashlib, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HespressScraper:
    def __init__(self):
        self.base_url = "https://www.hespress.com"
        self.sections = {
            "politique":     "https://www.hespress.com/politique",
            "societe":       "https://www.hespress.com/societe",
            "economie":      "https://www.hespress.com/economie",
            "sport":         "https://www.hespress.com/sport",
            "international": "https://www.hespress.com/international",
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8",
        }
        self.delay = 2
        self.max_per_section = 8
        os.makedirs("data/bronze", exist_ok=True)
        logger.info("HespressScraper initialisé")

    def get_page(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
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
        skip = list(self.sections.values()) + [self.base_url]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = self.base_url + href
            if ("hespress.com" in href and href not in skip
                    and href.count("/") >= 4):
                if href not in links:
                    links.append(href)
        links = links[:self.max_per_section]
        logger.info(f"[Hespress/{category}] {len(links)} liens trouvés")
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
                titre = t.get_text(strip=True).replace(" - Hespress", "")

        auteur = "Hespress"
        by = soup.find(class_=lambda c: c and "author" in c.lower())
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
            for div in soup.find_all(class_=lambda c: c and any(
                    k in c for k in ["entry-content", "field-body", "article-content"])):
                for p in div.find_all("p"):
                    t = p.get_text(strip=True)
                    if t and len(t) > 20:
                        paragraphes.append(t)
        contenu = " ".join(paragraphes)

        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        # Détection langue (arabe ou français)
        langue = "fr"
        if titre:
            arabic = sum(1 for c in titre if '\u0600' <= c <= '\u06FF')
            if arabic > len(titre) * 0.3:
                langue = "ar"

        return {
            "id":               hashlib.md5(url.encode()).hexdigest()[:12],
            "titre":            titre or "Sans titre",
            "auteur":           auteur,
            "date_publication": date_pub,
            "categorie":        category,
            "description":      description,
            "contenu":          contenu,
            "source":           "Hespress",
            "pays":             "Maroc",
            "url":              url,
            "langue":           langue,
            "date_collecte":    datetime.now().isoformat(),
            "nb_mots":          len(contenu.split()),
        }

    def valider(self, article):
        problemes = []
        if not article["titre"] or article["titre"] == "Sans titre":
            problemes.append("Titre manquant")
        if article["nb_mots"] < 50:
            problemes.append(f"Contenu trop court ({article['nb_mots']} mots)")
        if not article["url"]:
            problemes.append("URL manquante")
        return len(problemes) == 0, problemes

    def run(self):
        logger.info("=" * 55)
        logger.info("SCRAPER HESPRESS")
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
        logger.info(f"Hespress — {len(valides)} articles valides")
        return valides

if __name__ == "__main__":
    articles = HespressScraper().run()
    print(f"{len(articles)} articles collectés.")