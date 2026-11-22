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
    match = re.search(r"(?:REVISE |PASS |space and )([0-9a-f]{12,16})", query)
    if not match:
        raise AssertionError("Review prompt is missing a deterministic verdict tag")
    tag = match[1]
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

    def test_attention_priority_is_in_review_without_removing_checks(self):
        from attention_guard import context_hash
        data = dict(self.data)
        data["attention"] = {
            "status":"active",
            "context_sha256":context_hash(data["question"], [c["requirement"] for c in data["checks"]]),
            "ranked_indices":[0]
        }
        sent = []
        def ask(query):
            sent.append(query)
            return vote(query, "PASS")
        result = evaluate(data, ask, lambda _:"Rated 20 V")
        self.assertEqual(result["review"],"SPRAWDZONE")
        self.assertTrue(any("attention highlights" in q for q in sent))
        self.assertTrue(all("Voltage" in q for q in sent))

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

    def test_review_ignores_massive_exploration_logs(self):
        packet = dict(self.data, search_log=[{"route":"bulk-noise"}] * 1000,
                      candidate_log=[{"model":"bulk-noise"}] * 1000,
                      feasibility={"bulk-noise":"not a proof"})
        prompts = []
        def ask(q):
            prompts.append(q)
            return vote(q, "PASS")
        result = evaluate(packet, ask, lambda _: "Rated 20 V")
        self.assertEqual(result["parts"], 1)
        self.assertEqual(result["review"], "SPRAWDZONE")
        self.assertFalse(any("bulk-noise" in p for p in prompts))
        self.assertTrue(all(len(p.encode()) <= 2000 for p in prompts))

    def test_ambiguous_google_answer_retried_with_focused_prompt(self):
        prompts = []
        def ask(q):
            prompts.append(q)
            if q.startswith("Audit this complete"):
                return vote(q, "ambiguous")
            return vote(q, "PASS")
        result = evaluate(self.data, ask, lambda _: "Rated 20 V")
        self.assertEqual(result["review"], "SPRAWDZONE")
        self.assertEqual(len(prompts), 3)
        self.assertTrue(prompts[1].startswith("Check this claim"))

    def test_unreadable_google_verdict_is_never_fake_pass(self):
        def ask(q):
            return vote(q, "ambiguous")
        result = evaluate(self.data, ask, lambda _: "Rated 20 V")
        self.assertEqual(result["review"], "NIEPOTWIERDZONE")
        self.assertIn("after two distinct prompts", result["reason"])

    def test_every_fragment_reviewed_even_if_first_is_rejected(self):
        data = dict(self.data, draft="Safe technical description. " * 250)
        prompts = []
        def ask(query):
            prompts.append(query)
            return vote(query, "REVISE" if "Part 1/" in query else "PASS")
        result = evaluate(data, ask, lambda _: "Rated 20 V")
        self.assertGreater(result["parts"], 1)
        self.assertEqual(result["review"], "DO POPRAWY")
        self.assertEqual(result["reviewed"], result["parts"])
        self.assertEqual(result["failed_parts"], [1])
        for index in range(1, result["parts"] + 1):
            self.assertTrue(any("Part "+str(index)+"/"+str(result["parts"]) in q
                                for q in prompts))

    def test_missing_middle_verdict_does_not_skip_later_fragments(self):
        data = dict(self.data, draft="More source verification required. " * 180)
        prompts = []
        def ask(query):
            prompts.append(query)
            return vote(query, "ambiguous" if "Part 2/" in query else "PASS")
        result = evaluate(data, ask, lambda _: "Rated 20 V")
        self.assertGreater(result["parts"], 2)
        self.assertEqual(result["review"], "NIEPOTWIERDZONE")
        self.assertEqual(result["reviewed"], result["parts"])
        self.assertIn(2, result["unreadable_parts"])
        self.assertTrue(any("Part "+str(result["parts"])+"/"+str(result["parts"]) in q
                            for q in prompts))

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
            tag = re.search(r'"tag":"([a-f0-9]{16})"', query)[1]
            packet = json.dumps(dict(tag=tag, old="draft one", new="Corrected voltage"))
            packet = packet.replace("Corrected voltage", "Corrected\nvoltage")
            return dict(question=query, page=dict(url="https://www.google.com/search?"+
                        urlencode({"q":query, "udm":"50"}), text="Answer:\n"+packet))
        revised = google_research(self.data, {"reason":"Check voltage"}, research_response)
        self.assertEqual(revised["checks"][0]["status"], "met")
        self.assertEqual(revised["checks"][0]["requirement"], "Voltage")
        self.assertEqual(revised["draft"], "Corrected\nvoltage")

    def test_s700_research_disallows_station_swaps_prices_and_unrelated_claims(self):
        from consult import google_research
        import json
        data = dict(question="ALLPOWERS S700 606Wh, max £100", 
                    draft="Nie znaleziono kompletnego potwierdzonego zestawu.",
                    checks=[dict(requirement="Budget", status="unknown")])
        for attempted in ("ALLPOWERS R600 jest lepszy.",
                          "Kup panel za £29.99.",
                          "Beton wapienny sam się naprawia."):
            with self.subTest(attempted=attempted):
                def answer(query):
                    tag = re.search(r'"tag":"([a-f0-9]{16})"', query)[1]
                    packet = json.dumps(dict(tag=tag, old=data["draft"],
                                             new=attempted), ensure_ascii=False)
                    return dict(question=query, page=dict(url="https://www.google.com/search?"+
                                urlencode({"q":query, "udm":"50"}), text=packet))
                with self.assertRaisesRegex(ValueError, "No safe patch accepted"):
                    google_research(data, {"reason":"DO POPRAWY"}, answer)
        self.assertEqual(data["checks"][0]["status"], "unknown")

    def test_s700_deterministic_correction_of_false_voltage(self):
        from consult import evidence_revision
        data = dict(question="ALLPOWERS S700", draft="25,2 V mieści się w 24 V",
                    checks=[dict(requirement="Voltage", status="failed")])
        r = evidence_revision(data, {"reason":"DO POPRAWY"}, lambda _: "")
        self.assertIn("przekracza limit 24 V", r["draft"])
        self.assertEqual(r["checks"], data["checks"])

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
        self.assertEqual(len(r["history"]), 1)
        self.assertIn("research_error", r["history"][0])
        self.assertEqual(r["history"][0]["correction_status"], "BLOCKED_UNVERIFIED")
        self.assertEqual(r["draft"], "draft one")
        self.assertEqual(r["status"], "NIEPOTWIERDZONE")

    def test_google_must_recheck_every_revision(self):
        # A local patch is not confirmation: every revised draft must trigger a
        # separate Google AI query with the amended text.
        packet = dict(question="Charge existing ALLPOWERS S700.",
                      draft="25,2 V mieści się w 24 V",
                      checks=[dict(requirement="Voltage", status="met",
                                   finding="Limit 24 V",
                                   source="https://example.org/voltage",
                                   quote="The maximum rated input is 24 V")])
        calls = []
        def google(query):
            calls.append(query)
            return vote(query, "REVISE" if "mieści się" in query else "PASS")
        def patch(data, result, ask):
            self.assertEqual(result["review"], "DO POPRAWY")
            return dict(data, draft="25,2 V przekracza limit 24 V")
        receipt = solve(packet, google, lambda _:"The maximum rated input is 24 V", patch)
        self.assertEqual(receipt["status"], "POTWIERDZONE")
        self.assertEqual(len(receipt["history"]), 2)
        self.assertTrue(receipt["history"][1]["correction_rechecked_by_google"])
        self.assertEqual(receipt["google_ai_edits_rechecked"], 1)
        self.assertTrue(any("25,2 V przekracza" in q for q in calls))
        self.assertEqual(receipt["google_ai_responses_received"], len(calls))
        self.assertEqual(receipt["google_ai_queries_sent"], len(calls))

    def test_no_google_verdict_after_patch_discards_the_patch(self):
        packet = dict(question="Charge ALLPOWERS S700.",
                      draft="25,2 V mieści się w 24 V",
                      checks=[dict(requirement="Voltage", status="unknown")])
        calls = []
        def google(query):
            calls.append(query)
            if "przekracza limit" in query:
                raise TimeoutError("Google AI unavailable")
            return vote(query, "REVISE")
        def patch(data, result, ask):
            return dict(data, draft="25,2 V przekracza limit 24 V")
        receipt = solve(packet, google, lambda _: "", patch)
        self.assertEqual(receipt["review"], "NIEPOTWIERDZONE")
        self.assertEqual(receipt["status"], "NIEPOTWIERDZONE")
        self.assertEqual(receipt["draft"], packet["draft"])
        self.assertEqual(receipt["google_ai_edits_rechecked"], 1)
        self.assertEqual(receipt["history"][1]["correction_status"], "BLOCKED_NO_GOOGLE_VERDICT")
        self.assertGreaterEqual(receipt["google_ai_queries_sent"], 3)
        self.assertGreaterEqual(len(calls), 3)

    def test_stop_hook_waits_and_routes_rejection_to_next_round(self):
        from unittest.mock import patch
        import hashlib
        title = "[consult] " + hashlib.sha256(b"session\x00turn").hexdigest()[:24]
        event = dict(session_id="session",turn_id="turn",hook_event_name="Stop",
                     last_assistant_message="NIEPOTWIERDZONE\n"+waiter.LINK+"132")
        with patch.object(waiter,"lookup",return_value=dict(title=title,pending="in_progress")):
            self.assertIn("--wait 132",waiter.evaluate(event)["reason"])
        with patch.object(waiter,"lookup",return_value=dict(title=title,review="DO POPRAWY",
                status="NIEPOTWIERDZONE",reason="Napięcie",history=[{}])):
            self.assertIn(title+" /2",waiter.evaluate(event)["reason"])
        with patch.object(waiter,"lookup",return_value=dict(title=title+" /3",review="DO POPRAWY",
                status="NIEPOTWIERDZONE",reason="Napięcie",history=[{}])):
            self.assertEqual(waiter.evaluate(event),{})

    def test_stop_hook_cannot_skip_github_when_unavailable(self):
        event = dict(session_id="session", turn_id="turn", hook_event_name="Stop",
                     last_assistant_message="NIEPOTWIERDZONE Brak dostępu: GitHub")
        result = waiter.evaluate(event)
        self.assertEqual(result["decision"], "block")

    def test_stop_hook_rejects_fake_positive_without_google_answer(self):
        from unittest.mock import patch
        import hashlib
        title = "[consult] " + hashlib.sha256(b"session" + bytes([0]) + b"turn").hexdigest()[:24]
        event = dict(session_id="session", turn_id="turn", hook_event_name="Stop",
                     last_assistant_message="POTWIERDZONE test\n" + waiter.LINK + "132")
        with patch.object(waiter, "lookup", return_value=dict(
                title=title, review="SPRAWDZONE", status="POTWIERDZONE",
                draft="test", google_ai_responses_received=0)):
            self.assertEqual(waiter.evaluate(event)["decision"], "block")
