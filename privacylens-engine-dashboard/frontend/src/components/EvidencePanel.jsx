import { witnessOf } from "../lib/witnesses.js";

const WITNESS_LABEL = { code: "App code", datasafety: "Data Safety label", policy: "Privacy policy", reviews: "User review" };

/** The exact evidence rows behind one verdict. (The interactive Evidence Graph arrives in Iteration 6.) */
export default function EvidencePanel({ evidence }) {
  if (!evidence.length) return <p className="muted">No evidence rows.</p>;
  return (
    <ul className="evidence">
      {evidence.map((e) => (
        <li key={`${e.id}-${e.raw_value}`}>
          <span className="src">{WITNESS_LABEL[witnessOf(e)]}</span>
          {e.polarity === "denies" && <span className="deny"> · states it does NOT do this</span>}
          <div className="raw">{e.raw_value}</div>
          {e.snippet && e.snippet !== e.raw_value && <div className="muted small">{e.snippet}</div>}
        </li>
      ))}
    </ul>
  );
}
