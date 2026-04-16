# data_agent_project_v3

面向行业标准/规范类 PDF 的 Python 数据清洗项目（改进版）。

## 当前能力
- 读取 PDF
- 去除常见页眉页脚/页码噪音
- 识别部分标题、章节标题、部分无编号小节
- 隔离目录页，避免目录混入正文
- 过滤常见图示编号/表内编号误判标题
- 提取表格并做基础去重
- 生成原文解析 Markdown
- 生成 summary / tags / 多个结构化 JSON
- 每个源文件输出到一个以原始文件名（去扩展名）命名的独立文件夹
- 若设置 OPENAI_API_KEY，可选调用 OpenAI Responses API 生成更强的 summary/tags

## 快速开始
```bash
pip install -r requirements.txt
python app.py --input "/path/to/file.pdf" --output "./output"
```

## 输出结构
如果输入文件是 `SN200_2007-02_中文.pdf`，输出会写入：

```text
output/
  SN200_2007-02_中文/
    文件基础信息.json
    章节结构.json
    表格.json
    数值型参数.json
    规则类内容.json
    检验与证书.json
    引用标准.json
    原文解析.md
    summary.json
    tags.json
    process_log.json
```

## 可选环境变量
```bash
export OPENAI_API_KEY="你的 key"
export OPENAI_MODEL="gpt-5.4"
```

## 说明
这是规则优先的工程版本。当前最适合处理：
- 行业标准
- 工艺规范
- 技术要求文件

对于扫描版 PDF、极复杂跨页表格、图像内容深度解析，建议后续继续迭代。


## 新版评分与迭代机制
- reviewer 采用三层评分：基础质量分、事实正确性分、一致性与可追溯性分
- 同时引入红线规则：伪标题、表格规则压缩错误、非法来源锚点、标签分类错位、主要部分覆盖缺失
- 最终通过条件不是只看总分，还要求三类分项达到阈值且不触发红线
- 输出新增 `review.json` 与 `review_rounds.json`


## 关于 output_root / output_iter
这些目录属于开发和测试阶段留下的示例输出目录，不是运行项目必须依赖的代码。
- output_root: 早期单轮或基础版输出
- output_iter: 带 review / fix / review_rounds 的迭代版输出
正式交付的项目包中建议不携带这些目录，避免和你自己的真实输出混淆。
