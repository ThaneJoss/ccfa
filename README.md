# CCFA — Zotero 出版物简称列

在 Zotero 文献列表新增 **CCFA** 列：识别 CCF A 类期刊或会议，显示其简称，例如 **AAAI、CVPR、ICLR、TPAMI、TIFS**。未匹配到 A 类出版物时留空。

目录采用 **CCF 2026 年第七版正式目录**，覆盖全部 **37 种期刊、58 个会议、10 个领域**。完整清单见 [CATALOG.md](CATALOG.md)。

## 安装

1. 从 [Releases](https://github.com/ThaneJoss/ccfa/releases/latest) 下载 `ccfa-1.0.1.xpi`。不要下载 GitHub 自动生成的 Source code ZIP。
2. 在 Zotero 桌面版中打开 **工具 → 插件**（部分版本为“附加组件”）。
3. 点击齿轮菜单 → **Install Add-on From File / 从文件安装插件**，选择 `.xpi`。
4. 在文献列表表头右键，勾选 **CCFA**。可拖动列位置、调整宽度或点击表头排序。

插件启用后随 Zotero 启动自动加载，重启后无需运行 JavaScript。面向 **Zotero 7 / 8 / 9 / 10 桌面版**；不适用于 Zotero 6、网页版或移动版。

## 匹配方式

- 读取出版物标题及其 Zotero 映射字段、论文集标题、书名、会议名称。标题缺失时可读取期刊简称。
- 兼容大小写、空白、全角字符、年份、会议届次、常见出版社前缀、旧名称和 NIPS 等旧简称。
- 字典采用确定性名称匹配；不在论文标题、摘要、标签里搜索缩写，不用模糊相似度猜测归属。
- 出版物名称出现 Workshop、CVPRW、ICCVW、Findings、Companion、Short papers 等标记时留空，即使另一字段填写了主会议；不同字段指向不同会议时也留空。
- 简称实时计算，不写入 Extra，不保存或修改任何条目。现有 Extra 内容保持原样，新导入或修改的条目使用同一规则。
- 本地离线识别。插件本身不上传文献信息；Zotero 的标准插件更新机制会访问 GitHub 的更新清单。

| 出版物 | CCFA |
|---|---|
| Proceedings of the AAAI Conference on Artificial Intelligence | AAAI |
| 2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) | CVPR |
| Advances in Neural Information Processing Systems | NeurIPS |
| IEEE Transactions on Pattern Analysis and Machine Intelligence | TPAMI |
| International Conference on Learning Representations | ICLR |
| CVPR Workshops | 留空 |

## 目录口径与限制

按 **2026 目录**判断所有年份的文献，不回溯论文发表当年的等级。该版 ICLR 属于 A 类，IJCAI、ECCV、EMNLP 不在 A 类名单内。名称识别只能提示出版物归属，无法仅靠名称证明一篇论文是 CCF 口径中的正式长文。

Journal of Cryptology 在官方表中没有简称，本插件显示 `J. Cryptol.`。其余显示值使用目录简称，去掉“原名称”注记，例如旧 USENIX ATC 统一显示 `ACM SIGOPS ATC`，KDD 显示 `SIGKDD`。

缺少出版物字段、仅有 PDF 附件、使用尚未收录的名称变体，或只写 `Proceedings of the ACM on Programming Languages` 等包含多个会议的系列名时，可能留空。补全会议/出版物名称即可。此列是插件显示列，不会自动加入 Zotero 的文献导出文件。

## 数据来源

- [CCF 官方第七版正式发布说明](https://www.ccf.org.cn/Academic_Evaluation/By_category/)（2026-03-31 发布；官网注明 4 月 9 日勘误）。
- [CCF 编制的正式目录 PDF，丽水学院科研处公开副本](https://kyc.lsu.edu.cn/_upload/article/files/20/77/2cbaa3754eb9aff9ed74cafed8ff/23a8de02-594c-445f-b084-69b0193c05b3.pdf)。全部 95 个 A 类条目的全称和简称已逐项核对；`data/catalog.json` 记录页码及 PDF SHA-256。
- [Zotero 7 插件开发文档](https://www.zotero.org/support/dev/zotero_7_for_developers)、[Zotero 8 插件开发文档](https://www.zotero.org/support/dev/zotero_8_for_developers)、[Zotero 9 插件开发文档](https://www.zotero.org/support/dev/zotero_9_for_developers)、[Zotero 10 插件开发文档](https://www.zotero.org/support/dev/zotero_10_for_developers)。

本项目是第三方工具，与 CCF、Zotero 无隶属关系；目录名称与分类信息来源于 CCF。

## 开发与验证

无需 npm 依赖。需要 Node.js 20+ 和 Python 3：

```sh
node --check src/bootstrap.js
node --check src/matcher.js
npm test
python3 -m unittest discover -s tests -p 'test_*.py' -v
npm run build
```

`dist/` 输出 `.xpi`、`updates.json` 和 `SHA256SUMS.txt`。构建前检查 `manifest.json` 与 `package.json` 版本一致。XPI 使用固定时间戳，可重复构建；构建测试在临时目录中验证产物及更新清单的校验和、重复构建一致性，并加载实际打包的字典与脚本检查列行为。字典维护入口为 `data/catalog.json`。

所有推送、Pull Request、合并队列及手动触发均以 `@main` 调用 [通用 CI](https://github.com/ThaneJoss/github-ci/blob/main/.github/workflows/ci.yml)。每次新运行使用当时 `main` 的版本，实际解析的提交以运行记录为准。调用文件不添加项目专属参数、步骤或兼容矩阵；通用流程从标准元数据自动发现检查。本项目 `package.json` 声明了 `test` 和 `build`，通用流程执行 JavaScript 单元测试和 XPI 构建，并自动发现 `tests/test_build.py` 中的 Python 构建测试。语法检查不等同于完整 lint 或类型检查；未被自动发现的检查不代表通过。

单元测试覆盖完整字典、名称变体、非 A 类和 Workshop 排除、只读元数据行为、插件启用/禁用及启动中取消。原先发布流程中的独立单元测试及真实 Zotero 10 安装/重启验证已移除；`scripts/smoke-zotero.py` 保留供手动验证，自动 CI 不下载或启动 Zotero，后续发布不再生成 `zotero-smoke.json`。Windows/macOS 未实机验证。

## 发布

将版本号同步更新至 `manifest.json` 和 `package.json`，准备 `RELEASE_NOTES.md`，推送 `main`。现有发布触发范围保持为 `manifest.json`、`scripts/smoke-zotero.py` 或 `.github/workflows/release.yml` 的变更，也可手动触发。[发布流程](.github/workflows/release.yml) 只负责打包及为尚不存在的版本创建 Release，上传 `.xpi`、更新清单和校验文件；版本一致性及已有 Tag/Release 保护保留。通用 CI 独立运行，发布流程不再执行单元测试或真实 Zotero 验证，且没有新增通用 CI 成功依赖。已有 Release 不会被覆盖。
