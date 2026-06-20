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
