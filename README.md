# 智慧树掌握度油猴脚本｜知到 AI 课程自动答题助手

**智慧树掌握度助手**是一款面向知到（Zhihuishu）AI 智慧课程知识点练习的开源 **Tampermonkey 油猴脚本**。支持单选、多选、填空和图题，复用可核对的历史解析，通过平台原生入口保存、交卷和续答。可配置 DeepSeek 或 OpenAI 兼容中转 API。

脚本只处理知识点掌握度，允许查询课程；不刷视频、不签到、不操作正式考试。

**[点击安装 / 更新掌握度脚本 2.5.7](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery.user.js)** · [下载完整安装包](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery-v2.5.7.zip) · [查看源码与测试](https://github.com/17hwliao/zhihuishu/tree/main) · [反馈问题](https://github.com/17hwliao/zhihuishu/issues)

> **源码开发版 v2.5.17** 包含图题解析与视觉作答、同题重载恢复、暂缓补答、历史页续接和 GitHub 更新检查。上面的安装链接指向已发布的 **稳定版 v2.5.7**。下文标为开发版的功能以当前源码为准。

## 可以做什么

| 功能 | 具体行为 |
| --- | --- |
| 扫描智慧树课程知识点 | 读取当前课程目录，跳过免考、无评分和已达到 100% 的知识点 |
| 自动答题与填空 | 处理可识别的单选、多选、文字填空和多空题，保留代码符号、大小写及必要空格 |
| 图题与历史解析（开发版） | 核对题干与选项内容，在选项换序后复用已确认答案；可单独开启图片发送和视觉作答 |
| 保存与交卷 | 核对当前题、页面选填值和原生组件状态，取得平台保存成功回执后记录答案；整卷核对完整后才交卷 |
| 断点续答 | 暂停、刷新后接续原试卷；从中间题恢复时，卷末自动回查前题并补齐遗漏 |
| 暂缓补答（开发版） | 暂缓当前题，继续原卷其他题；补齐并确认保存后才交卷 |
| 掌握度提升 | 每轮读取对应解析和判分，再查询平台最高掌握度；只以平台实际返回的 100% 记为达标 |
| 有界重试 | 每个知识点默认最多 10 轮，包含首轮，可设 1–10；达到上限会记录原因并继续下一点 |
| 当前知识点临时记忆 | 同一知识点多轮复用已确认答案，达标、放弃或结束任务后清除，不建立长期题库 |
| 简洁操作面板 | 可拖动，支持开始、暂停、继续、结束、待办清单和暂停原因提示 |
| GitHub 更新检查（开发版） | 手动或按天检查公开稳定版，确认有较新脚本附件后显示安装入口 |

## 怎么安装智慧树掌握度脚本

1. 在电脑浏览器中安装并启用 **Tampermonkey**。
2. 用同一个浏览器打开 **[油猴脚本安装链接](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery.user.js)**，在油猴安装页确认安装或更新。
3. 刷新已登录的智慧树 AI 课程页面，确认出现“掌握度助手”面板，版本显示 **v2.5.7**。

如果浏览器显示源码或下载文件，可在原同名油猴脚本的编辑器中替换全文并保存，或者在 Tampermonkey 中导入下载的 `.user.js` 文件。更新时只保留一份启用的同名脚本。

日常使用只需要油猴脚本，**无需 Python 或本机日志服务**。浏览器集成测试使用 Microsoft Edge；其他浏览器及脚本管理器的实际兼容性需以运行结果为准。

## 配置 DeepSeek 或中转 API

展开面板中的“API 与重试设置”，填写接口信息并保存，再点击“测试 API 连接”。

| 接口类型 | 需要填写 |
| --- | --- |
| DeepSeek 官方 | 该平台签发的 API Key、实际可调用的模型名 |
| OpenAI 兼容 / 自定义中转站 | 服务商地址、该站 API Key、该站支持的模型名 |

中转站支持根地址、带前缀的 Base URL，以及完整的 `/chat/completions` 地址。例如，`https://relay.example.com/v1` 会补全为 `https://relay.example.com/v1/chat/completions`；此域名仅作格式示例。

不同接口地址独立保存 Key 和模型。模型名请使用服务商实际提供的名称；界面默认值不代表当前账号一定可调用。普通使用无需手动配置 Token、temperature 或 thinking 参数。

开发版需要你单独开启题图发送。脚本先用合成图检测当前接口，再向你选择的地址发送题图。可设置先确认视觉候选再保存，也可开启核对后自动填写。

[查看完整 API 配置与错误排查说明](https://github.com/17hwliao/zhihuishu/blob/main/docs/configuration.md)

## 如何开始自动答题、提升掌握度

1. 从全部课程页进入需要处理的 **AI 智慧课程**。
2. 点击“开始本课程”，扫描未满分的知识点；已有暂停任务则点击“继续任务”。
3. 脚本经平台原生掌握度入口进入练习，依次选填、确认保存、交卷并核验掌握度。
4. 在面板查看已完成、未达标或暂停原因。也可自行开启“进入课程自动启动”。

流程为：**课程目录 → 掌握度历史 → 原生提升练习 → 逐题保存 → 交卷判分 → 重新核验最高掌握度**。

遇到 API 鉴权、答案保存或提交状态异常时，脚本会保留进度并暂停。处理原因后继续原任务；提交结果不明时先核验原试卷，不盲目重复交卷。

## 适用范围与限制

- 面向智慧树 **AI 智慧课程网页中的知识点掌握度练习**，不是所有智慧树课程页面的通用适配器。
- 识别 AI 课程站点 `ai-smart-course-student-pro.zhihuishu.com`，以及带掌握度参数的 `studentexamcomh5.zhihuishu.com/studentReviewTestOrExam/` 练习页；全部课程入口可用于查询课程。
- 不处理视频时长、课程资源观看、签到、正式考试或知到手机 App 的原生界面。
- 不伪造掌握度，也不以连续全对次数代替 100%；分数由平台实际判定。
- 图题的视觉作答需要支持图像输入的接口，并依赖可读取的题图和可核对的选项。可选试答不保证正确，模型、题型和页面变化均可能影响结果。

## 常见问题

### 智慧树刷掌握度脚本会同时刷视频吗？

不会。本项目的自动化范围只有课程查询和知识点掌握度练习，不附带刷课时、播放资源或正式考试功能。

### 能保证知识点全部达到 100% 吗？

不能。脚本只在平台返回 100% 时记录达标。每个知识点有轮次上限，达到上限仍未满分会保留未达标原因，不把队列结束写成全部满分。

### 填空、保存或交卷时暂停怎么办？

先查看面板“暂停原因”，确认脚本版本及当前 API 配置，处理后点击“继续任务”。原任务的试卷、轮次和临时记忆会保留。开发版可暂缓当前题；历史页缺少可用的最高掌握度时，继续任务会重载当前历史页。平台出现验证码时由用户完成。

### 需要题库、Python 项目或本机接收器吗？

不需要。浏览器直接运行 `.user.js`。本项目只保留当前任务及知识点的临时答案；仓库中的 Python 文件用于开发测试和可选诊断，不是日常答题依赖。

### API Key、账号和答案会如何处理？

Key 保存在本机油猴存储中。文字题目、选项及少量相关错误反馈会发送给你配置的模型服务。脚本不识别平台账号，不把 Key、Cookie 或答案上传到本 GitHub 仓库。手动换号前应结束旧任务。

### 为什么安装后版本和 GitHub Release 不一样？

源码可以包含尚未发布的功能。实际安装版本以面板和 `@version` 为准。开发版的“检查 GitHub 更新”仅比较公开稳定发行，不会自动替换脚本。历史 **v1.0.0** 仍可在发行页查看。

## 问题反馈与验证状态

请在 [GitHub Issues](https://github.com/17hwliao/zhihuishu/issues) 提供脚本版本、页面类型、题型和相关脱敏日志。不要公开 API Key、Cookie、学号、完整个人资料或未脱敏诊断包。

隔离自动化覆盖图题解析、选项换序、多空填写、保存前重置、暂缓补答、历史页续接和更新限流。**隔离测试与真实课程验收分开记录**。真实图题、历史页恢复和 Edge 油猴升级仍需补齐现场证据。可按 [回归与脱敏反馈说明](docs/regression-and-reporting.md) 提交可分享的复现。

开发者可在[当前源码分支](https://github.com/17hwliao/zhihuishu/tree/main)查看测试和可选诊断工具：

```powershell
node --check zhihuishu-mastery.user.js
node tests/test_point_memory.cjs
.venv/Scripts/python.exe tests/check_binding_recovery.py
.venv/Scripts/python.exe tests/check_image_review.py
.venv/Scripts/python.exe tests/check_mastery_history_resume.py
.venv/Scripts/python.exe tests/check_defer_and_release.py
```

[实现说明](https://github.com/17hwliao/zhihuishu/blob/main/docs/implementation.md) · [临时记忆与日志边界](https://github.com/17hwliao/zhihuishu/blob/main/docs/data-and-logs.md)

## English overview

**Zhihuishu Mastery Userscript** is a Tampermonkey script for knowledge-point mastery practice in Zhihuishu AI courses. Development version v2.5.17 adds image-question matching and optional vision input, deferred questions, history-page recovery, and GitHub release checks. It uses native answer saving and resumes the original paper. Stable downloads and development source are versioned separately.

## 许可

本项目以 [MIT License](LICENSE) 提供。
