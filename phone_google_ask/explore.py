"""Deterministic configuration screening. NOT a product search or safety certificate.

Every combination is a hypothesis from source-listed models. Prices, connector
polarity, real-world output and inverter compatibility need separate verification.
"""
import hashlib
import json
import re

ROUTES = (
    "direct_panel", "parallel_panels", "series_panels",
    "regulated_converter", "other_input", "buffer_or_hybrid",
    "market_comparison",
)
CONNECTIONS = {
    "direct_panel": ("single",),
    "parallel_panels": ("parallel",),
    "series_panels": ("series",),
    "regulated_converter": ("parallel_dc_dc", "series_dc_dc", "mixed_dc_dc"),
    "other_input": ("solar_plus_usb_c", "solar_plus_dc"),
    "buffer_or_hybrid": ("solar_plus_buffer", "solar_plus_grid"),
    "market_comparison": ("panel_cable_bundle", "regulated_bundle"),
}
MIN_WATTS_FOR_AVERAGE = 606 / (169.35 / 100 * 0.85)


def nameplate_watts(model):
    match = re.search(r"(?<!\\d)(\\d{2,4})\\s*w(?:att)?(?:s)?\\b", model, flags=re.I)
    return int(match.group(1)) if match else None


def screen(data, target):
    """Quickly evaluate 100 or 1000 distinct *configurations*, not listings."""
    if target not in (100, 1000):
        raise ValueError("idea_target must be exactly 100 or 1000")
    catalog = []
    for entry in data.get("candidate_log", []):
        if not isinstance(entry, dict):
            continue
        name, source = entry.get("model", ""), entry.get("source", "")
        watts = entry.get("rated_watts")
        if type(watts) not in (int, float) or not (0 < watts <= 2000):
            watts = nameplate_watts(name)
        if name and isinstance(source, str) and source.startswith("https://") and watts:
            catalog.append(dict(model=name, source=source, watts=watts))
    catalog = list({e["model"]: e for e in catalog}.values())
    if not catalog:
        raise ValueError("Need source-listed candidate_log models and nameplate watts")

    pool = []
    for model in catalog:
        for quantity in range(1, 31):
            for route in ROUTES:
                if route == "direct_panel" and quantity != 1:
                    continue
                if route in ("parallel_panels", "series_panels") and quantity == 1:
                    continue
                for wiring in CONNECTIONS[route]:
                    for cable_m in (3, 10):
                        ident = f"{model['model']}|{quantity}|{route}|{wiring}|{cable_m}"
                        pool.append(dict(
                            id=hashlib.sha256(ident.encode()).hexdigest()[:16],
                            model=model["model"], source=model["source"],
                            nameplate_w=quantity * model["watts"], count=quantity,
                            route=route, connection=wiring, cable_m=cable_m,
                        ))
    # Stable diverse sample, independent of a model's position in candidate_log.
    pool.sort(key=lambda x: x["id"])
    picked = pool[:target]

    route_counts = dict.fromkeys(ROUTES, 0)
    status_counts = {}
    shortlist = []
    for candidate in picked:
        route = candidate["route"]
        route_counts[route] += 1
        # 169.35Wh/48h per 100Wp (illustrative Belfast December average).
        # This upper estimate assumes NO input clipping and 85% battery efficiency.
        output_wh = round(candidate["nameplate_w"] * 1.6935 * .85, 1)
        candidate["modelled_wh_48h_no_clipping"] = output_wh
        if route == "buffer_or_hybrid" and candidate["connection"] == "solar_plus_grid":
            status = "needs_external_energy_not_solar_only"
        elif route == "other_input":
            status = "requires_port_and_energy_source_proof"
        elif candidate["nameplate_w"] < MIN_WATTS_FOR_AVERAGE:
            status = "fails_modelled_average_energy_even_without_clipping"
        elif route in ("series_panels", "parallel_panels"):
            status = "needs_regulation_and_electrical_proof"
        else:
            status = "needs_price_voltage_clipping_and_weather_proof"
        candidate["screen"] = status
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "needs_price_voltage_clipping_and_weather_proof":
            shortlist.append(candidate)

    # Favor least oversizing, rotate panel models for the shortlist.
    shortlist.sort(key=lambda x: (x["count"], x["nameplate_w"], x["id"]))
    top = []
    seen = set()
    for candidate in shortlist:
        if candidate["model"] in seen:
            continue
        seen.add(candidate["model"])
        top.append(candidate)
        if len(top) >= 12:
            break
    summary = dict(
        mode="COMPUTATIONAL_PRE_SCREEN_ONLY",
        requested=target, generated=len(pool), screened=len(picked),
        catalog_models=len(catalog), genuinely_verified_retail_products=0,
        google_ai_deep_reviews=0, by_route=route_counts, by_status=status_counts,
        shortlist=top, no_verified_purchase_recommendation=True,
        note=("Konfiguracje sa wygenerowanymi kombinacjami sprzetu, nie "
              "osobnymi produktami ani potwierdzonymi ofertami. Modelowe Wh "
              "nie uwzgledniaja ograniczenia 100W ani ceny i pogody danego dnia."),
    )
    if len(picked) < target:
        summary["warning"] = "Insufficient distinct combinations for target"
    return dict(summary=summary, combinations=picked)


if __name__ == "__main__":
    import sys
    source = json.load(sys.stdin)
    json.dump(screen(source, int(source.get("idea_target", 100))), sys.stdout, ensure_ascii=False)
