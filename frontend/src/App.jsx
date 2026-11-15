import { useCallback, useEffect, useRef, useState } from "react";
import { createScan, getEvidence, getScan } from "./api.js";
import { POLL_MS, indexById, isFinished } from "./lib/witnesses.js";
import SubmitForm from "./components/SubmitForm.jsx";
import ScanProgress from "./components/ScanProgress.jsx";
import VerdictTable from "./components/VerdictTable.jsx";
import Charts from "./components/Charts.jsx";

/** Polls GET /scans/:id every POLL_MS until it is done/failed, then loads the evidence once. */
function useScan(scanId) {
  const [scan, setScan] = useState(null);
  const [evidence, setEvidence] = useState({});
  const [error, setError] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    if (!scanId) return undefined;
    let cancelled = false;
    setScan(null);
    setEvidence({});
    setError(null);

    const tick = async () => {
      try {
        const s = await getScan(scanId);
        if (cancelled) return;
        setScan(s);
        if (s.status === "done") {
          const rows = await getEvidence(scanId);
          if (!cancelled) setEvidence(indexById(rows));
        }
        if (!isFinished(s.status) && !cancelled) timer.current = setTimeout(tick, POLL_MS);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer.current);
    };
  }, [scanId]);

  return { scan, evidence, error };
}

export default function App() {
  const [scanId, setScanId] = useState(() => window.location.hash.slice(1) || null);
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const { scan, evidence, error } = useScan(scanId);

  const submit = useCallback(async (query) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await createScan(query);
      window.location.hash = res.scan_id; // refresh-safe: the URL remembers the scan
      setScanId(res.scan_id);
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }, []);

  return (
    <main className="page">
      <header>
        <h1>PrivacyLens+</h1>
        <p className="tagline">
          Does what an Android app <em>does</em> match what it <em>says</em>? We cross-check its code,
          Play Store label, privacy policy and user reviews.
        </p>
      </header>

      <SubmitForm onSubmit={submit} busy={submitting} error={submitError} />

      {error && <p role="alert" className="error">{error}</p>}
      {scan && <ScanProgress scan={scan} />}

      {scan?.status === "done" && (
        <>
          <Charts findings={scan.findings} evidenceById={evidence} />
          <VerdictTable findings={scan.findings} evidenceById={evidence} />
        </>
      )}
    </main>
  );
}
