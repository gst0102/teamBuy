# 群二维码上传到服务器标准提示词

下面这段提示词可以直接复制到一个新的 Codex 会话中使用。

---

你现在是 `teamBuy` 项目的运营执行 Codex。

请严格按以下顺序执行，不要跳步。

## 第一步：先读取项目文档

请先读取以下文件：

- `AGENTS.md`
- `docs/project-memory.md`
- `docs/decisions.md`
- `docs/pitfalls.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/stage2-docs/30-group-qr-server-upload-handoff.md`

然后读取当前：

- `git status --short --branch`
- `git diff --stat`

在没有完成接手理解前，不要直接改代码。

## 第二步：输出接手理解

请先输出：

1. 你理解的任务目标
2. 当前代码状态
3. 本次要执行的具体范围
4. 当前风险
5. 你的执行顺序

## 第三步：执行本次二维码上传任务

我会给你一批微信群二维码图片，可能是：

- 一个本地文件夹路径
- 若干张图片路径
- 或附带一份说明文本

你的任务是：

1. 读取我给出的二维码图片
2. 尽可能从图片中提取：
   - 群名称
   - 有效期
   - 是否为微信群二维码
3. 把这些二维码图片上传到生产服务器可访问目录
4. 为每张图片生成公网访问 URL
5. 整理出一份资源模板，字段包含：
   - 群名称
   - 城市
   - 区域
   - 类型
   - 标签
   - 二维码链接
   - 有效期
   - 备注
6. 输出最终整理结果
7. 如环境允许，生成：
   - `.csv`
   - `.xlsx`

## 第四步：执行规则

执行时必须遵守：

- 不要覆盖服务器已有同名文件
- 上传文件名必须唯一化
- 上传后必须验证生成的 URL 是否可访问
- 批量模板中的 `二维码链接` 指的是：
  - 二维码图片上传到服务器后的公网图片地址
  - 不是扫码后的微信内部内容
- 如果城市、区域、类型、标签无法从图片直接判断，不要乱猜，统一标记为：
  - `待补`
- 如果你需要我补充信息，请把缺失项汇总列出来，一次性告诉我

## 第五步：服务器信息

生产服务器信息如下：

- IP：`81.70.84.35`
- user：`ubuntu`
- project dir：`/home/ubuntu/teamBuy`
- domain：`https://teambuy.lifelove.top`
- ssh key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`

建议上传目录：

```text
/home/ubuntu/teamBuy/backend/mock/media/group-qrs/
```

如你判断更合适，也可以使用：

```text
/home/ubuntu/teamBuy/backend/mock/media/resources/group-qrs/
```

最终公网 URL 应可通过：

```text
https://teambuy.lifelove.top/media/...
```

访问。

## 第六步：最终交付要求

完成后请明确输出：

1. 一共处理了多少张二维码图片
2. 成功上传多少张
3. 失败多少张
4. 生成了哪些 URL
5. 哪些字段是你自动识别的
6. 哪些字段需要我人工补充
7. 模板文件保存在哪里

如果你发现当前仓库或服务器状态不适合直接上传，请先说明阻塞点，再继续给出最接近可执行的方案。

---

如果我附带了一个文件夹路径，你就从那个文件夹开始处理。
如果我附带了若干张图片路径，你就逐张处理。
如果我附带了说明文本，请优先用说明文本补足城市、区域、类型、标签、备注。
