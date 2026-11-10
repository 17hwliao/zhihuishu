# 掌握度回归与脱敏反馈

开发版 v2.5.17 的回归范围是课程查询和知识点掌握度练习。隔离测试使用虚构课程、试卷和模型回执，避免消耗真实课程轮次。

| 场景 | 隔离用例 |
| --- | --- |
| 解析关联、图片换址及选项换序、历史参考与视觉候选 | `tests/check_image_review.py` |
| 填空与选择题重置、原生保存回执 | `tests/check_binding_recovery.py`、`tests/check_selection_updates.py` |
| 历史页空值、无效响应及重载续接 | `tests/check_mastery_history_resume.py` |
| 手动或自动暂缓、补齐后仅提交一次、GitHub 限流 | `tests/check_defer_and_release.py` |
| 课程范围、轮次上限和平台 100% 核验 | `tests/check_mastery_scope.py`、`tests/check_course_flow.py` |

实机反馈可以复制下面的模板。记录观察到的最高掌握度和本轮判分，便于区分页面暂未更新与真实评分差异。请只分享虚构标识、脱敏的结构和必要日志片段。

```text
脚本版本和构建号：
浏览器和 Tampermonkey 版本：
当前阶段（答题 / 保存 / 交卷 / 解析 / 历史页 / 更新）：
触发步骤：
最后一项成功的动作或平台回执：
期望结果、实际结果和暂停提示：
本轮判分、页面最高掌握度与轮次有无变化：
脱敏结构或日志：
```

目前已有填空恢复的真实保存日志。图题解析的个别现场差异、历史页故障时的具体响应，以及从更新提示到 Edge 油猴安装完成的结果仍待实测证据。请在相关 Issue 补充结果。[真实课程回归跟踪](https://github.com/17hwliao/zhihuishu/issues/11)
