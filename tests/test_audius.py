import unittest
from unittest import mock

import requests

from src.audius.client import (
    AudiusClient,
    AudiusConnectionError,
    AudiusRateLimitError,
    AudiusResponseError,
    AudiusTrackUnavailableError,
)
from src.audius.models import AudiusTrack, format_duration

SAMPLE_TRACK = {
    "id": "vZJJz",
    "title": "workit (daftpunk flip)",
    "duration": 185,
    "genre": "Electronic",
    "permalink": "/artist/workit-daftpunk-flip",
    "is_streamable": True,
    "is_available": True,
    "is_stream_gated": False,
    "access": {"stream": True, "download": True},
    "album_backlink": {"playlist_id": 1, "playlist_name": "Flips", "permalink": "/a/album/flips"},
    "artwork": {
        "150x150": "https://node-a.example/content/Qm/150x150.jpg",
        "480x480": "https://node-a.example/content/Qm/480x480.jpg",
        "mirrors": ["https://node-b.example", "https://node-c.example"],
    },
    "user": {"id": "u1", "name": "Some Artist", "handle": "someartist"},
}


def fake_response(status: int = 200, payload=None, headers=None) -> mock.Mock:
    response = mock.Mock(status_code=status, headers=headers or {})
    response.json.return_value = payload
    return response


class AudiusTrackTests(unittest.TestCase):
    def test_parses_all_fields(self) -> None:
        track = AudiusTrack.from_api(SAMPLE_TRACK)
        self.assertEqual(track.id, "vZJJz")
        self.assertEqual(track.artist, "Some Artist")
        self.assertEqual(track.album, "Flips")
        self.assertEqual(track.duration_label, "3:05")
        self.assertEqual(track.web_url, "https://audius.co/artist/workit-daftpunk-flip")
        self.assertTrue(track.can_stream)

    def test_missing_optional_fields(self) -> None:
        track = AudiusTrack.from_api({"id": "abc"})
        self.assertEqual(track.title, "Sin título")
        self.assertEqual(track.album, "")
        self.assertFalse(track.artwork.available)
        self.assertFalse(track.can_stream)

    def test_invalid_or_deleted(self) -> None:
        self.assertIsNone(AudiusTrack.from_api(None))
        self.assertIsNone(AudiusTrack.from_api({"title": "sin id"}))
        self.assertIsNone(AudiusTrack.from_api({**SAMPLE_TRACK, "is_delete": True}))

    def test_gated_track_not_playable(self) -> None:
        raw = {**SAMPLE_TRACK, "is_stream_gated": True, "access": {"stream": False}}
        track = AudiusTrack.from_api(raw)
        self.assertFalse(track.can_stream)
        self.assertIn("restringido", track.unavailable_reason)

    def test_artwork_mirror_urls(self) -> None:
        urls = AudiusTrack.from_api(SAMPLE_TRACK).artwork.candidate_urls("150x150")
        self.assertEqual(urls[0], "https://node-a.example/content/Qm/150x150.jpg")
        self.assertEqual(urls[1], "https://node-b.example/content/Qm/150x150.jpg")
        self.assertEqual(len(urls), 3)

    def test_format_duration(self) -> None:
        self.assertEqual(format_duration(59), "0:59")
        self.assertEqual(format_duration(3725), "1:02:05")


class AudiusClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = mock.Mock()
        self.client = AudiusClient(base_url="https://api.test/v1", api_key="", session=self.session)

    def test_search_uses_official_endpoint_and_caches(self) -> None:
        self.session.get.return_value = fake_response(payload={"data": [SAMPLE_TRACK, {"bad": 1}]})
        tracks = self.client.search_tracks("  daft   punk ", limit=5)
        self.assertEqual([t.id for t in tracks], ["vZJJz"])
        url = self.session.get.call_args.args[0]
        params = self.session.get.call_args.kwargs["params"]
        self.assertEqual(url, "https://api.test/v1/tracks/search")
        self.assertEqual(params, {"query": "daft punk", "limit": 5, "offset": 0})
        self.assertIn("timeout", self.session.get.call_args.kwargs)
        self.client.search_tracks("Daft Punk", limit=5)
        self.assertEqual(self.session.get.call_count, 1)  # servido desde caché

    def test_api_key_sent_when_configured(self) -> None:
        client = AudiusClient(base_url="https://api.test/v1", api_key="k123", session=self.session)
        self.session.get.return_value = fake_response(payload={"data": []})
        client.search_tracks("x")
        self.assertEqual(self.session.get.call_args.kwargs["params"]["api_key"], "k123")

    def test_empty_query_makes_no_request(self) -> None:
        self.assertEqual(self.client.search_tracks("   "), [])
        self.session.get.assert_not_called()

    def test_stream_url(self) -> None:
        self.session.get.return_value = fake_response(payload={"data": "https://cn.example/stream?sig=1"})
        track = AudiusTrack.from_api(SAMPLE_TRACK)
        self.assertEqual(self.client.get_stream_url(track), "https://cn.example/stream?sig=1")
        self.assertEqual(self.session.get.call_args.args[0], "https://api.test/v1/tracks/vZJJz/stream")
        self.assertEqual(self.session.get.call_args.kwargs["params"]["no_redirect"], "true")

    def test_stream_unplayable_track_skips_request(self) -> None:
        track = AudiusTrack.from_api({**SAMPLE_TRACK, "is_streamable": False})
        with self.assertRaises(AudiusTrackUnavailableError):
            self.client.get_stream_url(track)
        self.session.get.assert_not_called()

    def test_stream_404_is_unavailable(self) -> None:
        self.session.get.return_value = fake_response(404, {"error": "track not found"})
        with self.assertRaises(AudiusTrackUnavailableError):
            self.client.get_stream_url("abc12")

    def test_rate_limit(self) -> None:
        self.session.get.return_value = fake_response(429, {}, {"Retry-After": "30"})
        with self.assertRaises(AudiusRateLimitError) as ctx:
            self.client.search_tracks("x")
        self.assertEqual(ctx.exception.retry_after, 30.0)

    def test_connection_error(self) -> None:
        self.session.get.side_effect = requests.ConnectionError()
        with self.assertRaises(AudiusConnectionError):
            self.client.search_tracks("x")

    def test_invalid_json(self) -> None:
        response = fake_response()
        response.json.side_effect = ValueError()
        self.session.get.return_value = response
        with self.assertRaises(AudiusResponseError):
            self.client.search_tracks("x")

    def test_unexpected_shape(self) -> None:
        self.session.get.return_value = fake_response(payload={"data": "nope"})
        with self.assertRaises(AudiusResponseError):
            self.client.search_tracks("y")


if __name__ == "__main__":
    unittest.main()
