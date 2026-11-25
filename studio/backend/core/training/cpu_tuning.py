# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""Decides how a CPU training run uses the machine it lands on.

A CPU run is fifty to a hundred times the wall-clock of a GPU run, and that gap is mostly decided
by settings nobody sets: how many threads feed the matrix multiplies, which attention
implementation runs, how many dataloader workers exist, whether activations are recomputed, and
which precision the frozen base holds. ``plan_cpu_training`` turns host measurements into those
answers so the rules live in one testable place and the loader only applies them. Nothing here
imports torch and nothing here touches the machine: every unknown or nonsensical measurement
degrades to the conservative answer instead of raising.
"""

from __future__ import annotations

from dataclasses import dataclass

# The dtype rule defers to the training module's fit helper so this planner and the loader's
# estimate block can never disagree about what "does not fit" means. Importing the sibling costs
# nothing: ``core.training.__init__`` imports it before this module can load, and it pulls in no
# torch at module scope.
from .training import cpu_fp32_weights_fit


@dataclass(frozen = True)
class CpuTrainingPlan:
    """The settings a CPU training run should start with.

    ``reasons`` holds one plain sentence per non-obvious choice so the loader can log why the
    machine ended up with these numbers.
    """

    torch_threads: int  # argument for torch.set_num_threads
    interop_threads: int  # argument for torch.set_num_interop_threads; always 1
    attn_implementation: str  # "sdpa" | "eager"
    dataloader_workers: int  # 0 on the spawn platforms, a small count on Linux
    gradient_checkpointing: bool  # trade recomputation for activation memory
    dtype: str  # "float32" | "bfloat16"
    reasons: tuple[str, ...]


def measured_physical_cpus() -> int | None:
    """Physical cores this host has, or None when the measurement is unavailable.

    ``os.cpu_count`` answers logical CPUs, which on an SMT machine is twice the cores a GEMM can
    use; psutil reads the real topology on win32, linux and darwin. The planner halves the usable
    count only when it has nothing better, so this measurement is what keeps a CPU without SMT
    (a 4C/4T laptop, a Graviton, an Apple Silicon part) from training on half its cores.

    Lives here rather than in the loader so it can be tested without importing torch, and returns
    None rather than raising: a backend installed without psutil keeps the old heuristic.

    The measurement itself lives in ``utils.cpu_threads``, which is also where the OpenBLAS default
    reads it: one implementation means a host cannot get six torch threads and three numpy ones.
    """
    from utils.cpu_threads import measured_physical_cpus as _measured

    return _measured()


def plan_cpu_training(
    *,
    usable_cpus: int | None,
    available_memory_bytes: int | None,
    fp32_weight_bytes: int | None,
    platform: str | None = None,
    supports_sdpa: bool = True,
    fast_bf16: bool = False,
    physical_cpus: int | None = None,
) -> CpuTrainingPlan:
    """Build the CPU training plan from host measurements.

    Every measurement may be None ("unknown"), and every rule below then picks the conservative
    answer: one thread, zero dataloader workers, eager attention, fp32, no checkpointing.

    ``physical_cpus`` is the host's physical core count when the loader could measure it
    (psutil's ``cpu_count(logical = False)``), and None when it could not. A measured count is
    used as-is instead of halving the usable count, so a CPU without SMT keeps all of its cores.
    It is ignored when larger than the usable count: an affinity mask narrows what this process
    may run on, and the mask wins.

    ``fast_bf16`` is the one measurement that is not a number: the loader probes the CPU with
    ``utils.cpu_features`` and passes the answer in, so this planner stays a pure function of its
    arguments. It defaults to False because on most x86 CPUs bf16 is emulated through fp32 and a
    bf16 run is therefore slower at half the memory; only AMX-BF16, AVX512-BF16 and Apple Silicon
    make bf16 the faster choice.
    """
    reasons: list[str] = []

    # Treat zero and negative measurements as unknown: they describe no real host and must not
    # steer a rule into dividing by zero or comparing against nothing.
    memory_known = available_memory_bytes is not None and available_memory_bytes > 0
    weights_known = fp32_weight_bytes is not None and fp32_weight_bytes > 0
    cpus_known = usable_cpus is not None and usable_cpus > 0

    # Threads: one per physical core. When the caller measured that count (psutil answers on
    # win32, linux and darwin) it is used directly: halving the usable count throws away half the
    # machine on a CPU without SMT -- every 4C/4T laptop, a Graviton, an Apple Silicon part, and
    # the 6C/6T host this repo is developed on -- which is the opposite of tuning. Only when the
    # physical count is unknown is it approximated as half the usable CPUs, and only past two
    # CPUs: SMT siblings add little to a GEMM and cost cache contention. A machine with two CPUs
    # or fewer is taken at face value, because halving it would leave the matrix multiplies
    # single-threaded for no measurable win.
    #
    # AMX-class hardware is the other exception: bf16 matmuls run on matrix units where SMT
    # siblings do add throughput, so the usable count is kept and merely capped at 32, the same
    # choice utils.cpu_threads makes for the OpenBLAS pool. The count is clamped to at least one
    # thread and never more than the usable CPUs.
    if not cpus_known:
        torch_threads = 1
        reasons.append("The CPU count is unknown, so the run keeps a single thread.")
    elif fast_bf16:
        torch_threads = min(usable_cpus, 32)
        reasons.append(
            "AMX-class hardware runs bf16 matmuls on matrix units where SMT siblings add "
            "throughput, so the thread count follows the usable CPU count up to 32."
        )
    elif physical_cpus is not None and 0 < physical_cpus <= usable_cpus:
        torch_threads = physical_cpus
        reasons.append(
            "One thread per physical core, measured directly, because halving the usable CPU "
            "count would waste half the machine on a CPU without SMT."
        )
    else:
        torch_threads = usable_cpus // 2 if usable_cpus > 2 else usable_cpus
        torch_threads = max(1, min(torch_threads, usable_cpus))
        if usable_cpus > 2:
            reasons.append(
                "One thread per physical core is approximated as half the usable CPUs because "
                "the physical count could not be measured and SMT siblings add little to a GEMM."
            )

    # Memory clamp on the thread count, the way utils.cpu_threads clamps OpenBLAS: fewer threads
    # share the same weights, but each thread keeps its own per-thread buffers, so once the fp32
    # weights take more than 60% of the available memory those buffers decide between a run and
    # an OOM kill. A memory-bound GEMM loses little from half the threads.
    if (
        memory_known
        and weights_known
        and fp32_weight_bytes * 10 > available_memory_bytes * 6
    ):
        torch_threads = max(1, torch_threads // 2)
        reasons.append(
            "The thread count is halved because the fp32 weights take more than 60% of the "
            "available memory and every thread keeps its own buffers."
        )

    # Inter-op threads: always 1. torch sizes its intra-op and inter-op pools independently, so a
    # core-sized inter-op pool beside a core-sized intra-op pool oversubscribes the machine
    # (the pools multiply, not add), and a CPU training run has exactly one forward graph to
    # schedule at a time anyway.
    interop_threads = 1
    reasons.append(
        "The inter-op pool stays at one thread because a second core-sized pool beside the "
        "intra-op one would oversubscribe the machine."
    )

    # Attention: SDPA runs the fused kernel torch ships instead of materializing the full
    # attention matrix in plain tensor math; only a stack without SDPA support falls back to
    # eager. An unknown capability is falsy and degrades to the safe fallback.
    if supports_sdpa:
        attn_implementation = "sdpa"
        reasons.append("SDPA is the fused attention kernel torch ships for this stack.")
    else:
        attn_implementation = "eager"
        reasons.append("Eager attention is the fallback for a stack without SDPA support.")

    # Dataloader workers: zero on win32 and darwin, where spawned workers re-import the training
    # module (torch and unsloth_zoo with it) and the spawn hazards are not worth it on one
    # machine. Linux forks cheaply, so a few workers can collate the next batch while the CPU
    # computes this one; the cap at four keeps the collate workers off the GEMM threads.
    if platform in ("win32", "darwin"):
        dataloader_workers = 0
        reasons.append(
            "Dataloader workers stay at zero because spawned workers re-import the training "
            "module and the spawn platforms are not worth the hazard."
        )
    elif isinstance(platform, str) and platform.startswith("linux") and cpus_known:
        dataloader_workers = min(4, max(1, usable_cpus // 4))
        reasons.append(
            "Linux forks dataloader workers cheaply, so a few collate the next batch while the "
            "CPU computes this one."
        )
    else:
        # An unknown platform or unknown CPU count keeps the spawn-platform answer: zero workers
        # can never hurt a run.
        dataloader_workers = 0
        reasons.append(
            "Dataloader workers stay at zero because the platform or the CPU count is unknown."
        )

    # Gradient checkpointing: on once the fp32 weights take over 40% of the available memory.
    # Recomputing activations trades compute for memory, and a CPU run that starts swapping is
    # slower than one that recomputes. Unknown measurements keep it off.
    gradient_checkpointing = (
        memory_known and weights_known and fp32_weight_bytes * 10 > available_memory_bytes * 4
    )
    if gradient_checkpointing:
        reasons.append(
            "Gradient checkpointing trades recomputation for memory because a run that starts "
            "swapping is slower than one that recomputes."
        )

    # Dtype: cpu_fp32_weights_fit is the single fit rule (the fp32 weights plus a 2 GiB
    # activation headroom inside the available RAM), the same one _load_cpu_model applied before
    # this module existed. The loader now asks this plan instead of deciding locally, so this
    # module is the single place that decides the CPU load dtype and the two cannot drift.
    # Memory is checked first and wins: when fp32 cannot fit, bf16 is the only runnable dtype,
    # so the reason must name the memory squeeze even on hardware where bf16 is also faster.
    if not cpu_fp32_weights_fit(fp32_weight_bytes, available_memory_bytes):
        dtype = "bfloat16"
        reasons.append(
            "The frozen base loads in bfloat16 because the fp32 weights cannot fit in the "
            "available memory."
        )
    elif fast_bf16:
        # Hardware bf16 (AMX-BF16, AVX512-BF16, Apple Silicon): the same run is faster than fp32
        # and takes half the memory, so the tolerance argument that keeps fp32 elsewhere does
        # not apply here.
        dtype = "bfloat16"
        reasons.append(
            "The frozen base loads in bfloat16 because this CPU runs bf16 in hardware, which is "
            "faster than fp32 at half the memory."
        )
    else:
        dtype = "float32"

    return CpuTrainingPlan(
        torch_threads = torch_threads,
        interop_threads = interop_threads,
        attn_implementation = attn_implementation,
        dataloader_workers = dataloader_workers,
        gradient_checkpointing = gradient_checkpointing,
        dtype = dtype,
        reasons = tuple(reasons),
    )


def cpu_base_load_kwargs(
    dtype,
    *,
    token: str | None = None,
    trust_remote_code: bool = False,
    revision: str | None = None,
    local_files_only: bool = False,
) -> dict:
    """The ``from_pretrained`` kwargs the CPU recipe uses for its frozen base.

    The dtype is spelled through ``utils.transformers_dtype.dtype_kwargs`` because the argument
    changed name: transformers renamed ``torch_dtype`` to ``dtype`` in 4.56 and the floor this
    project supports is 4.52, where ``dtype`` is not a load argument at all. It lands on the
    config and is dropped, so a run that chose bfloat16 because the fp32 weights do not fit
    would load the checkpoint's own dtype -- which is usually the wider one -- and pay exactly
    the memory squeeze the choice exists to avoid. The wrong spelling does not raise, so only
    asking by name prevents it.

    ``low_cpu_mem_usage`` is always on: it streams each shard into the finished parameters
    instead of materialising a full second copy of the weights on the way in.
    """
    from utils.transformers_dtype import dtype_kwargs

    return {
        **dtype_kwargs(dtype),
        "token": token,
        "trust_remote_code": trust_remote_code,
        "revision": revision,
        "local_files_only": local_files_only,
        "low_cpu_mem_usage": True,
    }
