"""Deterministic configuration screening. NOT a product search or safety certificate.

Every combination is a hypothesis from source-listed models. Prices, connector
polarity, real-world output and inverter compatibility need separate verification.
"""
import hashlib
import json
import re
import unicodedata

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
MAX_SOLAR_VOC_V = 24.0
MAX_SOLAR_INPUT_A = 5.0

# Quotes supplied in candidate_log are input evidence, not independently checked prices.
def positive_number(value):
    if type(value) not in (int, float) or not 0 < value < 1_000_000:
        return None
    return float(value)


def budget_limit_gbp(data):
    """Resolve a budget ceiling from the current request, never a global £100.

    An expressly unlimited user request overrides stale optional budget fields.
    Without an explicitly supported cap, costs are compared but NOT rejected.
    """
    question = data.get("question", "")
    if not isinstance(question, str):
        question = ""
    text = unicodedata.normalize("NFKD", question.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\\s+", " ", text)

    unlimited = (
        r"(?:bez|brak)\\s+(?:gornego\\s+)?limitu(?:\\s+(?:budzetu|cen|ceny|kwoty))?",
        r"budzet\\s+bez\\s+limitu",
        r"nie\\s+ma\\s+(?:gornego\\s+)?limitu\\s+budzetu",
        r"nie\\s+ograniczaj\\s+budzetu",
        r"no\\s+(?:upper\\s+)?budget\\s+(?:limit|cap)",
        r"(?:unlimited|uncapped)\\s+budget",
        r"without\\s+(?:a\\s+)?budget\\s+cap",
    )
    if any(re.search(pattern, text) for pattern in unlimited):
        return None

    if data.get("budget_mode") in ("unlimited", "uncapped", "no_cap"):
        return None
    if "budget_max_gbp" in data:
        amount = data["budget_max_gbp"]
        if amount is None:
            return None
        checked = positive_number(amount)
        if checked is None:
            raise ValueError("budget_max_gbp must be a positive number or null")
        return checked
    # Recognise currency-bearing explicit limits in older, free-form tasks.
    # Avoid matching 'max 5 A' or '100 W' as a pound-denominated budget.
    cap = re.search(
        r"(?:\\b(?:budzet|budget|limit|maksymalnie|maximum|max|do)\\b.{0,30}?)"
        r"(?:£\\s*([0-9]+(?:[.,][0-9]+)?)|([0-9]+(?:[.,][0-9]+)?)\\s*(?:gbp|£))",
        text,
    )
    if not cap:
        cap = re.search(r"(?:<=|≤)\\s*£\\s*([0-9]+(?:[.,][0-9]+)?)", text)
    if not cap:
        return None
    value = next((x for x in cap.groups() if x), None)
    return float(value.replace(",", ".")) if value else None


def cold_voc(model):
    explicit = positive_number(model.get("voc_cold_v"))
    if explicit:
        return explicit
    stc = positive_number(model.get("voc_stc_v"))
    coefficient = model.get("voc_temp_coeff_pct_per_c")
    if stc and type(coefficient) in (int, float) and -2 <= coefficient < 0:
        return stc * (1 + coefficient / 100 * (-10 - 25))
    return None



def nameplate_watts(model):
    match = re.search(r"(?<!\d)(\d{2,4})\s*w(?:att)?(?:s)?\b", model, flags=re.I)
    return int(match.group(1)) if match else None


def screen(data, target):
    """Quickly evaluate 100 or 1000 distinct *configurations*, not listings."""
    if target not in (100, 1000):
        raise ValueError("idea_target must be exactly 100 or 1000")
    budget_cap = budget_limit_gbp(data)
    catalog = []
    for entry in data.get("candidate_log", []):
        if not isinstance(entry, dict):
            continue
        name, source = entry.get("model", ""), entry.get("source", "")
        watts = entry.get("rated_watts")
        if type(watts) not in (int, float) or not (0 < watts <= 2000):
            watts = nameplate_watts(name)
        if name and isinstance(source, str) and source.startswith("https://") and watts:
            catalog.append(dict(
                model=name, source=source, watts=watts,
                unit_price_gbp=positive_number(entry.get("unit_price_gbp")),
                price_source=entry.get("price_source", ""),
                retailer=entry.get("retailer", ""),
                voc_stc_v=positive_number(entry.get("voc_stc_v")),
                voc_cold_v=positive_number(entry.get("voc_cold_v")),
                voc_temp_coeff_pct_per_c=entry.get("voc_temp_coeff_pct_per_c"),
                isc_a=positive_number(entry.get("isc_a")),
                cable_min_cost_gbp=positive_number(entry.get("cable_min_cost_gbp")),
                regulator_min_cost_gbp=positive_number(entry.get("regulator_min_cost_gbp")),
            ))
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
                            unit_price_gbp=model["unit_price_gbp"],
                            price_source=model["price_source"],
                            retailer=model["retailer"],
                            voc_stc_v=model["voc_stc_v"],
                            voc_cold_v=cold_voc(model),
                            isc_a=model["isc_a"],
                            cable_min_cost_gbp=model["cable_min_cost_gbp"],
                            regulator_min_cost_gbp=model["regulator_min_cost_gbp"],
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
        # Average December from the user's source assumptions; never a weather guarantee.
        # Production estimate ignores 100W input clipping. It cannot prove feasibility.
        output_wh = round(candidate["nameplate_w"] * 1.6935 * .85, 1)
        candidate["modelled_wh_48h_no_clipping"] = output_wh
        quantity = candidate["count"]
        wiring = candidate["connection"]
        quote = candidate["unit_price_gbp"]
        lower_cost = quote * quantity if quote is not None else None
        if lower_cost is not None and candidate["cable_min_cost_gbp"]:
            lower_cost += candidate["cable_min_cost_gbp"]
        if lower_cost is not None and "dc_dc" in wiring and candidate["regulator_min_cost_gbp"]:
            lower_cost += candidate["regulator_min_cost_gbp"]
        candidate["quoted_lower_bound_gbp"] = round(lower_cost, 2) if lower_cost is not None else None

        # Known violations first. Unknown values must never be called verified.
        direct = route in ("direct_panel", "parallel_panels", "series_panels") or (
            wiring == "panel_cable_bundle")
        voc_per_panel = candidate["voc_cold_v"] or candidate["voc_stc_v"]
        series = route == "series_panels"
        if wiring == "solar_plus_grid":
            status, why = ("excluded_uses_grid",
                           "Uses grid power, not a solar-only answer.")
        elif budget_cap is not None and lower_cost is not None and lower_cost > budget_cap:
            status, why = ("reject_known_price_over_budget",
                           "Quoted minimum cost exceeds the current request's GBP budget cap; verify quote.")
        elif series and voc_per_panel and voc_per_panel * quantity > MAX_SOLAR_VOC_V:
            status, why = ("reject_direct_overvoltage",
                           "Series open-circuit voltage exceeds 24V without regulation.")
        elif direct and route == "direct_panel" and voc_per_panel and voc_per_panel > MAX_SOLAR_VOC_V:
            status, why = ("reject_direct_overvoltage",
                           "Panel open-circuit voltage exceeds 24V.")
        elif direct and route == "parallel_panels" and candidate["isc_a"] and candidate["isc_a"] * quantity > MAX_SOLAR_INPUT_A:
            status, why = ("reject_direct_overcurrent",
                           "Combined panel short-circuit current exceeds rated 5A; regulation required.")
        elif route == "direct_panel" and candidate["isc_a"] and candidate["isc_a"] > MAX_SOLAR_INPUT_A:
            status, why = ("reject_direct_overcurrent",
                           "Panel short-circuit current exceeds rated 5A; manufacturer compatibility unproven.")
        elif route not in ("other_input", "buffer_or_hybrid") and candidate["nameplate_w"] < MIN_WATTS_FOR_AVERAGE:
            status, why = ("reject_average_energy_shortfall",
                           "Below 606Wh in modelled average December even without 100W clipping.")
        elif route == "other_input":
            status, why = ("unknown_other_input", "No proved compatible second-input energy source.")
        elif route == "buffer_or_hybrid":
            status, why = ("unknown_buffer_energy", "Buffer does not create energy; extra components unverified.")
        elif lower_cost is None:
            status, why = ("unknown_price", "No sourced per-unit price; cannot compare total value.")
        elif candidate["retailer"] not in ("amazon_uk", "argos"):
            status, why = ("unknown_retailer", "Quote is not verified to be Amazon UK or Argos.")
        elif direct and (not voc_per_panel or not candidate["isc_a"]):
            status, why = ("unknown_electrical", "Missing measured/cited Voc or current.")
        else:
            status, why = ("unknown_accessories_clipping_weather",
                           "Quote cannot establish safe converter, cables, clipping or winter weather.")
        candidate["screen"] = status
        candidate["reason"] = why
        # A price supplied by a user or model remains UNVERIFIED until checked at seller.
        candidate["verified_offer"] = False
        status_counts[status] = status_counts.get(status, 0) + 1
        if status.startswith("unknown_"):
            shortlist.append(candidate)

    shortlist.sort(key=lambda x: (
        0 if x["quoted_lower_bound_gbp"] is not None else 1,
        x["quoted_lower_bound_gbp"] if x["quoted_lower_bound_gbp"] is not None else 1e9,
        x["count"], x["id"]))
    top, seen = [], set()
    for candidate in shortlist:
        if candidate["model"] in seen:
            continue
        seen.add(candidate["model"])
        top.append(candidate)
        if len(top) >= 12:
            break
    rejected = sum(number for status, number in status_counts.items() if status.startswith("reject_") or status == "excluded_uses_grid")
    unknown = len(picked) - rejected
    summary = dict(
        mode="COMPUTATIONAL_PRE_SCREEN_ONLY",
        requested=target, generated=len(pool), screened=len(picked),
        budget_max_gbp=budget_cap, budget_mode="capped" if budget_cap is not None else "uncapped",
        catalog_models=len(catalog), genuinely_verified_retail_products=0,
        google_ai_deep_reviews=0, by_route=route_counts, by_status=status_counts,
        definitely_screened_out=rejected, still_unverified=unknown,
        verified_feasible_count=0, shortlist=top,
        no_verified_purchase_recommendation=True,
        note=("Budget rejection uses only the current request's explicit cap (if any). "
              "Modelled combinations are NOT real offers. Price quotes in candidate_log "
              "are not independently checked. Unknown electrical parameters, polarity, "
              "regulator cost, weather and 100W input clipping mean NOT VERIFIED."),
    )
    if len(picked) < target:
        summary["warning"] = "Insufficient distinct combinations for target"
    return dict(summary=summary, combinations=picked)


if __name__ == "__main__":
    import sys
    source = json.load(sys.stdin)
    json.dump(screen(source, int(source.get("idea_target", 100))), sys.stdout, ensure_ascii=False)
