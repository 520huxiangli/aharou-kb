# Aharou 共享知识库

一个纯 Markdown 的仓库，作为「共享知识库」的**单一事实源**。同一份内容，三端共读：

| 端 | 怎么读 |
| --- | --- |
| 小染 / 群友 | 254 机器人定时拉取，内容进向量库与全文索引，检索工具直接引用 |
| Aharou App | App 的「知识库订阅」按 GitHub 镜像拉取，AI 用 `knowledge_search` 检索 |
| 公开订阅 | 仓库公开，任何人可 clone / 浏览 |

## 目录

| 目录 | 内容 |
| --- | --- |
| `ima/` | 从腾讯 ima 知识库导出的内容 |
| `aharou/` | Aharou App 使用文档 |
| `freekill/` | 新月杀：武将、技能、规则 |
| `fox/` | 狐狸服：扩展包、流程、常见问题 |

## 写作规范

每篇 Markdown 必须带 frontmatter：

```yaml
---
title: 标题
description: 一句话摘要（用于列表与检索结果展示）
tags: [标签, 标签]
updated: 2026-10-10
---
```

- 文件名用英文小写短横线，中文标题写在 frontmatter。
- 一篇讲一件事，别写超长文。
- 不放密钥、口令、私人联系方式、未公开的服务器细节。

## 同步

- 主仓：`cnb.cool/huxiangli/aharou-kb`（本仓库）
- 镜像：`github.com/520huxiangli/aharou-kb`（供 App 与公开站读取，由定时 workflow 自动同步）

改动推到主仓即可，镜像自动跟上。
