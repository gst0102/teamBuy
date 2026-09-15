# 展示页构建器 V1 Codex 自测报告

更新时间：2026-06-20

## 1. 自测结论

通过自动化自测。展示页构建器 V1 的后端创建、更新、发布、公开访问、下架、权限校验和最新资料摘要读取已覆盖；小程序新增页面已完成 JS 和 JSON 静态检查。

小程序真机分享、banner 裁切、电话拨号和微信号复制仍需用户在微信开发者工具或真机中人工确认。

## 2. 本轮完成

- 新增开发文档：`docs/stage2-docs/13-showcase-builder-v1.md`。
- 新增测试清单：`docs/qa/展示页构建器V1_测试清单与验收标准.md`。
- 后端新增 `ShowcasePage` / `ShowcaseItem` 模型。
- 后端新增 `/api/showcases` 接口：
  - 列表
  - 创建
  - owner 详情
  - 更新
  - 发布
  - 下架
  - 公开访问
- 小程序新增：
  - `pages/showcases/index`
  - `pages/showcase-edit/index`
  - `pages/showcase-view/index`
- “我的”页新增展示页入口。
- 构建页支持 banner 上传、资料排序、隐藏、移除、展示标题和自定义分组标题。

## 3. 已覆盖测试

- 创建展示页草稿。
- 展示页列表返回自己的展示页。
- 不能选择其他用户资料。
- 无有效资料不能发布。
- 未发布展示页不能公开访问。
- 发布后公开页可访问。
- 公开页只返回资料摘要，不返回 owner 私有字段。
- 隐藏资料和被删除资料不会出现在公开页。
- 下架后公开页不可访问。
- 资料更新后公开页读取最新资料摘要。

## 4. 验证命令

```bash
/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests
find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check
find miniprogram -name '*.json' -print0 | xargs -0 -n 1 /Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m json.tool >/dev/null
git diff --check
/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q
```

结果：

- 后端编译：通过。
- 小程序 JS 检查：通过。
- 小程序 JSON 解析：通过。
- `git diff --check`：通过。
- 后端全量测试：`112 passed`。

## 5. 未覆盖 / 需人工确认

- 未通过微信开发者工具上传体验版。
- 未做真机视觉验收。
- 未验证微信真实分享卡片。
- 未验证真机电话拨号和复制微信号体验。
- V1 只支持基础展示页，不含多模板装修、权益计数、支付或 AI 自动生成。
