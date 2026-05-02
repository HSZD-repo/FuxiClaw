# Application UI：会话文件布局、执行产出与安全边界

本文档描述 **Application UI**（`frontend/application-ui` + `src/openharness/web`）在引入「上传 + 编程类 tools/skills 执行」时的 **目录约定、产出规则、artifact 行为与安全边界**，供后续实现对照。

当前实现状态以代码为准；文中「规划」段落表示尚未落地、但应按此规格演进。

---

## 1. 目标与范围

### 1.1 目标

- **输入**：用户上传的文件只落在**当前 session** 的受控目录（与「其他 session」隔离）。
- **执行**：当模型路由到编程类 **tools** 或 **skills** 需要跑代码时，在**隔离环境**中执行；执行过程只能访问本会话允许的路径。
- **输出**：执行生成的文件统一落在同一 session 下的 **`output/`**（与 **`uploads/`** 并列），语义为 **agent 产出**，便于与「用户上传」区分。
- **展示**：产出文件可通过 **Artifact** 面板查看；大文件仅提供下载，不内联进预览。

### 1.2 非目标（可单独开文档）

- 多租户公网部署的完整鉴权方案（本文仅列原则）。
- 与完整 OpenHarness 引擎（`ReactBackendHost`、Matrix 等）的协议对齐细节。

---

## 2. 目录布局（约定）

在「按项目分桶」的会话根下（实现上可与现有 `~/.openharness/data/web_sessions/<项目名-摘要>/` 对齐），每个 **session_id** 建议具备如下结构：

```text
<project_session_dir>/
  session-<session_id>.json     # 会话快照（消息历史等），已存在或规划中
  uploads/
    <session_id>/               # 用户上传；仅用户与受控执行可读
      <8hex>_<original_filename>
  output/
    <session_id>/               # 工具执行写出；仅 agent 与受控执行可写
      ...                       # 具体命名规则见第 3 节
```

**语义划分**

| 目录 | 含义 | 典型读者 |
|------|------|----------|
| `uploads/<session_id>/` | 用户带入的输入文件 | 用户、沙箱内只读挂载 |
| `output/<session_id>/` | 本轮 / 本会话 agent **产出** | 用户通过 artifact 查看、沙箱内可写 |

删除会话时，策略上应可同时清理 `uploads` 与 `output` 下该 `session_id`（与是否删除 `session-*.json` 一致）。

---

## 3. 产出文件命名与「版本」

### 3.1 同名冲突：**追加时间戳**

- 当 `output/<session_id>/` 下已存在与**拟定输出**同 basename 的文件时，新文件**不得静默覆盖**。
- 新文件名采用 **basename + 时间戳**（或等价单调后缀），例如：`report_20260417-153012.csv`（具体格式在实现中写死并写入文档附录即可）。

**实现注意**：若用户代码在沙箱内**自行**写入固定路径（如始终写 `out.csv`），宿主或执行封装层需明确责任——例如：

- 由 **SDK / 封装 API** 统一提供「申请写入路径」并自动重命名；或  
- 在进程退出后由宿主对**新出现文件**做冲突检测并重命名（复杂度高，需定义与「程序本意」的边界）。

### 3.2 多步对话

- **允许**后续 turn 继续向同一 `output/<session_id>/` 写入。
- **展示「版本」**：Artifact 列表按 **时间**（或 turn / request 元数据）排序；可选在 UI 副标题展示 **Turn N** 或 `request_id`，与时间戳命名互补。

### 3.3 执行失败但部分落盘

- 磁盘上**已存在且路径校验通过**的文件，**一律视为产出**，进入 artifact 列表。
- 建议在元数据中标记 **`exit_code` ≠ 0** 或 **`partial` / `error`**，并附 **stderr 摘要**，避免用户将失败 run 误判为完全成功。

### 3.4 大文件（如 GB 级）

- 当文件大小超过**约定阈值**（实现时需在前后端同时定义，例如 >20MB 或项目自定）：
  - **Artifact**：仅提供 **下载**（`Content-Disposition: attachment`、支持 `Range` 更佳），**不**将全文拉进浏览器内存做 CodeMirror / 内联预览。
  - UI 展示文件大小、类型与（经 token 化或 session 校验的）下载链接即可。

---

## 4. Artifact 与 HTTP 访问

- **上传区**：已有或可沿用 `GET /api/uploads/{session_id}/{filename}` 模式；需 **路径规范化 + 前缀校验**，禁止 `..` 穿越。
- **产出区**：建议对称提供 `GET /api/session-output/{session_id}/{...}`（或等价路径），仅允许落在 `output/<session_id>/` 已解析根之下。
- 推送给前端的 `ArtifactRef` 应包含 **可 fetch 的 `url`**、**展示用 `label`/`path`**、**`mime_type`**；大文件走下载分支时由前端根据大小或类型切换 UI。

---

## 5. 安全策略（摘要）

### 5.1 逻辑层

- **session_id** 仅表示工作区；**触发执行**前须校验：当前连接 / 当前主体有权操作该 session（与「仅活跃 session 可上传」同思路）。
- **Tools / skills 白名单**：仅允许注册过的工具入口；避免开放任意 shell。
- 可选：**首次执行**、**网络访问**、**读 uploads 外路径** 时 UI 二次确认。

### 5.2 执行隔离

- 代码在 **沙箱 / 子进程 / 容器** 中运行；**禁止**在 Web 进程内直接执行不可信字符串。
- **资源上限**：CPU、wall clock、内存、子进程数、`output` 目录总大小、单文件大小。
- **网络**：默认断网或域名白名单；若需访问公共数据库，单独开关 + 审计日志。
- **密钥**：不把宿主 `.env` API key 注入沙箱；若需调云 API，由宿主侧代理，不把 key 交给用户脚本。

### 5.3 路径与 HTTP

- 所有文件 API：`realpath` / `relative_to` 校验前缀在 **session 根或明确允许的根** 下。
- 若服务暴露在非本机，需 **token 或会话绑定**，防止枚举 `session_id` 读取他人 `output`。

### 5.4 内容安全

- 模型生成代码不可信：必须在沙箱内执行。
- 对 **压缩包、反序列化格式**（如 pickle）声明策略：默认不自动解压不信任归档，或限制大小与解压路径。

### 5.5 可观测性

- 每次执行记录：`session_id`、工具名、命令/入口摘要、耗时、`exit_code`、**写出文件列表**、stdout/stderr 摘要，便于与 artifact 列表交叉核对。

---

## 6. 与当前代码库的关系

- **现状**（以仓库为准）：`src/openharness/web/server.py` 主要为 **HTTP + WebSocket + 流式 chat**；上传落在 `uploads/<session_id>/`；**无**通用 tools/skills 执行与 `output/` 写入。
- **演进**：执行与产出应落在**独立模块**（子进程 / 沙箱桥），由宿主在 tool 路径上调用；聊天循环只负责编排与向前端发送 **transcript / tool / artifact** 事件。

---

## 7. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-04-17 | 初版：整合会话 I/O、安全边界与产品四则（覆盖策略、多步版本、失败仍展示、大文件仅下载）。 |
