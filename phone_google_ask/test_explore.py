"""Fast and offline tests for the deterministic 100/1000 configuration screener."""
import unittest

from explore import ROUTES, nameplate_watts, screen


def sample_data():
    models = [
        "Renogy 100W rigid", "ECO-WORTHY 100W rigid",
        "EcoFlow 100W rigid", "DOKIO 150W rigid",
        "Lowenergie 100W rigid", "ZOUPW 50W rigid", "AeternaSol 100W rigid",
    ]
    return {"candidate_log": [
        {"model": model, "source": "https://example.org/" + str(i)}
        for i, model in enumerate(models)
    ]}


class ExploreTests(unittest.TestCase):
    def test_wattage_recognition(self):
        self.assertEqual(nameplate_watts("Renogy RSP100DC-UK 100 W"), 100)
        self.assertEqual(nameplate_watts("DOKIO 150W"), 150)
        self.assertIsNone(nameplate_watts("Unnamed panel"))

    def test_screen_100_and_1000(self):
        data = sample_data()
        for n in (100, 1000):
            with self.subTest(n=n):
                r = screen(data, n)
                s = r["summary"]
                self.assertEqual(s["screened"], n)
                self.assertEqual(len(r["combinations"]), n)
                self.assertEqual(len({x["id"] for x in r["combinations"]}), n)
                self.assertEqual(set(s["by_route"]), set(ROUTES))
                self.assertEqual(sum(s["by_route"].values()), n)
                self.assertEqual(sum(s["by_status"].values()), n)
                self.assertEqual(s["genuinely_verified_retail_products"], 0)
                self.assertTrue(s["no_verified_purchase_recommendation"])
                self.assertTrue(all(x["source"].startswith("https://") for x in r["combinations"]))

    def test_no_false_retail_claim_and_reproducible(self):
        a = screen(sample_data(), 100)
        b = screen(sample_data(), 100)
        self.assertEqual(a, b)
        self.assertEqual(a["summary"]["google_ai_deep_reviews"], 0)

    def test_missing_catalog_does_not_invent_products(self):
        with self.assertRaises(ValueError):
            screen({"candidate_log": []}, 100)

    def test_illegal_count_rejected(self):
        with self.assertRaises(ValueError):
            screen(sample_data(), 500)

    def test_weak_solar_configurations_fail_average_energy(self):
        result = screen(sample_data(), 1000)
        low = [x for x in result["combinations"]
               if x["nameplate_w"] <= 200 and x["route"] not in ("other_input",)]
        self.assertTrue(low)
        self.assertTrue(all(x["screen"] in
            ("reject_average_energy_shortfall", "excluded_uses_grid",
             "unknown_buffer_energy")
            for x in low))

    def test_hard_budget_screen_on_documented_quote(self):
        sample = sample_data()
        sample["budget_max_gbp"] = 100
        for entry in sample["candidate_log"]:
            entry.update(unit_price_gbp=59.49,
                         retailer="amazon_uk",
                         price_source="https://www.amazon.co.uk/example")
        result = screen(sample, 1000)
        costly = [c for c in result["combinations"] if c["count"] >= 2]
        self.assertTrue(costly)
        self.assertTrue(all(c["screen"] == "reject_known_price_over_budget" or
                            c["screen"] == "excluded_uses_grid" for c in costly))
        self.assertEqual(result["summary"]["verified_feasible_count"], 0)
        self.assertEqual(result["summary"]["genuinely_verified_retail_products"], 0)

    def test_unlimited_budget_does_not_reject_247_or_any_expensive_variants(self):
        sample = sample_data()
        sample["question"] = "Belfast S700: Bez limitu budżetu, wybierz opłacalny zestaw."
        sample["budget_max_gbp"] = 100  # stale older field must not override user
        for entry in sample["candidate_log"]:
            entry.update(unit_price_gbp=129.99, retailer="amazon_uk",
                         price_source="https://www.amazon.co.uk/example")
        result = screen(sample, 1000)
        summary = result["summary"]
        self.assertIsNone(summary["budget_max_gbp"])
        self.assertEqual(summary["budget_mode"], "uncapped")
        self.assertEqual(summary["by_status"].get("reject_known_price_over_budget", 0), 0)
        self.assertEqual(summary["screened"], 1000)

    def test_explicit_budget_parsing_and_no_invented_limit(self):
        from explore import budget_limit_gbp
        self.assertEqual(budget_limit_gbp({"question":"Budżet maksymalnie £100"}), 100)
        self.assertEqual(budget_limit_gbp({"question":"Budget max GBP 150"}), 150)
        self.assertIsNone(budget_limit_gbp({"question":"PV max 5A and 100W"}))
        self.assertIsNone(budget_limit_gbp({"question":"Bez górnego limitu ceny. £100 nie ogranicza."}))
        self.assertIsNone(budget_limit_gbp({"question":"Brak kwoty."}))
        with self.assertRaises(ValueError):
            budget_limit_gbp({"budget_max_gbp":"100"})

    def test_voltage_limit_and_unproven_price(self):
        models = [
            dict(model="High Voc 500W", source="https://example.org/high",
                 rated_watts=500, voc_stc_v=25.2, isc_a=4.5),
            dict(model="Low Voc 500W", source="https://example.org/low",
                 rated_watts=500, voc_stc_v=20, isc_a=4.5),
        ]
        for item, expected in ((models[0], "reject_direct_overvoltage"),
                               (models[1], "unknown_price")):
            r = screen({"candidate_log": [item]}, 1000)
            direct = [x for x in r["combinations"] if x["route"] == "direct_panel"]
            self.assertTrue(direct)
            self.assertTrue(all(x["screen"] == expected for x in direct))

    def test_legacy_candidates_never_pass_as_verified(self):
        r = screen(sample_data(), 1000)
        self.assertEqual(r["summary"]["verified_feasible_count"], 0)
        self.assertEqual(r["summary"]["definitely_screened_out"] +
                         r["summary"]["still_unverified"], 1000)
        self.assertFalse(any(x["screen"] == "verified" for x in r["combinations"]))

    def test_no_external_energy_is_guaranteed(self):
        r = screen(sample_data(), 1000)
        self.assertFalse(any(x.get("verified") for x in r["combinations"]))


if __name__ == "__main__":
    unittest.main()
