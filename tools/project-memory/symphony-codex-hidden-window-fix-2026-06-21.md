# Symphony Codex Hidden Window Fix

Date: 2026-06-21

Mini Orchestrator observed visible Windows console windows created by Symphony
when launching `codex app-server -c shell_environment_policy.inherit=all`.

Root cause: the local Symphony Windows launch path could fall back to
`cmd.exe /c codex app-server ...` when Elixir did not discover the npm
`codex.cmd` shim. That fallback starts visible console windows.

Local fix applied in `D:\AI\symphony\elixir`:

- `lib/symphony_elixir/codex/app_server.ex` now searches the user npm shim at
  `%APPDATA%\npm\codex.cmd` and starts `node.exe ...\@openai\codex\bin\codex.js`
  directly before falling back to `cmd.exe`.
- `bin/symphony` was rebuilt with `mise exec -- mix escript.build`.
- Symphony was restarted hidden in the background.
- Old visible `cmd.exe -> node -> codex.exe` app-server chains with
  `shell_environment_policy.inherit=all` were stopped.

Verification:

- `GET http://127.0.0.1:4000/api/v1/state` returned healthy Symphony counts.
- `GET http://127.0.0.1:8000/api/daemon/runs?source=combined` returned both
  dispatcher and Symphony sources available.
- No remaining process matched
  `cmd.exe /c "codex app-server -c shell_environment_policy.inherit=all"`.

Test caveat: focused Symphony tests were attempted, but the current Windows test
environment still fails existing path/symlink/`sh` cases unrelated to this
launch hardening.

Update, 2026-06-22:

- User observed a visible Codex vendor console window even after the direct
  `node.exe ...\@openai\codex\bin\codex.js` launch path.
- Added the Windows `:hide` port option only to the direct local Codex node
  launch path in `D:\AI\symphony\elixir\lib\symphony_elixir\codex\app_server.ex`.
  Shell fallback commands and remote SSH worker launches remain unchanged.
- Rebuilt `D:\AI\symphony\elixir\bin\symphony` with
  `mise exec -- mix escript.build`.
- Verified `Port.open({:spawn_executable, node}, [:hide, ...])` with a real
  `node` process returns `ok` and `exit=0`.
- Existing visible windows belong to already-running app-server processes and
  require a Symphony/Codex worker restart to disappear.

Restart verification, 2026-06-22:

- Stopped the Symphony daemon listener on port 4000 and cleaned 530 old
  `node.exe/codex.exe app-server --stdio` worker processes from the development
  machine.
- Restarted Symphony with `Start-Process ... -WindowStyle Hidden` using the
  rebuilt `bin/symphony`.
- Verified `GET http://127.0.0.1:4000/api/v1/state` returned a fresh state:
  `running=0`, `retrying=0`, `blocked=0`, `completed=0`, tokens `0`.
- Ran a real Mini-owned smoke through Mini -> Symphony:
  `symphony-gateway-ce240599c29f`, status `done`.
- Verified Symphony retained the completed issue
  `MO-mini-orchestrator-hidden-window-smoke-1-hidden-window-smoke-agent` and
  Mini's Symphony monitor card shows `model=gpt-5.5`, `stageModel=gpt-5.5`.
