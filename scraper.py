import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


def extract_item_id(url: str) -> str:
    match = re.search(r"MLA-?(\d+)", url)
    return f"MLA{match.group(1)}" if match else None


def scrape_listing(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {"url": url, "item_id": extract_item_id(url)}

    # Title
    el = soup.find("h1", class_="ui-pdp-title")
    data["title"] = el.text.strip() if el else None

    # Price
    el = soup.find("span", class_="andes-money-amount__fraction")
    data["price_raw"] = el.text.replace(".", "").strip() if el else None
    data["price"] = int(data["price_raw"]) if data["price_raw"] else None

    # Description
    el = soup.find("p", class_="ui-pdp-description__content")
    data["description"] = el.get_text("\n").strip() if el else None

    # JSON-LD (images, brand, price confirmation)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string)
            if ld.get("@type") == "Product":
                brand = ld.get("brand")
                if isinstance(brand, dict):
                    data["brand"] = brand.get("name") or brand.get("@value")
                else:
                    data["brand"] = brand
                imgs = ld.get("image", [])
                data["images"] = imgs if isinstance(imgs, list) else [imgs]
                data["images_count"] = len(data["images"])
                offers = ld.get("offers", {})
                if not data["price"] and offers.get("price"):
                    data["price"] = int(float(offers["price"]))
                data["currency"] = offers.get("priceCurrency", "ARS")
                break
        except Exception:
            pass

    # Rating
    el = soup.find("span", class_="ui-pdp-review__rating")
    data["rating"] = float(el.text.strip()) if el else None
    el = soup.find("span", class_="ui-pdp-review__amount")
    if el:
        nums = re.findall(r"\d+", el.text)
        data["reviews_count"] = int(nums[0]) if nums else 0
    else:
        data["reviews_count"] = 0

    # Free shipping
    green = soup.find("p", class_="ui-pdp-color--GREEN")
    data["free_shipping"] = bool(green and "gratis" in green.text.lower())

    # Attributes / specs
    attrs = {}
    for row in soup.find_all("tr", class_="andes-table__row"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            attrs[th.text.strip()] = td.text.strip()
    data["attributes"] = attrs

    # Seller reputation
    el = soup.find("span", class_="ui-seller-info__status-title")
    data["seller_reputation"] = el.text.strip() if el else None

    # Video flag
    data["has_video"] = bool(soup.find("video"))

    # Images from gallery (fallback count)
    if not data.get("images_count"):
        gallery = soup.find_all("img", class_="ui-pdp-gallery__figure__image")
        data["images_count"] = max(len(gallery), 1)

    return data


def scrape_search_results(query: str, limit: int = 25) -> list:
    slug = query.replace(" ", "-")
    url = f"https://listado.mercadolibre.com.ar/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []

    results = []
    for item in soup.find_all("li", class_="ui-search-layout__item")[:limit]:
        product = {}

        title_el = item.find("a", class_="poly-component__title") or item.find("h2")
        product["title"] = title_el.text.strip() if title_el else None

        price_el = item.find("span", class_="andes-money-amount__fraction")
        if price_el:
            raw = price_el.text.replace(".", "").strip()
            product["price"] = int(raw) if raw.isdigit() else None
        else:
            product["price"] = None

        rating_el = item.find("span", class_="poly-reviews__rating")
        product["rating"] = float(rating_el.text.strip()) if rating_el else None

        reviews_el = item.find("span", class_="poly-reviews__total")
        if reviews_el:
            nums = re.findall(r"\d+", reviews_el.text)
            product["reviews"] = int(nums[0]) if nums else 0
        else:
            product["reviews"] = 0

        shipping_el = item.find("p", class_="poly-component__shipping")
        product["free_shipping"] = bool(
            shipping_el and "gratis" in shipping_el.text.lower()
        )

        link_el = item.find("a", class_="poly-component__title")
        product["url"] = link_el.get("href", "").split("#")[0] if link_el else None

        if product["title"]:
            results.append(product)

    return results


def build_search_query_from_title(title: str) -> str:
    """Extract the most relevant keywords from a listing title for competitor search."""
    import unicodedata

    def normalize(text: str) -> str:
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    stopwords = {
        "de", "la", "el", "en", "con", "sin", "para", "y", "a", "del",
        "los", "las", "un", "una", "por", "al", "se", "su", "que",
    }
    normalized = normalize(title.lower())
    words = re.findall(r"[a-z]+", normalized)
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    return " ".join(keywords[:5])
