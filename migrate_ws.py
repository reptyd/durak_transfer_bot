import re
import json
import time
import sys
from urllib.parse import urlparse, parse_qs

import requests
from websocket import create_connection

# Optional: browser cookies auto-extraction
try:
    import browser_cookie3  # type: ignore
    HAS_BCJ = True
except Exception:
    HAS_BCJ = False

SERVERS = [
    "https://storage.yandexcloud.net/rst-durak/servers.json",
    "http://static.rstgames.com/durak/servers.json",
    "http://durakgame.s3.amazonaws.com/public/servers.json",
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

SANITIZE = True
COOKIE_HEADER = ""
PREF_BROWSER = ""  # chrome|edge|firefox|brave|chromium|opera


def sanitize_text(text: str) -> str:
    """Mask potentially sensitive tokens (JWT-like) in output."""
    if not SANITIZE:
        return text
    try:
        text = re.sub(r"eyJ[\w\-]{20,}\.[\w\-]+\.[\w\-]+", "[JWT]", text)
        text = re.sub(r"[A-Za-z0-9_\-]{80,}", "[BLOB]", text)
    except Exception:
        pass
    return text


def print_sanitized(prefix: str, payload):
    if isinstance(payload, str):
        print(prefix, sanitize_text(payload))
    else:
        try:
            s = json.dumps(payload, ensure_ascii=False)
        except Exception:
            s = str(payload)
        print(prefix, sanitize_text(s))


def extract_token(url: str) -> str:
    u = url.replace("#", "?", 1) if "#" in url else url
    parsed = urlparse(u)
    q = parse_qs(parsed.query)
    tok = q.get("id_token", [None])[0]
    if tok:
        return tok
    for part in parsed.path.split("/"):
        if part and len(part) > 100:
            return part
    raise RuntimeError("id_token не найден в ссылке")


def fetch_ws_endpoints() -> list[str]:
    for s in SERVERS:
        try:
            r = requests.get(s, timeout=10)
            r.raise_for_status()
            js = r.json()
            urls = []
            for _, v in js.get("user", {}).items():
                web_url = v.get("web_url")
                if isinstance(web_url, str) and web_url.startswith("wss://"):
                    urls.append(web_url)
            if urls:
                return sorted(set(urls))
        except Exception:
            continue
    raise RuntimeError("Не удалось получить список WS серверов")


def recv_all(ws, wait: float = 0.2, total: float = 3.0) -> list:
    out = []
    t0 = time.time()
    while time.time() - t0 < total:
        try:
            msg = ws.recv()
            out.append(msg)
        except Exception:
            time.sleep(wait)
    return out


def cj_to_cookie_header(cj) -> str:
    pairs = []
    seen = set()
    for c in cj:
        if (c.domain.endswith("rstgames.com") or c.domain.endswith(".rstgames.com")) and c.name not in seen:
            seen.add(c.name)
            pairs.append(f"{c.name}={c.value}")
    return "; ".join(pairs)


def auto_cookie_from_browsers(preferred: str = "") -> str:
    if not HAS_BCJ:
        return ""
    order = []
    pref = preferred.lower().strip()
    if pref:
        order = [pref]
    else:
        order = ["chrome", "edge", "brave", "chromium", "opera", "firefox"]

    for name in order:
        try:
            if name == "chrome":
                cj = browser_cookie3.chrome(domain_name="rstgames.com")
            elif name == "edge":
                cj = browser_cookie3.edge(domain_name="rstgames.com")
            elif name == "brave":
                cj = browser_cookie3.brave(domain_name="rstgames.com")
            elif name == "chromium":
                cj = browser_cookie3.chromium(domain_name="rstgames.com")
            elif name == "opera":
                cj = browser_cookie3.opera(domain_name="rstgames.com")
            elif name == "firefox":
                cj = browser_cookie3.firefox(domain_name="rstgames.com")
            else:
                continue
            ck = cj_to_cookie_header(cj)
            if ck:
                print(f"Auto-cookie: picked {name}, {len(ck)} bytes")
                return ck
        except Exception:
            continue
    return ""


def try_migrate(ws_url: str, source_token: str, target_token: str) -> bool:
    headers = {
        "Origin": "https://durak.rstgames.com",
        "User-Agent": USER_AGENT,
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.6,en;q=0.5",
    }
    if COOKIE_HEADER:
        headers["Cookie"] = COOKIE_HEADER
    ws = create_connection(ws_url, header=[f"{k}: {v}" for k, v in headers.items()], timeout=10)
    try:
        auth_msg = {"cmd": "web_auth", "id_token": source_token, "platform": "web"}
        ws.send(json.dumps(auth_msg))
        auth_resp = recv_all(ws)
        print_sanitized("AUTH RESP:", auth_resp)

        candidates = [
            {"cmd": "migrate_tokens", "source_id_token": source_token, "target_id_token": target_token},
            {
                "cmd": "migrate",
                "source": {"type": "oauth_token", "token": source_token, "platform": "web"},
                "target": {"type": "oauth_token", "token": target_token, "platform": "web"},
            },
            {"cmd": "set_tokens", "source": source_token, "target": target_token},
        ]
        for payload in candidates:
            ws.send(json.dumps(payload))
            resp = recv_all(ws)
            print_sanitized(f"TRY {payload['cmd']} RESP:", resp)
            if any(isinstance(x, str) and re.search(r"(success|ok|done|migrat)", x, re.I) for x in resp):
                return True
        return False
    finally:
        ws.close()


def main():
    global SANITIZE, COOKIE_HEADER, PREF_BROWSER
    if len(sys.argv) < 3:
        print("Usage: python migrate_ws.py [--raw] [--cookie <cookie>|--cookie=<cookie>] [--auto-cookie[=<browser>]] <source_url> <target_url>")
        sys.exit(1)

    args = sys.argv[1:]
    i = 0
    parsed = []
    want_auto_cookie = False
    while i < len(args):
        a = args[i]
        if a == "--raw":
            SANITIZE = False
            i += 1
            continue
        if a.startswith("--cookie="):
            COOKIE_HEADER = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--cookie" and i + 1 < len(args):
            COOKIE_HEADER = args[i + 1]
            i += 2
            continue
        if a == "--auto-cookie":
            want_auto_cookie = True
            i += 1
            continue
        if a.startswith("--auto-cookie="):
            want_auto_cookie = True
            PREF_BROWSER = a.split("=", 1)[1]
            i += 1
            continue
        parsed.append(a)
        i += 1

    if len(parsed) < 2:
        print("Usage: python migrate_ws.py [--raw] [--cookie <cookie>|--cookie=<cookie>] [--auto-cookie[=<browser>]] <source_url> <target_url>")
        sys.exit(1)

    if want_auto_cookie and not COOKIE_HEADER:
        ck = auto_cookie_from_browsers(PREF_BROWSER)
        if ck:
            COOKIE_HEADER = ck
        else:
            print("Auto-cookie: not found or browser not supported; continue without Cookie")

    source_url = parsed[0]
    target_url = parsed[1]
    try:
        source_token = extract_token(source_url)
        target_token = extract_token(target_url)
    except Exception as e:
        print(f"Token extraction error: {e}")
        sys.exit(2)

    try:
        ws_list = fetch_ws_endpoints()
    except Exception as e:
        print(f"WS endpoints error: {e}")
        sys.exit(3)

    print("WS endpoints:", ws_list)
    if COOKIE_HEADER:
        print("Using Cookie header (len):", len(COOKIE_HEADER))
    for ws_url in ws_list:
        print("Connecting:", ws_url)
        try:
            ok = try_migrate(ws_url, source_token, target_token)
            if ok:
                print("OK: перенос инициирован")
                sys.exit(0)
        except Exception as e:
            print_sanitized("Fail:", f"\n{ws_url}\n{e}")
    print("Не удалось выполнить перенос. Скопируйте ответы выше и пришлите их.")
    sys.exit(4)


if __name__ == "__main__":
    main()