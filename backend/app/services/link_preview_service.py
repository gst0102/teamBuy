from __future__ import annotations

import html
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


MAX_LINK_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_LINK_REDIRECTS = 4


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "").strip() for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
            return
        if tag.lower() != "meta":
            return
        key = (values.get("property") or values.get("name") or "").lower()
        content = values.get("content") or ""
        if key and content and key not in self.meta:
            self.meta[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title and data.strip():
            self.title_parts.append(data.strip())


def _clean(value: str | None, limit: int) -> str:
    text = " ".join(html.unescape(value or "").split())
    return text[:limit]


def _validate_public_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("只支持公开的 https:// 网页链接")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("链接域名无法访问") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("不支持内网或本机链接")
    return url


def _ensure_global_ip(value: str) -> None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("链接服务器地址异常") from exc
    if not ip.is_global:
        raise ValueError("不支持内网或本机链接")


def _peer_ip(response: httpx.Response) -> str:
    network_stream = response.extensions.get("network_stream")
    if not network_stream or not hasattr(network_stream, "get_extra_info"):
        return ""
    server_addr = network_stream.get_extra_info("server_addr")
    if isinstance(server_addr, (tuple, list)) and server_addr:
        return str(server_addr[0])
    return str(server_addr or "")


def fetch_link_preview(url: str) -> dict:
    current_url = _validate_public_https_url(url.strip())
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DataOrganizerBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    page_bytes = b""
    encoding = "utf-8"
    with httpx.Client(headers=headers, timeout=8.0, follow_redirects=False) as client:
        for redirect_count in range(MAX_LINK_REDIRECTS + 1):
            with client.stream("GET", current_url) as response:
                peer_ip = _peer_ip(response)
                if peer_ip:
                    _ensure_global_ip(peer_ip)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("链接跳转地址无效")
                    if redirect_count >= MAX_LINK_REDIRECTS:
                        raise ValueError("链接跳转次数过多")
                    current_url = _validate_public_https_url(urljoin(current_url, location))
                    continue
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise ValueError("该链接不是可解析的网页")
                chunks: list[bytes] = []
                total_size = 0
                for chunk in response.iter_bytes():
                    remaining = MAX_LINK_RESPONSE_BYTES - total_size
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    total_size += min(len(chunk), remaining)
                    if len(chunk) > remaining:
                        break
                page_bytes = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                break

    parser = _MetadataParser()
    parser.feed(page_bytes.decode(encoding, errors="replace"))
    meta = parser.meta
    parsed_url = urlparse(current_url)
    title = _clean(meta.get("og:title") or meta.get("twitter:title") or " ".join(parser.title_parts), 160)
    description = _clean(meta.get("og:description") or meta.get("description") or meta.get("twitter:description"), 500)
    cover_url = _clean(meta.get("og:image") or meta.get("twitter:image"), 1000)
    if cover_url:
        cover_url = urljoin(current_url, cover_url)
        if urlparse(cover_url).scheme.lower() != "https":
            cover_url = ""
    source_name = _clean(meta.get("og:site_name"), 80) or (parsed_url.hostname or "网页链接")
    return {
        "url": current_url,
        "title": title,
        "description": description,
        "coverUrl": cover_url,
        "sourceName": source_name,
        "sourceLabel": "公众号文章" if parsed_url.hostname == "mp.weixin.qq.com" else "网页链接",
        "parseStatus": "meta_done" if title or description or cover_url else "meta_empty",
    }
