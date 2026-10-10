---
title: 订阅源镜像
description: 按 sources.json 镜像进来的第三方开放许可内容
tags: [订阅源]
updated: 2026-10-10
---

# 订阅源镜像

本目录内容由 `tools/kb_sources.py` 按仓库根目录的 **`sources.json`** 清单自动拉取——**加一个源 = 清单里加一条**。

## 规矩

- 每个源一个子目录；子目录里的 `_SOURCE.md` 写明来源、许可与拉取到的提交。
- **只收有明确开放许可的来源**（MIT / Apache-2.0 等），版权归各原作者所有，仅作镜像转发。
- 只搬 Markdown：图片、notebook、源码一律不进来。
- **别直接改这里的文件**——下次同步会被整目录覆盖。要改就去上游仓库提 PR，或改 `sources.json`。

## 加一个源

在 `sources.json` 的 `sources` 里加一条：

```json
"源id": {
  "name": { "zh": "展示名", "en": "Display Name" },
  "kind": "repo",
  "host": "github",
  "repo": "owner/仓库名",
  "branch": "main",
  "path": "只镜像这个子路径（留空整仓）",
  "license": "MIT",
  "homepage": "https://github.com/owner/仓库名"
}
```

然后运行（会自动下载、只挑 .md、写 `_SOURCE.md`、commit）：

```bash
python3 tools/kb_sources.py --sources sources.json --out /tmp/kb-mirror
```

镜像落在 `/tmp/kb-mirror/<源id>/`，把它搬进本目录的对应位置提交即可。
