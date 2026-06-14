# MedClaw

**MedClaw** 是一个基于 [OpenHarness](https://github.com/HKUDS/OpenHarness) 构建的生物信息学 GUI Agent 应用。

English version: [README_EN.md](README_EN.md)

<p align="center">
  <img src="assets/branding/MedClaw_Logo.png" alt="MedClaw Logo" width="320">
</p>

<!-- Demo video placeholder -->
## Demo

<p align="center">
  <img src="assets/demo/sample_demo.gif" alt="MedClaw sample demo" width="100%">
</p>

样例：MedClaw 可以把一个给定的蛋白-配体结构自动解析成一份包含结合口袋、关键相互作用、突变影响和优化建议的药物发现报告。若需观看更清晰的演示视频，可打开 [`assets/demo/sample_demo.mp4`](assets/demo/sample_demo.mp4)。

## Application UI（浏览器界面）

MedClaw 附带一个完整的浏览器图形界面（Application UI），位于 `frontend/application-ui/`。它是与 Agent 交互的主要方式，支持聊天会话、文件上传、Artifact 预览、设置管理等功能。

### 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                    浏览器 (http://localhost:5173)              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  React 18 + TypeScript + Tailwind v4                     │ │
│  │  · CodeMirror 编辑器（Artifact 预览）                      │ │
│  │  · Radix UI 组件 + shadcn 样式                             │ │
│  │  · react-markdown（Markdown 渲染）                         │ │
│  │  · react-resizable-panels（聊天 / Artifact 分栏）           │ │
│  └──────┬──────────────┬────────────────────────────────────┘ │
│         │ WebSocket     │ HTTP REST                            │
│         │ (/ws)         │ (/api/upload, /api/session-export…)   │
└─────────┼──────────────┼────────────────────────────────────────┘
          │              │
┌─────────┼──────────────┼────────────────────────────────────────┐
│  Vite   ▼              ▼                                        │
│  Dev    ┌──────────────────────────┐                             │
│  Proxy  │  /ws → ws://127.0.0.1:8765                            │
│         │  /api → http://127.0.0.1:8765                         │
│         └──────────┬───────────────┘                             │
└────────────────────┼────────────────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────────────────┐
│  Python Backend    ▼                                             │
│  (Starlette + uvicorn, port 8765)                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ · WebSocket 协议： assistant_delta / tool_started / ...     │ │
│  │ · REST 端点：/upload, /session-output, /artifacts           │ │
│  │ · 会话持久化（Session JSON 文件）                             │ │
│  │ · 文件上传服务（600 MB 上限）                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  启动命令:                                                        │
│    oh web --port 8765                                             │
│    python -m openharness.web --port 8765                         │
└──────────────────────────────────────────────────────────────────┘
```

**核心数据流：**

1. **WebSocket 连接** — 浏览器连到 `/ws`，发送 JSON 指令（`submit_line`、`new_session` 等），后端流式返回事件（`assistant_delta` 实时补全、`tool_started` 工具调用、`transcript_item` 对话条目等）。
2. **REST API** — 文件上传走 `POST /api/upload`，会话输出/导出走 `GET /api/session-output/{id}` 和 `GET /api/session-export/{id}`。
3. **代理转发** — 开发时 Vite dev server 将 `/ws` 和 `/api` 代理到后端端口（默认 `8765`），浏览器只需与 `localhost:5173` 同源通信。
4. **协议一致性** — 前后端共享同一套协议类型定义：TypeScript 端在 `frontend/application-ui/src/types/protocol.ts`，Python 端在 `src/openharness/ui/protocol.py`。

### 启动方式

**完整模式（后端 + 前端开发服务器）：**

```bash
scripts/dev_application_ui.sh
```

这会同时启动 Python 后端（port `8765`）和 Vite 前端开发服务器（port `5173`）。

**仅后端（供独立前端或生产构建使用）：**

```bash
# 使用 CLI
oh web --port 8765

# 或直接使用 Python 模块
python -m openharness.web --port 8765
```

**仅前端 Mock 模式（无需后端，独立验证 UI 布局）：**

```bash
cd frontend/application-ui
npm install
npm run dev
```

打开 `http://localhost:5173`。所有后端调用均被 Mock 数据替代，适合快速迭代 UI 组件。

### 前端构建产物

生产构建可由 Vite 生成，并部署到任意静态服务器：

```bash
cd frontend/application-ui
npm run build     # 输出到 frontend/application-ui/dist/
```

### 后端 CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | `8765` | 后端端口 |
| `--host` | `127.0.0.1` | 监听地址 |
| `--model` | 环境变量 | 模型名称（如 `gpt-4.1`） |
| `--base-url` | 环境变量 | API 基础 URL |
| `--api-key` | 环境变量 | API 密钥 |
| `--provider` | 环境变量 | 提供商标签（如 `OpenAI`、`DeepSeek`） |

所有 CLI 参数均有对应的环境变量回退（`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENHARNESS_MODEL` 等）。

### 配置

1. 复制 `.env.example` 为 `.env`，填入 API 密钥：
   ```bash
   cp .env.example .env
   ```
2. 后端自动读取根目录 `.env` 文件；前端环境变量在 `frontend/application-ui/.env` 中配置。
3. 前端 WebSocket 地址解析顺序：UI 设置面板覆盖 → `VITE_OH_WS_URL` 环境变量 → `ws://<当前域名>/ws`（代理默认）。

### 协议参考

- **前端 → 后端**：`submit_line`（发送消息）、`new_session`（新建会话）、`load_session`（恢复历史）、`session_control`（停止运行）、`permission_response`（权限响应）等。
- **后端 → 前端**：`assistant_delta`（流式文本）、`assistant_complete`（回复结束）、`tool_started`（工具调用开始）、`tool_completed`（工具调用完成）、`transcript_item`（对话条目）、`state_snapshot`（状态快照）等。

完整协议定义见 `frontend/application-ui/src/types/protocol.ts` 和 `src/openharness/ui/protocol.py`。

## Quick Start

Choose your platform:

- [macOS](#macos)
- [Windows (PowerShell)](#windows-powershell)

### macOS

> macOS only. The commands below assume a Unix-like shell on macOS.

下面的流程面向第一次把仓库 `git clone` 到本地的用户。完成后，你会得到一个带 GUI 的 MedClaw，并让前端 Agent 通过 OpenSandbox 使用本地 Docker 提供的 `bioinformatics` 生信环境。

开始之前，可以先看一遍下面这个 Mac Quick Start 演示视频：

<video src="assets/demo/mac_demo.mp4" controls preload="metadata" width="100%">
  你的环境不支持直接播放该视频，可改为打开下方 MP4 链接。
</video>

如果视频无法直接播放，可直接打开 [`assets/demo/mac_demo.mp4`](assets/demo/mac_demo.mp4)。

#### 1. 检查本机前置环境

先确认这些工具已经装好：

- Python `>= 3.10`
- Node.js `>= 18`
- Docker Desktop

可以先执行：

```bash
python --version
node -v
npm -v
docker version
docker info
```

#### 2. Clone 仓库并进入项目根目录

```bash
git clone <你的仓库地址> MedClaw
cd MedClaw
```

如果你已经 clone 过仓库，就直接 `cd` 到项目根目录即可。

#### 3. 检查并准备生信 Docker Image

MedClaw 默认使用 `bioinformatics` sandbox 环境，对应镜像：

```text
openharness/sandbox-bioinformatics:latest
```

默认环境配置位于：

```text
src/openharness/sandbox/default_envs.yaml
```

先检查这个镜像是否已经存在：

```bash
docker image ls | grep openharness/sandbox-bioinformatics
```

如果上面没有看到 `openharness/sandbox-bioinformatics:latest`，就先构建：

```bash
docker build -t openharness/sandbox-bioinformatics:latest \
  -f src/openharness/sandbox/Dockerfile src/openharness/sandbox
```

这里检查的是 Docker `image`，不是先看有没有已经运行中的 `container`。

这一步建议尽量提前完成，因为 `bioinformatics` image 是整个 sandbox 运行底座里最关键的一层。

#### 4. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e '.[opensandbox]'
pip install opensandbox-server

npm --prefix frontend/application-ui install
python -m playwright install chromium
```

说明：

- `.[opensandbox]` 会安装 GUI 后端和 OpenSandbox SDK 所需依赖
- `opensandbox-server` 单独安装，供本地 Docker sandbox 服务使用
- `python -m playwright install chromium` 会下载 Playwright 使用的 Chromium 浏览器二进制

#### 5. 配置模型 API

先复制一份环境变量模板：

```bash
cp .env.example .env
```

然后编辑 `.env`，至少填这几项：

```bash
OPENAI_API_KEY=你的_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1
OPENHARNESS_MODEL=gpt-4.1
```

如果你使用的是 OpenAI-compatible 服务，也可以改成对应配置。例如 DeepSeek V4 Flash：

```bash
OPENAI_API_KEY=你的_DeepSeek_API_Key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENHARNESS_MODEL=deepseek-v4-flash
OPENHARNESS_PROVIDER=DeepSeek
```

`scripts/dev_application_ui.sh` 会在启动时自动读取项目根目录下的 `.env`。

#### 6. 启动 OpenSandbox Server

打开第一个终端窗口并执行：

```bash
cd MedClaw
source .venv/bin/activate
opensandbox-server
```

如果看到端口占用错误，例如 `127.0.0.1:8081 already in use`，说明你可能已经起过一个 `opensandbox-server`，这时不要重复启动，直接继续下一步即可。

#### 7. 启动 GUI

再打开第二个终端窗口并执行：

```bash
cd MedClaw
source .venv/bin/activate
scripts/dev_application_ui.sh
```

这个脚本会同时启动：

- GUI 后端：`python -m openharness.web`
- 前端开发服务器：Vite (`http://localhost:5173`)

#### 8. 打开浏览器

在浏览器打开：

```text
http://localhost:5173/
```

首次进入后，你可以先复制下面这段 prompt 到前端里测试：

```text
请先查看当前可用的 sandbox 环境，并进入 `bioinformatics` sandbox。

然后在这个容器里做一次“生信环境盘点”，要求如下：

1. 不要猜测，必须通过实际命令检查。
2. 分别检查并汇总下面几类工具/包是否已安装，以及版本号：
   - Python
   - R
   - 常见命令行生信工具：samtools, bcftools, bedtools, bwa, bowtie2, minimap2, blastn, fastqc, multiqc, seqkit
3. 对每个工具明确标注：
   - 已安装 + 版本
   - 未安装
4. 请把结果整理成一个清晰的 Markdown 报告。
5. 把最终报告保存到：
   `/workspace/output/sandbox_bioinfo_audit.md`

如果可以，也请把你执行过的关键检查命令一起写进报告里，方便我后续复现。
```

#### 后续再次启动

如果依赖和 Docker image 都已经准备好，以后通常只需要：

1. 打开 Docker Desktop
2. 在一个终端里运行 `opensandbox-server`
3. 在另一个终端里运行 `scripts/dev_application_ui.sh`
4. 打开 `http://localhost:5173/`

### Windows (PowerShell)

> Windows only. The commands below assume native Windows, PowerShell, and Docker Desktop.

下面的流程面向第一次把仓库 `git clone` 到本地的用户。完成后，你会在 Windows 原生 PowerShell 环境下启动 GUI，并通过 OpenSandbox + Docker Desktop 使用 `bioinformatics` 沙箱环境。与 macOS 不同，这里不直接使用 `scripts/dev_application_ui.sh`，而是分别启动 OpenSandbox Server、Web 后端和前端 Vite dev server。

开始之前，可以先看一遍下面这个 Windows Quickstart 演示视频：

<video src="assets/demo/win_demo.mp4" controls preload="metadata" width="100%">
  你的环境不支持直接播放该视频，可改为打开下方 MP4 链接。
</video>

如果视频无法直接播放，可直接打开 [`assets/demo/win_demo.mp4`](assets/demo/win_demo.mp4)。

#### 1. 检查本机前置环境

先确认这些工具已经装好：

- Python `>= 3.10`
- Node.js `>= 18`
- Docker Desktop

可以先执行：

```powershell
python --version
node -v
npm.cmd -v
docker version
docker info
```

在继续后续步骤之前，请先手动打开 Docker Desktop，并确认 `docker info` 能正常返回。

如果 `docker version` 或 `docker info` 报错，不要继续后面的 OpenSandbox 步骤，先把 Docker Desktop 启动完成。

#### 2. Clone 仓库并进入项目根目录

```powershell
git clone <你的仓库地址> MedClaw
cd MedClaw
```

如果你已经 clone 过仓库，就直接 `cd` 到项目根目录即可。

#### 3. 检查并准备生信 Docker Image

MedClaw 默认使用 `bioinformatics` sandbox 环境，对应镜像：

```text
openharness/sandbox-bioinformatics:latest
```

默认环境配置位于：

```text
src/openharness/sandbox/default_envs.yaml
```

先检查这个镜像是否已经存在：

```powershell
docker image ls openharness/sandbox-bioinformatics
```

如果上面没有看到 `openharness/sandbox-bioinformatics:latest`，就先构建：

```powershell
docker build -t openharness/sandbox-bioinformatics:latest -f ".\src\openharness\sandbox\Dockerfile" ".\src\openharness\sandbox"
```

这里检查的是 Docker `image`，不是先看有没有已经运行中的 `container`。

这一步建议尽量提前完成，因为 `bioinformatics` image 是整个 sandbox 运行底座里最关键的一层。

#### 4. 创建虚拟环境并安装依赖

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\pip.exe install -e ".[opensandbox]"
.\.venv\Scripts\pip.exe install opensandbox-server

npm.cmd --prefix frontend/application-ui install
.\.venv\Scripts\python.exe -m playwright install chromium
```

说明：

- PowerShell 中如果 `npm` 被执行策略拦住，请直接使用 `npm.cmd`
- `.[opensandbox]` 会安装 GUI 后端和 OpenSandbox SDK 所需依赖
- `opensandbox-server` 单独安装，供本地 Docker sandbox 服务使用
- `.\.venv\Scripts\python.exe -m playwright install chromium` 会下载 Playwright 使用的 Chromium 浏览器二进制

如果后面运行 `opensandbox-server.exe` 时看到 `SyntaxError: source code string cannot contain null bytes`，通常说明当前 `.venv` 已损坏。最稳妥的处理方式是删除 `.venv` 后重新执行本步骤。

#### 5. 准备模型配置

Windows 这里最直接的做法，是在后面启动 Web 后端的那个 PowerShell 窗口里设置环境变量。

如果你使用 OpenAI，可在启动后端时填：

```powershell
$env:OPENAI_API_KEY="你的_API_KEY"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENHARNESS_MODEL="gpt-4.1"
```

如果你使用的是 DeepSeek V4 Flash，可改成：

```powershell
$env:OPENAI_API_KEY="你的_DeepSeek_API_Key"
$env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
$env:OPENHARNESS_MODEL="deepseek-v4-flash"
$env:OPENHARNESS_PROVIDER="DeepSeek"
```

#### 6. 初始化 OpenSandbox 配置

先生成 `C:\Users\<你的用户名>\.sandbox.toml`：

```powershell
$cfg = Join-Path $HOME ".sandbox.toml"
& ".\.venv\Scripts\opensandbox-server.exe" init-config $cfg --example docker
Get-Content $cfg
```

注意：上面这几行要按行执行，不要把 `$cfg = ...` 和后面的 `& ".\.venv\Scripts\opensandbox-server.exe" ...` 粘成同一行。

如果你确实想写成一行，请使用分号：

```powershell
$cfg = Join-Path $HOME ".sandbox.toml"; & ".\.venv\Scripts\opensandbox-server.exe" init-config $cfg --example docker
```

如果你保留默认的空 `server.api_key`，首次启动时需要在同一个窗口输入大写 `YES` 确认继续。

#### 7. 启动 OpenSandbox Server

打开第一个 PowerShell 窗口并执行：

```powershell
cd MedClaw
docker info
$cfg = Join-Path $HOME ".sandbox.toml"
& ".\.venv\Scripts\opensandbox-server.exe" --config $cfg
```

如果出现：

```text
Type 'YES' to continue startup without API key
```

就在同一个窗口输入：

```text
YES
```

看到 `Application startup complete` 或服务开始监听本地端口后，保持这个窗口不要关闭。

如果这里出现端口占用错误，通常说明你已经起过一个 `opensandbox-server`，这时不要重复启动，直接继续下一步即可。

如果这里出现 `DOCKER::INITIALIZATION_ERROR`、`Error while fetching server API version` 或 `CreateFile`，通常表示 Docker Desktop 没启动，或者还没有完全 ready。先确认 Docker Desktop 已打开，并且 `docker info` 能正常返回，再重新执行本步骤。

#### 8. 启动 Web 后端

打开第二个 PowerShell 窗口并执行：

```powershell
cd MedClaw
$env:OPENAI_API_KEY="你的_API_KEY"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENHARNESS_MODEL="gpt-4.1"
$env:PYTHONPATH=(Resolve-Path .\src).Path

.\.venv\Scripts\python.exe -m openharness.web --host 127.0.0.1 --port 8765
```

如果你使用的是 DeepSeek V4 Flash，就把前 3 行改成：

```powershell
$env:OPENAI_API_KEY="你的_DeepSeek_API_Key"
$env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
$env:OPENHARNESS_MODEL="deepseek-v4-flash"
$env:OPENHARNESS_PROVIDER="DeepSeek"
```

#### 9. 启动前端 GUI

打开第三个 PowerShell 窗口并执行：

```powershell
cd MedClaw
npm.cmd --prefix frontend/application-ui run dev -- --port 5173
```

#### 10. 打开浏览器

然后在浏览器打开：

```text
http://localhost:5173/
```

首次进入后，你可以先复制下面这段 prompt 到前端里测试：

```text
请先查看当前可用的 sandbox 环境，并进入 `bioinformatics` sandbox。

然后在这个容器里做一次“生信环境盘点”，要求如下：

1. 不要猜测，必须通过实际命令检查。
2. 分别检查并汇总下面几类工具/包是否已安装，以及版本号：
   - Python
   - R
   - 常见命令行生信工具：samtools, bcftools, bedtools, bwa, bowtie2, minimap2, blastn, fastqc, multiqc, seqkit
3. 对每个工具明确标注：
   - 已安装 + 版本
   - 未安装
4. 请把结果整理成一个清晰的 Markdown 报告。
5. 把最终报告保存到：
   `/workspace/output/sandbox_bioinfo_audit.md`

如果可以，也请把你执行过的关键检查命令一起写进报告里，方便我后续复现。
```

上传文件后，可以让 Agent 在容器中运行分析，并把结果保存到：

```text
/workspace/output
```

写入这里的结果文件会同步回前端，作为 artifact 预览或下载。

#### 后续再次启动

如果依赖、`.sandbox.toml` 和 Docker image 都已经准备好，以后通常只需要：

1. 打开 Docker Desktop
2. 在第一个 PowerShell 窗口里运行 `opensandbox-server`
3. 在第二个 PowerShell 窗口里运行 `python -m openharness.web`
4. 在第三个 PowerShell 窗口里运行前端 `npm.cmd --prefix frontend/application-ui run dev -- --port 5173`
5. 打开 `http://localhost:5173/`

## 项目简介

MedClaw 的目标是让不熟悉命令行的用户，也能通过浏览器界面调用具备生信分析能力的 Agent：上传数据、提出分析需求、查看工具执行过程，并下载生成的结果文件。

本项目在 Vibe Code 的 Agent loop、工具系统、权限机制和会话能力之上，新增了面向生信场景的 Web UI，并结合 OpenSandbox 与本地 Docker，把复杂依赖封装到容器中运行。

## 核心特点

- 通过 GUI 使用 Vibe Code Agent
- 支持文件上传、会话管理与结果 artifact 预览
- 结合本地 Docker / OpenSandbox 执行隔离任务
- 面向生物信息学分析场景，适合运行重依赖或需隔离的程序

底层框架的原始说明见 [README-OpenHarness.md](docs/app/README-OpenHarness.md)。

## 生信工具说明

MedClaw 当前可用的生物信息学能力、内置 skills、sandbox tools、本地绘图工具和公共数据库查询工具，见 [README-bio-tools.md](docs/app/README-bio-tools.md)。
