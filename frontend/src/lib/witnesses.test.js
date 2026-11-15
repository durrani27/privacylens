import test from "node:test";
import assert from "node:assert/strict";
import {
  evidenceByWitness, evidenceFor, indexById, isFinished, sortFindings, verdictCounts,
  witnessOf, witnessSummary,
} from "./witnesses.js";

const evidence = [
  { id: "a", source: "static", polarity: "declares" },
  { id: "b", source: "sdk", polarity: "declares" },
  { id: "c", source: "datasafety", polarity: "declares" },
  { id: "d", source: "policy", polarity: "denies" },
  { id: "e", source: "policy", polarity: "declares" },
  { id: "f", source: "reviews", polarity: "declares" },
];
const byId = indexById(evidence);

test("static and sdk evidence both count as the 'code' witness", () => {
  assert.equal(witnessOf({ source: "static" }), "code");
  assert.equal(witnessOf({ source: "sdk" }), "code");
  assert.equal(witnessOf({ source: "policy" }), "policy");
});

test("witnessSummary separates policy declarations from denials", () => {
  assert.deepEqual(witnessSummary(evidence), {
    code: 2, datasafety: 1, policyDeclares: 1, policyDenies: 1, reviews: 1,
  });
});

test("evidenceFor skips unknown ids", () => {
  assert.deepEqual(evidenceFor({ evidence_ids: ["a", "zzz"] }, byId).map((e) => e.id), ["a"]);
  assert.deepEqual(evidenceFor({}, byId), []);
});

const findings = [
  { category: "location", verdict: "consistent", evidence_ids: ["a", "c"] },
  { category: "camera", verdict: "potentially_inconsistent", evidence_ids: ["a"] },
  { category: "calendar", verdict: "uncertain", evidence_ids: ["f"] },
  { category: "analytics", verdict: "potentially_inconsistent", evidence_ids: ["b"] },
];

test("findings sort worst-first then alphabetically", () => {
  assert.deepEqual(sortFindings(findings).map((f) => f.category), ["analytics", "camera", "calendar", "location"]);
});

test("verdictCounts always returns all three verdicts", () => {
  assert.deepEqual(verdictCounts(findings).map((v) => [v.key, v.count]), [
    ["potentially_inconsistent", 2], ["uncertain", 1], ["consistent", 1],
  ]);
  assert.deepEqual(verdictCounts([]).map((v) => v.count), [0, 0, 0]);
});

test("evidenceByWitness builds stacked-chart rows", () => {
  const rows = evidenceByWitness(findings.slice(0, 1), byId);
  assert.deepEqual(rows, [{ name: "Location", Code: 1, "Data Safety": 1, Policy: 0, Reviews: 0 }]);
});

test("isFinished", () => {
  assert.ok(isFinished("done") && isFinished("failed"));
  assert.ok(!isFinished("running") && !isFinished("queued"));
});
