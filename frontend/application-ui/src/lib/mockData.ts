/**
 * Mock fixtures used in place of the real OpenHarness backend.
 *
 * These drive the UI enough that you can visually verify all components
 * (sidebar / welcome card / message list / tool blocks / artifact panel /
 * permission modal / status panel) without running a Python process.
 */

import type { LucideIcon } from "lucide-react";
import { Compass, FileText, GitPullRequestArrow, TestTubeDiagonal } from "lucide-react";
import type {
  AppStateSnapshot,
  McpServerSnapshot,
  SelectOptionPayload,
  TaskSnapshot,
} from "../types/protocol";
import type { SessionSummary } from "../components/SessionItem";

export const MOCK_APP_STATE: AppStateSnapshot = {
  model: "kimi-k2-turbo-preview",
  cwd: "/Users/you/projects/openharness",
  provider: "Moonshot (Kimi)",
  auth_status: "ok",
  base_url: "https://api.moonshot.cn/v1",
  permission_mode: "default",
  theme: "dark",
  vim_enabled: false,
  voice_enabled: false,
  voice_available: false,
  voice_reason: "",
  fast_mode: false,
  effort: "medium",
  passes: 1,
  mcp_connected: true,
  mcp_failed: false,
  bridge_sessions: 0,
  output_style: "default",
  keybindings: {},
};

export const MOCK_COMMANDS: string[] = [
  "/help",
  "/clear",
  "/resume",
  "/plan",
  "/commit",
  "/review",
  "/compact",
  "/permissions",
];

export const MOCK_TASKS: TaskSnapshot[] = [
  {
    id: "t-1",
    type: "agent",
    status: "running",
    description: "Collecting repository structure",
    metadata: {},
  },
  {
    id: "t-2",
    type: "shell",
    status: "completed",
    description: "pytest -q (114 passed)",
    metadata: {},
  },
];

export const MOCK_MCP_SERVERS: McpServerSnapshot[] = [
  {
    name: "filesystem",
    state: "connected",
    transport: "stdio",
    auth_configured: false,
    tool_count: 6,
    resource_count: 0,
  },
  {
    name: "github",
    state: "connected",
    transport: "http",
    auth_configured: true,
    tool_count: 12,
    resource_count: 4,
  },
];

/**
 * Sidebar history starts empty so a fresh user sees the real empty state.
 * Example prompts that used to live here have moved to `EXAMPLE_PROMPTS`
 * and are rendered on the welcome screen.
 */
export const MOCK_SESSIONS: SessionSummary[] = [];

export const MOCK_SELECT_OPTIONS: SelectOptionPayload[] = [];

/**
 * Showcase prompts rendered as cards on the welcome screen. Clicking a
 * card submits the `prompt` string as if the user had typed it.
 */
export interface ExamplePrompt {
  title: string;
  description: string;
  prompt: string;
  icon: LucideIcon;
}

export const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  {
    title: "Explore the codebase",
    description: "Scan the repo layout and summarise what each top-level folder does.",
    prompt:
      "Give me a tour of this repository. Summarise what each top-level folder is for and call out anything unusual.",
    icon: Compass,
  },
  {
    title: "Draft project docs",
    description: "Write a README section that explains the new Application UI.",
    prompt:
      "Draft a README section that introduces the new Application UI: what it is, how to run it, and how it talks to the backend.",
    icon: FileText,
  },
  {
    title: "Run tests & debug",
    description: "Execute the test suite and triage the failures for me.",
    prompt:
      "Run the project's test suite, then summarise which tests failed and the most likely root cause for each.",
    icon: TestTubeDiagonal,
  },
  {
    title: "Review recent changes",
    description: "Read the latest diff and flag anything risky before I commit.",
    prompt:
      "Review my uncommitted changes. Flag anything risky, unclear, or missing a test, and suggest a commit message.",
    icon: GitPullRequestArrow,
  },
];
