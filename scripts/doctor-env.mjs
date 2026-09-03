import { readFileSync } from "node:fs";

export const REQUIRED_B2_VARS = [
  "B2_REGION",
  "B2_APPLICATION_KEY_ID",
  "B2_APPLICATION_KEY",
  "B2_BUCKET_NAME",
];

export const OPTIONAL_B2_VARS = [
  "B2_PUBLIC_URL_BASE",
];

export const PLACEHOLDERS = new Set([
  "your_b2_region",
  "your_application_key_id",
  "your_application_key",
  "your-bucket-name",
]);

export const B2_REGION_PATTERN = /^[a-z]{2}(?:-[a-z]+)+-\d{3}$/;

export const B2_ROLLING_MIGRATION_FIX = [
  "For rolling upgrades from legacy B2 env names, add the standardized",
  "variables alongside the legacy key-id/endpoint variables before deploying this release;",
  "remove legacy variables only after old API instances are drained.",
].join(" ");

function parseQuotedValue(raw) {
  const quote = raw[0];
  let value = "";
  for (let i = 1; i < raw.length; i += 1) {
    const char = raw[i];
    if (char === "\\" && quote === '"' && i + 1 < raw.length) {
      value += raw[i + 1];
      i += 1;
      continue;
    }
    if (char === quote) return value;
    value += char;
  }
  return raw;
}

function stripInlineComment(raw) {
  for (let i = 0; i < raw.length; i += 1) {
    if (raw[i] === "#" && (i === 0 || /\s/.test(raw[i - 1]))) {
      return raw.slice(0, i).trimEnd();
    }
  }
  return raw;
}

export function parseEnvText(text) {
  const out = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const rawValue = line.slice(eq + 1).trim();
    let value = rawValue;
    if (value.startsWith('"') || value.startsWith("'")) {
      value = parseQuotedValue(value);
    } else {
      value = stripInlineComment(value).trim();
    }
    out[key] = value;
  }
  return out;
}

export function parseEnvFile(path) {
  return parseEnvText(readFileSync(path, "utf8"));
}
