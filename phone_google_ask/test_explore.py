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
            ("fails_modelled_average_energy_even_without_clipping",
             "needs_external_energy_not_solar_only") for x in low))

    def test_no_external_energy_is_guaranteed(self):
        r = screen(sample_data(), 1000)
        self.assertFalse(any(x.get("verified") for x in r["combinations"]))


if __name__ == "__main__":
    unittest.main()
