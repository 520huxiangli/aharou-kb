---
title: 飞书知识库导出
description: 从飞书知识库导出文档到本仓库，由 tools/feishu_import.py 生成
tags: [feishu, 导入]
updated: 2026-10-10
---

# 飞书知识库导出

本目录存放从飞书知识库导出的内容，由 `tools/feishu_import.py` 生成。

## 一次性准备（都在飞书侧做）

1. **建应用**：飞书开放平台 → 开发者后台 → 创建「企业自建应用」，拿到 **App ID / App Secret**。
2. **开权限**：给应用加两个权限并发布版本：
   - `wiki:wiki:readonly`（查看知识库）
   - `docx:document:readonly`（查看新版文档，取正文要用）
3. **把应用加进知识库**：打开目标知识库 → 设置 → 成员管理 → 添加成员，搜应用名加进去（不加会报 permission denied）。要让应用看到整个库就加为**管理员**。

## 怎么导出

```bash
FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=yyy python3 tools/feishu_import.py --out ./feishu

# 先看看应用能看到哪些知识库
python3 tools/feishu_import.py --env-file /path/to/.env --list
# 只导一个
python3 tools/feishu_import.py --env-file /path/to/.env --space "产品文档" --out ./feishu
```

- 凭证走 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`（环境变量或 `--env-file`），只发往 `open.feishu.cn`，不落盘、不进仓库。
- 目录结构按知识库的节点树还原。

## 导出规则

- **新版文档（docx）/ 旧版文档（doc）**：取纯文本正文，落成 `.md`。
- **电子表格 / 多维表格 / 思维导图 / 文件 / 幻灯片**：只落一份说明存根——它们的正文要走各自的产品接口或导出流程。
- 每篇带 frontmatter（`title` / `description` / `tags` / `source` / `obj_type` / `node_token`）。

## 注意

导出内容属于你（或你所在组织）的知识库，公开仓库前先确认有权外发。
