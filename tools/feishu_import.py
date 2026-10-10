#!/usr/bin/env python3
"""feishu_import.py — 把飞书知识库导出成 Markdown，供共享知识库归档。

用法：
    FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=yyy python3 feishu_import.py --out ./feishu
    # 也可以读环境文件（每行 KEY=VALUE）：
    python3 feishu_import.py --env-file /path/to/.env --out ./feishu
    # 只导某个知识空间 / 先看看有哪些：
    python3 feishu_import.py --env-file .env --list
    python3 feishu_import.py --env-file .env --space "产品文档" --out ./feishu

前置条件（缺一不可，都得在飞书侧操作）：
  1. 在开放平台建一个「企业自建应用」，拿到 App ID / App Secret；
  2. 给应用开权限：`wiki:wiki:readonly`（读知识库）与 `docx:document:readonly`（读新版文档正文）；
  3. **把应用加为目标知识库的成员或管理员**——不加的话接口会返回 permission denied。
     （知识库 → 设置 → 成员管理 → 添加成员，搜应用名）

凭证只从环境变量 / 环境文件读，只发往 open.feishu.cn，不写进产物。
能导出正文的是 docx / doc（旧版文档）；表格、多维表格、文件、思维导图这类
只落一份说明存根——它们的正文要走各自的产品接口或导出流程。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://open.feishu.cn"
TEXT_OBJ_TYPES = {"docx", "doc"}
OBJ_TYPE_NAMES = {
    "docx": "新版文档", "doc": "旧版文档", "sheet": "电子表格",
    "bitable": "多维表格", "mindnote": "思维导图", "file": "文件",
    "slides": "幻灯片", "folder": "文件夹",
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
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    app_id = env.get("FEISHU_APP_ID")
    app_secret = env.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        sys.exit("缺凭证：请设置 FEISHU_APP_ID / FEISHU_APP_SECRET，或用 --env-file 指定环境文件")
    return app_id, app_secret


class Feishu:
    def __init__(self, app_id, app_secret):
        self.token = self._token(app_id, app_secret)

    def _token(self, app_id, app_secret):
        body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
        req = urllib.request.Request(
            BASE + "/open-apis/auth/v3/tenant_access_token/internal",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 0:
            sys.exit("取 tenant_access_token 失败: %s" % data.get("msg"))
        return data["tenant_access_token"]

    def get(self, path, params=None):
        url = BASE + path
        if params:
            clean = {k: v for k, v in params.items() if v not in (None, "")}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json; charset=utf-8"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = json.loads(resp.read())
                if payload.get("code") != 0:
                    raise RuntimeError("%s -> code=%s msg=%s" % (
                        path, payload.get("code"), payload.get("msg")))
                return payload.get("data") or {}
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("重试耗尽: " + path)

    def spaces(self):
        out, page_token = [], ""
        while True:
            data = self.get("/open-apis/wiki/v2/spaces",
                            {"page_size": 50, "page_token": page_token})
            out.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")
        return out

    def nodes(self, space_id, parent=None, path=""):
        page_token = ""
        while True:
            data = self.get("/open-apis/wiki/v2/spaces/%s/nodes" % space_id,
                            {"page_size": 50, "parent_node_token": parent, "page_token": page_token})
            for item in data.get("items") or []:
                yield item, path
                if item.get("has_child"):
                    child_path = "%s/%s" % (path, safe_name(item.get("title") or "未命名")) if path \
                        else safe_name(item.get("title") or "未命名")
                    yield from self.nodes(space_id, item.get("node_token"), child_path)
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")

    def raw_content(self, obj_type, obj_token):
        if obj_type == "docx":
            data = self.get("/open-apis/docx/v1/documents/%s/raw_content" % obj_token)
            return data.get("content") or ""
        if obj_type == "doc":
            data = self.get("/open-apis/doc/v2/%s/raw_content" % obj_token)
            return data.get("content") or ""
        return None


def safe_name(text):
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", (text or "").strip()).strip("._ ")
    name = re.sub(r"\s+", " ", name)
    return name[:80] or "untitled"


def frontmatter(title, space_name, obj_type, node_token):
    return (
        "---\n"
        "title: %s\n"
        "description: 从飞书知识库《%s》导出\n"
        "tags: [feishu]\n"
        "source: feishu\n"
        "obj_type: %s\n"
        "node_token: %s\n"
        "---\n\n" % (json.dumps(title, ensure_ascii=False), space_name, obj_type, node_token)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./feishu", help="输出目录")
    parser.add_argument("--space", default="", help="知识空间名字或 space_id；留空导出全部")
    parser.add_argument("--env-file", default="", help="环境文件（每行 KEY=VALUE）")
    parser.add_argument("--list", action="store_true", help="只列出可见的知识空间")
    args = parser.parse_args()

    app_id, app_secret = load_credentials(args)
    api = Feishu(app_id, app_secret)

    spaces = api.spaces()
    if args.list:
        for space in spaces:
            print("%-22s %s" % (space.get("space_id"), space.get("name")))
        return
    if args.space:
        spaces = [s for s in spaces
                  if s.get("space_id") == args.space or s.get("name") == args.space]
        if not spaces:
            sys.exit("没找到知识空间：%s（用 --list 看有哪些）" % args.space)
    if not spaces:
        sys.exit("应用看不到任何知识空间——多半是没把应用加为知识库成员")

    written = stubbed = failed = 0
    for space in spaces:
        space_id = space.get("space_id")
        space_name = space.get("name") or space_id
        print("== 知识空间：%s" % space_name)
        for node, path in api.nodes(space_id):
            title = node.get("title") or node.get("node_token")
            obj_type = node.get("obj_type")
            obj_token = node.get("obj_token")
            label = OBJ_TYPE_NAMES.get(obj_type, obj_type or "?")
            target_dir = os.path.join(args.out, safe_name(space_name), path)
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, "%s.md" % safe_name(title))

            content = None
            if obj_type in TEXT_OBJ_TYPES:
                try:
                    content = api.raw_content(obj_type, obj_token)
                    time.sleep(0.3)
                except Exception as exc:
                    print("   取正文失败：%s（%s）" % (title, exc))
                    failed += 1
                    continue

            with open(target, "w", encoding="utf-8") as fh:
                fh.write(frontmatter(title, space_name, obj_type, node.get("node_token")))
                if content is not None:
                    fh.write(content if content.strip() else "# %s\n\n（文档为空）\n" % title)
                    print("   导出 %s/%s" % (path, os.path.basename(target)) if path
                          else "   导出 %s" % os.path.basename(target))
                    written += 1
                else:
                    fh.write("> 原文类型：%s。正文需走对应的产品接口或导出流程，这里只留索引。\n\n" % label)
                    fh.write("# %s\n" % title)
                    print("   存根 %s（%s）" % (os.path.basename(target), label))
                    stubbed += 1

    print("完成：导出正文 %d 篇，存根 %d 篇，失败 %d 篇" % (written, stubbed, failed))


if __name__ == "__main__":
    main()
