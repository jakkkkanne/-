from threads_ops import affiliate, config


def test_rakuten_search_url_encodes_keyword():
    url = affiliate.rakuten_search_url("抱っこ紐")
    assert url.startswith("https://search.rakuten.co.jp/search/mall/")
    assert "%E6%8A%B1" in url  # percent-encoded


def test_build_affiliate_link_without_id_returns_placeholder_note(monkeypatch):
    monkeypatch.setattr(config, "RAKUTEN_AFFILIATE_ID", "")
    link = affiliate.build_affiliate_link("抱っこ紐")
    assert link.startswith("https://search.rakuten.co.jp/search/mall/")
    assert "RAKUTEN_AFFILIATE_ID未設定" in link


def test_build_affiliate_link_with_id_wraps_in_rakuten_conversion_url(monkeypatch):
    monkeypatch.setattr(config, "RAKUTEN_AFFILIATE_ID", "1234567.89012345")
    link = affiliate.build_affiliate_link("抱っこ紐")
    assert link.startswith("https://hb.afl.rakuten.co.jp/hgc/1234567.89012345/?pc=")
    assert "RAKUTEN_AFFILIATE_ID未設定" not in link


def test_recommend_product_known_pain_point():
    result = affiliate.recommend_product("夜泣き")
    assert result is not None
    keyword, link = result
    assert keyword == "ホワイトノイズマシン 赤ちゃん"
    assert link.startswith("https://search.rakuten.co.jp/") or link.startswith(
        "https://hb.afl.rakuten.co.jp/"
    )


def test_recommend_product_unknown_pain_point_returns_none():
    assert affiliate.recommend_product("存在しない悩み") is None


def test_recommend_in_price_range_within_band():
    # 夜泣き -> ホワイトノイズマシン, price_jpy 3480, within 2000-6000
    result = affiliate.recommend_in_price_range("夜泣き", min_price_jpy=2000, max_price_jpy=6000)
    assert result is not None
    assert result["name"] == "ホワイトノイズマシン"
    assert 2000 <= result["price_jpy"] <= 6000
    assert result["link"]


def test_recommend_in_price_range_excludes_out_of_band_products():
    # イヤイヤ期 -> 絵本, price_jpy 1200, below 2000
    assert affiliate.recommend_in_price_range("イヤイヤ期", min_price_jpy=2000, max_price_jpy=6000) is None
    # 時短家事 -> 食洗機, price_jpy 25000, above 6000
    assert affiliate.recommend_in_price_range("時短家事", min_price_jpy=2000, max_price_jpy=6000) is None


def test_recommend_in_price_range_uses_config_defaults(monkeypatch):
    monkeypatch.setattr(config, "AFFILIATE_MIN_PRICE_JPY", 2000)
    monkeypatch.setattr(config, "AFFILIATE_MAX_PRICE_JPY", 6000)
    assert affiliate.recommend_in_price_range("夜泣き") is not None
    assert affiliate.recommend_in_price_range("イヤイヤ期") is None


def test_recommend_in_price_range_unknown_pain_point_returns_none():
    assert affiliate.recommend_in_price_range("存在しない悩み", 2000, 6000) is None
