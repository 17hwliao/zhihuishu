# 智慧树掌握度助手 v1.0.0

用于智慧树 **AI 智慧课程掌握度练习**的 Tampermonkey 油猴脚本。配置模型接口后，自动处理当前课程中非免考且未达到 100% 的知识点，支持 DeepSeek 官方及自定义 OpenAI 兼容中转站。日常使用无需 Python 服务。

## 下载与安装

- [直接安装油猴脚本](https://github.com/17hwliao/zhihuishu/releases/download/v1.0.0/zhihuishu-mastery.user.js)
- [下载完整发行包](https://github.com/17hwliao/zhihuishu/releases/download/v1.0.0/zhihuishu-mastery-v1.0.0.zip)
- [API 与中转站配置说明](docs/configuration.md)
- [v1.0.0 发行说明](docs/releases/v1.0.0.md)

1. 安装并启用 Tampermonkey，打开上方脚本链接。若浏览器直接下载，可在油猴中导入文件，或创建新脚本后粘贴全文并保存。
2. 刷新已登录的智慧树课程页面，展开“API 与重试设置”，选择接口类型并填写 API Key、模型名。
3. 保存设置，点击“测试 API 连接”。再点击“开启进入课程自动启动”，从全部课程页进入目标课程；也可点击“开始本课程”立即启动。

更新时保留同名脚本，避免多份脚本同时操作页面。适配 AI 智慧课程及其知识点练习域名，执行范围为当前选定课程；脚本不处理视频、签到或正式考试。

## 功能与完成条件

- 自动读取课程目录与知识点卡片，跳过免考、已满分点，优先处理接近满分的待办。
- 沿平台入口进入练习，选填、保存、交卷、读取解析，再核对平台最高掌握度。
- **仅以平台实际返回的 100% 为该点完成条件**，不以固定连续全对次数代替。
- 每点默认最多 **10 轮（包含首轮）**，可设置 1–10。达到上限仍未满分会记录并继续下一点，队列结束时展示未达标项。
- 选择题按选项内容匹配；支持文本填空及多空顺序填写，保留代码标点，记录已判错答案供后续纠正。优先复用平台解析答案，缺失时调用 AI。
- 选项状态异常会有限自动恢复；需要处理鉴权、保存或交卷状态等问题时弹出暂停提示，可查看原因、设置及日志。
- 面板支持拖动、键盘移动、位置记忆，提供暂停、继续、结束、待办清单和未达标记录。

现有掌握度流程已由用户确认可用；中转站配置通过隔离自动化检查，未调用用户中转站账号。不保证所有服务商、模型或题目均能达到 100%。缺少可用题库答案的图片题暂不支持自动回答。

## API 与中转站

| 接口类型 | 配置方式 |
| --- | --- |
| DeepSeek 官方 | 填写官方 Key，模型默认 `deepseek-flash`，也可填写账号可用的实际模型 ID |
| OpenAI 兼容 / 自定义中转站 | 填写该站 Base URL、该站 Key 及该站提供的模型 ID |

支持根域名、带前缀 Base URL 或完整 `/chat/completions` 路径，面板显示最终请求地址。各地址独立保存 Key 和模型，切换服务商不会复用另一家的 Key。可配置 `max_tokens` / `max_completion_tokens` 及可选参数。详细示例和故障排查见[配置说明](docs/configuration.md)。

Key 只保存在本机油猴存储中，不包含在脚本、发行包或导出的诊断包中。模型请求将文字题目、选项及已判错答案发送给当前选择的接口。不要将 Key 发到公开反馈中。

## 版本说明

正式发行版本为 **v1.0.0**，面板显示此版本。为保证已安装开发版 2.4.0 的用户正常升级，油猴内部 `@version` 递增为 **2.4.1**，两者分别管理。脚本名称及命名空间保留，已有本机配置可继续使用。自动更新地址指向本仓库最新正式 Release 的脚本附件。

## 日志与可选本机调试

面板“运行日志与诊断”可查看记录、采集当前页面或导出诊断包。日志不记录 Key、Cookie、请求头或输入框值；诊断包留在本机，不会自动上传 GitHub。

需要实时本机日志时，在源码目录运行 `python tools/debug_collector.py`，再在面板开启对应设置。接收器只监听 `127.0.0.1:8790`，日志和快照写入被 Git 忽略的 `.local/`。本机调试支持读取状态、采集、扫描、启动、暂停与继续，不提供任意代码执行接口。正常使用脚本无需开启这些选项。

## 源码与开发

执行链路与验证边界见[交付说明](docs/delivery-plan.md)。

| 文件 | 用途 |
| --- | --- |
| [zhihuishu-mastery.user.js](zhihuishu-mastery.user.js) | 可直接安装的完整脚本，包含面板、API 配置与调度 |
| [docs/implementation.md](docs/implementation.md) | 入口跳转、DOM 元素、响应字段、掌握度策略与参考项目说明 |
| [tests/check_course_flow.py](tests/check_course_flow.py) | 平台与 AI 响应全部模拟的浏览器集成测试 |
| [tools/debug_collector.py](tools/debug_collector.py) | 无额外依赖的本机日志接收器，包含二次脱敏与重复包去重 |

本地修改 `.user.js` 后，更新油猴编辑器中的内容并刷新课程页。运行开发检查需 Node.js、Python 3.10+ 与 Microsoft Edge：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
node --check zhihuishu-mastery.user.js
node tests/test_helpers.cjs
.\.venv\Scripts\python.exe tests/check_course_flow.py
.\.venv\Scripts\python.exe tests/check_catalog_contract.py
.\.venv\Scripts\python.exe tests/check_two_question_exam.py
.\.venv\Scripts\python.exe tests/check_auth_recovery.py
.\.venv\Scripts\python.exe tests/check_native_saving.py
.\.venv\Scripts\python.exe tests/check_selection_updates.py
.\.venv\Scripts\python.exe tests/check_pause_notice.py
.\.venv\Scripts\python.exe tests/check_api_transports.py
.\.venv\Scripts\python.exe tests/check_custom_api.py
.\.venv\Scripts\python.exe tests/check_automatic_debug.py
.\.venv\Scripts\python.exe tests/test_debug_collector.py
# 先启动日志接收器，再运行诊断交互检查
.\.venv\Scripts\python.exe tests/check_diagnostics.py
# 可选：用自己导出的诊断包回放卡片，不调用账号或真实模型
.\.venv\Scripts\python.exe tests/check_snapshot_replay.py path/to/debug.json
```

浏览器使用脚本不需要这些开发依赖。测试截图写入被 Git 忽略的 `.local/` 目录。

## 来源与许可

本油猴版参考 [Cetirzine/zhihuishu-auto-mastery](https://github.com/Cetirzine/zhihuishu-auto-mastery) 的页面字段、两级入口与解析回收方式，保留其 MIT 许可。其他参考项目及适配差异见[实现说明](docs/implementation.md#参考项目的取舍)。本项目以 [MIT License](LICENSE) 提供。
