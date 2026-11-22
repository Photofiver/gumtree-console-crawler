import unittest
from attention_guard import (build_focus, context_hash, focus_hint, scaled_dot_product_attention)


class FakePretrainedEncoder:
    def encode(self, texts, **kwargs):
        self.texts = texts
        return [[4.0, 0.0], [4.0, 0.0], [0.0, 3.0]]


class AmbiguousTensor(list):
    def __bool__(self):
        raise ValueError("The truth value of an array with more than one element is ambiguous")


class ArrayEncoder:
    def encode(self, texts, **kwargs):
        return [AmbiguousTensor([4.0, 0.0]),
                AmbiguousTensor([4.0, 0.0]),
                AmbiguousTensor([0.0, 3.0])]


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.data = {"question":"Zachowaj główny cel", "draft":"Draft", "checks":[
            {"requirement":"Zachowaj cel", "status":"unknown"},
            {"requirement":"Uwzględnij cenę", "status":"unknown"}]}

    def test_real_scaled_attention_weights_and_values(self):
        weights, vec = scaled_dot_product_attention([4, 0], [[4, 0],[0, 3]])
        self.assertGreater(weights[0], weights[1])
        self.assertAlmostEqual(sum(weights), 1.0)
        self.assertAlmostEqual(vec[0], 4*weights[0])
        self.assertAlmostEqual(vec[1], 3*weights[1])

    def test_no_numpy_boolean_ambiguity_when_real_encoder_returns_arrays(self):
        weights, vec = scaled_dot_product_attention(
            AmbiguousTensor([4.0, 0.0]),
            [AmbiguousTensor([4.0, 0.0]), AmbiguousTensor([0.0, 3.0])]
        )
        self.assertGreater(weights[0], weights[1])
        self.assertEqual(len(vec), 2)
        self.assertEqual(build_focus(self.data, ArrayEncoder())["status"], "active")

    def test_pretrained_encoder_inputs_and_focus(self):
        encoder=FakePretrainedEncoder()
        result = build_focus(self.data, encoder)
        self.assertEqual(len(encoder.texts), 3)
        self.assertEqual(result["status"],"active")
        self.assertEqual(result["ranked_indices"],[0,1])
        self.data["attention"] = result
        self.assertIn("Zachowaj cel",focus_hint(self.data))

    def test_tamper_is_not_accepted(self):
        self.data["attention"] = build_focus(self.data, FakePretrainedEncoder())
        self.data["question"] = "Inne zadanie"
        self.assertEqual(focus_hint(self.data),"")

    def test_all_checks_represented_and_no_faux_attention(self):
        result = build_focus(self.data, FakePretrainedEncoder())
        self.assertEqual(result["requirements_total"],len(self.data["checks"]))
        self.assertEqual(context_hash(self.data["question"],[c["requirement"] for c in self.data["checks"]]),result["context_sha256"])
        self.assertEqual(focus_hint(self.data),"")
        with self.assertRaises(ValueError):
            scaled_dot_product_attention([1,2],[[1]])


if __name__ == "__main__":
    unittest.main()
