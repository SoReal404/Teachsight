import { z } from "zod";

export const diagnosticInput = z.object({
  projectId: z.string().min(1).max(200),
  projectName: z.string().min(1).max(200),
  logs: z.string().trim().min(1).max(100000),
  metrics: z.record(z.unknown()).refine((v) => JSON.stringify(v).length <= 50000, "Metrics are too large"),
});

export function ownsSubmission(ownerId: string, userId: string) {
  return ownerId === userId;
}