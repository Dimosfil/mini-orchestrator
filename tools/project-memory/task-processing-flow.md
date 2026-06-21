# Task Processing Flow

Date: 2026-06-20

This diagram describes the current Mini Orchestrator task-processing flow.
The user confirms an execution mode before running an approved task. Dispatcher
and Symphony both receive the selected chain preset. The chain is not
hard-coded: `Planner -> Executor -> Reviewer` is only the default example
preset, and saved presets may contain any approved number of configured agents
and stages.

```mermaid
flowchart TD
    A["User enters task in Mini Orchestrator Web UI"] --> B["Select executable chain preset"]
    B --> C["Load agent settings from cards/presets"]
    C --> X["Confirm execution mode"]
    X --> D{"User approves run?"}

    D -- "No" --> E["Task stays as draft/plan preview"]
    D -- "Yes + Dispatcher" --> F["POST /api/dispatcher/run"]
    D -- "Yes + Symphony" --> SF["POST /api/symphony/runs"]

    F --> G["Backend creates one task card"]
    G --> H["Status: In Progress"]
    H --> I["Save task and chain preset in SQLite"]

    I --> J["Dispatcher starts selected preset"]
    J --> K["Agent stage 1"]
    K --> L["Agent stage 2"]
    L --> M["Agent stage N"]

    K --> K1["Codex app-server thread"]
    L --> L1["Codex app-server thread"]
    M --> M1["Codex app-server thread"]

    K1 --> N["Dispatcher JSONL/events"]
    L1 --> N
    M1 --> N

    N --> O["Live Runs parser"]
    O --> P["Dashboard task card"]
    P --> P1["Current agent"]
    P --> P2["Stages"]
    P --> P3["Tokens"]
    P --> P4["Outputs/artifacts"]

    P --> Q{"Reviewer result"}
    Q -- "Ready result" --> R["Human Review"]
    Q -- "Error, blocked, stale" --> S["Blocked/Stale/Error"]

    R --> T{"User decision"}
    T -- "ToDone" --> U["Done"]
    T -- "Rework" --> V["Return to review/rework flow"]

    subgraph RuntimeStorage["Runtime storage"]
        DB[".mini_orchestrator/runtime.sqlite3"]
        FS[".mini_orchestrator/test-runs/"]
    end

    I --> DB
    G --> DB
    N --> DB
    L --> FS

    subgraph SymphonyLayer["Symphony execution/observability layer"]
        SY0["Resolve symphony service via GI config-service"]
        SY1["Start/verify Symphony with service startup command"]
        SY2["GET /api/v1/state"]
        SY3["Live Runs Combined/Symphony snapshot"]
        SY4["Read endpoints.contract"]
        SY5["Build agentTasks[] from selected preset"]
        SY6{"Intake endpoint documented?"}
        SY7["POST endpoints.taskIntake / agentIntake / intake"]
        SY8["Visible blocked gateway run"]
    end

    SY0 --> SY1 --> SY2 --> SY3
    SY3 --> P
    SF --> SY4 --> SY5 --> SY6
    SY6 -- "Yes" --> SY7 --> P
    SY6 -- "No" --> SY8 --> P
```

## Current responsibilities

- Dispatcher executes approved tasks through the selected chain preset.
- Symphony mode converts the selected preset into one `agentTasks[]` item per
  configured preset agent and submits it only through a documented intake
  endpoint.
- `Planner -> Executor -> Reviewer` is the default example, not a fixed
  workflow.
- A preset may contain any approved number of configured agents/stages.
- Agent models and behavior come from saved card/chain presets.
- Mini Orchestrator keeps one visible task card while a chain is running.
- SQLite stores runtime state except generated runnable artifacts.
- `test-runs/` stores generated release/demo artifacts.
- Symphony must be running and visible, but currently provides read-only
  daemon observability, not task execution.
