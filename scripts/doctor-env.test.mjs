import test from "node:test";
import assert from "node:assert/strict";

import { parseEnvText } from "./doctor-env.mjs";

test("parseEnvText strips dotenv inline comments from B2_REGION", () => {
  const env = parseEnvText("B2_REGION=us-west-004 # bucket region\n");

  assert.equal(env.B2_REGION, "us-west-004");
});

test("parseEnvText strips inline comments after quoted B2_REGION", () => {
  const env = parseEnvText('B2_REGION="us-west-004" # bucket region\n');

  assert.equal(env.B2_REGION, "us-west-004");
});

test("parseEnvText preserves hashes inside unquoted values", () => {
  const env = parseEnvText("B2_APPLICATION_KEY=abc#not-a-comment\n");

  assert.equal(env.B2_APPLICATION_KEY, "abc#not-a-comment");
});
