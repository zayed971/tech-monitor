import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import store_payments as sp  # noqa: E402

EVID = "### https://x.com/pay\nWe accept PayPal and Visa / Mastercard.  Cash on delivery   is available in Cairo. Installments via valU."


def test_quote_ok_verbatim_and_whitespace():
    assert sp.quote_ok("We accept PayPal", EVID)
    assert sp.quote_ok("Cash on delivery is available", EVID)   # whitespace-normalised
    assert not sp.quote_ok("We accept Bitcoin", EVID)
    assert not sp.quote_ok("PP", EVID)                           # too short


def test_prune_removes_invented_quotes():
    obj = {"payments": [{"method": "PayPal", "quote": "We accept PayPal"}, {"method": "Bitcoin", "quote": "We accept Bitcoin"}],
           "condition": [{"condition": "new", "quote": "Installments via valU"}, {"condition": "used", "quote": "second hand goods"}],
           "ships_to_uae": {"answer": "yes", "quote": "ships to Dubai"},
           "installment_providers": ["valU", "Tabby"]}
    clean, pruned = sp.prune_result(obj, EVID)
    assert [p["method"] for p in clean["payments"]] == ["PayPal"]
    assert [c["condition"] for c in clean["condition"]] == ["new"]
    assert clean["ships_to_uae"]["answer"] == "unknown"
    assert clean["installment_providers"] == ["valU"]
    assert len(pruned) == 4


def test_repair_json_variants():
    assert sp.repair_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert sp.repair_json('Sure! {"a": [1, 2,],} thanks') == {"a": [1, 2]}
    assert sp.repair_json("no json here") is None
    cut = sp.repair_json('{"payments":[{"method":"PayPal","quote":"We accept PayPal"},{"method":"Vi')
    assert cut and cut["payments"][0]["method"] == "PayPal"


def test_pick_links_prefers_payment_pages_same_site():
    links = [("/pages/payment-methods", "Payment"), ("/faq", "FAQ"), ("https://other.com/payment", "x"), ("/products/laptop-1", "Laptop shipping"),
             ("/about", "About"), ("/shipping-policy", "Shipping"), ("mailto:a@b.c", "mail"), ("/logo.png", "pay")]
    got = sp.pick_links(links, "https://shop.eg/", 3)
    assert got[0] == "https://shop.eg/pages/payment-methods"
    assert set(got) == {"https://shop.eg/pages/payment-methods", "https://shop.eg/faq", "https://shop.eg/shipping-policy"}


def test_html_to_text_skips_scripts_and_collects_links():
    t, links = sp.html_to_text("<html><head><title>x</title></head><body><script>var a=1</script><p>Pay by <b>card</b></p><a href='/faq'>FAQ</a></body></html>")
    assert "var a" not in t and "Pay by card" in t
    assert ("/faq", "FAQ") in links


def test_looks_blocked():
    assert sp.looks_blocked(403, "")
    assert sp.looks_blocked(200, "Just a moment... " + "x" * 500)
    assert sp.looks_blocked(200, "short")
    assert sp.looks_blocked(200, "normal page text " * 50) == ""


def test_build_evidence_cap():
    ev = sp.build_evidence([("https://a/", "h" * 9000), ("https://a/p", "p" * 9000), ("https://a/q", "q" * 9000)])
    assert len(ev) <= sp.EVID_CAP and "### https://a/p" in ev and "### https://a/q" in ev
