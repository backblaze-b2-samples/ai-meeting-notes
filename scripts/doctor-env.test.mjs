import test from "node:test";
import assert from "node:assert/strict";

import {
  OPTIONAL_B2_VARS,
  REQUIRED_B2_VARS,
  parseEnvText,
} from "./doctor-env.mjs";

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

test("B2 env contract tracks the optional public URL variable", () => {
  assert.deepEqual(OPTIONAL_B2_VARS, ["B2_PUBLIC_URL_BASE"]);
  assert.equal(REQUIRED_B2_VARS.includes("B2_PUBLIC_URL_BASE"), false);
});
