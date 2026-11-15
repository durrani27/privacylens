// Pure helpers that turn findings + evidence into what the UI shows. No React here, so they are
// unit-tested with `npm test` (node --test) without installing anything.

export const POLL_MS = 2000; // the dashboard polls the scan every couple of seconds

export const CATEGORY_LABEL = {
  location: "Location",
  camera: "Camera",
  microphone: "Microphone",
  contacts: "Contacts",
  identifiers: "Device identifiers",
  analytics: "Analytics",
  advertising: "Advertising",
  storage: "Files and storage",
  phone_sms: "Phone and SMS",
  calendar: "Calendar",
};

export const VERDICTS = {
  potentially_inconsistent: { label: "Potentially inconsistent", icon: "⚠", color: "#b3261e", order: 0 },
  uncertain: { label: "Uncertain", icon: "?", color: "#8a5a00", order: 1 },
  consistent: { label: "Consistent", icon: "✓", color: "#1b6e3a", order: 2 },
};

export const isFinished = (status) => status === "done" || status === "failed";

/** Which of the four witnesses a raw evidence row belongs to. */
export function witnessOf(row) {
  if (row.source === "static" || row.source === "sdk") return "code";
  return row.source; // datasafety | policy | reviews
}

/** Counts per witness for one finding's evidence rows. */
export function witnessSummary(rows) {
  const s = { code: 0, datasafety: 0, policyDeclares: 0, policyDenies: 0, reviews: 0 };
  for (const r of rows) {
    const w = witnessOf(r);
    if (w === "policy") r.polarity === "denies" ? s.policyDenies++ : s.policyDeclares++;
    else if (w === "code") s.code++;
    else if (w === "datasafety") s.datasafety++;
    else if (w === "reviews") s.reviews++;
  }
  return s;
}

/** Look up a finding's evidence rows by id (unknown ids are skipped). */
export function evidenceFor(finding, evidenceById) {
  return (finding.evidence_ids || []).map((id) => evidenceById[id]).filter(Boolean);
}

export function indexById(evidence) {
  return Object.fromEntries(evidence.map((e) => [e.id, e]));
}

/** Findings sorted worst-first, then by category label. */
export function sortFindings(findings) {
  return [...findings].sort(
    (a, b) =>
      (VERDICTS[a.verdict]?.order ?? 9) - (VERDICTS[b.verdict]?.order ?? 9) ||
      a.category.localeCompare(b.category)
  );
}

/** Data for the verdict bar chart (always all three verdicts, zero included). */
export function verdictCounts(findings) {
  return Object.entries(VERDICTS)
    .sort((a, b) => a[1].order - b[1].order)
    .map(([key, v]) => ({
      key,
      name: v.label,
      color: v.color,
      count: findings.filter((f) => f.verdict === key).length,
    }));
}

/** Data for the stacked "evidence per category by witness" chart. */
export function evidenceByWitness(findings, evidenceById) {
  return sortFindings(findings).map((f) => {
    const s = witnessSummary(evidenceFor(f, evidenceById));
    return {
      name: CATEGORY_LABEL[f.category] ?? f.category,
      "Code": s.code,
      "Data Safety": s.datasafety,
      "Policy": s.policyDeclares + s.policyDenies,
      "Reviews": s.reviews,
    };
  });
}
