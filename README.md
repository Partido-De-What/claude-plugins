# chatroom: agents that have to prove it

**Put your agents in one room and watch them work. Or hand them one file and a number to beat.**

By **Adrian Ciprian Iancu** ([GitHub](https://github.com/ArtyomITA) · [Hugging Face](https://huggingface.co/adriandj3) · [LinkedIn](https://www.linkedin.com/in/adrian-ciprian-iancu-a2a477391) · [site](https://artyomita.github.io/))

[![chatroom](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPartido-De-What%2Fclaude-plugins%2Fmain%2Fplugins%2Fchatroom%2F.claude-plugin%2Fplugin.json&query=%24.version&label=chatroom&color=2ea44f)](plugins/chatroom)
[![Claude Code](https://img.shields.io/badge/Claude_Code-marketplace-D97757?logo=claude&logoColor=white)](https://code.claude.com)
[![Codex](https://img.shields.io/badge/Codex-marketplace-10A37F)](https://developers.openai.com/codex)
[![papers](https://img.shields.io/badge/built_on-26_papers-B31B1B?logo=arxiv&logoColor=white)](#the-papers-behind-it)
[![license](https://img.shields.io/github/license/Partido-De-What/claude-plugins?color=blue)](LICENSE)
[![last commit](https://img.shields.io/github/last-commit/Partido-De-What/claude-plugins?color=orange)](https://github.com/Partido-De-What/claude-plugins/commits/main)
[![stars](https://img.shields.io/github/stars/Partido-De-What/claude-plugins?style=social)](https://github.com/Partido-De-What/claude-plugins/stargazers)

Give several coding agents the same task and they will agree with each other, call it done and move on. I wanted a team that argues, shows its evidence and cannot close until the proof is there, so I wrote those rules in code instead of asking nicely in a prompt.

```console
$ echo "CLOSED v2" | chat.py post --as ALFA
error: PLAN v2 cannot be closed yet: no vote yet from BETA, GAMMA. Nothing was posted.

$ chat.py task done T1 --proof "looks fine" --as BETA
error: a proof must name what shows it works: a command and its exit code, tests passed, file:line, #message, a hash, a path or a link
(task done ID --proof "pytest -q: 12 passed, exit 0"). What you did not do goes in --gaps. Nothing was closed.

$ chat.py lock acquire bench --as BETA
lock bench is held by ALFA (29 min left), you are in queue at place 1: end your turn, the room tags you when it is yours
```

## Two rooms

| | A room | A research room |
|---|---|---|
| **You give it** | A topic or a job | One file, an evaluator, a number to beat |
| **The team** | Agents you pick, with a lead | Fixed roles: workers, proposer, auditor, registrar, searchers |
| **The rules** | Plans, votes with evidence, tasks with proof of done, leases, locks | Phases with gates, a sealed evaluator, a worktree per worker, repeated measures, a final run on held-out data |
| **Who checks** | `chat.py`, the same for every agent | A kernel that measures every attempt the same way and keeps the books, all night if you like |

Both run in **Claude Code** and in **Codex**. Spawn mode adds roles on free external models.

## What you get to watch

- A live group chat with no turns: agents write when they have something to say, and you write to all of them from the same page.
- A 3D voxel office next to it, where you see who is coding, who is reading and who is waiting for you. It has a lounge, games, an arena and an arcade cabinet you can play with a friend.
- A relay that wakes the lead only when something needs it, with the rest in one digest at the next wake.
- `chat.py cost`: what each agent really spent, read from its transcript.

## Install

In Claude Code:

```text
/plugin marketplace add Partido-De-What/claude-plugins
/plugin install chatroom@artyomita-plugins
```

Then start a room with `/chatroom:start <topic>`.

In Codex:

```bash
codex plugin marketplace add Partido-De-What/claude-plugins
codex plugin add chatroom@artyomita-plugins
```

Then, in a new thread, ask Codex to open a chatroom on your topic.

Every mechanism is listed point by point in the **[chatroom README](plugins/chatroom/README.md)**.

## The papers behind it

These papers shaped the plugin, and each row is something they changed in the code. All are arXiv preprints.

### chatroom

| Paper | What it changed |
|---|---|
| Destefanis et al., [When Agents Coordinate: Measuring Coordination in Multi-Agent AI Coding](https://arxiv.org/abs/2608.16801) | Work goes through the board and files, with one-line return reports and no round of introductions |
| Yang et al., [When Parallelism Pays Off: Cohesion-Aware Task Partitioning for Multi-Agent Coding](https://arxiv.org/abs/2606.00953) | Tasks are split along their declared files |
| Weinberger et al., [Token Reduction Is Not Cost Reduction](https://arxiv.org/abs/2607.12161) | Compression stays off by default and never runs as a proxy; `chat.py cost` measures instead |
| Wang et al., [Do We Need Complex Topology Control? Distinct-Peer Random Routing Improves Cost-Efficiency in Sparse Multi-Agent Debate](https://arxiv.org/abs/2609.27150) | Two votes at most on a plan, then the lead decides |
| Zerhoudi et al., [The Compaction Cliff in Long-Running AI Agent Memory](https://arxiv.org/abs/2608.22752) | `notebook --rule`: rules kept word for word through a compaction |
| Liu, [What Does Context Compression Cost an Agent? Interaction Costs Unrevealed by Task-Completion Metrics](https://arxiv.org/abs/2608.16370) | The notebook keeps rules and diary apart; only the diary may be summarised |
| Liu et al., [SoL-Pi: Recursively Scaling Auto-Research Loops for Efficient Agent Harness](https://arxiv.org/abs/2609.20519) | Only huge tool outputs get trimmed, keeping the failures and the tail |
| Mendoza et al., [Persistent LLM Orchestration of Heterogeneous Robot Teams via Partial Delegation to Multi-Agent Protocols](https://arxiv.org/abs/2610.15224) | `recap` rebuilds the lead's picture from the room's files, and the lead wakes on events |

### research

| Paper | What it changed |
|---|---|
| Lange et al., [The Agentic Scientist: Orchestrating Coding Agents for Automated Scientific (Co-)Discovery](https://arxiv.org/abs/2610.18933) | Phases with gates, fixed roles, the sealed evaluator |
| Wang et al., [Harness-Search: Guiding Long-Horizon Search through Multi-Agent Coordination](https://arxiv.org/abs/2610.05382) | The auditor and its verdicts at the gates |
| Zhang et al., [PatchBoard: Schema-Grounded State Mutation for Reliable and Auditable LLM Multi-Agent Collaboration](https://arxiv.org/abs/2605.29313) | Agents propose; only the kernel and the registrar write the state |
| Li et al., [MemTX: Transactional Belief Commit for Stateful Agent Memory](https://arxiv.org/abs/2607.23929) | Evidence stays tentative until it is curated, and a revoke withdraws what cited it |
| Tang et al., [AI Research Agents Narrow Scientific Exploration](https://arxiv.org/abs/2605.27905) | Ideas alternate between gap and analogy, and near-duplicates are refused |
| Liu et al., [IdeaScientist: Orchestrating Agents for Grounded Scientific Ideation](https://arxiv.org/abs/2610.04074) | Each idea comes as a full bundle, with its prior work |
| Virk et al., [SwarmResearch: Orchestrating Coding Agents for Open-Ended Discovery](https://arxiv.org/abs/2607.02807) | One branch per idea, explorers and optimizers, the lead as a shepherd |
| Zhao et al., [ScienceFlow: A long-horizon agent for ML research, scientific discovery and beyond](https://arxiv.org/abs/2608.14354) | A tag for every attempt and `reanchor` to restart from an old state |
| Pelleriti et al., [What Do Evolutionary Coding Agents Evolve?](https://arxiv.org/abs/2605.20086) | Detectors for cycling and tuning-only runs |
| Cui et al., [ARAC: Benchmarking Auto-Research's Alignment and Completeness on End-to-End Researchs](https://arxiv.org/abs/2608.12788) | The auditor's rubric, phase by phase |
| Ding et al., [Autonomous Research Agents: A Survey of AI Scientists and the Verification Gap](https://arxiv.org/abs/2608.05179) | The report's verifiability checklist |
| Hu et al., [The Winner's Curse in LLM Self-Improvement Loops: Selection Noise, Lock-in, and Acceptance Rules](https://arxiv.org/abs/2610.09239) | The best's margin in sigma and a run on fresh seeds in the report |
| Huang et al., [RealisticTritonBench: A Benchmark for Triton-Kernel Generation in Real-World AI Frameworks](https://arxiv.org/abs/2608.12004) | The contract template for kernels: fresh inputs at each iteration |
| Feng et al., [KREX: Concurrent Kernel Benchmarking on Shared GPUs via Region-Granular Exclusivity](https://arxiv.org/abs/2609.30057) | The same template: no side streams, noise thresholds |
| Prasad et al., [BAITBENCH: Measuring Agent Reward Hacking with Optional Shortcuts Planted in ML Tasks](https://arxiv.org/abs/2608.30724) | A canary task with a planted shortcut, to test the room before trusting it |
| Yu et al., [Beyond Execution: Auditing Experimental Fidelity in LLM-Driven Scientific Research](https://arxiv.org/abs/2608.26753) | A precheck on the data and the declared steps |
| Chen, [When Does Combining Language Models Help? A Co-Failure Ceiling on Routing, Voting, and Mixture-of-Agents Across 67 Frontier Models](https://arxiv.org/abs/2606.27288) | `research panel` asks many free models and takes no vote |
| Fadnavis et al., [Beyond Consensus: Trace-Level Synthesis in Mixture of Agents](https://arxiv.org/abs/2605.29116) | The panel keeps every answer whole, so an agent can read them all |

The first loop of the research kernel, one file and a fixed evaluator with a commit when the number improves, comes from Andrej Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

## Cite

```bibtex
@software{iancu_chatroom_2026,
  author = {Iancu, Adrian Ciprian},
  title  = {chatroom: a live room and a research kernel for coding agents},
  year   = {2026},
  url    = {https://github.com/Partido-De-What/claude-plugins}
}
```

## Find me

[GitHub](https://github.com/ArtyomITA) · [Hugging Face](https://huggingface.co/adriandj3) · [LinkedIn](https://www.linkedin.com/in/adrian-ciprian-iancu-a2a477391) · [YouTube](https://www.youtube.com/@artyomadriandj3) · [Instagram](https://www.instagram.com/artyomita) · [TikTok](https://www.tiktok.com/@artyomita) · [site](https://artyomita.github.io/)

## License

[AGPL-3.0-only](LICENSE). Versions up to 0.12.1 stay available under MIT; third-party credits are in [NOTICE](plugins/chatroom/NOTICE).
