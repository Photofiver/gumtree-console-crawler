import importlib.util
import re
import unittest
from pathlib import Path
from urllib.parse import urlencode

from consult import evaluate, parts, solve

spec = importlib.util.spec_from_file_location("waiter", Path(__file__).resolve().parents[1] /
    "plugins/google-ai-konsultant/hooks/review_turn.py")
waiter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(waiter)


def vote(query, decision):
    tag = re.search("space and ([0-9a-f]+)", query)[1]
    return {"question":query, "page":{"url":"https://www.google.com/search?" +
        urlencode({"q":query,"udm":"50"}), "text":"Evidence: voltage exceeds port limit\n"+decision+" "+tag}}


class ConsultTests(unittest.TestCase):
    def setUp(self):
        self.data = dict(question="S700 Belfast 606 Wh", draft="draft one",
            checks=[dict(requirement="Voltage",status="met",source="https://example.org",
                         finding="Rated voltage", quote="Rated 20 V")])

    def test_revise_then_verify(self):
        def research(data, result, ask):
            self.assertIn("voltage", result["reason"])
            return dict(data, draft="draft two")
        def ask(query):
            return vote(query, "REVISE" if "draft one" in query else "PASS")
        result = solve(self.data, ask, lambda _: "Rated 20 V", research)
        self.assertEqual([h["review"] for h in result["history"]], ["DO POPRAWY","SPRAWDZONE"])
        self.assertEqual(result["status"],"POTWIERDZONE")

    def test_no_reply(self):
        calls = []
        def ask(query):
            calls.append(query)
            raise TimeoutError()
        self.assertEqual(solve(self.data,ask,lambda _: "")["review"],"NIEPOTWIERDZONE")
        self.assertEqual(len(calls),2)

    def test_missing_quote_and_duplicate_revision(self):
        r = solve(self.data,lambda q: vote(q,"PASS"),lambda _: "", lambda d,r,a:d)
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")
        self.assertEqual(len(r["history"]),1)
        self.assertEqual(r["blocked"],["Voltage"])

    def test_round_limit(self):
        r = solve(self.data,lambda q:vote(q,"REVISE"),lambda _:"",lambda d,r,a:dict(d,draft=d["draft"]+"x"))
        self.assertEqual(len(r["history"]),3)

    def test_utf8(self):
        original = "ząb 🌞 " * 1400
        self.assertEqual("".join(parts(original, 1357)),original)
        def ask(query):
            self.assertLessEqual(len(query.encode()),2000)
            return vote(query,"PASS")
        r = evaluate(dict(self.data,draft=original),ask,lambda _:"Rated 20 V")
        self.assertGreater(r["parts"],1)
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")

    def test_delay_and_timeout(self):
        t = [0]
        def sleep(n):
            t[0] += n
        def poll(n):
            return {"pending":"in_progress"} if t[0]<60 else {"review":"DO POPRAWY"}
        self.assertEqual(waiter.wait(131,poll,100,lambda:t[0],sleep)["review"],"DO POPRAWY")
        t[0]=0
        self.assertEqual(waiter.wait(131,poll,45,lambda:t[0],sleep)["status"],"NIEPOTWIERDZONE")
