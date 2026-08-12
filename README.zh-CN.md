# PaperMeld

[English](README.md) | [简体中文](README.zh-CN.md)

![PaperMeld 工作流：论文库、目录与选中的证据论文](docs/media/papermeld-workflow.png)

> **一个用于构建、检索和维护本地、目录优先文献库的 Codex Skill 与插件。**

PaperMeld 为 Codex 提供了一套使用个人文献库的明确流程：调用
`$papermeld`，搜索 `library.jsonl`，选出少量候选论文，再将相应的
Markdown、PDF 或图片作为证据阅读。它避免了一种常见失误：智能体盲目扫描
大量文件，把文件名、标题或目录字段误作有文献支持的结论。

核心是一个可复用的 Codex Skill，并被打包为 Codex 插件。Python CLI 使目录创建、
入库和校验具有确定性；Skill 可直接读取已有的 `library.jsonl`，
进行目录优先的检索。

## 在 Codex 中使用

安装后，向 Codex 提出明确的检索任务，例如：

> 使用 `$papermeld` 在我的本地文献库中查找 4 篇关于基于扩散模型的轨迹预测
> 的论文。先返回候选论文的路径和版本信息，然后只阅读最相关论文的引言和方法
> 部分。不要修改任何文件。

PaperMeld 会将这一任务转化为一条以证据为中心的流程：

```text
研究问题 -> 检索目录 -> 少量候选文献 -> 查阅原始材料 -> 有证据支持的回答
```

目录只负责将智能体引导到原始材料，不能代替原始材料作为证据。

## 在 Codex 中安装

### 推荐方式：从 GitHub 安装插件

如果当前 Codex 环境支持 GitHub marketplace，请运行：

```bash
codex plugin marketplace add QinKB/PaperMeld --ref main
codex plugin add papermeld@papermeld
```

随后新建一个 Codex task，并调用 `$papermeld`。该插件将 Skill 打包为目录优先的
检索工作流。

也可以直接对 Codex 说：

> Install the Codex plugin from https://github.com/QinKB/PaperMeld

### 备用方式：只安装 Skill

如果当前 Codex 环境尚不能安装社区插件，可以对它说：

> Install the Codex Skill from GitHub repo `QinKB/PaperMeld`, path
> `plugins/papermeld/skills/papermeld`.

从源码克隆目录中工作时，Codex 也会自动发现仓库级的
`.agents/skills/papermeld`。安装 CLI 后，可创建、引导、校验和导入文献库。

## 安装 CLI

CLI 需要 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)。如果
`uv --version` 不可用，请先按 [官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)
安装 uv，然后运行：

```bash
uv tool install "git+https://github.com/QinKB/PaperMeld.git"
papermeld --help
```

从源码检出安装：

```bash
git clone https://github.com/QinKB/PaperMeld.git
cd PaperMeld
uv tool install .
papermeld --help
```

CLI 可以独立使用，也可在可用时由 Codex 通过 `$papermeld` 调用。PaperMeld
转换新的 PDF 时使用 MinerU。

### 可选：安装用于 PDF 转换的 MinerU

MinerU 通过 `ingest` 完成 PDF 转换。建议单独安装，避免其较大的机器学习依赖进入
PaperMeld 环境：

```bash
uv venv ~/.venvs/mineru
source ~/.venvs/mineru/bin/activate
uv pip install -U "mineru[all]"
mineru --version
```

`mineru[all]` 是 MinerU 面向一般用户的官方安装方式。首次解析可能下载模型，耗时也
会更长。激活该环境后，PaperMeld 会通过 `PATH` 找到 `mineru`；也可以显式传入
`--mineru "$(command -v mineru)"`。不同平台的加速与模型源配置见
[MinerU Quick Start](https://opendatalab.github.io/MinerU/quick_start/)。

## 它解决的问题

PDF 和转换得到的 Markdown 文件夹对人是可读的，但对 AI 往往并不透明：AI 不知道
哪些文件相关、不知道一项是预印本还是正式发表版本，也不知道某张图片属于哪里。
PaperMeld 使用 `library.jsonl` 保存目录，每个论文版本一条记录。正确的检索方式为：

```text
问题 -> 检索目录 -> 选取少量证据论文 -> 阅读这些原始材料
```

目录是路由层，**不是证据**。智能体在作出事实性论断前，仍必须检查被选中的
Markdown 或 PDF。

## 功能

- 本地优先：PDF 文本和转换产物保留在你的计算机上。
- 转换器可选：目录创建与校验使用 Python 标准库；MinerU 提供 PDF 转 Markdown
  转换。
- 安全导入：在转换前检查完全一致的 PDF 哈希、DOI 和 arXiv 标识。外部 PDF 默认
  被复制而不是移动。
- 现有文献库引导：为现有 Markdown 建立索引，并可关联 PDF；不会重命名、移动或
  重写已有文件。
- 代码关联：将现有本地 Git 仓库与对应论文连接，并记录后续阅读代码所需的仓库状态。
- 适合智能体检索：稳定、精简的 `search` 输出让智能体只打开相关的原始文件。
- 可移植布局：新的文献库使用中性的目录名；旧的 `INBOX/PDF/Markdown` 布局也会
  被识别以保持兼容。

## 创建新文献库

选择 PaperMeld 源码目录以外的位置：

```bash
papermeld --library ~/Research/Papers init
```

这会创建一个空的可移植文献库：

```text
Papers/
├── inbox/          # 可选的 PDF 落地目录
├── papers/         # 由 PaperMeld 管理的 PDF 副本
├── markdown/       # 每篇论文对应一个可读 Markdown 文件
├── assets/         # 转换产物和本地图片
└── library.jsonl   # 每个论文版本对应一条 JSON 记录
```

不会上传任何源 PDF、Markdown 或图片。

## 选择起点

### 已有 Markdown 或转换器输出目录

先预览将要建立的目录：

```bash
papermeld --library ~/Research/Papers bootstrap \
  --markdown-dir ~/OldLibrary/markdown \
  --pdf-dir ~/OldLibrary/pdfs \
  --dry-run
```

确认记录数量和 PDF 关联正确后，去掉 `--dry-run` 再运行相同命令：

```bash
papermeld --library ~/Research/Papers bootstrap \
  --markdown-dir ~/OldLibrary/markdown \
  --pdf-dir ~/OldLibrary/pdfs
```

可重复传入 `--markdown-dir` 或 `--pdf-dir` 来连接多套文献集合。源目录会保持
原位；PaperMeld 只写入 `library.jsonl` 以及空的文献库布局。无法匹配的文件会被
标记为待检查，而不会被猜测性处理。

### 有 PDF，希望由 PaperMeld 转换

先安装并测试本地的 PDF 转 Markdown 转换器。PaperMeld 原生支持 MinerU，同时也
允许使用其他转换器：

```bash
papermeld --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --mineru /absolute/path/to/mineru \
  --label concise-paper-label \
  --dry-run
```

检查拟使用的标题、年份、会议或期刊、文件名和重复状态。确认后，去掉
`--dry-run`：

```bash
papermeld --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --mineru /absolute/path/to/mineru \
  --label concise-paper-label
```

外部 PDF 会被复制到 `papers/`，原始文件仍保留在 Downloads 中。将 PDF 放入
`inbox/` 可由文献库接管。只有在确实想移动外部源文件时才使用 `--move-source`。

对于其他转换器，传入包含字面量 `{pdf}` 和 `{output}` 占位符的命令模板。转换器
必须在输出目录下生成恰好一个 Markdown 文件，并让本地图片可通过相对路径访问：

```bash
papermeld --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --converter 'my-converter --input {pdf} --output {output}' \
  --label concise-paper-label
```

## 在 Codex 之外检索论文

先检索，再打开少量记录：

```bash
papermeld --library ~/Research/Papers search "causal inference"
papermeld --library ~/Research/Papers verify
```

同一检索原则同样适用于脚本和其他 AI 智能体：先搜索，再只检查支撑任务所需的
原始材料。PaperMeld 默认保留文献库数据；只有在打算修改文献库时才使用导入流程。

## 将本地代码关联到论文

如果论文实现已在本地目录中，先预览 PaperMeld 根据 README 标题、论文题名和模型名
发现的关联：

```bash
papermeld --library ~/Research/Papers link-code \
  --code-root ~/Research/Code \
  --dry-run
```

确认后去掉 `--dry-run`，匹配的论文记录会增加 `code` 列表。每项关联保存本地路径、
远程地址、分支、当前提交、README 路径和匹配依据。代码更新后运行 `verify`，即可发现
仓库缺失、远程地址或当前提交的变化。

## 命令

| 命令 | 用途 | 需要转换器？ |
| --- | --- | --- |
| `init` | 创建空的文献库布局和目录 | 否 |
| `bootstrap` | 为已有 Markdown/PDF 目录建索引，不修改它们 | 否 |
| `search QUERY` | 将研究问题路由到候选记录 | 否 |
| `link-code` | 将已有本地 Git 仓库关联到论文记录 | 否 |
| `verify` | 检查目录路径、本地图片链接和代码关联 | 否 |
| `ingest PDF` | 转换一篇 PDF、整理资源并追加记录 | 是 |

每个选项请运行 `papermeld <command> --help` 查看。对新的转换器或 PDF 集合，
建议先运行 `ingest --dry-run`。

## 记录格式与隐私

`library.jsonl` 每行包含一个 JSON 对象。核心字段包括：

```json
{
  "paper_id": "2025-CVPR-Example",
  "title": "Example paper title",
  "year": 2025,
  "venue": "CVPR",
  "doi": "10.xxxx/example",
  "status": "published",
  "source_pdf": "papers/2025-CVPR-Example.pdf",
  "markdown": "markdown/2025-CVPR-Example.md",
  "artifact_dir": "assets/2025-CVPR-Example",
  "code": [{
    "relationship": "implementation",
    "local_path": "/home/me/Research/Code/Example",
    "repository_url": "https://github.com/example/Example.git",
    "commit": "<checked-out commit>"
  }]
}
```

当 DOI 可用时，PaperMeld 仅向 Crossref 请求书目信息。它不会发送 PDF 内容、
提取的 Markdown、目录或 API Key。缺失或不确定的元数据会被记录为待检查，不会被
悄然编造。

不要将个人 PDF、转换后的论文、图片资源或私有目录提交到公开仓库。提供的
`.gitignore` 会排除默认文献库布局，原因正在于此。

## 兼容性与安全性

PaperMeld 识别较早的目录布局：

```text
INBOX/  PDF/  Markdown/ALL_MARKDOWN/  Markdown/MINERU_OUTPUT/
```

并在不迁移的情况下继续建立索引。Bootstrap 不会重命名或重写源 Markdown。
导入时会先在临时目录转换，仅在成功验证输出后才添加 PDF、Markdown、资源和目录
记录。遇到完全相同的哈希、DOI 或 arXiv ID 时，会在转换前停止。

## 开发

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv build
```

贡献规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。项目采用 MIT 许可证，见
[LICENSE](LICENSE)。

## 致谢

PaperMeld 感谢使这一工作流成为可能的项目和社区：

- [OpenAI Codex](https://developers.openai.com/codex)：在实现、测试、文档和可复用
  Skill/插件工作流方面提供帮助。
- [MinerU](https://github.com/opendatalab/MinerU)：提供可选的本地 PDF 转 Markdown
  转换路径。
- [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)：提供基于
  DOI 的书目信息。
- [uv](https://docs.astral.sh/uv/)：提供可复现的 Python 打包和开发工作流。

这些项目未审查或背书 PaperMeld。PaperMeld 是独立的本地优先工具；用户应自行
遵守其源材料和所选转换器的许可证及访问条件。

## 社区与负责任披露

参与前请阅读 [Code of Conduct](CODE_OF_CONDUCT.md)。涉及本地文件或转换器的安全
敏感问题，请按照 [SECURITY.md](SECURITY.md) 报告，而不要公开提交 issue。
