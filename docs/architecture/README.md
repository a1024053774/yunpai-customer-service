# Archify 交付回执（2026-09-10）

图类型：architecture。两个 HTML 都由冻结 JSON 经 deliver 原子生成。

| 图 | JSON SHA-256 | HTML SHA-256 | 校验 |
|---|---|---|---|
| [request-trust-boundaries](request-trust-boundaries.html) | `aa2f8414682a52712cb123d6558aaf2a80a1723066080afc37e251861c1f6c38` | `896610a178c42481dd7db02aa359e981491ac6cdce1fd9dfc28e8a831948a814` | 9/9 showcase；0 errors；0 warnings |
| [current-customer-service](current-customer-service.html) | `7e13492bbc73473e4829c942e36a2bc2c59dfe72733af22b3753918b33e51790` | `d369b5cc10f3102ad9e31ef23fb5f9aa864b6c77583c7e0a4611054f2594249f` | 9/9 showcase；0 errors；0 warnings |

浏览器证据：未运行内置 Chrome/Chromium visual-check（遵从用户不用 Chromium 的要求）；使用 CUA 侧边浏览器做了四种桌面视口尺寸测量，浅/深主题均做视觉检查，结果见相邻 `.manual-browser.json`。不能把这些补充证据写成内置自动命令通过。

visual_review: passed（人工代理观察实际渲染及 PNG 导出）；几何修复：目标示意 0 轮，实际架构 2 轮标签偏移修复。

PNG/SVG 来自交付 HTML 的浏览器导出，不是手工重画。
