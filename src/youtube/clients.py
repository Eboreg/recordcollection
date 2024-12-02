import re
from abc import ABC, abstractmethod
from typing import Any, Iterator

import requests

from recordcollection.utils import merge_dicts, string_to_timedelta
from youtube.dataclasses import YoutubeMetadata, YoutubeVideo


BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"
PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
RESULTS_URL = "https://www.youtube.com/results"
SEARCH_URL = "https://www.youtube.com/youtubei/v1/search"
VIDEO_MIMETYPE_FILTER = r"^audio/.*$"
VIDEO_MIMETYPE_PREFERRED = ["audio/opus"]


class AbstractYoutubeClient(ABC):
    client_name: str
    client_version: str
    key: str
    region: str

    def __init__(self, region: str = "SE"):
        super().__init__()
        self.region = region

    @abstractmethod
    def get_video_renderers(self, response: dict[str, Any]) -> Iterator[dict]:
        ...

    def get_json(self, video_id: str | None = None) -> dict[str, Any]:
        d = {
            "contentCheckOk": True,
            "context": {
                "client": {
                    "clientName": self.client_name,
                    "clientVersion": self.client_version,
                    "gl": self.region,
                    "hl": "en_US",
                },
                "request": {
                    "internalExperimentFlags": [],
                    "useSsl": False,
                },
            },
            "playbackContext": {
                "contentPlaybackContext": {
                    "html5Preference": "HTML5_PREF_WANTS",
                },
            },
            "racyCheckOk": True,
            "thirdParty": {},
            "user": {
                "lockedSafetyMode": False,
            },
        }
        if video_id:
            d["videoId"] = video_id
        return d

    def get_headers(self, video_id: str | None = None) -> dict[str, str]:
        d = {
            "Accept": "*/*",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.5",
            "Origin": "https://www.youtube.com",
        }
        if video_id:
            d["Referer"] = f"https://www.youtube.com/watch?v={video_id}"
        return d

    def get_params(self, *args, **kwargs) -> dict[str, str]:
        return {
            "prettyPrint": "false",
            "key": self.key,
        }

    def post_json(
        self,
        url: str,
        video_id: str | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        headers = headers or {}
        json = json or {}

        return requests.post(
            url=url,
            headers={**self.get_headers(video_id), **headers},
            json=merge_dicts(self.get_json(video_id), json),
            params={**self.get_params(video_id), **params},
            timeout=10,
        ).json()

    def get_string(
        self,
        url: str,
        video_id: str | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        params = params or {}
        headers = headers or {}

        return requests.get(
            url=url,
            params={**self.get_params(video_id), **params},
            headers={**self.get_headers(video_id), **headers},
            timeout=10,
        ).text

    def get_best_metadata(self, video_id: str) -> YoutubeMetadata | None:
        metadata_list = self.get_metadata(video_id)
        for mime_type in VIDEO_MIMETYPE_PREFERRED:
            metadatas = [m for m in metadata_list if m.mime_type == mime_type]
            if metadatas:
                return max(metadatas, key=lambda m: m.quality)
        metadatas = [m for m in metadata_list if re.match(VIDEO_MIMETYPE_FILTER, m.mime_type)]
        return max(metadatas, key=lambda m: m.quality)

    def get_metadata(self, video_id: str) -> list[YoutubeMetadata]:
        response = self.post_json(url=PLAYER_URL, video_id=video_id)
        formats: list[dict] = response.get("streamingData", {}).get("formats", []) or []
        adaptive_formats: list[dict] = response.get("streamingData", {}).get("adaptiveFormats", []) or []
        metadata_list: list[YoutubeMetadata] = []

        for fmt in formats + adaptive_formats:
            mime_type = fmt.get("mimeType", None)
            bitrate = fmt.get("bitrate", None)
            sample_rate = fmt.get("audioSampleRate", None)
            url = fmt.get("url", None)
            duration_ms = fmt.get("approxDurationMs", None)

            if mime_type and bitrate and sample_rate and url and duration_ms:
                metadata_list.append(
                    YoutubeMetadata(
                        raw_mime_type=mime_type,
                        bitrate=int(bitrate),
                        sample_rate=int(sample_rate),
                        url=url,
                        duration_ms=int(duration_ms),
                    )
                )

        return metadata_list

    def get_playlist_video_renderers(self, response: dict[str, Any]) -> Iterator[dict]:
        for tab in (
            response.get("contents", {})
            .get("singleColumnBrowseResultsRenderer", {})
            .get("tabs", [])
        ) or []:
            for content in (
                tab.get("tabRenderer", {})
                .get("content", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            ) or []:
                for content2 in (
                    content.get("playlistVideoListRenderer", {})
                    .get("contents", [])
                ) or []:
                    yield content2.get("playlistVideoRenderer", {})

    def extract_yt_initial_data(self, body: str) -> str | None:
        matches = re.findall(r"var ytInitialData *= *(\{.*?\});", body, flags=re.MULTILINE)
        if matches:
            return matches[-1]
        matches = re.findall(r"var ytInitialData *= *'(\\x7b.*?\\x7d)'", body, flags=re.MULTILINE)
        if matches:
            return re.sub(r"\\x(..)", lambda m: chr(int(m.group(0), base=16)), matches[-1])
        return None

    def get_video_search_results(self, query: str) -> list[YoutubeVideo]:
        json = {"query": query}
        response = self.post_json(url=SEARCH_URL, json=json)
        videos: list[YoutubeVideo] = []

        for video_renderer in self.get_video_renderers(response):
            video_id = self.yquery_string(video_renderer, "videoId")
            title = self.yquery_string(video_renderer, "title")
            length_text = self.yquery_string(video_renderer, "lengthText")
            duration = string_to_timedelta(length_text) if length_text else None

            if video_id and title and duration:
                videos.append(
                    YoutubeVideo(
                        id=video_id,
                        title=title,
                        duration_ms=int(duration.total_seconds() * 1000),
                    )
                )

        return videos

    def yquery_string(self, d: dict, key: str) -> str | None:
        value = d.get(key, None)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            runs = value.get("runs", [])
            if runs:
                return runs[0].get("text", None)
            return value.get("simpleText", None)
        return None


class AbstractYoutubeAndroidClient(AbstractYoutubeClient, ABC):
    id: str
    os_version: str
    os_name: str = "Android"
    user_agent: str = "com.google.android.youtube"

    def get_headers(self, video_id: str | None = None) -> dict[str, str]:
        return {
            **super().get_headers(video_id),
            "User-Agent": (
                f"{self.user_agent}/{self.client_version} (Linux; U; {self.os_name} "
                f"{self.os_version}; {self.region}) gzip"
            ),
            "X-YouTube-Client-Name": self.id,
            "X-YouTube-Client-Version": self.client_version,
        }

    def get_video_renderers(self, response: dict[str, Any]) -> Iterator[dict]:
        for content in (
            response.get("contents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        ) or []:
            for content2 in content.get("itemSectionRenderer", {}).get("contents", []) or []:
                yield content2.get("compactVideoRenderer", {})

    def get_json(self, video_id: str | None = None) -> dict[str, Any]:
        return merge_dicts(
            super().get_json(video_id),
            {
                "context": {
                    "client": {
                        "androidSdkVersion": "34",
                        "osName": self.os_name,
                        "osVersion": self.os_version,
                        "platform": "MOBILE",
                    },
                },
                "params": "2AMBCgIQBg",
            },
        )


class YoutubeAndroidTestSuiteClient(AbstractYoutubeAndroidClient):
    client_name = "ANDROID_TESTSUITE"
    client_version = "1.9"
    id = "30"
    key = "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w"
    os_version = "14"


class YoutubeWebClient(AbstractYoutubeClient):
    client_name = "WEB"
    client_version = "2.20240304.00.00"
    key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

    def get_headers(self, video_id: str | None = None) -> dict[str, str]:
        d = {
            **super().get_headers(video_id),
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Host": "www.youtube.com",
        }
        if video_id:
            d["Referer"] = f"https://www.youtube.com/watch?v={video_id}"
        return d

    def get_video_renderers(self, response: dict[str, Any]) -> Iterator[dict]:
        for content in (
            response.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        ) or []:
            for content2 in content.get("itemSectionRenderer", {}).get("contents", []) or []:
                yield content2.get("videoRenderer", {})
