#!/usr/bin/env python3
"""feishu_auth.py — 走一次飞书 OAuth，拿 user_access_token（以你本人身份调接口）。

为什么需要它：应用身份（tenant_access_token）只能看到「应用被加为成员」的知识库；
个人知识库加不了成员，所以改用你的身份——你能看到的库，user token 就能看到。

用法：
    python3 feishu_auth.py --env-file ./feishu.env --port 8848
    # 然后把打印出来的授权链接在**手机浏览器**里打开（容器与手机共用 loopback）

前置：在开发者后台 → 该应用 → 安全设置 → 重定向 URL，添加
      http://localhost:8848/callback
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = "https://open.feishu.cn"
STATE = "aharou-kb"
SCOPES = "wiki:wiki:readonly docx:document:readonly"

_result = {}


def load_env(path):
    env = {}
    if path:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    if not env.get("FEISHU_APP_ID") or not env.get("FEISHU_APP_SECRET"):
        sys.exit("缺凭证：FEISHU_APP_ID / FEISHU_APP_SECRET")
    return env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]


def make_handler(redirect_uri):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            print("收到回调: %s 参数=%s" % (parsed.path, json.dumps(query, ensure_ascii=False)), flush=True)

            ok = False
            if parsed.path.startswith("/callback") and query.get("code"):
                _result["code"] = query["code"]
                _result["state"] = query.get("state", "")
                ok = True
                tip = "授权成功，可以关掉这个页面了。"
            elif query.get("error"):
                _result["error"] = query.get("error")
                _result["error_description"] = query.get("error_description", "")
                tip = "授权被拒绝或出错：%s" % query.get("error")
            else:
                tip = "没拿到授权码，请确认是从授权链接跳转过来的。"

            html = ("<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
                    "<h2>%s</h2></body></html>" % tip).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *args):
            pass

    return Handler


def exchange_code(app_id, app_secret, code, redirect_uri):
    payload = json.dumps({
        "grant_type": "authorization_code",
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(
        BASE + "/open-apis/authen/v2/oauth/token",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"http_error": exc.code, "body": exc.read().decode("utf-8", "replace")[:500]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="")
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--out", default="/root/kb-scripts/feishu_user_token.json")
    parser.add_argument("--timeout", type=int, default=900, help="等回调的最长秒数")
    args = parser.parse_args()

    app_id, app_secret = load_env(args.env_file)
    redirect_uri = "http://localhost:%d/callback" % args.port

    server = HTTPServer(("0.0.0.0", args.port), make_handler(redirect_uri))
    server.timeout = 5

    auth_url = (BASE + "/open-apis/authen/v1/authorize?" + urllib.parse.urlencode({
        "app_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": STATE,
    }))
    print("回调地址: %s" % redirect_uri, flush=True)
    print("授权链接: %s" % auth_url, flush=True)

    deadline = time.time() + args.timeout
    while time.time() < deadline and "code" not in _result and "error" not in _result:
        server.handle_request()

    if "code" not in _result:
        sys.exit("没等到授权码：%s" % (_result.get("error") or "超时"))

    data = exchange_code(app_id, app_secret, _result["code"], redirect_uri)
    token = data.get("access_token") or (data.get("data") or {}).get("access_token")
    if not token:
        sys.exit("换 token 失败: %s" % json.dumps(data, ensure_ascii=False)[:400])

    record = {
        "access_token": token,
        "refresh_token": data.get("refresh_token") or (data.get("data") or {}).get("refresh_token"),
        "expires_in": data.get("expires_in") or (data.get("data") or {}).get("expires_in"),
        "obtained_at": int(time.time()),
        "scope": data.get("scope") or (data.get("data") or {}).get("scope"),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)
    os.chmod(args.out, 0o600)
    print("拿到 user_access_token（%s...），已存到 %s" % (token[:8], args.out), flush=True)


if __name__ == "__main__":
    main()
