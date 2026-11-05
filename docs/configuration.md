# API 与中转站配置

适用于正式发行版 **v1.0.0**。安装 [zhihuishu-mastery.user.js](https://github.com/17hwliao/zhihuishu/releases/download/v1.0.0/zhihuishu-mastery.user.js) 后，刷新智慧树页面，在面板展开“API 与重试设置”。

## DeepSeek 官方

1. 接口类型选择“DeepSeek 官方”。
2. 填写 DeepSeek 官方平台创建的 API Key，模型默认 `deepseek-flash`；也可填写账号实际可调用的模型 ID。
3. 保存后点击“测试 API 连接”。连接检测与实际答题使用同一套已保存配置。

官方请求地址固定为 `https://api.deepseek.com/chat/completions`。Key 与地址分开填写，无需在 Key 前加 `Bearer`。

## OpenAI 兼容中转站

接口类型选择“OpenAI 兼容 / 自定义中转站”，依次填写服务商地址、该站签发的 Key、该站提供的模型 ID，再保存。模型名支持 `/`、`:` 等常见字符；必须使用服务商列出的实际模型 ID。

| 填写的地址 | 最终请求地址 |
| --- | --- |
| `https://relay.example.com` | `https://relay.example.com/v1/chat/completions` |
| `https://relay.example.com/v1/` | `https://relay.example.com/v1/chat/completions` |
| `https://relay.example.com/proxy/v1` | `https://relay.example.com/proxy/v1/chat/completions` |
| `https://relay.example.com/v1/chat/completions` | 保持完整路径 |

上表域名仅为格式示例。面板会预览实际请求地址，先检查地址再测试连接。

支持 HTTPS，以及 `localhost`、`127.0.0.1`、`::1` 的本机 HTTP 服务。地址不能包含用户名、密码、查询参数或片段；不要把 Key 拼进 URL。目前适配 **Chat Completions** 协议，原生 Responses 或 Anthropic Messages 地址需要由中转站转换为兼容接口后使用。

## 模型兼容参数

展开“模型兼容参数”，按服务商要求设置：

| 设置 | 用途 |
| --- | --- |
| `max_tokens` | 常见兼容接口的输出 Token 参数，默认选择 |
| `max_completion_tokens` | 需要此字段的模型使用 |
| 发送 temperature=0 | 仅在接口接受该参数时勾选 |
| 发送 DeepSeek 关闭思考参数 | 仅在接口兼容该参数时勾选 |

自定义中转站默认不附加 temperature 或 DeepSeek thinking 参数。出现不支持参数的 400/422 时，先核对服务商文档，再调整对应选项。连接测试不是模型列表查询，不会代替你选择模型。

## Key 保存与请求通道

Key 保存在本机油猴脚本存储中，不写入源码、发行包或导出的诊断包。每个最终接口地址独立保存 Key、模型和参数；切换到新地址需要填写该站 Key，不会自动把上一家的 Key 发给新地址。“清除 Key”只清除当前地址的 Key。

模型请求会把文字题目、选项及已判错答案发送给当前选定服务商。优先使用浏览器请求；跨域不可用或特定鉴权失败时，有限尝试油猴请求同一地址，不会切换到其他服务商。油猴若询问连接自定义域名，请核对域名后允许。重定向不作为自动切换接口的手段。

## 常见连接错误

| 提示 | 排查方向 |
| --- | --- |
| 401 | Key 是否由当前服务商签发、是否有效；重新保存后测试 |
| 402 | 账号余额或额度 |
| 403 | 账号权限、模型权限或服务商访问限制 |
| 404 | Base URL 路径、模型 ID 是否正确 |
| 400 / 422 | 模型名、Token 字段或可选参数是否受支持 |
| 429 | 服务商限流或额度限制，稍后继续 |
| 网络 / CORS | 域名是否可达、油猴是否允许连接、服务是否支持兼容协议 |
| 空回答或无法解析 | 模型是否返回有效的文本答案、输出额度是否足够 |

不要把完整 Key 粘贴到问题反馈、截图或日志中。反馈时提供服务商名称、无凭证接口地址、模型名及错误状态即可。

## 填空与重试

已适配文本填空输入及页面组件同步，多个空按顺序填写；会记录已判错答案，供后续轮次纠正。优先复用平台解析答案，缺失时调用当前 AI 配置。图片题若无可用题库答案，暂不支持自动回答。

每个知识点默认最多 **10 轮（包含首轮）**，可配置 1–10；以平台返回的最高掌握度 **100%** 为完成条件，不用固定全对次数替代。达到轮次上限仍未满分会记录并继续下一点。API 鉴权、保存或交卷结果无法确认时会暂停并弹出提示，避免把未知状态记作完成。
