#!/usr/bin/env python3
"""ima_import.py — 把腾讯 ima 知识库的内容导出成 Markdown，供共享知识库归档。

用法：
    IMA_OPENAPI_CLIENTID=xx IMA_OPENAPI_APIKEY=yy python3 ima_import.py --out ./ima
    # 也可以读环境文件（每行 KEY=VALUE）：
    python3 ima_import.py --env-file /path/to/.env --out ./ima
    # 只导某个知识库（按名字匹配，或直接给 id）：
    python3 ima_import.py --env-file .env --kb "微信用户的知识库" --out ./ima

凭证只从环境变量 / 环境文件读，不发往 ima.qq.com 以外的任何地方，也不写进产物。
Markdown / 纯文本原样落成 .md；其余类型（PDF / Office / 图片等）默认只跟一篇一行说明的提示，
不搬原始文件——它们对知识库的检索没价值，还会把仓库拖重。确要留底加 `--with-attachments`，
原始文件会存到 `_attachments/`。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = "https://ima.qq.com"
WIKI = "/openapi/wiki/v1"

TEXT_TYPES = {7, 13}  # 7=Markdown, 13=TXT
ATTACH_DIR = "_attachments"
TYPE_NAMES = {
    1: "PDF", 2: "网页", 3: "Word", 4: "PPT", 5: "Excel", 6: "公众号文章",
    7: "Markdown", 9: "图片", 11: "笔记", 12: "AI 会话", 13: "TXT",
    14: "Xmind", 15: "录音", 16: "视频",
}


def load_credentials(args):
    env = {}
    if args.env_file:
        with open(args.env_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ("IMA_OPENAPI_CLIENTID", "IMA_OPENAPI_APIKEY"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    cid = env.get("IMA_OPENAPI_CLIENTID")
    akey = env.get("IMA_OPENAPI_APIKEY")
    if not cid or not akey:
        sys.exit("缺凭证：请设置 IMA_OPENAPI_CLIENTID / IMA_OPENAPI_APIKEY，或用 --env-file 指定环境文件")
    return cid, akey


def make_post(cid, akey):
    def post(path, body):
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "ima-openapi-clientid": cid,
                "ima-openapi-apikey": akey,
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
        if payload.get("code") != 0:
            raise RuntimeError("ima 接口返回失败 %s: %s" % (path, payload.get("msg")))
        return payload.get("data") or {}
    return post


def download(url, headers):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def list_knowledge_bases(post):
    out, cursor = [], ""
    while True:
        data = post(WIKI + "/get_addable_knowledge_base_list", {"cursor": cursor, "limit": 50})
        out.extend(data.get("addable_knowledge_base_list") or [])
        if data.get("is_end", True) or not data.get("next_cursor"):
            break
        cursor = data["next_cursor"]
    return out


def walk(post, kb_id, folder_id=None, path=""):
    """产出 (条目, 所在路径)，文件夹会被递归展开。"""
    cursor = ""
    while True:
        body = {"cursor": cursor, "limit": 50, "knowledge_base_id": kb_id}
        if folder_id:
            body["folder_id"] = folder_id
        data = post(WIKI + "/get_knowledge_list", body)
        for item in data.get("knowledge_list") or []:
            if item.get("folder_id"):
                name = item.get("name") or item["folder_id"]
                yield from walk(post, kb_id, item["folder_id"], "%s/%s" % (path, name) if path else name)
            else:
                yield item, path
        if data.get("is_end", True) or not data.get("next_cursor"):
            break
        cursor = data["next_cursor"]


def safe_name(text, fallback="untitled"):
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", (text or "").strip()).strip("._ ")
    name = re.sub(r"\s+", " ", name)
    return name[:80] or fallback


def title_of(content, filename):
    """优先文档里的第一个一级标题，其次去掉原文件名的哈希前缀。"""
    match = re.search(r"(?m)^#\s+(.+?)\s*$", content)
    if match:
        return match.group(1).strip()
    stem = re.sub(r"\.md$", "", filename, flags=re.I)
    stem = re.sub(r"^[0-9a-f]{16,}_\d+_[a-z]?_?", "", stem)
    return stem or filename


def frontmatter(title, media_type, source_kb):
    return (
        "---\n"
        "title: %s\n"
        "description: 从 ima 知识库《%s》导出\n"
        "tags: [ima]\n"
        "source: ima\n"
        "media_type: %s\n"
        "---\n\n" % (json.dumps(title, ensure_ascii=False), source_kb, media_type)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./ima", help="输出目录")
    parser.add_argument("--kb", default="", help="知识库名字或 id；留空导出全部")
    parser.add_argument("--env-file", default="", help="环境文件（每行 KEY=VALUE）")
    parser.add_argument("--dry-run", action="store_true", help="只列出将要导出的条目")
    parser.add_argument("--with-attachments", action="store_true",
                        help="连 PDF / Office / 图片这类原始文件一起搬到 _attachments/")
    args = parser.parse_args()

    cid, akey = load_credentials(args)
    post = make_post(cid, akey)

    kbs = list_knowledge_bases(post)
    if args.kb:
        kbs = [kb for kb in kbs if kb.get("id") == args.kb or kb.get("name") == args.kb]
        if not kbs:
            sys.exit("没找到知识库：%s" % args.kb)
    if not kbs:
        sys.exit("账号下没有可读的知识库")

    os.makedirs(args.out, exist_ok=True)
    written = skipped = 0

    for kb in kbs:
        kb_id, kb_name = kb.get("id"), kb.get("name") or kb.get("id")
        print("== 知识库：%s" % kb_name)
        for item, folder in walk(post, kb_id):
            media_id = item.get("media_id")
            title = item.get("title") or media_id
            media_type = item.get("media_type")
            label = TYPE_NAMES.get(media_type, str(media_type))
            if args.dry_run:
                print("   [%s] %s%s" % (label, folder + "/" if folder else "", title))
                continue

            info = post(WIKI + "/get_media_info", {"media_id": media_id})
            url_info = info.get("url_info") or {}
            url = url_info.get("url")
            if not url:
                print("   跳过（拿不到原文地址）：%s" % title)
                skipped += 1
                continue

            raw = download(url, url_info.get("headers"))
            if media_type in TEXT_TYPES or url.endswith((".md", ".markdown", ".txt")):
                content = raw.decode("utf-8", errors="replace")
                name = safe_name(title_of(content, title))
                # 同一次导出里重名就加媒体 id 尾号，别覆盖
                target = os.path.join(args.out, "%s.md" % name)
                if os.path.exists(target):
                    target = os.path.join(args.out, "%s-%s.md" % (name, media_id[-6:]))
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(frontmatter(title_of(content, title), media_type, kb_name))
                    fh.write(content)
                print("   导出 %s" % os.path.basename(target))
            else:
                name = safe_name(title)
                target = os.path.join(args.out, "%s.md" % name)
                if args.with_attachments:
                    attach_dir = os.path.join(args.out, ATTACH_DIR)
                    os.makedirs(attach_dir, exist_ok=True)
                    with open(os.path.join(attach_dir, name), "wb") as fh:
                        fh.write(raw)
                    note = "> 原文类型：%s。原始文件见 `%s/%s`。\n\n" % (label, ATTACH_DIR, name)
                    saved = "，原文 %.1f KB 已留在 %s/" % (len(raw) / 1024, ATTACH_DIR)
                else:
                    note = "> 原文类型：%s，原始文件未搬。需要时用 `--with-attachments` 重跑。\n\n" % label
                    saved = "，原文 %.1f KB 未搬" % (len(raw) / 1024)
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(frontmatter(title, media_type, kb_name))
                    fh.write(note)
                    fh.write("# %s\n" % title)
                print("   存根 %s（%s%s）" % (os.path.basename(target), label, saved))
            written += 1

    print("完成：写出 %d 篇，跳过 %d 篇" % (written, skipped))


if __name__ == "__main__":
    main()
