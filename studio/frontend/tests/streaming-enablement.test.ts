// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// The Streaming checkbox was disabled on every fresh form: `trainOnCompletions`
// defaults to true, the reason list counted it as "unsupported", and the toggle that
// clears it (setDatasetStreaming) could therefore never be reached. These pin the split
// between a reason the toggle resolves for the user and one that really blocks.

import assert from "node:assert/strict";
import test from "node:test";

import { registerBundlerResolver } from "./helpers/kit.ts";

registerBundlerResolver();

const {
  getDatasetStreamingBlockers,
  getDatasetStreamingHardBlockers,
  streamingBlockerClearsOnEnable,
} = await import("../src/features/studio/sections/dataset-panel-helpers.ts");
const { initialTrainingConfigState, streamingCompatiblePatch } = await import(
  "../src/features/training/stores/training-config-policy.ts"
);

type StoreState = typeof initialTrainingConfigState;

function blockersFor(overrides: Partial<StoreState>) {
  const state = { ...initialTrainingConfigState, ...overrides };
  return getDatasetStreamingBlockers({
    datasetEvalSplit: state.datasetEvalSplit,
    evalDataset: state.evalDataset,
    datasetSource: state.datasetSource,
    datasetSplit: state.datasetSplit,
    evalSteps: state.evalSteps,
    isAudioModel: state.isAudioModel,
    isDatasetAudio: state.isDatasetAudio,
    isDatasetImage: state.isDatasetImage,
    isEmbeddingModel: state.isEmbeddingModel,
    isVisionModel: state.isVisionModel,
    maxSteps: state.maxSteps,
    trainOnCompletions: state.trainOnCompletions,
  });
}

test("a fresh Hugging Face form can enable streaming", () => {
  const state = initialTrainingConfigState;
  // The default the bug hinged on: training on completions is on until told otherwise.
  assert.equal(state.trainOnCompletions, true);
  assert.equal(state.datasetSource, "huggingface");

  const blockers = blockersFor({});
  assert.deepEqual(blockers, ["trainOnCompletions"], "the reason list still explains what changes");
  assert.deepEqual(
    getDatasetStreamingHardBlockers(blockers),
    [],
    "a reason the toggle clears itself must not disable the control",
  );
});

test("enabling streaming clears the reasons the control lists", () => {
  const patch = streamingCompatiblePatch({
    ...initialTrainingConfigState,
    datasetStreaming: true,
    trainOnCompletions: true,
    // Evaluation on, same split as training: the second reason the toggle resolves.
    evalSteps: 0.1,
  });
  assert.equal(patch.trainOnCompletions, false);
  assert.equal(patch.evalSteps, 0);
  assert.equal(patch.datasetStreaming, undefined, "streaming itself stays on");
});

test("reasons the toggle cannot resolve still disable it", () => {
  const hard: Array<[string, Partial<StoreState>]> = [
    ["source", { datasetSource: "upload" as const }],
    ["maxSteps", { maxSteps: 0 }],
    ["visionModel", { isVisionModel: true }],
    ["audioModel", { isAudioModel: true }],
    ["embeddingModel", { isEmbeddingModel: true }],
    ["imageDataset", { isDatasetImage: true }],
    ["audioDataset", { isDatasetAudio: true }],
  ];
  for (const [reason, override] of hard) {
    const blockers = blockersFor(override);
    assert.ok(
      getDatasetStreamingHardBlockers(blockers).includes(reason as never),
      `${reason} must stay a hard blocker`,
    );
  }
});

test("only the two auto-cleared reasons are soft", () => {
  const soft = [
    "trainOnCompletions",
    "evalSplit",
  ] as const;
  for (const reason of soft) {
    assert.equal(streamingBlockerClearsOnEnable(reason), true);
  }
  const hard = [
    "source",
    "maxSteps",
    "visionModel",
    "audioModel",
    "embeddingModel",
    "imageDataset",
    "audioDataset",
  ] as const;
  for (const reason of hard) {
    assert.equal(streamingBlockerClearsOnEnable(reason), false);
  }
});
