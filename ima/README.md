---
title: ima 知识库导出
description: 从腾讯 ima 知识库导出的内容，按原结构归档
tags: [ima, 导入]
updated: 2026-10-10
---

# ima 知识库导出

本目录存放从腾讯 ima 知识库导出的内容，由 `tools/ima_import.py` 生成。

## 怎么重新导出

```bash
python3 tools/ima_import.py --env-file /path/to/.env --out ./ima
```

- 凭证走 `IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`（环境变量或 `--env-file`），不落盘、不进仓库。
- `--kb "知识库名"` 只导一个库，留空导全部可读的库。
- `--dry-run` 只列条目不下载。

## 导出规则

- Markdown / 纯文本原样落成 `.md`，标题取正文里第一个一级标题，没有才退回原文件名。
- PDF / Office / 图片等类型：默认只跟一篇一行说明的存根，不搬原始文件（对检索没价值，还会把仓库拖重）。
  确要留底用 `--with-attachments`，原始文件会落到 `_attachments/`。
- 每篇都带 frontmatter（`title` / `description` / `tags` / `source` / `media_type`）。

## 注意

导出内容可能带个人笔记性质，进公开仓库前先扫一遍有没有不该外发的东西。
