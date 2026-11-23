// SPDX-License-Identifier: AGPL-3.0-only
// Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

// Streaming must survive the two store writers that used to kill it silently, and an
// imported run config must be reconciled before it reaches the backend:
// `routes/training.py` answers 422 for dataset_streaming with train_on_completions or
// with evaluation that has no separate eval split.

import assert from "node:assert/strict";
import test from "node:test";

import {
  installLocalStorageFake,
  registerStoreStubResolver,
} from "./helpers/kit.ts";

registerStoreStubResolver();
installLocalStorageFake();

const { recordedToasts } = await import("./helpers/store-stubs/toast.ts");
const { useTrainingConfigStore } = await import(
  "../src/features/training/stores/training-config-store.ts"
);
const { buildTrainingStartPayload } = await import(
  "../src/features/training/api/mappers.ts"
);

function resetTo(overrides: Record<string, unknown>): void {
  recordedToasts.length = 0;
  useTrainingConfigStore.getState().reset();
  useTrainingConfigStore.setState(overrides);
}

const STREAMING_READY = {
  datasetSource: "huggingface",
  dataset: "unsloth/alpaca-cleaned",
  datasetStreaming: false,
  datasetSplit: "train",
  datasetEvalSplit: null,
  evalSteps: 0,
  maxSteps: 60,
  trainOnCompletions: true,
  isVisionModel: false,
  isAudioModel: false,
  isEmbeddingModel: false,
  isDatasetImage: null,
  isDatasetAudio: false,
} as const;

test("a default Hugging Face form can turn streaming on", () => {
  resetTo(STREAMING_READY);

  useTrainingConfigStore.getState().setDatasetStreaming(true);

  const state = useTrainingConfigStore.getState();
  assert.equal(state.datasetStreaming, true, "the checkbox must take effect");
  assert.equal(state.trainOnCompletions, false, "completions masking cannot stream");
  assert.equal(state.maxSteps, 60, "a step count is what the backend needs");
  assert.ok(
    recordedToasts.some((toast) => toast.message.includes("Streaming enabled")),
    "the user is told which option was disabled",
  );
});

test("enabling completions while streaming refuses the toggle, not the stream", () => {
  resetTo({ ...STREAMING_READY, datasetStreaming: true, trainOnCompletions: false });

  useTrainingConfigStore.getState().setTrainOnCompletions(true);

  const state = useTrainingConfigStore.getState();
  assert.equal(state.datasetStreaming, true, "streaming stays on");
  assert.equal(state.trainOnCompletions, false, "the incompatible toggle is refused");
  assert.equal(
    state.trainingToggleChoices.trainOnCompletions,
    false,
    "the refusal is remembered, or the default would re-enable it later",
  );
  assert.ok(
    recordedToasts.some((toast) => toast.message.includes("Adjusted for streaming")),
    "the refusal is explained instead of silently switching streaming off",
  );
});

test("an imported run config is reconciled before it can be posted", () => {
  resetTo({
    ...STREAMING_READY,
    datasetStreaming: true,
    trainOnCompletions: false,
  });

  useTrainingConfigStore.getState().applyConfigPatch({
    training: {
      // The pair the backend refuses beside streaming.
      train_on_completions: true,
      eval_steps: 0.1,
      max_steps: 60,
    },
  });

  const state = useTrainingConfigStore.getState();
  assert.equal(state.datasetStreaming, true, "the import keeps streaming");
  assert.equal(
    state.trainOnCompletions,
    false,
    "completions from the import must not reach the payload",
  );
  assert.equal(
    state.evalSteps,
    0,
    "evaluation without its own split must not reach the payload",
  );
});

test("retiring the step count still turns streaming off, with the reason", () => {
  resetTo({ ...STREAMING_READY, datasetStreaming: true, trainOnCompletions: false });

  useTrainingConfigStore.getState().setMaxSteps(0);

  const state = useTrainingConfigStore.getState();
  assert.equal(state.maxSteps, 0, "epochs mode is kept");
  assert.equal(state.datasetStreaming, false, "a stream has no length to make epochs from");
  assert.ok(
    recordedToasts.some((toast) => toast.message.includes("Streaming turned off")),
    "the user is told why streaming went away",
  );
});

test("a streaming payload can never carry completion masking", () => {
  // Belt and braces at the wire boundary: whatever a future writer does to the store,
  // the request the backend refuses must not be constructible.
  resetTo({ ...STREAMING_READY, datasetStreaming: true, trainOnCompletions: true });

  const payload = buildTrainingStartPayload(
    useTrainingConfigStore.getState(),
    null,
  );

  assert.equal(payload.dataset_streaming, true);
  assert.equal(payload.train_on_completions, false);
  assert.equal(payload.max_steps, 60);
});

test("replaying a stale recipe cannot resurrect the pair either", () => {
  resetTo({ ...STREAMING_READY });

  useTrainingConfigStore.getState().restoreRunConfig({
    model_name: "unsloth/Llama-3.2-1B",
    hf_dataset: "unsloth/alpaca-cleaned",
    train_split: "train",
    format_type: "alpaca",
    // Hand-edited or pre-rule recipe: streaming and completions masking together.
    dataset_streaming: true,
    train_on_completions: true,
    max_steps: 60,
    num_epochs: 3,
  } as never);

  const state = useTrainingConfigStore.getState();
  assert.equal(state.datasetStreaming, true, "the replay keeps streaming");
  assert.equal(
    state.trainOnCompletions,
    false,
    "the replay cannot carry completion masking beside streaming",
  );
});
