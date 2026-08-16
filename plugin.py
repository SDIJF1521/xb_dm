from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from xb_svcb_plugin import Plugin

API_URL = "https://api.yaohud.cn/api/v5/yingshi"
TIMEOUT_SECONDS = 18

plugin = Plugin("com.xbsvcb.xb_dm")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any, *, field: str, required: bool = False) -> int | None:
    raw = _text(value)
    if not raw:
        if required:
            raise ValueError(f"{field} 不能为空")
        return None
    try:
        number = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc
    if number <= 0:
        raise ValueError(f"{field} 必须大于 0")
    return number


def _request_api(params: dict[str, Any]) -> dict[str, Any]:
    query = {key: value for key, value in params.items() if value not in (None, "")}
    if not _text(query.get("key")):
        raise ValueError("请填写 API key")
    if not _text(query.get("msg")):
        raise ValueError("请填写动漫搜索关键词")

    url = API_URL + "?" + urlencode(query)
    request = Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "XB-SVCB xb_dm Plugin/1.0",
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", "replace")
    except HTTPError as exc:
        raise RuntimeError(f"影视 API 请求失败：HTTP {exc.code}") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"影视 API 网络错误：{reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("影视 API 返回的不是有效 JSON") from exc

    code = payload.get("code")
    if str(code) != "200":
        raise RuntimeError(_text(payload.get("msg")) or f"影视 API 返回异常：{code}")
    return payload


def _source(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    return {
        "id": source.get("id"),
        "name": _text(source.get("name")) or "未知资源站",
    }


def _item(raw: Any) -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {}
    return {
        "n": item.get("n"),
        "id": item.get("id"),
        "name": _text(item.get("name")) or "未命名动漫",
        "subtitle": _text(item.get("subtitle")),
        "remarks": _text(item.get("remarks")),
        "pic": _text(item.get("pic")),
        "year": _text(item.get("year")),
        "area": _text(item.get("area")),
        "language": _text(item.get("language")),
        "actor": _text(item.get("actor") or item.get("actors")),
        "director": _text(item.get("director")),
        "score": _text(item.get("score") or item.get("douban_score")),
        "type": _text(item.get("type")),
        "state": _text(item.get("state")),
        "class": _text(item.get("class")),
        "duration": _text(item.get("duration")),
        "update_time": _text(item.get("update_time")),
        "content": _text(item.get("content") or item.get("intro") or item.get("blurb")),
        "total_episodes": item.get("total_episodes") or 0,
    }


def _episode(raw: Any) -> dict[str, str]:
    item = raw if isinstance(raw, dict) else {}
    return {
        "title": _text(item.get("title")) or "未命名剧集",
        "url": _text(item.get("url")),
        "m3u8url": _text(item.get("m3u8url")),
    }


@plugin.action("search_anime")
def search_anime(ctx, values: dict[str, Any]):
    source = _positive_int(values.get("source"), field="source")
    payload = _request_api({
        "key": _text(values.get("key")),
        "msg": _text(values.get("msg")),
        "source": source,
    })
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw_items = data.get("list") if isinstance(data.get("list"), list) else []
    return {
        "mode": "search",
        "source": _source(data),
        "total": data.get("total") or len(raw_items),
        "page": data.get("page") or 1,
        "pagecount": data.get("pagecount") or 1,
        "items": [_item(item) for item in raw_items],
        "exec_time": payload.get("exec_time"),
        "tips": _text(payload.get("tips")),
    }


@plugin.action("load_detail")
def load_detail(ctx, values: dict[str, Any]):
    source = _positive_int(values.get("source"), field="source")
    n = _positive_int(values.get("n"), field="n", required=True)
    payload = _request_api({
        "key": _text(values.get("key")),
        "msg": _text(values.get("msg")),
        "source": source,
        "n": n,
    })
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw_episodes = data.get("episodes") if isinstance(data.get("episodes"), list) else []
    return {
        "mode": "detail",
        "source": _source(data),
        "detail": _item(data),
        "parser": _text(data.get("parser")),
        "episodes": [_episode(item) for item in raw_episodes],
        "exec_time": payload.get("exec_time"),
        "tips": _text(payload.get("tips")),
    }

@plugin.action("health_check")
def health_check(ctx, values: dict[str, Any]):
    return {
        "mode": "health",
        "plugin_id": ctx.plugin_id,
        "actions": ["search_anime", "load_detail", "health_check"],
    }