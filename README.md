# 智慧树掌握度油猴脚本｜知到 AI 课程自动答题助手

**智慧树掌握度助手**是一款面向知到（Zhihuishu）AI 智慧课程知识点练习的开源 **Tampermonkey 油猴脚本**。支持自动答题、多选与填空、答案保存、交卷判分和暂停续答，可配置 DeepSeek 或 OpenAI 兼容中转 API。

脚本只处理知识点掌握度，允许查询课程；不刷视频、不签到、不操作正式考试。

**[点击安装 / 更新掌握度脚本 2.5.7](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery.user.js)** · [下载完整安装包](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery-v2.5.7.zip) · [查看源码与测试](https://github.com/17hwliao/zhihuishu/tree/main) · [反馈问题](https://github.com/17hwliao/zhihuishu/issues)

> 当前交付版本为 **2.5.7**，包含填空、整卷回查和原生答案绑定修复；默认分支源码与此版本的脚本内容一致。相关隔离测试已通过，最新绑定修复的真实页面效果仍待确认。历史 **v1.0.0 Release** 保留，不包含这些修复。

## 可以做什么

| 功能 | 具体行为 |
| --- | --- |
| 扫描智慧树课程知识点 | 读取当前课程目录，跳过免考、无评分和已达到 100% 的知识点 |
| 自动答题与填空 | 处理可识别的单选、多选、文字填空和多空题，保留代码符号、大小写及必要空格 |
| 保存与交卷 | 核对当前题、页面选填值和原生组件状态，取得平台保存成功回执后记录答案；整卷核对完整后才交卷 |
| 断点续答 | 暂停、刷新后接续原试卷；从中间题恢复时，卷末自动回查前题并补齐遗漏 |
| 掌握度提升 | 每轮读取对应解析和判分，再查询平台最高掌握度；只以平台实际返回的 100% 记为达标 |
| 有界重试 | 每个知识点默认最多 10 轮，包含首轮，可设 1–10；达到上限会记录原因并继续下一点 |
| 当前知识点临时记忆 | 同一知识点多轮复用已确认答案，达标、放弃或结束任务后清除，不建立长期题库 |
| 简洁操作面板 | 可拖动，支持开始、暂停、继续、结束、待办清单和暂停原因提示 |

## 怎么安装智慧树掌握度脚本

1. 在电脑浏览器中安装并启用 **Tampermonkey**。
2. 用同一个浏览器打开 **[油猴脚本安装链接](https://github.com/17hwliao/zhihuishu/releases/download/v2.5.7/zhihuishu-mastery.user.js)**，在油猴安装页确认安装或更新。
3. 刷新已登录的智慧树 AI 课程页面，确认出现“掌握度助手”面板，版本显示 **v2.5.7**。

如果浏览器显示源码或下载文件，可在原同名油猴脚本的编辑器中替换全文并保存，或者在 Tampermonkey 中导入下载的 `.user.js` 文件。更新时只保留一份启用的同名脚本。

日常使用只需要油猴脚本，**无需 Python、参考项目或本机日志服务**。浏览器集成测试使用 Microsoft Edge；其他浏览器及脚本管理器的实际兼容性需以运行结果为准。

## 配置 DeepSeek 或中转 API

展开面板中的“API 与重试设置”，填写接口信息并保存，再点击“测试 API 连接”。

| 接口类型 | 需要填写 |
| --- | --- |
| DeepSeek 官方 | 该平台签发的 API Key、实际可调用的模型名 |
| OpenAI 兼容 / 自定义中转站 | 服务商地址、该站 API Key、该站支持的模型名 |

中转站支持根地址、带前缀的 Base URL，以及完整的 `/chat/completions` 地址。例如，`https://relay.example.com/v1` 会补全为 `https://relay.example.com/v1/chat/completions`；此域名仅作格式示例。

不同接口地址独立保存 Key 和模型。模型名请使用服务商实际提供的名称；界面默认值不代表当前账号一定可调用。普通使用无需手动配置 Token、temperature 或 thinking 参数。

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
- 文字模型不能识别图片内容。可选的尝试作答功能不保证正确，模型、题型和平台页面变化均可能影响结果。

## 常见问题

### 智慧树刷掌握度脚本会同时刷视频吗？

不会。本项目的自动化范围只有课程查询和知识点掌握度练习，不附带刷课时、播放资源或正式考试功能。

### 能保证知识点全部达到 100% 吗？

不能。脚本只在平台返回 100% 时记录达标。每个知识点有轮次上限，达到上限仍未满分会保留未达标原因，不把队列结束写成全部满分。

### 填空、保存或交卷时暂停怎么办？

先查看面板“暂停原因”，确认脚本版本及当前 API 配置，处理后点击“继续任务”。原任务的试卷、轮次和临时记忆会保留，不必为恢复而重新扫描整门课程。平台出现验证码时由用户完成。

### 需要题库、Python 项目或本机接收器吗？

不需要。浏览器直接运行 `.user.js`。本项目只保留当前任务及知识点的临时答案；仓库中的 Python 文件用于开发测试和可选诊断，不是日常答题依赖。

### API Key、账号和答案会如何处理？

Key 保存在本机油猴存储中。文字题目、选项及少量相关错误反馈会发送给你配置的模型服务。脚本不识别平台账号，不把 Key、Cookie 或答案上传到本 GitHub 仓库。手动换号前应结束旧任务。

### 为什么安装后版本和 GitHub Release 不一样？

当前 Release 与默认分支的脚本均为 **2.5.7**；历史 **v1.0.0** 仍可查看，但不是当前安装入口。本版保留原交付文件的 `@updateURL none`，更新请使用本页的安装链接。内部诊断中的旧 `release: 1.0.0` 是沿用的历史字段，实际脚本版本以面板及 `@version 2.5.7` 为准，本次没有为了改显示字段而更换已交付脚本的字节。

## 问题反馈与验证状态

请在 [GitHub Issues](https://github.com/17hwliao/zhihuishu/issues) 提供脚本版本、页面类型、题型和相关脱敏日志。不要公开 API Key、Cookie、学号、完整个人资料或未脱敏诊断包。

隔离自动化覆盖课程目录、选项匹配、多空填写、业务保存回执、异步题目响应、原卷续答、整卷回查、提交关联及轮次上限。**模拟测试通过不代表所有真实课程已验收；2.5.7 的最新绑定恢复仍待真实使用结果确认。**

开发者可在[当前源码分支](https://github.com/17hwliao/zhihuishu/tree/main)查看测试和可选诊断工具：

```powershell
node --check zhihuishu-mastery.user.js
node tests/test_point_memory.cjs
.venv/Scripts/python.exe tests/check_binding_recovery.py
.venv/Scripts/python.exe tests/check_blank_prefetch.py
.venv/Scripts/python.exe tests/check_two_question_exam.py
```

[实现说明](https://github.com/17hwliao/zhihuishu/blob/main/docs/implementation.md) · [临时记忆与日志边界](https://github.com/17hwliao/zhihuishu/blob/main/docs/data-and-logs.md)

## English overview

**Zhihuishu Mastery Userscript** is a Tampermonkey script for knowledge-point mastery practice in Zhihuishu AI courses. It supports multiple-choice and text-blank answers, native answer saving, paper submission, and resume within the original paper, with configurable DeepSeek or OpenAI-compatible Chat Completions APIs. It does not automate videos, attendance, or formal exams. Current fixes are covered by isolated tests; real-course results are not guaranteed.

## 来源与许可

本项目以 [MIT License](LICENSE) 提供。早期实现参考 [Cetirzine/zhihuishu-auto-mastery](https://github.com/Cetirzine/zhihuishu-auto-mastery) 的页面字段及解析流程，保留相关许可；当前油猴脚本独立运行，不依赖该 Python 项目。其他参考与适配差异见[实现说明](https://github.com/17hwliao/zhihuishu/blob/main/docs/implementation.md#参考项目的取舍)。
