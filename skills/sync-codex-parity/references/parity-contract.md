# Kuraka Codex Parity Contract

## Authority and Scope

Claude-source framework content remains authoritative. Codex support is a
deterministic projection of that content, implemented in the Codex branches of
`kuraka-mount.py` and `kuraka-export.py`. Antigravity output is independent and
must not be repurposed as Codex output merely because layouts look similar.

Use this contract after changes under `agents/`, `skills/`, `commands/`,
`rules/`, `kuraka-artifacts/`, `MODEL-ROUTING.yaml`, or lifecycle scripts.

## Required Semantic Mapping

| Kuraka concern | Claude source | Codex projection |
| --- | --- | --- |
| Specialist agent | `agents/<name>.md` | Native agent definition with a stable name, description, model policy, and full `developer_instructions` |
| Reusable workflow | `skills/<name>.md` or `skills/<name>/SKILL.md` | `SKILL.md` directory discovered by the installed Codex CLI |
| User-invoked command | `commands/<name>.md` | Project `SKILL.md`, invoked as `$name` or selected through `/skills`; no custom `/name` dependency |
| Project governance | root rules and instructions | Root or nearest `AGENTS.md` with applicable project instructions |
| Model policy | `MODEL-ROUTING.yaml` | Generated model and effort selection; never a hand-maintained duplicate |
| Artifact contracts | `kuraka-artifacts/` | Referenced paths, schemas, and validation gates in agent or skill instructions |

## Orchestration Requirements

For each changed specialist or workflow, retain these semantics in Codex:

1. Entry condition: required context, input files, and phase.
2. Execution: expected scope, tools, and allowed delegation.
3. Exit condition: artifact path, validation, and success criteria.
4. Handoff: next agent or workflow and data to pass.
5. Escalation: ambiguous requirements, failed checks, or missing dependencies.

Do not translate only prose. Codex needs explicit instructions to delegate and
to preserve phase gates because an agent filename alone does not create a
workflow engine.

## Destination and Collision Policy

Codex layouts vary by installed version. Test the actual CLI after mounting.
Use `.codex/agents/*.toml` for native Codex agents. Keep skills in a directory
containing `SKILL.md` and choose the discovered project skill path deliberately.

`.agents/` may already be owned by Antigravity. Do not write Codex content there
unless the mount establishes explicit coexistence and ownership rules. A
Codex-compatible `.codex/skills` projection is preferable to overwriting an
Antigravity-owned `.agents/skills` tree.

## Change Matrix

| Source change | Update and verify |
| --- | --- |
| Agent instructions | Codex agent renderer, native TOML, session-model inheritance, effort mapping, artifact and handoff behavior |
| Skill workflow | Codex skill projection and all referenced agent, command, and artifact paths |
| Command | Codex command-skill translation, `$name` invocation wording, and phase transitions |
| Rule or policy | Applicable `AGENTS.md`, generated developer instructions, and precedence behavior |
| Model routing | Routing check plus every generated Codex agent affected by session-model inheritance and effort mapping |
| Mount/export code | Target isolation, dry-run or fixture output, and no changes to Claude/Antigravity trees |

## Acceptance Criteria

- Codex output is parseable, discoverable, and usable by the installed CLI.
- Every changed Claude workflow has an intentional Codex representation or a
  documented, user-visible gap.
- Claude and Antigravity fixture outputs are unchanged for Codex-only work.
- Structural tests cover generated paths and metadata, not only source files.
- No target-project override, credential, or user-authored instruction is lost.
- Codex lifecycle operations never delete or reapply Claude-owned overrides.
