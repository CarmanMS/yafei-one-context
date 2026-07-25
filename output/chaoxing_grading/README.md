# 超星作文批阅自动化方案

## 方案概述

本方案针对超星学习通平台的手写拍照作文批阅，实现**半自动化流程**：

1. **自动提取** → 脚本遍历所有学生，提取作文图片
2. **AI 评估** → 我（AI）逐篇阅读手写作文，给出分数和评语
3. **自动回填** → 脚本将分数和评语批量填入超星系统

**适用场景**：学生手写拍照上传的作文，需要批阅打分和写评语。

---

## 前提条件

1. Chrome 已启动远程调试模式（端口 9222）
2. 已登录超星系统（CDP 复用已登录的 session）
3. Node.js 环境（已配置）

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `extract_students.js` | 提取所有学生信息列表（姓名、学号、批阅URL） |
| `extract_images.js` | 下载所有学生的作文图片 |
| `fill_grades.js` | 根据 grading.json 批量回填分数和评语 |
| `grading.json` | 评分模板，填写分数和评语后用于回填 |
| `students.json` | 学生信息原始数据 |

---

## 使用步骤

### Step 1: 提取学生信息

```bash
cd 超星批阅自动化
node extract_students.js
```

生成 `grading.json` 和 `students.json`。

### Step 2: 下载作文图片

```bash
node extract_images.js grading.json ./submissions
```

所有学生图片会保存在 `submissions/` 目录下，按 `学号_姓名/img1.jpg` 组织。

### Step 3: AI 评估（对话中进行）

将图片发给我，我逐篇阅读并给出分数和评语。

将结果填入 `grading.json`：

```json
{
  "students": [
    {
      "name": "楼晨好",
      "studentId": "25060801038",
      "score": 85,           // 填写分数
      "comment": "内容完整..."  // 填写评语
    }
  ]
}
```

### Step 4: 批量回填

```bash
node fill_grades.js grading.json
```

脚本自动为每个学生填入分数和评语，并提交。

---

## 注意事项

- **批量测试建议**：先对 1-2 个学生测试，确认无误后再批量执行
- **评语长度**：建议控制在 100-200 字，避免过长
- **分数范围**：0-100（满分100）
- **备份**：操作前建议导出成绩备份

---

## 技术细节

- 使用 Chrome DevTools Protocol (CDP) 复用已登录的 Chrome session
- 图片下载通过 CDP 获取 cookies，绕过 CDN 认证
- 分数填入通过 `Runtime.evaluate` 直接操作 DOM
- 提交通过模拟点击 `markAction(1)` 按钮

---

## 自定义评分标准

如果需要自定义评分标准，请告诉我：
- 满分是多少
- 各维度分值分配（如：内容40分、结构30分、书写30分）
- 具体的评分细则

我会据此调整评估标准。
