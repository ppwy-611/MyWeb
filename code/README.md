# 睡眠体验模型与交互原型

本目录仅保留用于课程原型的最终模型：`model/final_model.joblib`。它使用同一晚最多 7 项客观睡眠指标，预测次晨 Groningen 睡眠质量量表总分 `Groningen_ts`，支持只提供部分指标。分数范围为 0–14，越高表示主观睡眠质量问题越严重。预测结果是连续数值，不应当被解释为诊断结论。`web/` 提供与该模型连接的本地交互网页“眠序”。

## 数据集来源与处理

数据来自 Budapest Sleep, Experiences and Traits Study（BSETS）的 [Zenodo 公开记录](https://zenodo.org/records/10657021)，本地文件为 `../dataset/bsets/Multilevel raw data.xlsx`。相关论文：[Objective sleep quality predicts subjective sleep ratings](https://doi.org/10.1038/s41598-024-56668-0)。原始表共有 1,901 条夜间记录、267 位参与者。`Model Ready` 工作表保留目标和候选客观指标完整的 1,612 条记录、253 位参与者。

工作表已按参与者 `ID` 固定划分：训练集 1,136 条 / 177 人，验证集 239 条 / 38 人，测试集 237 条 / 38 人。同一人不跨集合。`ID` 和 `data_split` 只用于划分，不输入模型。数据清理、字段定义与限制见项目根目录的 `工作记录.md`、`睡眠数据集说明.md`。原始数据的再分发与许可应以 Zenodo 记录为准。

## 模型如何工作

最终版本是 Ridge 回归（`alpha=10`），输入以下 **7 个原始字段**：

| 字段 | 含义 | 模型中的处理 |
|---|---|---|
| `tst` | 总睡眠时间，按数据说明暂以分钟理解 | 原值 |
| `sol` | 入睡潜伏期，暂以分钟理解 | `log(1 + sol)` |
| `waso` | 入睡后清醒时间，暂以分钟理解 | `log(1 + waso)` |
| `n3_percentage` | N3 深睡占比，百分比 0–100 | 原值 |
| `rem_percentage` | REM 睡眠占比，百分比 0–100 | 原值 |
| `n3_latency_aasm` | N3 潜伏期，暂以分钟理解 | `log(1 + n3_latency_aasm)` |
| `sleep_efficiency` | 睡眠效率，百分比 >0–100 | 原值 |

模型流水线依次进行字段范围检查、上述变换、训练数据中位数填补、标准化和 Ridge 回归。可以省略整列，或在单独一行留空；非数值、无穷大和越界输入也按缺失处理。对数变量先变换，再使用模型已保存的训练中位数填补，填补参数不会根据用户输入重新拟合。未提供的值不视为 0。每行至少有一项有效输入，否则报错；字段名重复也会报错。输出分数可能超出 0–14，因此界面应说明这是估计值，不应静默改成量表整数。请使用同一套字段名和计量单位输入新记录。

历史版本曾比较线性回归、随机森林、梯度提升、MLP，以及 11 项、16 项、五项比例和 7–9 项紧凑输入。训练集按参与者做 5 折交叉验证；七项模型折外 MAE 2.491、RMSE 3.064，固定验证集 MAE 2.520、RMSE 3.035。九项模型的折外 RMSE 略低，为 3.058；七项模型因输入更简洁、验证误差相近而被选作原型版本。最终模型用训练集与验证集合并拟合。七项版本没有独立的新数据验证，且已有实验曾查看测试集，因此不能把现有验证结果当作临床准确度。迭代过程与结果统一记在 `../工作记录.md`，旧代码和模型可从本项目 Git 历史查阅。

## 如何使用

在 Windows PowerShell 中进入 `code` 目录。已有 `.venv` 时可直接使用其中的 Python；否则先用 Python 3.11 创建环境并安装依赖：

```powershell
cd "D:\0njust\2026-2027-1\人机交互\code"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 启动网页

推荐在项目根目录双击 **`启动网页.cmd`**，自动使用项目虚拟环境并打开浏览器；不需要先切换到 `code`。也可在项目根目录的 PowerShell 终端执行：

```powershell
.\code\.venv\Scripts\python.exe .\code\web\server.py --open-browser
```

如果终端已经位于 `code` 目录，则执行：

```powershell
.\.venv\Scripts\python.exe web\server.py
```

保留服务终端运行，按 `Ctrl+C` 停止；也可以使用 `web/start.ps1`。默认网页地址为 [http://127.0.0.1:8000](http://127.0.0.1:8000)，以终端显示的实际地址为准。已有同项目服务时，启动程序提示已有地址并正常退出，不重复占用端口；端口被其他项目或程序占用时，自动选择附近的可用端口。可通过 `--port 8001` 指定起始端口，或通过 `--open-browser` 自动打开网页。后端代码修改后，先在原服务终端按 `Ctrl+C`，再启动以加载新代码。必须通过本地服务访问，直接双击 `web/index.html` 无法连接模型。

注意：`.\.venv\Scripts\python.exe` 是相对于 `code` 目录的路径，在项目根目录应使用 `.\code\.venv\Scripts\python.exe`。截图中若出现 Windows 错误 10048，表示端口已被占用，不能在同一个端口同时启动两个服务；新的启动逻辑已自动处理这种情况。

页面支持：

- 一至七项输入，四项常见指标优先显示，三个分期指标可展开；单位说明、就地范围检查和深睡＋REM 合计检查。
- 三项、四项和完整示例，明确标记“示例评估”；首次打开不展示虚构分数。
- 百分制体验指数与“舒适／一般／较差”，逐项模型贡献图、缺失信息与同组合历史误差。
- 基于真实模型贡献的本地分析报告和复制报告。
- 修改或补充输入后显示前后差异；尚未重新评估时保留旧结果并标记输入已变化。
- 明确标记的模拟调整模式，以最近一次实际记录评估为参考；退出后恢复原记录。
- 桌面左右布局、手机上下布局、键盘操作、方法说明与连接失败重试。

网页输入在本机服务处理，记录只在当前页面的内存中保存，刷新或清空后消失。第一版报告使用 Ridge 贡献和文字模板，没有调用外部大语言模型。

### 命令行预测

准备 CSV 或 Excel 文件，每行一晚，包含上表字段的任意非空子集。无需提供 `Groningen_ts`、`ID` 或 `data_split`。对现有工作簿的 `Model Ready` 工作表预测：

```powershell
.\.venv\Scripts\python.exe predict.py --data "..\dataset\bsets\Multilevel raw data.xlsx" --sheet "Model Ready" --output predictions.csv
```

对自己的 CSV 预测：

```powershell
.\.venv\Scripts\python.exe predict.py --data new_nights.csv --output predictions.csv
```

三项示例（也可直接打开项目中提供的 `../experiments/missing_inputs/example_3_inputs.csv`）：

```csv
tst,waso,sleep_efficiency
420,30,88
390,50,82
```

```powershell
.\.venv\Scripts\python.exe predict.py --data "..\experiments\missing_inputs\example_3_inputs.csv" --output "..\experiments\missing_inputs\my_3_predictions.csv"
```

输出文件保留原始列并增加以下列；同名输出列会被本次结果覆盖：

| 输出列 | 含义 |
|---|---|
| `prediction` | 连续 GSQS 估计分数 |
| `valid_input_count` | 范围检查后实际有效的指标数量 |
| `used_features` / `missing_features` | 实际使用 / 填补的字段名，用 `\|` 分隔 |
| `input_status` | `complete_input`：七项；`partial_input`：三至六项；`limited_input`：一至两项 |
| `reference_cv_mae` / `reference_cv_rmse` | 该固定组合在训练集参与者分组五折评估中的历史误差 |
| `reference_validation_rmse` | 该组合在固定验证集的历史 RMSE |

`input_status` 只描述输入完整度；三项或更多输入也可能表现较差。`reference_*` 是群体历史评估结果，不是这条预测的实际误差、准确率或个人置信区间。参考值随模型保存在同一个 `final_model.joblib` 中，推理无需读取实验目录。Excel 输入可用 `--sheet` 指定工作表。`joblib` 模型只能加载来自可信来源的文件；请保留 `compact_features.py`，反序列化模型时需要该类。

## 缺失输入的适用范围

当前沿用七项 Ridge 的全部拟合参数。2026-10-09 的缺失输入评估枚举了 127 种非空组合；未使用本轮测试集结果选模。可筛选的表格和独立 SVG 图位于项目根目录下 `experiments/missing_inputs/`，迭代过程、比较依据和限制见根目录 `工作记录.md`。

| 输入组合（未提供的字段按训练中位数填补） | 分组 CV MAE | 分组 CV RMSE | 验证 RMSE |
|---|---:|---:|---:|
| 完整七项 | 2.491 | 3.064 | 3.035 |
| TST、WASO、睡眠效率（三项 CV 首选） | 2.510 | 3.081 | 2.950 |
| TST、WASO、N3 潜伏期、睡眠效率（四项 CV 首选） | 2.500 | 3.063 | 2.989 |
| TST、SOL、WASO、睡眠效率（便于减少分期指标） | 2.499 | 3.079 | 2.953 |

表中最优组合的训练评估包含从多种组合中选择的影响。额外的外层五折、内层四折参与者分组验证对“选择组合再预测”整个过程评估，三项 RMSE 为 3.102，四项为 3.063。这支持部分组合可以接近七项输入，不支持“任意三项都足够”或“少输入更准确”。只用 TST、SOL、WASO 的结果也在全部组合表中，不能把深睡潜伏期假定为普通用户容易获取的指标。

中位数填补在所有三项、四项组合上的汇总 CV RMSE 为 3.207。针对每种子集拟合 Ridge 可降低到 3.157，但验证集改善只有约 0.002 分，按参与者重抽样的 RMSE 差 95% 区间为 [-0.075, 0.068]，因此尚未替换拟合参数。各组合对高分段仍会低估；输入缺失模拟基于完整的客观测量，不能直接证明手环或自报数据具有相同效果。

## 网页评分与解释方式

2026-10-09 第八轮诊断确认：完整七项模型的训练集参与者分组折外 R² 约 0.188，预测标准差 1.550 分，而真实评分标准差 3.399 分；存在明显的向均值收缩。去掉正则化的线性回归 RMSE 3.064，与当前 Ridge 3.064 接近，本轮固定候选的样条和浅层梯度提升也未改善。不能把页面展示精度或逐项贡献解释为模型已准确掌握个人体验。当前模型参数保持不变；下一轮拟优先验证个人历史基线与额外背景信息，方案、对比和限制统一见根目录 `工作记录.md`，诊断产物在 `../experiments/prediction_diagnosis/`。

同日第九至十二轮进一步检验小型神经网络、正则化、残差学习、加权、融合和优化上限。训练内五折外层/四折内层选择流程的 RMSE 为 3.084，仍高于 Ridge 的 3.064；提高迭代上限后的复查也未改善。因此继续交付当前 Ridge，不能将训练集拟合能力等同于新用户预测能力。完整过程见根目录 `工作记录.md`，实验产物在 `../experiments/neural_iterations/`。

网页把原始连续预测 `p` 转换为 `100 × (14 − p) / 14`，展示时限制到 0–100，保留一位小数；原始 `p` 保留在接口响应和页面方法说明中。文字等级按实际显示的分数划分：80–100 为“舒适”，60–不足80 为“一般”，0–不足60 为“较差”。这些阈值是原型展示规则，未经临床或等级数据验证；百分制不表示概率、准确率或健康百分比。

解释以全部字段取模型训练中位数的输入为参考：`GSQS贡献_j = 系数_j × (标准化输入_j − 标准化训练中位数_j)`。参考预测加上所有已提供字段的 GSQS 贡献，等于本次原始预测。体验指数的贡献为 `−100 / 14 × GSQS贡献_j`；正值表示上调展示指数，负值表示下调。缺失字段贡献为零，报告不会将填补值解释成用户的实测值。当展示分数限制到 0 或 100 时，限制前的贡献不再直接加总为限制后的页面分数，页面会明确提示。

报告先以“给这一晚的一句话”自然总结主要影响，例如“这一晚夜里清醒的时间比参考记录长一些，拉低了这次模型评分”；详细分析依据默认收起，数值贡献仍可在贡献图中查看。复制报告也以自然总结开头。报告依据当前输入、贡献排序及缺失状态生成；说明的是模型关联，不是因果机制。例如未提供深睡占比时，不会断言“深睡不足导致质量差”。参考记录是训练数据的典型输入，不是医学上的正常标准。时长、分期定义与输入单位必须与训练数据一致；时间单位仍沿用现有项目按分钟理解的假设。模拟调整不代表改变某一指标就会得到真实改善。

## 网页接口与运行检查

FastAPI 启动时一次性加载 `model/final_model.joblib`。网页与接口由同一服务提供，接口包括：

| 接口 | 用途 |
|---|---|
| `GET /api/health` | 检查服务就绪 |
| `GET /api/config` | 获取字段说明、展示等级阈值与示例输入 |
| `POST /api/predict` | 校验输入、模型预测、指数与等级、缺失信息、误差参考、贡献及报告 |

预测请求示例：

```json
{"inputs":{"tst":420,"waso":35,"sleep_efficiency":88},"mode":"record"}
```

`mode` 可为 `record` 或 `simulation`。省略字段或提供 `null` 表示缺失。网页接口对已填写的非法值返回带字段说明的 422 错误，要求用户纠正；命令行批量接口延续原有策略，将无效值按缺失处理。这两种入口的正常有效输入使用同一份模型参数。

模型迁移前的缺失输入版本保存在 Git 提交 `0ec7437`，迁移后模型文件逐字节一致。接口检查覆盖 127 种组合、完整 1,612 条记录的预测分解、评分边界与错误反馈；真实浏览器检查覆盖桌面、390 像素手机、模拟恢复、补充输入、复制报告和网络失败等流程。检查脚本及截图位于项目根目录的 `experiments/web_prototype/`，不影响网页部署。

如需复现自动检查，先在虚拟环境额外安装 `httpx` 和 `playwright`；浏览器脚本使用 Windows 已安装的 Edge，无需下载浏览器。接口检查运行 `../experiments/web_prototype/check_api.py`；浏览器检查需先启动 8000 端口服务，再运行 `check_browser.py`。自动检查不替代至少三名同学的真实用户评价。

## 目录

```text
code/
├── README.md
├── predict.py
├── compact_features.py
├── requirements.txt
├── model/
│   ├── __init__.py
│   ├── service.py
│   └── final_model.joblib
└── web/
    ├── server.py
    ├── start.ps1
    ├── index.html
    ├── styles.css
    ├── app.js
    └── favicon.svg
```


## 云端发布（Render）

部署仓库为 `https://github.com/ppwy-611/MyWeb`，仅同步运行源码和最终模型，不上传虚拟环境、原始数据或实验产物。根目录 `render.yaml` 定义免费 Python Web Service，工作目录 `code`，安装命令 `pip install -r requirements.txt`，启动命令 `uvicorn web.server:app --host 0.0.0.0 --port $PORT`，健康检查 `/api/health`。本地启动方式保持可用。

Render 账号连接后可导入该仓库的 Blueprint。网站上线后提供公开 HTTPS 地址；免费服务存在休眠和首次访问等待，不保证搜索收录。云端输入会发送到托管服务进行计算；应用不主动持久保存评估输入，页面记录刷新后消失，托管平台可能保存访问日志。当前没有反馈收集功能，用户测试继续使用匿名测试表。

首页已补充描述，并提供 `/robots.txt` 与 `/sitemap.xml`。公开网址优先取 `PUBLIC_URL` 或 Render 的 `RENDER_EXTERNAL_URL`；绑定域名后可设置 `PUBLIC_URL`。这些配置有助于发现页面，仍须自行验证搜索平台网站所有权并申请收录。
