import { jsPDF } from "jspdf";

export function buildRunReport(projectName: string, run: Record<string, unknown>, files: Record<string, string>, progress?: unknown) {
  const pdf = new jsPDF();
  let y = 22;
  const write = (text: string, size = 10) => {
    pdf.setFontSize(size);
    const lines: string[] = pdf.splitTextToSize(text.replace(/[^\x20-\x7E\n]/g, "?"), 174);
    for (const line of lines) {
      if (y > 274) { pdf.addPage(); y = 22; }
      pdf.text(line, 18, y); y += size === 10 ? 5 : 8;
    }
    y += 5;
  };
  write("Teachsight | Training run report", 18);
  write(`${projectName}\nRun: ${String(run['id'])}\nExported: ${new Date().toISOString()}`);
  write("Settings", 14);
  write(files["config.yaml"] || JSON.stringify(run['config'] ?? run['settings'] ?? "Not recorded by the engine", null, 2));
  write("Progress", 14);
  write(JSON.stringify(progress ?? run['progress'] ?? run['steps'] ?? { status: run['status'] ?? "Not recorded by the engine" }, null, 2));
  write("Evaluation results", 14);
  write(JSON.stringify(run['metrics'] ?? run['result'] ?? "No evaluation results recorded", null, 2));
  write("Run record", 14); write(JSON.stringify(run, null, 2));
  for (let i = 1; i <= pdf.getNumberOfPages(); i++) { pdf.setPage(i); pdf.setFontSize(8); pdf.text(`Teachsight | Page ${i} of ${pdf.getNumberOfPages()}`, 18, 288); }
  return pdf.output("blob");
}

export function downloadReport(blob: Blob, filename: string) {
  const file = new File([blob], filename, { type: "application/pdf" });
  if (matchMedia("(pointer: coarse)").matches && navigator.canShare?.({ files: [file] })) {
    void navigator.share({ files: [file], title: filename }).catch((e) => { if (e.name !== "AbortError") save(); });
  } else save();
  function save() {
    const url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
}