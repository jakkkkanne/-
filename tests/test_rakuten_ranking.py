from unittest.mock import MagicMock, patch

import pytest

from threads_ops import config, rakuten_ranking


def test_fetch_ranking_page_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(config, "RAKUTEN_APPLICATION_ID", "")
    monkeypatch.setattr(config, "RAKUTEN_ACCESS_KEY", "")
    with pytest.raises(RuntimeError):
        rakuten_ranking.fetch_ranking_page("100939")


def test_fetch_ranking_page_sends_confirmed_working_request_shape(monkeypatch):
    monkeypatch.setattr(config, "RAKUTEN_APPLICATION_ID", "app-id")
    monkeypatch.setattr(config, "RAKUTEN_ACCESS_KEY", "access-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Items": [{"Item": {"itemName": "商品A", "reviewCount": 10}}],
    }
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        items = rakuten_ranking.fetch_ranking_page("100939")

    assert items == [{"itemName": "商品A", "reviewCount": 10}]
    call_args = mock_get.call_args
    assert call_args.args[0] == rakuten_ranking.RAKUTEN_RANKING_API
    assert call_args.args[0] == "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
    params = call_args.kwargs["params"]
    assert params["applicationId"] == "app-id"
    assert params["accessKey"] == "access-key"
    assert params["genreId"] == "100939"


def test_fetch_top_ranked_pages_until_count_reached(monkeypatch):
    monkeypatch.setattr(config, "RAKUTEN_APPLICATION_ID", "app-id")
    monkeypatch.setattr(config, "RAKUTEN_ACCESS_KEY", "access-key")

    pages = [
        [{"itemName": f"item{i}"} for i in range(30)],
        [{"itemName": f"item{i}"} for i in range(30, 40)],
    ]

    with patch.object(rakuten_ranking, "fetch_ranking_page", side_effect=pages):
        items = rakuten_ranking.fetch_top_ranked("100939", count=35)

    assert len(items) == 35


def test_rank_by_review_count_sorts_desc_and_truncates():
    items = [
        {"itemName": "A", "reviewCount": 5},
        {"itemName": "B", "reviewCount": 50},
        {"itemName": "C", "reviewCount": 20},
    ]
    ranked = rakuten_ranking.rank_by_review_count(items, top_n=2)
    assert [i["itemName"] for i in ranked] == ["B", "C"]
