"""
polymarket_api.py — Odds Polymarket en tiempo real via Gamma API
Extrae condition_id automáticamente desde la URL del mercado.
"""

import requests
import re
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com"

# Mercados activos con slugs verificados via Polymarket Gamma API
MERCADOS = {
    "pos1_ceasefire_apr15": "us-x-iran-ceasefire-by-april-15-182-528-637",
    "pos2_iran_jun30":      "iran-x-israelus-conflict-ends-by-june-30-813-454-138-725",
    "ceasefire_apr30":      "us-x-iran-ceasefire-by-april-30-194-679-389",
}


def get_slug_from_url(url: str) -> str:
    """Extrae el slug de una URL de Polymarket."""
    match = re.search(r"polymarket\.com/event/([^/?#]+)", url)
    return match.group(1) if match else url


def get_market_by_slug(slug: str) -> dict:
    """
    Obtiene todos los outcomes de un mercado dado su slug.

    Returns:
        {
            "titulo": "Iran x Israel conflict ends Jun30?",
            "outcomes": [
                {"label": "Yes", "price": 0.27, "volume": 150.88},
                {"label": "No",  "price": 0.73, "volume": 120.00},
            ],
            "volume_total": 270.88,
            "end_date": "2026-06-30",
        }
    """
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={"slug": slug},
            timeout=5
        )
        r.raise_for_status()
        markets = r.json()
        if not markets:
            return {"error": f"Mercado no encontrado: {slug}"}

        m = markets[0]
        outcome_labels = m.get("outcomes", "[]")
        outcome_prices = m.get("outcomePrices", "[]")

        import json
        labels = json.loads(outcome_labels) if isinstance(outcome_labels, str) else outcome_labels
        prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices

        outcomes = [
            {
                "label": labels[i] if i < len(labels) else f"Outcome {i}",
                "price": round(float(prices[i]), 4) if i < len(prices) else 0.5,
            }
            for i in range(len(labels))
        ]

        return {
            "titulo":        m.get("question", slug),
            "outcomes":      outcomes,
            "volume_total":  round(float(m.get("volume", 0)), 2),
            "end_date":      m.get("endDate", ""),
            "condition_id":  m.get("conditionId", ""),
            "slug":          slug,
        }

    except Exception as e:
        return {"error": str(e)}


def get_pos2_odds() -> dict:
    """Shortcut para obtener odds de Pos2 (Iran conflict ends Jun30)."""
    data = get_market_by_slug(MERCADOS["pos2_iran_jun30"])
    if "error" in data:
        return data
    yes = next((o for o in data["outcomes"] if o["label"].lower() == "yes"), None)
    no  = next((o for o in data["outcomes"] if o["label"].lower() == "no"), None)
    return {
        "yes_price":    yes["price"] if yes else None,
        "no_price":     no["price"] if no else None,
        "volume_total": data["volume_total"],
        "condition_id": data["condition_id"],
    }


def snapshot_portfolio() -> dict:
    """
    Obtiene snapshot completo de todos tus mercados de interés.
    Útil para el resumen horario del monitor.
    """
    snapshot = {}
    for nombre, slug in MERCADOS.items():
        data = get_market_by_slug(slug)
        snapshot[nombre] = data
    snapshot["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return snapshot


if __name__ == "__main__":
    print("=== Snapshot Polymarket ===")
    snap = snapshot_portfolio()
    for nombre, data in snap.items():
        if nombre == "timestamp":
            continue
        if "error" in data:
            print(f"\n{nombre}: ERROR — {data['error']}")
        else:
            print(f"\n{nombre}: {data['titulo'][:50]}")
            for o in data["outcomes"][:4]:
                print(f"  {o['label']}: {round(o['price']*100, 1)}¢")
            print(f"  Vol total: ${data['volume_total']:,.0f}")
