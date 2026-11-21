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

    def test_wait_rejects_stale_result_and_non_bot(self):
        from hashlib import sha256
        import json
        body = '{"draft":"nowszy tekst"}'
        result = dict(issue=132,sha256=sha256(body.encode()).hexdigest(),run=5,status="NIEPOTWIERDZONE")
        def comment(login, value):
            return {"user":{"login":login},"body":"Konsultant/2 "+json.dumps(value)}
        comments = [comment("Photofiver",result),comment("github-actions[bot]",dict(result,run=6)),
                    comment("github-actions[bot]",dict(result,sha256="old"))]
        def read(path):
            if "comments" in path:
                return comments
            if "/actions/" in path:
                return {"workflow_runs":[dict(display_title="Google AI issue #132",id=5,status="in_progress")]}
            return dict(title="[consult] example",body=body,user={"login":"Photofiver"})
        self.assertEqual(waiter.lookup(132,read)["pending"],"in_progress")
        comments.append(comment("github-actions[bot]",result))
        self.assertEqual(waiter.lookup(132,read)["status"],"NIEPOTWIERDZONE")

    def test_transport_research_parser_and_reverification(self):
        from consult import google_research
        import json
        def research_response(query):
            tag = re.search(r"BEGIN-([a-f0-9]+)",query)[1]
            packet = json.dumps(dict(draft="Corrected voltage",evidence=[dict(index=0,status="failed",
                finding="24 V exceeded",source="https://example.org",quote="Rated 25 V")]))
            packet = packet.replace("Corrected voltage", "Corrected\nvoltage")
            return dict(question=query,page=dict(url="https://www.google.com/search?"+
                        urlencode({"q":query,"udm":"50"}),text="BEGIN-"+tag+"\n"+packet+"\nEND-"+tag))
        revised = google_research(self.data,{"reason":"Check voltage"},research_response)
        self.assertEqual(revised["checks"][0]["status"],"failed")
        self.assertEqual(revised["checks"][0]["requirement"],"Voltage")
        self.assertEqual(revised["draft"],"Corrected\nvoltage")

    def test_timeout_while_fetching_sources(self):
        def inaccessible(url):
            raise TimeoutError()
        r = evaluate(self.data,lambda q:vote(q,"PASS"),inaccessible)
        self.assertEqual(r["blocked"],["Voltage"])
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")

    def test_independent_coverage_can_reject_approved_draft(self):
        def ask(q):
            return vote(q,"REVISE" if q.startswith("Check ALL") else "PASS")
        r = evaluate(self.data,ask,lambda _:"Rated 20 V")
        self.assertEqual(r["review"],"SPRAWDZONE")
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")
        self.assertIn("DO POPRAWY",r["blocked"][0])

    def test_s700_delayed_rejection_correction_and_silent_provider(self):
        requirements = ["£100 z przewodami, Amazon UK lub Argos", "sztywny wodoodporny panel na zewnątrz",
                        "stacja w domu w Belfaście", "606 Wh w 48 h także zimą", "Anderson 12,7–24 V, 5 A, 100 W"]
        packet = dict(question="Znajdź zestaw do ALLPOWERS S700.", draft="25,2 V mieści się w 24 V",
                      checks=[dict(requirement=r,status="unknown") for r in requirements])
        def ask(q):
            return vote(q,"REVISE" if packet["draft"] in q else "PASS")
        def correct(data, feedback, _ask):
            self.assertEqual(feedback["review"],"DO POPRAWY")
            return dict(data,draft="25,2 V przekracza 24 V. Dobór kompletnego zestawu pozostaje otwarty.")
        def research(data,feedback,_ask):
            return data if feedback["review"] == "SPRAWDZONE" else correct(data,feedback,_ask)
        elapsed = [0]
        def delayed(number):
            if elapsed[0] < 90:
                return {"pending":"in_progress"}
            return solve(packet,ask,lambda _:"", research)
        def sleep(n):
            elapsed[0] += n
        r=waiter.wait(132,delayed,120,lambda:elapsed[0],sleep)
        self.assertEqual(r["review"],"SPRAWDZONE")
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")
        self.assertEqual(r["blocked"],requirements)
        self.assertEqual(len(r["history"]),2)
        def silent(_):
            raise TimeoutError("test transport")
        r=solve(packet,silent)
        self.assertEqual(r["review"],"NIEPOTWIERDZONE")

    def test_bad_research_format_triggers_grounded_revision(self):
        def broken(data,result,ask):
            raise ValueError("Bad WebView JSON")
        def ask(q):
            return vote(q,"REVISE" if "draft one" in q else "PASS")
        r=solve(self.data,ask,lambda _:"Rated 20 V",broken)
        self.assertGreaterEqual(len(r["history"]),2)
        self.assertIn("research_error",r["history"][0])
        self.assertIn("Rated 20 V",r["draft"])
        self.assertEqual(r["status"],"NIEPOTWIERDZONE")
