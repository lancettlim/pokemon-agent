import requests

from pipelines.render import bulbagarden_items


class _FakeResponse:
    def __init__(self, *, json_payload=None, content: bytes = b"fake-item-bytes"):
        self._json_payload = json_payload
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_payload


class _FailingResponse:
    def raise_for_status(self) -> None:
        raise requests.HTTPError("404")


class _FakeSession:
    """Routes API calls (api.php URL) to a canned imageinfo payload and
    image downloads (any other URL) to canned bytes, recording every URL
    requested for assertions."""

    def __init__(self, *, api_payload=None, download_fails: bool = False):
        self.requested_urls: list[str] = []
        self.api_payload = api_payload if api_payload is not None else {"query": {"pages": {}}}
        self.download_fails = download_fails

    def get(self, url: str, params=None, timeout: int = 30):
        self.requested_urls.append(url)
        if url == bulbagarden_items.API_BASE_URL:
            return _FakeResponse(json_payload=self.api_payload)
        if self.download_fails:
            return _FailingResponse()
        return _FakeResponse()


def _payload_resolving(title: str, url: str = "https://cdn.example/icon.png") -> dict:
    return {
        "query": {
            "pages": {
                "1": {"title": title, "imageinfo": [{"url": url}]},
            }
        }
    }


def test_resolves_primary_bag_sprite_title(tmp_path):
    session = _FakeSession(api_payload=_payload_resolving("File:Bag Leftovers Sprite.png"))

    path = bulbagarden_items.ensure_item_icon_bulbagarden(
        "Leftovers", cache_dir=tmp_path, session=session
    )

    assert path == tmp_path / "bulbagarden_items_hd" / "leftovers.png"
    assert path.read_bytes() == b"fake-item-bytes"
    assert session.requested_urls[0] == bulbagarden_items.API_BASE_URL

    # second call should hit the cache, not the network
    session.requested_urls = []
    bulbagarden_items.ensure_item_icon_bulbagarden("Leftovers", cache_dir=tmp_path, session=session)
    assert session.requested_urls == []


def test_falls_back_to_a_later_title_variant(tmp_path):
    # Only the last candidate ("File:<Name>.png") resolves.
    session = _FakeSession(api_payload=_payload_resolving("File:Weird Item.png"))

    path = bulbagarden_items.ensure_item_icon_bulbagarden(
        "Weird Item", cache_dir=tmp_path, session=session
    )

    assert path == tmp_path / "bulbagarden_items_hd" / "weird-item.png"


def test_prefers_the_high_res_render_over_the_pixel_sprite(tmp_path):
    # Both the 160px Z-A render and the 24px bag sprite exist; the render wins.
    payload = {
        "query": {
            "pages": {
                "1": {
                    "title": "File:Bag Leftovers Sprite.png",
                    "imageinfo": [{"url": "https://cdn.example/pixel.png"}],
                },
                "2": {
                    "title": "File:Bag Leftovers ZA Sprite.png",
                    "imageinfo": [{"url": "https://cdn.example/za.png"}],
                },
            }
        }
    }
    session = _FakeSession(api_payload=payload)

    bulbagarden_items.ensure_item_icon_bulbagarden("Leftovers", cache_dir=tmp_path, session=session)

    assert session.requested_urls[-1] == "https://cdn.example/za.png"


def test_returns_none_when_no_candidate_resolves(tmp_path):
    session = _FakeSession(api_payload={"query": {"pages": {}}})

    assert (
        bulbagarden_items.ensure_item_icon_bulbagarden(
            "Nonexistent Item", cache_dir=tmp_path, session=session
        )
        is None
    )


def test_returns_none_on_download_failure(tmp_path):
    session = _FakeSession(
        api_payload=_payload_resolving("File:Bag Leftovers Sprite.png"), download_fails=True
    )

    assert (
        bulbagarden_items.ensure_item_icon_bulbagarden(
            "Leftovers", cache_dir=tmp_path, session=session
        )
        is None
    )


def test_uses_a_cache_subdirectory_distinct_from_pokeapi_items(tmp_path):
    session = _FakeSession(api_payload=_payload_resolving("File:Bag Leftovers Sprite.png"))

    path = bulbagarden_items.ensure_item_icon_bulbagarden(
        "Leftovers", cache_dir=tmp_path, session=session
    )

    assert path.parent.name == "bulbagarden_items_hd"
    assert path.parent != tmp_path / "items"
