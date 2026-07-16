from __future__ import annotations

import unittest

from netease_album_wallpaper.netease import (
    albums_from_songs,
    extract_first_url,
    extract_id_from_url,
    resolve_playlist_id,
)


class NeteaseParsingTests(unittest.TestCase):
    def test_extract_url_from_share_text(self) -> None:
        text = "分享歌单: 测试 https://163cn.tv/abc123 (@网易云音乐)"
        self.assertEqual(extract_first_url(text), "https://163cn.tv/abc123")

    def test_extract_playlist_id_from_query(self) -> None:
        self.assertEqual(
            extract_id_from_url("https://music.163.com/playlist?id=123456&userid=7"),
            "123456",
        )

    def test_extract_playlist_id_from_fragment(self) -> None:
        self.assertEqual(
            extract_id_from_url("https://music.163.com/#/playlist?id=987654"),
            "987654",
        )

    def test_raw_numeric_id(self) -> None:
        self.assertEqual(resolve_playlist_id("123456"), ("123456", None))

    def test_album_id_deduplication(self) -> None:
        songs = [
            {
                "id": 1,
                "name": "A",
                "album": {
                    "id": 10,
                    "name": "Album A",
                    "picUrl": "https://p1.music.126.net/a.jpg",
                },
                "artists": [{"name": "Artist"}],
            },
            {
                "id": 2,
                "name": "B",
                "album": {
                    "id": 10,
                    "name": "Album A",
                    "picUrl": "https://p1.music.126.net/a.jpg",
                },
                "artists": [{"name": "Artist"}],
            },
            {
                "id": 3,
                "name": "C",
                "album": {
                    "id": 11,
                    "name": "Album B",
                    "picUrl": "https://p1.music.126.net/b.jpg",
                },
                "artists": [{"name": "Other"}],
            },
        ]
        albums = albums_from_songs(songs)
        self.assertEqual([album.id for album in albums], ["10", "11"])


if __name__ == "__main__":
    unittest.main()

