---
title: 飞书知识库导出
description: 从飞书知识库导出文档到本仓库，由 tools/feishu_import.py 生成
tags: [feishu, 导入]
updated: 2026-10-10
---

# 飞书知识库导出

本目录存放从飞书知识库导出的内容，由 `tools/feishu_import.py` 生成。

## 两条路子：走哪条看你的库是什么类型

### A. 你自己的库都能读（推荐，用 `user_access_token`）

以**你本人身份**调接口——你能在飞书里看到的知识库，它就能导出，包括个人知识库、别人分享给你的库。

1. 开发者后台 → 应用 → **安全设置** → **重定向 URL** 添加 `http://localhost:8848/callback` → **发布新版本**（改完必须发版才生效）
2. 跑一次授权（本机起回调服务，用**手机浏览器**打开它打印的链接并同意）：

```bash
python3 tools/feishu_auth.py --env-file /path/to/.env --port 8848
```

3. 然后就能列库和导出：

```bash
python3 tools/feishu_import.py --user-token-file feishu_user_token.json --list
python3 tools/feishu_import.py --user-token-file feishu_user_token.json --space "库名" --out ./feishu
```

注意：`user_access_token` **两小时过期**（返回里带 `refresh_token`）。过期了重跑一次授权即可，前面的配置不用再动。

### B. 只有应用被加为成员的库能读（`tenant_access_token`）

```bash
FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=yyy python3 tools/feishu_import.py --out ./feishu
python3 tools/feishu_import.py --env-file /path/to/.env --list
```

需要三件事：应用开 `wiki:wiki:readonly` + `docx:document:readonly` 权限、**把应用加进目标知识库**（个人知识库加不了成员，只能走 A）、应用开启机器人能力。

## 导出规则

- **新版文档 docx / 旧版文档 doc**：取纯文本正文，落成 `.md`。
- **电子表格 / 多维表格 / 思维导图 / 文件 / 幻灯片**：只落说明存根——它们的正文要走各自的产品接口或导出流程。
- 目录结构按知识库的节点树还原；每篇带 frontmatter（`title` / `source` / `obj_type` / `node_token`）。

## 注意

导出内容属于你（或你所在组织）的知识库，公开仓库前先确认有权外发。
