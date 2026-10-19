import csv
import hashlib

import requests

from pipelines.extract import bulbagarden
from pipelines.extract import http as extract_http


class _FakeResponse:
    def __init__(self, *, json_data=None, content: bytes = b"", status_code: int = 200):
        self._json_data = json_data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._json_data


class _FakeSession:
    """Dispatches on the request: MediaWiki API calls (categorymembers,
    imageinfo) return canned JSON; anything else (a resolved image URL) is
    treated as a binary image download and returns fixed bytes content."""

    def __init__(
        self,
        *,
        categorymembers_pages: list[list[dict]],
        imageinfo_by_title: dict,
        fail_count: int = 0,
        fail_status_code: int = 500,
    ):
        self._categorymembers_pages = categorymembers_pages
        self._imageinfo_by_title = imageinfo_by_title
        self._fail_count = fail_count
        self._fail_status_code = fail_status_code
        self.requested_urls: list[str] = []
        self.downloaded_urls: list[str] = []
        self._cm_call_index = 0

    def get(self, url: str, params: dict | None = None, timeout: int = 30):
        self.requested_urls.append(url)
        if len(self.requested_urls) <= self._fail_count:
            return _FakeResponse(status_code=self._fail_status_code)
        if url != bulbagarden.API_BASE_URL:
            self.downloaded_urls.append(url)
            return _FakeResponse(content=_FAKE_IMAGE_BYTES)

        if params.get("list") == "categorymembers":
            page = self._categorymembers_pages[self._cm_call_index]
            self._cm_call_index += 1
            has_more = self._cm_call_index < len(self._categorymembers_pages)
            payload = {"query": {"categorymembers": page}}
            if has_more:
                payload["continue"] = {"cmcontinue": f"token-{self._cm_call_index}"}
            return _FakeResponse(json_data=payload)

        if params.get("prop") == "imageinfo":
            titles = params["titles"].split("|")
            pages = {}
            for i, title in enumerate(titles):
                info = self._imageinfo_by_title.get(title)
                if info is not None:
                    pages[str(i)] = {"title": title, "imageinfo": [info]}
            return _FakeResponse(json_data={"query": {"pages": pages}})

        raise AssertionError(f"Unexpected API params: {params}")


_FAKE_IMAGE_BYTES = b"\x89PNG fake bytes for testing"
_FAKE_IMAGE_SHA1 = hashlib.sha1(_FAKE_IMAGE_BYTES).hexdigest()

MEGA_TITLE = "File:Menu Champs 0003-Mega.png"
BASE_TITLE = "File:Menu Champs 0004.png"
PALDEA_TITLE = "File:Menu Champs 0128-Paldea Aqua.png"

MEMBERS_PAGE_1 = [{"pageid": 1, "ns": 6, "title": MEGA_TITLE}]
MEMBERS_PAGE_2 = [{"pageid": 2, "ns": 6, "title": BASE_TITLE}]

IMAGEINFO = {
    MEGA_TITLE: {
        "url": "https://archives.bulbagarden.net/media/upload/d/dc/Menu_CP_0003-Mega.png",
        "width": 128,
        "height": 128,
        "mime": "image/png",
        "sha1": _FAKE_IMAGE_SHA1,
        "size": len(_FAKE_IMAGE_BYTES),
    },
    BASE_TITLE: {
        "url": "https://archives.bulbagarden.net/media/upload/a/ab/Menu_CP_0004.png",
        "width": 128,
        "height": 128,
        "mime": "image/png",
        "sha1": _FAKE_IMAGE_SHA1,
        "size": len(_FAKE_IMAGE_BYTES),
    },
}


def _make_session(**kwargs):
    return _FakeSession(
        categorymembers_pages=kwargs.get("categorymembers_pages", [MEMBERS_PAGE_1, MEMBERS_PAGE_2]),
        imageinfo_by_title=kwargs.get("imageinfo_by_title", IMAGEINFO),
        fail_count=kwargs.get("fail_count", 0),
        fail_status_code=kwargs.get("fail_status_code", 500),
    )


def test_extract_paginates_category_members_and_writes_manifest_rows(tmp_path):
    session = _make_session()
    output_path = tmp_path / "bulbagarden.csv"
    cache_dir = tmp_path / "cache"

    bulbagarden.extract(output_path, dataset_version="0.1.0", session=session, cache_dir=cache_dir)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2
    mega_row = next(r for r in rows if r["bulbagarden_title"] == MEGA_TITLE)
    assert mega_row["pokedex_number_raw"] == "0003"
    assert mega_row["form_suffix_raw"] == "Mega"
    assert mega_row["image_kind"] == "menu_sprite"
    assert mega_row["local_cache_path"] == "0003-Mega.png"
    assert mega_row["sha1"] == _FAKE_IMAGE_SHA1
    assert mega_row["width"] == "128"
    assert mega_row["source_name"] == "Bulbagarden Archives"
    assert mega_row["source_url"] == IMAGEINFO[MEGA_TITLE]["url"]
    assert mega_row["source_record_id"] == MEGA_TITLE
    assert mega_row["dataset_version"] == "0.1.0"
    assert mega_row["extracted_at_utc"]

    base_row = next(r for r in rows if r["bulbagarden_title"] == BASE_TITLE)
    assert base_row["pokedex_number_raw"] == "0004"
    assert base_row["form_suffix_raw"] == ""
    assert base_row["local_cache_path"] == "0004.png"


def test_extract_downloads_image_bytes_to_cache_dir(tmp_path):
    session = _make_session()
    output_path = tmp_path / "bulbagarden.csv"
    cache_dir = tmp_path / "cache"

    bulbagarden.extract(output_path, session=session, cache_dir=cache_dir)

    downloaded = cache_dir / "0003-Mega.png"
    assert downloaded.exists()
    assert downloaded.read_bytes() == _FAKE_IMAGE_BYTES
    assert hashlib.sha1(downloaded.read_bytes()).hexdigest() == _FAKE_IMAGE_SHA1


def test_extract_parses_multi_word_form_suffix(tmp_path):
    session = _make_session(
        categorymembers_pages=[[{"pageid": 3, "ns": 6, "title": PALDEA_TITLE}]],
        imageinfo_by_title={
            PALDEA_TITLE: {
                "url": "https://archives.bulbagarden.net/media/upload/x/xy/Menu_CP_0128-Paldea_Aqua.png",
                "width": 128,
                "height": 128,
                "mime": "image/png",
                "sha1": _FAKE_IMAGE_SHA1,
                "size": len(_FAKE_IMAGE_BYTES),
            }
        },
    )
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=tmp_path / "cache")

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["pokedex_number_raw"] == "0128"
    assert row["form_suffix_raw"] == "Paldea Aqua"
    assert row["local_cache_path"] == "0128-Paldea Aqua.png"


def test_extract_skips_unparseable_titles(tmp_path):
    weird_title = "File:Some Other Sprite.png"
    session = _make_session(
        categorymembers_pages=[[{"pageid": 4, "ns": 6, "title": weird_title}]],
        imageinfo_by_title={},
    )
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=tmp_path / "cache")

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows == []


def test_extract_skips_redownload_when_cached_sha1_matches(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "0003-Mega.png").write_bytes(_FAKE_IMAGE_BYTES)

    session = _make_session(categorymembers_pages=[MEMBERS_PAGE_1])
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=cache_dir)

    assert IMAGEINFO[MEGA_TITLE]["url"] not in session.downloaded_urls


def test_extract_redownloads_when_cached_file_differs(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "0003-Mega.png").write_bytes(b"stale content")

    session = _make_session(categorymembers_pages=[MEMBERS_PAGE_1])
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=cache_dir)

    assert IMAGEINFO[MEGA_TITLE]["url"] in session.downloaded_urls
    assert (cache_dir / "0003-Mega.png").read_bytes() == _FAKE_IMAGE_BYTES


def test_extract_defaults_dataset_version_when_not_provided(tmp_path):
    session = _make_session(categorymembers_pages=[MEMBERS_PAGE_1])
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=tmp_path / "cache")

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["dataset_version"] == bulbagarden.DEFAULT_DATASET_VERSION


def test_extract_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda seconds: None)
    session = _make_session(categorymembers_pages=[MEMBERS_PAGE_1], fail_count=2)
    output_path = tmp_path / "bulbagarden.csv"

    bulbagarden.extract(output_path, session=session, cache_dir=tmp_path / "cache")

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1


def test_parse_title_accepts_current_and_legacy_prefixes():
    # Bulbagarden renamed every file from "Menu CP" to "Menu Champs" by
    # 2026-10; the old pattern silently matched nothing and wrote an empty
    # snapshot.
    assert bulbagarden._parse_title("File:Menu Champs 0359-Mega Z.png") == ("0359", "Mega Z")
    assert bulbagarden._parse_title("File:Menu CP 0003.png") == ("0003", None)
    assert bulbagarden._parse_title("File:Something Else 0003.png") is None
