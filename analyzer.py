import os
import json
import anthropic

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def analyze_publication(my_listing: dict, competitors: list) -> dict:
    """
    Analyze a MercadoLibre listing vs competitors and return structured recommendations.
    Returns a dict with keys: score, summary, recommendations (list of dicts).
    """
    competitors_text = ""
    for i, c in enumerate(competitors[:15], 1):
        price = f"${c.get('price'):,}" if c.get("price") else "N/D"
        rating = c.get("rating") or "sin calificación"
        reviews = c.get("reviews") or 0
        shipping = "envío gratis" if c.get("free_shipping") else "sin envío gratis"
        competitors_text += (
            f"{i}. {c.get('title','?')} | {price} | ★{rating} ({reviews} reseñas) | {shipping}\n"
        )

    attrs_text = json.dumps(my_listing.get("attributes", {}), ensure_ascii=False, indent=2)

    prompt = f"""Sos un experto en optimización de publicaciones de MercadoLibre Argentina.
Analizá mi publicación y comparala con los competidores para darme recomendaciones concretas y accionables.

## MI PUBLICACIÓN
- **Título**: {my_listing.get("title", "N/D")}
- **Precio**: ${my_listing.get("price", "N/D"):,} ARS
- **Calificación**: {my_listing.get("rating") or "Sin calificaciones aún"}
- **Reseñas**: {my_listing.get("reviews_count", 0)}
- **Fotos**: {my_listing.get("images_count", 0)} imágenes
- **Video**: {"Sí" if my_listing.get("has_video") else "No"}
- **Envío gratis**: {"Sí" if my_listing.get("free_shipping") else "No"}
- **Marca**: {my_listing.get("brand") or "Genérica"}
- **Reputación del vendedor**: {my_listing.get("seller_reputation") or "N/D"}
- **Atributos**: {attrs_text}
- **Descripción (primeros 500 chars)**: {(my_listing.get("description") or "")[:500]}

## TOP COMPETIDORES (búsqueda orgánica)
{competitors_text}

## TAREA
Analizá en profundidad y devolvé un JSON con esta estructura exacta (sin texto extra, solo JSON):
{{
  "score": <número 1-10 que representa la calidad actual de la publicación>,
  "score_reason": "<1 oración explicando el puntaje>",
  "summary": "<resumen ejecutivo de 2-3 oraciones del estado actual vs competidores>",
  "price_position": "<premium|competitivo|económico|muy económico> con una breve explicación",
  "recommendations": [
    {{
      "priority": "<alta|media|baja>",
      "category": "<título|precio|fotos|video|descripción|envío|atributos|palabras_clave|oferta>",
      "issue": "<qué está mal o qué falta>",
      "action": "<qué hacer exactamente, con ejemplos concretos>",
      "impact": "<cuál es el impacto esperado en ventas>"
    }}
  ]
}}

Ordená las recomendaciones de mayor a menor prioridad. Sé muy específico y usa ejemplos reales del mercado."""

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code block if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    import re
    return json.loads(text)


def analyze_opportunities(vertical_data: list, selected_vertical: str) -> dict:
    """
    Analyze BigQuery vertical data to find niche import opportunities.
    Returns dict with opportunities list and analysis.
    """
    data_text = json.dumps(vertical_data[:50], ensure_ascii=False, indent=2)

    prompt = f"""Sos un experto en importación y comercio electrónico, especializado en MercadoLibre Argentina.
Tenés datos del vertical "{selected_vertical}" de MercadoLibre. Analizalos para encontrar oportunidades de nicho
para importar productos desde China y vender en Argentina.

## DATOS DEL VERTICAL
{data_text}

## TAREA
Identificá los mejores nichos dentro de este vertical para importar y vender. Considerá:
- Demanda vs competencia (nichos con demanda pero pocos vendedores establecidos)
- Margen potencial (productos que se pueden importar a bajo costo)
- Tendencias del mercado
- Barreras de entrada bajas

Devolvé un JSON con esta estructura exacta (sin texto extra):
{{
  "vertical": "{selected_vertical}",
  "market_summary": "<resumen del mercado en 2-3 oraciones>",
  "opportunities": [
    {{
      "product": "<nombre del producto/nicho>",
      "score": <1-10 de atractivo para importar>,
      "demand_level": "<alta|media|baja>",
      "competition_level": "<alta|media|baja>",
      "estimated_import_cost": "<rango en USD>",
      "estimated_selling_price": "<rango en ARS>",
      "why": "<por qué es una buena oportunidad>",
      "key_differentiators": ["<diferenciador 1>", "<diferenciador 2>"],
      "search_keywords": ["<keyword 1>", "<keyword 2>", "<keyword 3>"]
    }}
  ],
  "top_recommendation": "<el mejor producto específico para importar ahora y por qué>"
}}

Ordená las oportunidades de mayor a menor score."""

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    import re
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    return json.loads(text)


def quick_listing_preview(url: str) -> dict:
    """Ask Claude to describe what it knows about this type of product for a quick preview."""
    prompt = f"""Para la URL de MercadoLibre: {url}

Extraé el ID del item (formato MLA-XXXXXXXXX) y el tipo de producto del título en la URL.
Devolvé JSON:
{{"item_id": "<MLA-XXX>", "product_type": "<tipo de producto inferido del título URL>"}}"""

    client = get_client()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    import re, json
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        return {}
