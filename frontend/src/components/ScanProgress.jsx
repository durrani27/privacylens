const STAGE_TEXT = {
  queued: "Waiting for a worker…",
  acquisition: "Collecting the Play Store page and APK…",
  analysis: "Analysing code, Data Safety label, policy and reviews…",
  findings: "Cross-checking the sources…",
  finished: "Done",
};

export default function ScanProgress({ scan }) {
  const failed = scan.status === "failed";
  return (
    <section className="card" aria-live="polite">
      <h2>{scan.title || scan.package}</h2>
      <p className="muted">
        {scan.package}
        {scan.app_version ? ` · v${scan.app_version}` : ""}
        {scan.developer ? ` · ${scan.developer}` : ""}
      </p>
      {failed ? (
        <p role="alert" className="error">Scan failed: {scan.error || "unknown error"}</p>
      ) : scan.status !== "done" ? (
        <>
          <progress max="100" value={scan.progress} aria-label="Scan progress" />
          <p className="muted">{STAGE_TEXT[scan.stage] || scan.stage}</p>
        </>
      ) : (
        <p className="muted">{scan.findings.length} categories analysed.</p>
      )}
    </section>
  );
}
