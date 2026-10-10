# 眠序 · 睡眠体验评估课程原型

使用最多七项客观睡眠指标估计次晨 Groningen 睡眠质量量表分数，并展示模型贡献、缺失信息和模拟调整。唯一交付模型为 `code/model/final_model.joblib`，七项 Ridge；这是课程原型，结果不用于医学诊断。

## 本地运行

使用 Python 3.11，在 `code` 目录执行：

```shell
python -m venv .venv
python -m pip install -r requirements.txt
python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
```

安装与启动前请先激活虚拟环境，或将以上 `python` 替换为环境中的 Python 路径。打开 `http://127.0.0.1:8000`。完整模型原理、输入输出、依赖安装与命令行预测说明见 [code/README.md](code/README.md)。

## Render 部署

导入根目录的 `render.yaml`，或创建 Python Web Service：

- 仓库：`https://github.com/ppwy-611/MyWeb`，分支 `main`。
- 根目录：`code`。
- Python：`3.11.8`。
- 安装：`pip install -r requirements.txt`。
- 启动：`uvicorn web.server:app --host 0.0.0.0 --port $PORT`。
- 健康检查：`/api/health`。

配置使用 Free 服务，存在休眠、冷启动与资源额度限制。仓库中的部署配置不表示网站已经上线；以 Render 返回的部署状态为准。自定义域名可通过 `PUBLIC_URL` 设置网站基础地址。

## 数据与测试

数据来自 [BSETS Zenodo 记录](https://zenodo.org/records/10657021)，研究论文为 [Objective sleep quality predicts subjective sleep ratings](https://doi.org/10.1038/s41598-024-56668-0)。来源和字段限制见 [睡眠数据集说明.md](睡眠数据集说明.md)。原始工作簿和实验产物未上传，本网站推理无需读取原始数据。

云端输入会发送到托管服务计算；应用不主动保存评估输入，页面记录刷新后消失，托管平台可能保存访问日志。网站目前没有反馈收集入口；真实用户测试另用匿名测试表记录。可先使用页面示例数据体验。
