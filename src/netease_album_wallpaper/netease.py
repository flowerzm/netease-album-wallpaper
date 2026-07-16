from __future__ import annotations

import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
    "Accept": "application/json,text/html,application/xhtml+xml,image/avif,image/webp,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
}
ALLOWED_INPUT_HOSTS = {
    "163cn.tv",
    "163cn.com",
    "music.163.com",
    "m.music.163.com",
    "y.music.163.com",
}
URL_RE = re.compile(r"https?://[^\s<>\"'）)]+", re.IGNORECASE)
ID_RE = re.compile(r"[?&]id=(\d+)", re.IGNORECASE)
INVALID_FILENAME_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
MAX_IMAGE_BYTES = 30 * 1024 * 1024


class NeteaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    creator: str
    track_count: int
    resolved_url: str | None


@dataclass(frozen=True)
class Album:
    id: str
    name: str
    artist: str
    cover_url: str
    first_song: str
    song_id: str


@dataclass
class DownloadResult:
    album: Album
    path: Path | None
    status: str
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = asdict(self.album)
        result.update(
            {
                "file": self.path.name if self.path else "",
                "status": self.status,
                "error": self.error,
            }
        )
        return result


def extract_first_url(value: str) -> str | None:
    match = URL_RE.search(value)
    return match.group(0).rstrip(".,，。") if match else None


def _validate_input_host(url: str) -> None:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in ALLOWED_INPUT_HOSTS:
        raise NeteaseError(f"不支持的链接域名：{host or '(空)'}")


def extract_id_from_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    decoded = urllib.parse.unquote(url)
    for text in (parsed.query, parsed.fragment, decoded):
        match = ID_RE.search("?" + text.lstrip("?#"))
        if match:
            return match.group(1)
    path_match = re.search(
        r"/(?:playlist|songlist)/(\d+)(?:[/?#]|$)", decoded, re.IGNORECASE
    )
    return path_match.group(1) if path_match else None


def resolve_playlist_id(
    value: str, opener: urllib.request.OpenerDirector | None = None
) -> tuple[str, str | None]:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return value, None

    url = extract_first_url(value)
    if not url:
        raise NeteaseError("输入中没有找到网易云歌单链接或纯数字歌单 ID")
    _validate_input_host(url)

    playlist_id = extract_id_from_url(url)
    if playlist_id:
        return playlist_id, url

    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in {"163cn.tv", "163cn.com"}:
        raise NeteaseError("链接中没有找到歌单 ID")

    client = opener or urllib.request.build_opener()
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with client.open(request, timeout=15) as response:
            final_url = response.geturl()
            response.read(64)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NeteaseError(f"网易云短链解析失败：{exc}") from exc

    _validate_input_host(final_url)
    playlist_id = extract_id_from_url(final_url)
    if not playlist_id:
        raise NeteaseError(f"短链已跳转，但最终链接中没有歌单 ID：{final_url}")
    return playlist_id, final_url


def _get_json(
    url: str,
    params: dict[str, object],
    timeout: int = 30,
) -> dict[str, object]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
        data = json.loads(body.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError) as exc:
        raise NeteaseError(f"请求失败：{url}：{exc}") from exc
    if not isinstance(data, dict):
        raise NeteaseError(f"网易云接口响应格式异常：{url}")
    return data


def _fetch_track_details(
    track_ids: list[int],
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, object]]:
    songs: list[dict[str, object]] = []
    batch_size = 100
    for start in range(0, len(track_ids), batch_size):
        batch = track_ids[start : start + batch_size]
        data = _get_json(
            "https://music.163.com/api/song/detail",
            {"ids": json.dumps(batch, separators=(",", ":"))},
        )
        raw_songs = data.get("songs") or []
        if isinstance(raw_songs, list):
            songs.extend(song for song in raw_songs if isinstance(song, dict))
        if progress:
            progress(f"已读取歌曲详情：{min(start + len(batch), len(track_ids))}/{len(track_ids)}")
        if start + batch_size < len(track_ids):
            time.sleep(0.35)
    return songs


def albums_from_songs(songs: list[dict[str, object]]) -> list[Album]:
    seen: set[str] = set()
    albums: list[Album] = []
    for song in songs:
        raw_album = song.get("al") or song.get("album")
        if not isinstance(raw_album, dict):
            continue
        cover_url = raw_album.get("picUrl") or raw_album.get("blurPicUrl")
        if not cover_url:
            continue
        album_id = str(raw_album.get("id") or "")
        clean_cover_url = str(cover_url).split("?", 1)[0]
        dedupe_key = f"id:{album_id}" if album_id else f"url:{clean_cover_url}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        raw_artists = song.get("ar") or song.get("artists") or []
        artist_names = [
            str(artist.get("name", "")).strip()
            for artist in raw_artists
            if isinstance(artist, dict) and artist.get("name")
        ] if isinstance(raw_artists, list) else []
        albums.append(
            Album(
                id=album_id or "no-id",
                name=str(raw_album.get("name") or "未知专辑").strip(),
                artist="、".join(artist_names) or "未知歌手",
                cover_url=clean_cover_url,
                first_song=str(song.get("name") or ""),
                song_id=str(song.get("id") or ""),
            )
        )
    return albums


def fetch_playlist_albums(
    value: str, progress: Callable[[str], None] | None = None
) -> tuple[Playlist, list[Album]]:
    playlist_id, resolved_url = resolve_playlist_id(value)
    if progress:
        progress(f"歌单 ID：{playlist_id}")

    data = _get_json(
        "https://music.163.com/api/v6/playlist/detail",
        {"id": playlist_id, "n": 100000, "s": 0},
    )
    raw_playlist = data.get("playlist")
    if data.get("code") != 200 or not isinstance(raw_playlist, dict):
        message = data.get("message") or data.get("msg") or f"code={data.get('code')}"
        raise NeteaseError(f"歌单读取失败（可能是私密歌单或接口受限）：{message}")

    raw_track_ids = raw_playlist.get("trackIds") or []
    track_ids = [
        int(item["id"])
        for item in raw_track_ids
        if isinstance(item, dict) and str(item.get("id", "")).isdigit()
    ] if isinstance(raw_track_ids, list) else []
    if not track_ids:
        raise NeteaseError("歌单中没有可读取的歌曲；歌单可能是私密的")

    creator = raw_playlist.get("creator") or {}
    playlist = Playlist(
        id=playlist_id,
        name=str(raw_playlist.get("name") or f"playlist-{playlist_id}"),
        creator=str(creator.get("nickname") or "") if isinstance(creator, dict) else "",
        track_count=len(track_ids),
        resolved_url=resolved_url,
    )
    if progress:
        progress(f"歌单：{playlist.name}，共 {len(track_ids)} 首")
    songs = _fetch_track_details(track_ids, progress)
    albums = albums_from_songs(songs)
    if not albums:
        raise NeteaseError("歌曲详情中没有可下载的专辑封面")
    if progress:
        progress(f"专辑去重：{len(songs)} 首可用歌曲 → {len(albums)} 张唯一专辑封面")
    return playlist, albums


def safe_filename(value: str, max_length: int = 145) -> str:
    value = INVALID_FILENAME_RE.sub("_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "未知专辑")[:max_length].rstrip(" .")


def _validate_cover_host(url: str) -> None:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not (host == "music.126.net" or host.endswith(".music.126.net")):
        raise NeteaseError(f"拒绝下载非网易云图片域名：{host or '(空)'}")


def _image_extension(content_type: str, url: str) -> str:
    content_type = content_type.split(";", 1)[0].strip().lower()
    known = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type in known:
        return known[content_type]
    guessed = mimetypes.guess_extension(content_type) if content_type else None
    if guessed:
        return ".jpg" if guessed == ".jpe" else guessed
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _download_one(album: Album, index: int, directory: Path, retries: int) -> DownloadResult:
    try:
        _validate_cover_host(album.cover_url)
    except Exception as exc:
        return DownloadResult(album, None, "failed", str(exc))

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(album.cover_url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=35) as response:
                content_type = response.headers.get_content_type()
                data = response.read(MAX_IMAGE_BYTES + 1)
            if not content_type.startswith("image/"):
                raise NeteaseError(f"封面响应不是图片：{content_type}")
            if not data:
                raise NeteaseError("封面响应为空")
            if len(data) > MAX_IMAGE_BYTES:
                raise NeteaseError("封面文件超过 30 MB")
            extension = _image_extension(content_type, album.cover_url)
            filename = safe_filename(
                f"{index:03d} - {album.name} - {album.artist} - {album.id}"
            ) + extension
            path = directory / filename
            path.write_bytes(data)
            return DownloadResult(album, path, "ok")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1 + attempt)
    return DownloadResult(album, None, "failed", str(last_error))


def download_albums(
    albums: list[Album],
    directory: Path,
    workers: int = 4,
    retries: int = 2,
    progress: Callable[[str], None] | None = None,
) -> list[DownloadResult]:
    directory.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(workers, 8))
    retries = max(0, min(retries, 5))
    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_one, album, index, directory, retries): index
            for index, album in enumerate(albums, 1)
        }
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            if progress:
                marker = "✓" if result.status == "ok" else "✗"
                progress(f"[{completed}/{len(albums)}] {marker} {result.album.name}")
    order = {album.id + album.cover_url: index for index, album in enumerate(albums)}
    results.sort(key=lambda item: order[item.album.id + item.album.cover_url])
    return results
