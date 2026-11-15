import { useState } from "react";
import {
  CATEGORY_LABEL, VERDICTS, evidenceFor, sortFindings, witnessSummary,
} from "../lib/witnesses.js";
import EvidencePanel from "./EvidencePanel.jsx";

function Badge({ verdict }) {
  const v = VERDICTS[verdict] || { label: verdict, icon: "•", color: "#444" };
  // icon + text + colour, so the verdict is never conveyed by colour alone
  return (
    <span className="badge" style={{ color: v.color, borderColor: v.color }}>
      <span aria-hidden="true">{v.icon}</span> {v.label}
    </span>
  );
}

function Witnesses({ s }) {
  const chip = (label, text) => <span className="chip" key={label}><b>{label}</b> {text}</span>;
  const policy = s.policyDenies && !s.policyDeclares ? "denies" : s.policyDeclares ? "mentions" : "silent";
  return (
    <div className="chips">
      {chip("Code", s.code ? `${s.code}` : "none")}
      {chip("Data Safety", s.datasafety ? "declared" : "not declared")}
      {chip("Policy", policy)}
      {s.reviews > 0 && chip("Reviews", `${s.reviews} (unverified)`)}
    </div>
  );
}

export default function VerdictTable({ findings, evidenceById }) {
  const [open, setOpen] = useState(null);
  const rows = sortFindings(findings);

  return (
    <section className="card">
      <h2>Category-by-category verdicts</h2>
      <table>
        <thead>
          <tr><th>Category</th><th>Verdict</th><th>What each source says</th><th>Why</th><th /></tr>
        </thead>
        <tbody>
          {rows.map((f) => {
            const evidence = evidenceFor(f, evidenceById);
            const isOpen = open === f.category;
            return (
              <FragmentRow key={f.category}>
                <tr>
                  <td>{CATEGORY_LABEL[f.category] || f.category}</td>
                  <td><Badge verdict={f.verdict} /></td>
                  <td><Witnesses s={witnessSummary(evidence)} /></td>
                  <td>
                    {f.explanation}
                    <div className="muted small">Rule {f.rule_id}</div>
                  </td>
                  <td>
                    <button
                      className="link"
                      aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : f.category)}
                    >
                      {isOpen ? "Hide evidence" : `Evidence (${evidence.length})`}
                    </button>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="evidence-row">
                    <td colSpan={5}><EvidencePanel evidence={evidence} /></td>
                  </tr>
                )}
              </FragmentRow>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// a keyed fragment so each finding can render two <tr>s
function FragmentRow({ children }) {
  return <>{children}</>;
}
