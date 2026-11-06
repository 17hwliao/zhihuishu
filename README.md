# 智慧树掌握度助手（源码 2.5.7）

用于智慧树 **AI 智慧课程掌握度练习**的 Tampermonkey 油猴脚本。配置模型接口后，自动处理当前课程中非免考且未达到 100% 的知识点，支持 DeepSeek 官方及自定义 OpenAI 兼容中转站。日常使用无需 Python 服务。

## 源码更新（2.5.7）

2.5.7 处理页面已回显答案、平台 Vue 父组件绑定为空或同步延迟时的保存前暂停。先有界等待原生绑定；仍不一致时，仅在当前题号、页面选填值和原生组件引用全部核对后，通过平台 `reviewTopic.chooseAnswer → update:userAnswer` 入口同步一次，再核对绑定并调用原生保存。仍必须取得业务成功回执。题目或页面值变化、组件指向其他题或原生同步失败时保持暂停。用户紧凑日志只能确认绑定检查失败，不能证明其内部原因；本版新增不含答案的绑定状态诊断。

2.5.6 修复从原卷中间题目进入/恢复后，走到卷末只核对 4/6 题就暂停的问题。卷末尚未完整核对时，通过平台原生“上一题”回查同一试卷，复核已保存答案并补做前题；本次实际遍历全部题目且保存记录完整后才交卷。原卷、知识点轮次及已有模型预算保留，切题失败和缺少唯一返回入口时保留进度暂停。没有降低题数或保存断言。

2.5.5 修复填空题已收到平台保存成功回执后，记录临时答案时出现 `Cannot read properties of undefined (reading '0')` 的问题。填空题即使返回非空 `optionVos` 也不建立选择题选项映射；选择题仍保留原映射。旧 2.5.4 已在“保存成功后记录失败”的隔离用例复现，新增非空 `optionVos` 的六题填空及原暂停试卷恢复检查。本版尚未在真实页面验证。

2.5.4 修复填空题在模型回答返回前捕获到另一题响应时误暂停的问题：当前练习的响应按题号有界缓存，通过原生当前题号及 DOM 匹配读取，不把最后返回的题目当作当前题；保存回执也关联实际当前题。允许同一道填空题的输入框重建后重新获取节点，仍阻止切题或题目版本变化后的旧答案写入。新增六题填空的预加载、延迟响应及输入框重建隔离回归。

本地源码保留原有面板及扫描、跳转、选填、保存、交卷和暂停提示。答案绑定任务 ID、课程、班级和当前知识点：同点多轮、跨页、刷新和暂停保留，确认 100%、放弃或结束任务后清除，不跨任务复用。已移除平台账号识别、资料请求及账号等待闸门。

每次判分关联对应的试卷实例与实际提交答案，复用前校验题目版本；模型重复错答最多有界纠正两次。日志展示与待发送队列分离，显示送达时间和丢失数；本机日志轮转，快照仅采结构并限制数量。详见[数据与日志设计](docs/data-and-logs.md)。本阶段 Review 已修复日志故障传播、整卷恢复漏检、纠错旧快照与提交前异步回写问题，见[审查记录](docs/review-data-logs.md)。

2.5.2 曾在真实练习页被账号识别阻塞，不能视为已修好。2.5.3 删除整个识别链路；旧任务升级保留轮次、原试卷、保存答案与提交凭据。调度直接进入掌握度历史页，核对平台最高掌握度后进入原生练习。普通设置只保留服务、地址、Key、模型与尝试次数，兼容参数自动处理。

当前分支同步 2.5.7 源码，未改动已发布的 v1.0.0 附件。将根目录 `.user.js` 导入油猴即可，无需 Python 或本机接收器。当前源码禁用远端自动更新，避免覆盖为旧发行脚本。2.5.7 的绑定恢复已完成隔离测试，真实页面效果尚未复验。

## 安装与历史发行

本次脚本使用根目录 [zhihuishu-mastery.user.js](zhihuishu-mastery.user.js)。下列 GitHub 链接是历史 v1.0.0，**不含本地 2.5.7 修复**。

[安装当前分支的 2.5.7 脚本](https://raw.githubusercontent.com/17hwliao/zhihuishu/refs/heads/codex/mastery-userscript/zhihuishu-mastery.user.js)。这是当前开发分支源码，不是新的正式 Release。

- [直接安装油猴脚本](https://github.com/17hwliao/zhihuishu/releases/download/v1.0.0/zhihuishu-mastery.user.js)
- [下载完整发行包](https://github.com/17hwliao/zhihuishu/releases/download/v1.0.0/zhihuishu-mastery-v1.0.0.zip)
- [API 与中转站配置说明](docs/configuration.md)
- [v1.0.0 发行说明](docs/releases/v1.0.0.md)

1. 安装并启用 Tampermonkey，导入本地 `zhihuishu-mastery.user.js`，或在原同名脚本编辑器中替换全文并保存。
2. 刷新已登录的智慧树课程页面，展开“API 与重试设置”，选择接口类型并填写 API Key、模型名。
3. 保存设置，点击“测试 API 连接”。再点击“开启进入课程自动启动”，从全部课程页进入目标课程；也可点击“开始本课程”立即启动。

更新时保留同名脚本，避免多份脚本同时操作页面。适配 AI 智慧课程及其知识点练习域名，执行范围为当前选定课程；脚本不处理视频、签到或正式考试。

## 功能与完成条件

- 自动读取课程目录与知识点卡片，跳过免考、已满分点，优先处理接近满分的待办。
- 沿平台入口进入练习，选填、保存、交卷、读取解析，再核对平台最高掌握度。
- **仅以平台实际返回的 100% 为该点完成条件**，不以固定连续全对次数代替。
- 每点默认最多 **10 轮（包含首轮）**，可设置 1–10。达到上限仍未满分会记录并继续下一点，队列结束时展示未达标项。
- 选择题按选项内容匹配；支持文本填空及多空顺序填写，保留代码标点，记录已判错答案供后续纠正。优先复用当前知识点中已由平台确认的答案，缺失时调用 AI。
- 选项状态异常会有限自动恢复；需要处理鉴权、保存或交卷状态等问题时弹出暂停提示，可查看原因、设置及日志。
- 面板支持拖动、键盘移动、位置记忆，提供暂停、继续、结束、待办清单和未达标记录。

真实使用日志陆续暴露了异步题目响应、填空记录、整卷遍历和保存前绑定暂停。当前 2.5.7 已针对这些路径做隔离验证，尚未确认本版在真实页面的最终结果。自动化使用模拟平台和模型，不保证所有服务商、模型或题目均能达到 100%。暂不识别图片内容，可尝试答案后收集平台解析。

## API 与中转站

| 接口类型 | 配置方式 |
| --- | --- |
| DeepSeek 官方 | 填写官方 Key，模型默认 `deepseek-flash`，也可填写账号可用的实际模型 ID |
| OpenAI 兼容 / 自定义中转站 | 填写该站 Base URL、该站 Key 及该站提供的模型 ID |

支持根域名、带前缀 Base URL 或完整 `/chat/completions` 路径，脚本自动补全请求路径。各地址独立保存 Key 和模型，切换服务商不会复用另一家的 Key。无需手工配置 Token 或厂商扩展参数。详细示例和故障排查见[配置说明](docs/configuration.md)。

Key 只保存在本机油猴存储中，不包含在脚本、发行包或导出的诊断包中。模型请求将文字题目、选项及已判错答案发送给当前选择的接口。不要将 Key 发到公开反馈中。

## 版本说明

GitHub 历史正式发行版本为 **v1.0.0**。当前分支脚本及面板显示 **2.5.7**，脚本名称及命名空间保留，已有本机 API 配置继续使用。`@updateURL none`，不自动获取历史发行附件。本次仅同步源码，不合并 main，不创建 PR、标签或 Release。

## 日志与可选本机调试

面板“运行日志与诊断”可查看记录、采集当前页面或导出诊断包。日志不记录 Key、Cookie、请求头、完整题干、答案或 AI 正文；诊断包只含脱敏运行记录及元素结构，不包含临时记忆。

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
node tests/test_point_memory.cjs
.\.venv\Scripts\python.exe tests/check_temporary_memory.py
node tests/test_resume_routes.cjs
.\.venv\Scripts\python.exe tests/check_panel_ui.py
.\.venv\Scripts\python.exe tests/check_resume_and_trials.py
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
