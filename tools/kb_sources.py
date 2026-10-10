#!/usr/bin/env python3
"""kb_sources.py — 按「知识库源清单」把各来源的 Markdown 拉到本地。

清单就是仓库根目录的 `sources.json`：一行一个源（仓库 + 分支 + 子路径 + 许可），
消费端（机器人 / App）按它自己去源站拉——不再需要把内容镜像进本仓库。

用法：
    python3 kb_sources.py --sources ./sources.json --out /home/fk/kb-ext
    python3 kb_sources.py --sources ./sources.json --out /home/fk/kb-ext --only oh-story
    python3 kb_sources.py --sources ./sources.json --out /home/fk/kb-ext --force

每个源落到 `<out>/<源 id>/`，目录里会写一份 `_SOURCE.md`（名称 / 许可 / 来源链接 / 拉取到的
commit）与 `.kb-source-sha`（用于增量：commit 没变就整体跳过）。源仓库里非 Markdown 的
文件一律不搬。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

CLONE_URL = "https://{host}/{repo}.git"


def load_sources(path_or_url):
    if path_or_url.startswith(("http://", "https://")):
        import urllib.request
        with urllib.request.urlopen(path_or_url, timeout=30) as resp:
            return json.loads(resp.read())
    with open(path_or_url, encoding="utf-8") as fh:
        return json.load(fh)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def sync_repo(source_id, spec, out_root, force):
    host = spec.get("host") or "github"
    host = host if "." in host else {"github": "github.com", "gitee": "gitee.com",
                                     "gitlab": "gitlab.com"}.get(host, host)
    repo = spec["repo"]
    branch = spec.get("branch") or "main"
    sub_path = (spec.get("path") or "").strip("/")
    target = os.path.join(out_root, source_id)

    with tempfile.TemporaryDirectory(prefix="kbsrc-") as tmp:
        clone = os.path.join(tmp, "repo")
        result = run(["git", "clone", "--depth", "1", "--branch", branch,
                      CLONE_URL.format(host=host, repo=repo), clone])
        if result.returncode != 0:
            return False, "clone 失败: %s" % (result.stderr or "").strip()[:200], 0

        sha = run(["git", "rev-parse", "HEAD"], cwd=clone).stdout.strip()
        shas = {}
        for root, dirs, files in os.walk(out_root):
            for name in files:
                if name == ".kb-source-sha":
                    with open(os.path.join(root, name), encoding="utf-8") as fh:
                        shas[os.path.basename(root)] = fh.read().strip()

        if not force and shas.get(source_id) == sha and os.path.isdir(target):
            return True, "未变化 (%s)" % sha[:7], 0

        src_root = os.path.join(clone, sub_path) if sub_path else clone
        if not os.path.isdir(src_root):
            return False, "路径不存在: %s" % sub_path, 0

        if os.path.isdir(target):
            shutil.rmtree(target)
        os.makedirs(target, exist_ok=True)

        copied = 0
        for root, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
            for name in files:
                if not name.lower().endswith(".md"):
                    continue
                src = os.path.join(root, name)
                rel = os.path.relpath(src, src_root)
                dst = os.path.join(target, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1

        license_name = spec.get("license") or "未标注"
        note = (
            "---\n"
            "title: %s\n"
            "description: 订阅源「%s」的镜像（%s）\n"
            "tags: [订阅源, %s]\n"
            "updated: %s\n"
            "---\n\n"
            "# %s\n\n"
            "本目录内容来自订阅源 **%s**，按 **%s** 许可分发，版权归原作者所有。\n\n"
            "- 来源：%s\n"
            "- 仓库：`%s`（分支 `%s`，路径 `%s`）\n"
            "- 拉取到的提交：`%s`\n\n"
            "由 `tools/kb_sources.py` 按 `sources.json` 自动拉取，**请勿在此目录直接修改**。\n"
        ) % (
            display_name(spec) or source_id, source_id, license_name, source_id, TODAY,
            display_name(spec) or source_id, source_id, license_name,
            spec.get("homepage") or "https://%s/%s" % (host, repo),
            repo, branch, sub_path or "/", sha,
        )
        with open(os.path.join(target, "_SOURCE.md"), "w", encoding="utf-8") as fh:
            fh.write(note)
        with open(os.path.join(target, ".kb-source-sha"), "w", encoding="utf-8") as fh:
            fh.write(sha)
        return True, "已同步 %d 篇（%s）" % (copied, sha[:7]), copied


def display_name(spec):
    name = spec.get("name") or {}
    return name.get("zh") or next(iter(name.values()), "") if isinstance(name, dict) else str(name)


TODAY = __import__("time").strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json", help="源清单路径或 URL")
    parser.add_argument("--out", required=True, help="落到哪个目录")
    parser.add_argument("--only", default="", help="只同步某个源 id")
    parser.add_argument("--force", action="store_true", help="忽略增量，强制重拉")
    args = parser.parse_args()

    data = load_sources(args.sources)
    sources = data.get("sources") or {}
    if args.only:
        sources = {k: v for k, v in sources.items() if k == args.only}
        if not sources:
            sys.exit("清单里没有源：%s" % args.only)
    if not sources:
        sys.exit("清单里没有任何源")

    os.makedirs(args.out, exist_ok=True)
    failed = 0
    for source_id, spec in sources.items():
        kind = (spec.get("kind") or "repo").lower()
        if kind != "repo":
            print("[跳过] %s：kind=%s 暂不支持" % (source_id, kind))
            continue
        ok, message, count = sync_repo(source_id, spec, args.out, args.force)
        print("[%s] %s：%s" % ("OK" if ok else "失败", source_id, message))
        if not ok:
            failed += 1
    print("完成：%d 个源，失败 %d 个 -> %s" % (len(sources), failed, args.out))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
