"""Retired vbpl.vn links are rewritten to the new site; other links are kept as stored."""

from legal_checker.modules.reports.legal_basis import live_source_url


def test_old_vbpl_document_pages_point_to_the_new_site():
    for page in ("vbpq-thuoctinh", "vbpq-toanvan"):
        old = f"https://vbpl.vn/TW/Pages/{page}.aspx?ItemID=169708"
        assert live_source_url(old) == "https://vbpl.vn/van-ban/chi-tiet/van-ban--169708"
    assert (
        live_source_url("http://www.vbpl.vn/tw/Pages/vbpq-toanvan.aspx?dvid=13&ItemID=26356")
        == "https://vbpl.vn/van-ban/chi-tiet/van-ban--26356"
    )


def test_other_links_are_unchanged():
    related = "https://vbpl.vn/TW/Pages/vbpq-vanbanlienquan.aspx?ItemID=26904"
    for url in (
        related,  # names another document; left for the data owner
        "https://vanban.chinhphu.vn/?docid=208363&pageid=27160",
        "https://vbpl.vn/van-ban/chi-tiet/van-ban--169708",
        None,
        "",
    ):
        assert live_source_url(url) == url
