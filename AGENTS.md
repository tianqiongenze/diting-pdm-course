# AGENTS.md · 本仓库维护规则

> 任何人（含 AI 助手）修改本仓库前，先读完这 8 条。
> 违反其中任何一条，修改一律回退。

---

## 1. 这是「教学投影」，不是独立项目

本课程的全部案例、代码、指标来自上游 **Diting-PdM**：

- GitHub：https://github.com/tianqiongenze/diting-pdm
- Gitee：https://gitee.com/enze_tian_qiong/diting-pdm

**规则**：上游任何变更（文档/代码/指标/事故），必须同步到本仓库对应位置。
不允许课堂讲旧数据，不允许编造上游没有的"案例"。

## 2. 同步流程（每次上游更新后执行）

```bash
python tools/sync_course.py --check     # 看变更、受影响讲次、事实漂移
python tools/sync_course.py --apply     # 写记录 + 刷新快照 + 更新基线
# 按 PROJECT_UPDATES.md 的清单人工修订正文
python tools/build_slides.py --only N   # 重建受影响课件
python tools/verify_course.py           # 自检
```

- 同步记录只追加，不修改历史行。
- 事实漂移（测试数、文档数、镜像版本）**必须人工核对**，脚本不自动改正文。

## 3. 事实必须可追溯

任何数字（146 项单测、211 项浏览器、48 份文档、0.9.24）必须能指到上游文件。
写不清楚来源的数字，删掉。

## 4. 教学语言优先

正文是给教师和学生看的，不是给机器看的：

- 一页 PPT ≤ 5 条要点，每条 ≤ 2 行；
- 术语第一次出现必须解释；
- 反例比正例重要，每个概念至少配 1 个反例。

## 5. 课件由脚本生成，不手改 pptx

```bash
python tools/build_slides.py            # 全部重建
python tools/build_slides.py --only 7   # 只重建第 7 讲
```

内容源在 `tools/src/content_m*.py`。手改 pptx 会在下次重建时被覆盖。

## 6. 数据与合规

- 课堂只用脱敏/合成数据；
- 不得写入企业真实设备编号、工艺参数、人名；
- 不得把上游 `docs/28`、`docs/29` 事故报告中的敏感细节原样搬进课件（只讲教训，不讲可复现的攻击细节）。

## 7. 提交规范

```
[类型] 简述

类型：docs / slides / tools / sync / fix
示例：[sync] 上游 f2b09af → 3a1c2d：更新第 13 讲缺陷案例
```

## 8. 完成定义（DoD）

一次修改算完成，必须同时满足：

- [ ] `python tools/verify_course.py` 通过
- [ ] 受影响的课件已重建
- [ ] 若涉及上游事实，`PROJECT_UPDATES.md` 有对应记录
- [ ] 新增/修改的文档链接可达
