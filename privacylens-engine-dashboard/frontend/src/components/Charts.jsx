import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { evidenceByWitness, verdictCounts } from "../lib/witnesses.js";

const WITNESS_COLORS = {
  Code: "#2f5d8a",
  "Data Safety": "#6a4c93",
  Policy: "#2a7f62",
  Reviews: "#8a6d1d",
};

export default function Charts({ findings, evidenceById }) {
  if (!findings.length) return null;
  const counts = verdictCounts(findings);
  const byWitness = evidenceByWitness(findings, evidenceById);

  return (
    <section className="grid2">
      <div className="card">
        <h2>Verdicts</h2>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={counts}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" name="Categories">
              {counts.map((d) => <Cell key={d.key} fill={d.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h2>Evidence by source</h2>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={byWitness}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" interval={0} angle={-25} textAnchor="end" height={70} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Legend verticalAlign="top" />
            {Object.entries(WITNESS_COLORS).map(([key, color]) => (
              <Bar key={key} dataKey={key} stackId="a" fill={color} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
