// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// The policy module, not the feature barrel: the barrel pulls the store, and with it the
// toast/components layer, which a plain-node test cannot resolve.
import { hasSeparateStreamingEvalSplit } from "@/features/training/stores/training-config-policy";
import type { DatasetSource } from "@/types/training";

const POSITIVE_INTEGER_PATTERN = /^\d+$/;

export type DatasetStreamingBlocker =
  | "source"
  | "maxSteps"
  | "trainOnCompletions"
  | "evalSplit"
  | "visionModel"
  | "audioModel"
  | "embeddingModel"
  | "imageDataset"
  | "audioDataset";

/**
 * Blockers the streaming toggle clears itself.
 *
 * `setDatasetStreaming(true)` turns training on completions off and drops evaluation
 * when it has no separate split, then says so in a toast. Listing these as reasons the
 * control is unavailable made the auto-clear unreachable: `trainOnCompletions` defaults
 * to true, so the checkbox was disabled on every fresh form and the only way to stream
 * was to find that toggle in another panel first.
 */
const AUTO_CLEARED_BLOCKERS: ReadonlySet<DatasetStreamingBlocker> = new Set([
  "trainOnCompletions",
  "evalSplit",
]);

/** True for a blocker enabling streaming resolves on the user's behalf. */
export function streamingBlockerClearsOnEnable(
  blocker: DatasetStreamingBlocker,
): boolean {
  return AUTO_CLEARED_BLOCKERS.has(blocker);
}

/** The blockers that genuinely prevent streaming: the control stays disabled for these. */
export function getDatasetStreamingHardBlockers(
  blockers: readonly DatasetStreamingBlocker[],
): DatasetStreamingBlocker[] {
  return blockers.filter((blocker) => !streamingBlockerClearsOnEnable(blocker));
}

/** Whether the Streaming control is usable. The one predicate the panel reads. */
export function isDatasetStreamingEnabled(
  blockers: readonly DatasetStreamingBlocker[],
): boolean {
  return getDatasetStreamingHardBlockers(blockers).length === 0;
}

export function getFileExtension(fileName: string): string {
  const extensionStart = fileName.lastIndexOf(".");
  return extensionStart >= 0
    ? fileName.slice(extensionStart).toLowerCase()
    : "";
}

export function formatUpdatedDate(timestamp: number | null): string {
  if (typeof timestamp !== "number") {
    return "--";
  }
  return new Date(timestamp * 1000).toLocaleDateString();
}

export function normalizeSliceInput(value: string): string | null {
  const trimmed = value.trim();
  return POSITIVE_INTEGER_PATTERN.test(trimmed) ? trimmed : null;
}

export function getDatasetStreamingBlockers({
  datasetEvalSplit,
  evalDataset,
  datasetSource,
  datasetSplit,
  evalSteps,
  isAudioModel,
  isDatasetAudio,
  isDatasetImage,
  isEmbeddingModel,
  isVisionModel,
  maxSteps,
  trainOnCompletions,
}: {
  datasetEvalSplit: string | null;
  evalDataset: string | null;
  datasetSource: DatasetSource;
  datasetSplit: string | null;
  evalSteps: number;
  isAudioModel: boolean;
  isDatasetAudio: boolean;
  isDatasetImage: boolean | null;
  isEmbeddingModel: boolean;
  isVisionModel: boolean;
  maxSteps: number;
  trainOnCompletions: boolean;
}): DatasetStreamingBlocker[] {
  const blockers: DatasetStreamingBlocker[] = [];
  if (datasetSource !== "huggingface") {
    blockers.push("source");
  }
  if (maxSteps <= 0) {
    blockers.push("maxSteps");
  }
  if (trainOnCompletions) {
    blockers.push("trainOnCompletions");
  }
  if (
    !hasSeparateStreamingEvalSplit({
      evalSteps,
      datasetSplit,
      datasetEvalSplit,
      evalDataset,
    })
  ) {
    blockers.push("evalSplit");
  }
  if (isVisionModel) {
    blockers.push("visionModel");
  }
  if (isAudioModel) {
    blockers.push("audioModel");
  }
  if (isEmbeddingModel) {
    blockers.push("embeddingModel");
  }
  if (isDatasetImage) {
    blockers.push("imageDataset");
  }
  if (isDatasetAudio) {
    blockers.push("audioDataset");
  }
  return blockers;
}
