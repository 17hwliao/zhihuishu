# 智慧树掌握度助手

适用于智慧树 **AI 智慧课程掌握度练习**的 Tampermonkey 油猴脚本。进入课程后，通过页面右下角面板配置 DeepSeek API Key、启动当前课程的知识点队列。无需运行 Python 服务。

## 安装

1. 在浏览器中安装并启用 Tampermonkey。
2. [打开安装文件](https://raw.githubusercontent.com/17hwliao/zhihuishu/main/zhihuishu-mastery.user.js)。若未自动显示油猴安装页，在油猴中“创建新脚本”，粘贴该文件全部内容并保存。
3. 打开已登录的 AI 智慧课程并刷新页面，在右下角“掌握度助手”中展开“API 与重试设置”。
4. 填写自己的 **DeepSeek API Key**，确认模型名与每点轮次，点击“保存设置”，再点击“开始本课程”。

已安装旧版或其他同类脚本时，请先停用，避免重复操作。适配域名为 `ai-smart-course-student-pro.zhihuishu.com` 与 `studentexamcomh5.zhihuishu.com` 的知识点练习页面；其他课程界面尚未适配。

## 功能与完成条件

- 自动读取当前课程目录，发现掌握度低于 100% 的知识点，优先处理接近满分的点。
- 沿平台“去提升”入口进入对应练习，选填答案、交卷、读取解析，再重新查询最高掌握度。
- **仅以平台实际返回的 100% 为该点完成条件**；不会用固定的连续全对次数代替分数核验。
- 每点默认最多 **10 轮，包含首轮**，可配置 1–10。达到上限仍未满分则记录并继续下一个，课程队列结束后展示未达标项。
- 优先使用已积累的官方解析答案，缺失时调用 AI。选择题按选项内容匹配，填空保留标点并记录已判错答案。
- 提供暂停、继续、结束、返回课程目录、未达标记录和清除 Key；匹配的练习链接在当前标签页接续。

Key 存在本机脚本管理器中，模型请求仅发往 DeepSeek 官方接口，包含当前文字题目、选项及已判错答案。当前版本支持填写 Key 和模型名，尚不支持自定义 API 中转地址。

## 验证状态与限制

已通过离线模拟浏览器流程：跳过已有满分点、一个填空点失败 10 轮后继续下一个、另一个点三轮后获得平台 100%、乱序选项、解析答案复用、交卷与分数核验。模拟使用固定测试数据，没有调用真实模型或提交真实练习。测试夹具模拟单标签页的脚本存储，不覆盖真实油猴的多标签页同步或隔离。

**真实账号、实际课程 DOM 与真实 API 调用尚未验证，不能保证所有知识点都能达到 100%。** 验证码、模型请求错误、未知界面或无法确认保存时会暂停；缺少可用题库的图片题暂不支持自动回答。

## 源码与开发

| 文件 | 用途 |
| --- | --- |
| [zhihuishu-mastery.user.js](zhihuishu-mastery.user.js) | 可直接安装的完整脚本，包含面板、API 配置与调度 |
| [docs/implementation.md](docs/implementation.md) | 入口跳转、DOM 元素、响应字段、掌握度策略与参考项目说明 |
| [tests/check_course_flow.py](tests/check_course_flow.py) | 平台与 AI 响应全部模拟的浏览器集成测试 |

本地修改 `.user.js` 后，更新油猴编辑器中的内容并刷新课程页。运行开发检查需 Node.js、Python 3.10+ 与 Microsoft Edge：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
node --check zhihuishu-mastery.user.js
.\.venv\Scripts\python.exe tests/check_course_flow.py
```

浏览器使用脚本不需要这些开发依赖。测试截图写入被 Git 忽略的 `.local/` 目录。

## 来源与许可

本油猴版参考 [Cetirzine/zhihuishu-auto-mastery](https://github.com/Cetirzine/zhihuishu-auto-mastery) 的页面字段、两级入口与解析回收方式，保留其 MIT 许可。其他参考项目及适配差异见[实现说明](docs/implementation.md#参考项目的取舍)。本项目以 [MIT License](LICENSE) 提供。
