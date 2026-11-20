# <img src="images/logo-x-plus-icon.svg" width="46" align="middle" alt="" /> Unsloth X+

A fork of [Unsloth](https://github.com/unslothai/unsloth) that keeps the Studio exactly as upstream
ships it and pushes on what runs **under** it: a run can train on a CPU, an integrated GPU or an NPU
as well as a discrete card, and the extra engines (adapter merge/surgery, arch swap, automated
training, lineage) are working code with tests rather than a preview.

> **Branch:** `x+-main`, where this fork is developed. `main` mirrors the imported upstream tree.
> **Synced to:** upstream `main` at `8c5ca83271` (19 Nov 2026).
> **Releases:** [v1.0.0 … v1.5.0](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases)

The Studio front end in `studio/frontend` is **upstream's, unmodified**. The X+ work is backend:
device selection, the training worker, the Labs engines and the installers. If you are looking for
the blue / glass reskin of earlier fork releases, it is gone on purpose — this fork now looks and
behaves like Unsloth.

---

## What X+ changes on top of upstream

| Area | What this fork adds |
| --- | --- |
| **Device selection** | `UNSLOTH_TRAINING_DEVICE` (`cpu`, `igpu`, `npu`, `cuda`, `xpu`, `hip`, `mps`), a device registry with per-device capabilities (`core.training.device_targets`), and a compute-target contract carried into the worker (`core.training.compute_target_env`) |
| **CPU training** | A CPU recipe (CoRA/QLoRA) that runs stock transformers + PEFT, with fp32/bf16 selection from the RAM actually left on the host |
| **Integrated GPUs** | Intel XPU and AMD iGPU paths, an iGPU-safe optimizer, and 4-bit refused (not silently slow) where bitsandbytes has no kernel |
| **NPUs** | Vendor detection for AMD XDNA 2 / Intel / Qualcomm / Apple, FLM runtime readiness, an NPU assist path and a Q4NX export for FastFlowLM |
| **CPU export** | Merged model / adapter / GGUF export through the same code with no accelerator present (`core.export.cpu_export`) |
| **Labs** | Working engines: adapter merge, model surgery, architecture swap, automated training, lineage, run diff, benchmarks |
| **Runs** | Parent-loss early-stop guard, dataset/tokenizer fingerprints that a resume is checked against, disk preflight, run manifests |
| **Telemetry** | An opt-in collector and operator console in `telemetry/` (off unless enabled in Settings) |
| **Installers** | Per-flavour desktop builds (`cpu`, `cpu-npu`, `gpu`, `cpu-gpu`) that pin the runtime they were built as |

The training fork's backend wheel carries a PEP 440 local segment (`unsloth==2026.11.7+xplus.1`) so an
index can never satisfy it with the upstream package of the same base version. `GET /api/health`
reports `backend_build_kind` (`xplus` / `upstream` / `dev`) so a mixed install is visible instead of
guessed at.

---

## Install this fork

```bash
# macOS, Linux, WSL
curl -fsSL https://raw.githubusercontent.com/Goldodemon-Automation/unsloth_X_PLUS/x+-main/install.sh | sh

# Windows (PowerShell)
irm https://raw.githubusercontent.com/Goldodemon-Automation/unsloth_X_PLUS/x+-main/install.ps1 | iex
```

The desktop installers are built and signed by
[`.github/workflows/release-x-plus.yml`](.github/workflows/release-x-plus.yml); release notes are in
[docs/releases/](docs/releases/).

To run the Studio from a checkout:

```bash
git clone -b x+-main https://github.com/Goldodemon-Automation/unsloth_X_PLUS.git
cd unsloth_X_PLUS
./studio/setup.sh --local        # Windows: .\studio\setup.ps1 -Local
```

Everything else — what the Studio does, the model catalogue, the API, remote access, the notebooks,
the desktop downloads upstream ships — is upstream's product and is documented below exactly as
upstream documents it.

---

## Checks

```bash
cd studio/frontend
npm run typecheck    # tsc over src and tests
npm test             # node --test over tests/**/*.test.ts
npm run i18n:check   # locale overlay parity

cd studio/backend
python -m pytest tests -q
```

From the repository root, `pre-commit run --all-files` runs Ruff and the repo's lint scripts. The
fork's own suites are named where they live: `test_device_targets.py`, `test_compute_target_env.py`,
`test_compute_route.py`, `test_npu_assist.py`, `test_cpu_tuning.py`, `test_labs_*.py`,
`test_advanced_*.py`, and `test_backend_build_identity.py`.

A suite that looks mysteriously red on Windows is usually line endings: `.gitattributes` asks for LF
under `studio/frontend/`, `core.autocrlf=true` checks out CRLF, and several tests pin exact source text.

---

## Docs

| Doc | Covers |
| --- | --- |
| [docs/labs.md](docs/labs.md) | The Labs engines, the experiment registry, Artifacts and Pipelines |
| [docs/simulated-training.md](docs/simulated-training.md) | The Debugging simulator: a job with no hardware behind it |
| [docs/compute-targets.md](docs/compute-targets.md) | CPU, integrated-GPU and NPU training, the budget, and troubleshooting |
| [docs/igpu.md](docs/igpu.md) | Intel iGPUs: the XPU wheel, pinning one GPU, symptom-first fixes |
| [docs/llama-architectures.md](docs/llama-architectures.md) | The architecture picker and installer: what is verified and what a row's status means |
| [docs/security.md](docs/security.md) | Threat model and the controls that exist |
| [docs/README.md](docs/README.md) | Repository map and the local CRLF trap |

---

## Releases

Tags are on `x+-main` and independent of the wheel version in `unsloth/_version.py`, which tracks
upstream. Notes for each are in [docs/releases/](docs/releases/).

| Tag | Theme |
| --- | --- |
| [`v1.0.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.0.0) | CPU and integrated-GPU training |
| [`v1.1.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.1.0) | NPU detection and NPU-assisted training |
| [`v1.2.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.2.0) | Capability card and the perf layer |
| [`v1.2.1`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.2.1) | Windowed run history |
| [`v1.2.2`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.2.2) | The review fixes |
| [`v1.2.3`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.2.3) | Vendor-correct NPU refusals |
| [`v1.3.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.3.0) | Tuned CPU runs, tested device decisions |
| [`v1.4.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.4.0) | Branding, security hardening, installers |
| [`v1.4.1`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.4.1) | Intel detection, matching backend, opt-in telemetry |
| [`v1.5.0`](https://github.com/Goldodemon-Automation/unsloth_X_PLUS/releases/tag/v1.5.0) | The Labs wave, disk preflight, per-flavour installers |
| `v1.6.0` | Synced to upstream `main` at `8c5ca83271`; Studio UI is upstream's again |

---

## License

Three sets of terms, no overlap:

- **`unsloth/`** — Apache-2.0, inherited from upstream.
- **`studio/`** — AGPL-3.0, see [studio/LICENSE.AGPL-3.0](studio/LICENSE.AGPL-3.0).
- **Original additions** — the Labs engines, the device/compute-target layer, the run records —
  [NRC-3](LICENSE-NRC-3.md). Files carrying the NRC-3 header are covered; shared files keep
  upstream's terms.

NRC-3 allows private, internal and commercial use, modification and sharing with attribution, and
reserves five things that need written permission: relaunching the work as a rebranded product (a
different name, logo or interface, a near-miss name, an "official" claim), running it as a hosted
service for other people, public distribution of packaged builds at scale, folding it into something
you sell, and stripping its notices or relicensing it. Publishing your changed source on a code host
stays allowed. Model weights, tokenizers and datasets keep whatever license came with them.

Produced checkpoints carry `LICENSE-NRC-3.txt` beside `run_manifest.json`, so a folder keeps those
terms wherever it is copied.

---

## Contributing

Issues and pull requests are welcome. Small fixes can go straight to a PR; for anything larger, open
an issue with the shape you have in mind first.

The most self-contained places to start: `studio/backend/core/labs/` (each engine is a module with its
own tests), `studio/backend/core/advanced/` (custom eval tasks, the repair preset, adapter merging),
and `studio/backend/core/training/device_targets.py` with `compute_target_env.py` (the device contract).

---

Everything below is upstream's README, unchanged apart from headings, and it is the reference for
what the Studio itself does.

---

# Unsloth — the Studio

## ⚡ Get started
Download the native Unsloth Desktop app for your operating system:
<table>
  <tr>
    <td><b>Platform</b></td>
    <td><b>Link</b></td>
  </tr>
  <tr>
    <td><b>Windows</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-Windows.exe'>Download</a></td>
  </tr>
  <tr>
    <td><b>macOS</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-MacOS.dmg'>Download</a></td>
  </tr>
  <tr>
    <td><b>Linux / Ubuntu (deb)</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-Ubuntu.deb'>Download</a></td>
  </tr>
  <tr>
    <td><b>Linux / Ubuntu (ARM64) (deb)</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-Ubuntu-ARM64.deb'>Download</a></td>
  </tr>
  <tr>
    <td><b>Linux (AppImage)</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-Linux.AppImage'>Download</a></td>
  </tr>
  <tr>
    <td><b>Windows (ARM64)</b></td>
    <td><a href='https://github.com/unslothai/unsloth/releases/latest/download/Unsloth-Desktop-Windows-ARM64.exe'>Download</a></td>
  </tr>
</table>

Download from [Unsloth](https://unsloth.ai/download) or [GitHub Releases](https://github.com/unslothai/unsloth/releases).

Or if you prefer to install manually:

#### macOS, Linux, WSL:
```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

#### Windows:
```powershell
irm https://unsloth.ai/install.ps1 | iex
```
#### Docker:

The [Unsloth Docker image](https://hub.docker.com/r/unsloth/unsloth) `unsloth/unsloth` is available on Docker. [Read guide.](https://unsloth.ai/docs/get-started/install/docker)

#### Homebrew:
```bash
brew install --cask unsloth
```

#### Winget (Windows):
```powershell
winget install --id UnslothAI.Unsloth -e
```
On a managed work PC where endpoint protection blocks `irm ... | iex`, use winget instead.

#### Community:

- [Discord](https://discord.gg/unsloth)
- [𝕏 (Twitter)](https://x.com/UnslothAI)
- [Reddit](https://reddit.com/r/unsloth)

## ⭐ Features
Unsloth works on **Windows, Linux, WSL** and **macOS**. We support **Multi GPU setups, NVIDIA, AMD, Intel GPUs, CPUs** and the **Vulkan** backend.

### Run & Build with AI
* Run and train LLMs, MLX, GGUF, diffusion, decision, embedding, audio models: [Qwen3.8](https://unsloth.ai/docs/models/qwen3.8), [GLM-5.3-Flash](https://unsloth.ai/docs/models/glm-5.3-flash), [Kimi K3](https://unsloth.ai/docs/models/kimi-k3), [Qwen-Image-2.1](https://unsloth.ai/docs/models/qwen-image-2.1), MiniMax-H3, [DeepSeek-V4](https://unsloth.ai/docs/models/deepseek-v4), [Gemma 4](https://unsloth.ai/docs/models/gemma-4).
* **Agents & Tools:** Use local models with [Claude Code](https://unsloth.ai/docs/basics/claude-code), [Codex](https://unsloth.ai/docs/basics/codex), and [MCP](https://unsloth.ai/docs/basics/mcp), including tool calling and code execution.
* **Browser use:** [Navigate sites](https://unsloth.ai/docs/basics/browser-use), fill out forms, read PDFs, and edit files beside your chat with a local model.
* **Sandboxing:** Restrict which files your model can access when it runs commands in a [sandbox](https://unsloth.ai/docs/new/studio/sandboxing-in-unsloth).
* **Search & RAG:** Use private and unlimited web search, deep research, auto-compaction (rolling context window) and RAG.
* **Image and video:** Run and train [image](https://unsloth.ai/docs/basics/diffusion-image) and video diffusion or multimodal models
* **Remote & LAN:** Access your local models from any device on [LAN](https://unsloth.ai/docs/basics/lan) or remotely through secure [Cloudflare](https://unsloth.ai/docs/basics/how-to-serve-local-llms-anywhere-secure-remote-access-with-cloudflare-and-unsloth) HTTPS.
* **Connect:** Serve models through an [OpenAI compatible API](https://unsloth.ai/docs/basics/api). Also connect your ChatGPT/Codex subscription and [cloud providers](https://unsloth.ai/docs/integrations/connections)


### Train & Deploy
* **Fine-tuning:** Train LLMs, diffusion, decision, TTS, and embedding models 2× faster with 70% less VRAM with [no accuracy loss](https://unsloth.ai/blog#training)
* **Complete support:** Supports [reinforcement learning](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide), LoRA, QLoRA, full fine tuning, pretraining, RL, GRPO, DPO, and FP8.
* **Export & Deploy:** [Export](https://unsloth.ai/docs/new/studio/export) or Deploy models including [GGUF](https://unsloth.ai/docs/basics/inference-and-deployment/saving-to-gguf), NVFP4, FP8 and more formats.
* **Datasets:** Build datasets from PDFs, CSVs, DOCX files, and more with [Data Recipes](https://unsloth.ai/docs/new/studio/data-recipe).

## 🚀 Unsloth Start

[Unsloth Start](https://unsloth.ai/docs/integrations/unsloth-start) connects [Claude Code](https://unsloth.ai/docs/basics/claude-code), [Codex](https://unsloth.ai/docs/basics/codex) and other agents to local models with one command.

```bash
unsloth start claude --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL
```

| Agent | Command |
| --- | --- |
| Claude Code | `unsloth start claude` |
| OpenAI Codex | `unsloth start codex` |
| Visual Studio Code | `unsloth start vscode` |
| DeepSeek Harness | `unsloth start dsh` |
| OpenCode | `unsloth start opencode` |
| Hermes Agent | `unsloth start hermes` |
| Pi | `unsloth start pi` |

## 📒 Free Notebooks
| Notebook | Description |
| --- | --- |
| [Unsloth Studio on Colab](studio/Unsloth_Studio_X_Plus_Colab.ipynb) | This fork's Studio on a free Colab T4 |
| [Unsloth Start on Kaggle](review/kaggle/README.md) | Verify the training stack on a free Kaggle GPU |

## 📥 Advanced Installation

#### Vulkan, custom llama.cpp backends:

Pick the llama.cpp build GGUF chat runs on during installation. PyTorch is picked separately from your GPU, so this does not change it:
```bash
export UNSLOTH_LLAMA_CPP_BACKEND=vulkan   # or cpu, cuda, rocm, auto
curl -fsSL https://unsloth.ai/install.sh | sh
```
```powershell
$env:UNSLOTH_LLAMA_CPP_BACKEND="vulkan"   # or cpu, cuda, rocm, auto
irm https://unsloth.ai/install.ps1 | iex
```

To choose PyTorch yourself, pin its index:
```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_TORCH_INDEX_FAMILY=cpu sh   # or a family like rocm7.2
```
Or skip PyTorch for GGUF chat only:
```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_NO_TORCH=1 sh
```

#### audio.cpp audio engine:

Setup also installs [audio.cpp](https://github.com/0xShug0/audio.cpp) (prebuilt by [unslothai/audio.cpp](https://github.com/unslothai/audio.cpp)), which runs the audio.cpp speech, music and speech-to-text models on the Audio page, in Voice settings and behind `/v1/audio/*`. It is optional and never blocks setup:
- `UNSLOTH_SKIP_AUDIO_CPP_INSTALL=1` skips it.
- `UNSLOTH_AUDIO_CPP_ACCELERATOR=cpu` (or `cuda`, `vulkan`, `metal`) picks the bundle instead of auto-detecting.
- `AUDIOCPP_SERVER_PATH=/path/to/audiocpp_server` uses your own build.

#### Uninstall

**MacOS, WSL, Linux:** `curl -fsSL https://raw.githubusercontent.com/unslothai/unsloth/main/scripts/uninstall.sh | sh`

**Windows (PowerShell):** `irm https://raw.githubusercontent.com/unslothai/unsloth/main/scripts/uninstall.ps1 | iex`

For more info, [see our docs](https://unsloth.ai/docs/new/studio/install#uninstall).

#### Deleting model files

You can delete old model files either from the bin icon in model search or by removing the relevant cached model folder from the default Hugging Face cache directory. By default, HF uses:

**MacOS, Linux, WSL:** `~/.cache/huggingface/hub/`

**Windows:** `%USERPROFILE%\.cache\huggingface\hub\`

## 💚 Community and Links
| Type | Links |
| --- | --- |
| <img width="16" src="https://cdn.prod.website-files.com/6257adef93867e50d84d30e2/66e3d80db9971f10a9757c99_Symbol.svg" /> **Discord** | [Join Discord server](https://discord.com/invite/unsloth) |
| <img width="15" src="https://redditinc.com/hs-fs/hubfs/Reddit%20Inc/Brand/Reddit_Logo.png" /> **r/unsloth Reddit** | [Join Reddit community](https://reddit.com/r/unsloth) |
| 📚 **Documentation & Wiki** | [Read Our Docs](https://unsloth.ai/docs) |
| <img width="13" src="https://upload.wikimedia.org/wikipedia/commons/0/09/X_(formerly_Twitter)_logo_late_2025.svg" /> **Twitter (aka X)** | [Follow us on X](https://twitter.com/unslothai) |
| 🔮 **Our Models** | [Unsloth Catalog](https://unsloth.ai/docs/get-started/unsloth-model-catalog) |
| ✍️ **Blog** | [Read our Blogs](https://unsloth.ai/blog) |

### Citation

You can cite the Unsloth repo as follows:
```bibtex
@software{unsloth,
  author = {Daniel Han, Michael Han and Unsloth team},
  title = {Unsloth},
  url = {https://github.com/unslothai/unsloth},
  year = {2023}
}
```
If you trained a model with 🦥Unsloth, you can use this cool sticker!   <img src="https://raw.githubusercontent.com/unslothai/unsloth/main/images/made%20with%20unsloth.png" width="200" align="center" />

### Upstream license
Unsloth uses a dual-licensing model of Apache 2.0 and AGPL-3.0. The core Unsloth package remains licensed under **[Apache 2.0](https://github.com/unslothai/unsloth?tab=Apache-2.0-1-ov-file)**, while certain optional components, such as the Unsloth Studio UI are licensed under the open-source license **[AGPL-3.0](https://github.com/unslothai/unsloth?tab=AGPL-3.0-2-ov-file)**.

This structure helps support ongoing Unsloth development while keeping the project open source and enabling the broader ecosystem to continue growing.

### Thank You to
- The [llama.cpp library](https://github.com/ggml-org/llama.cpp) that lets users run and save models with Unsloth
- The Hugging Face team and their libraries: [transformers](https://github.com/huggingface/transformers) and [TRL](https://github.com/huggingface/trl)
- The Pytorch and [Torch AO](https://github.com/unslothai/unsloth/pull/3391) team for their contributions
- NVIDIA for their [NeMo DataDesigner](https://github.com/NVIDIA-NeMo/DataDesigner) library and their contributions
- And of course for every single person who has contributed or has used Unsloth!
