# RAG 与 PDF 解析技术选择

调研日期：2026-09-09。本仓库不引入收费云端向量库或收费文档解析 API。

| 技术 | 许可 / 运行位置 | 当前决策 |
|---|---|---|
| FastEmbed + `BAAI/bge-small-zh-v1.5` | Apache-2.0，本机 ONNX | 生产式本地语义向量。首次会从 Hugging Face 下载模型到本机缓存，之后离线可用。不是 Qdrant Cloud，也不调用付费 embedding API。 |
| pdfplumber | 开源，本机 | 默认轻量路径：页码、原生文本、表格几何。 |
| Docling | MIT，本机 | 安装 `.[pdf-advanced]` 后优先使用：版式、阅读顺序、表格结构。短文本空页由 pdfplumber 补齐。 |
| Unstructured / Pinecone / Weaviate / Chroma Cloud | 含云端收费产品 | **未采用、未安装。** 文档中仅作调研对照，代码无依赖。 |

当前实现默认用 `pdfplumber` 保留页码、原生文本和表格；安装 `.[pdf-advanced]` 后，`knowledge_ingest.py` 会优先调用 Docling 的布局、阅读顺序和表格结构，再用原生抽取校验页覆盖。导入文件只写入本地 `DATA_DIR`，不会把原件发给模型或第三方 RAG 服务。

Docling 的结构输出不会直接覆盖原生页覆盖检查：若结构模型对某页返回空文本，导入器会从 pdfplumber 补回该页。真实两页含表格样例见 [`evidence-docling-merged.txt`](evidence-docling-merged.txt)。

检索排序采用 BM25 词法分数与持久化向量分数的混合排序。仓库模板和本机 `env.md` 使用 FastEmbed 中文模型 `BAAI/bge-small-zh-v1.5`。完全离线 Demo 可显式设为 `hash`；切换后应在管理页执行“按当前向量后端重建索引”。若未重建，维度不匹配的旧向量会被跳过，仅由 BM25 参与排序。

同一 `DATA_DIR` 只能由一个选定的 embedding 后端作为写入事实源。生产应按租户或部署实例隔离数据目录。

无论替换哪种解析器，都必须保留：

- `tenant_id` 隔离；
- 文件名、页码、片段号来源；
- 解析失败可观测且不写入半成品；
- 反馈候选经过评测、人工批准后才能进入生产知识；
- 原始文件和解析条目可回溯。

参考：[Docling](https://docling-project.github.io/docling/)、[FastEmbed](https://qdrant.tech/documentation/fastembed/)、[pdfplumber](https://github.com/jsvine/pdfplumber)。
