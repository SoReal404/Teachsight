CREATE TABLE public.training_diagnostics (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL DEFAULT auth.uid(),
 engine_project_id text NOT NULL,
 project_name text NOT NULL,
 logs text NOT NULL,
 metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
 diagnosis text NOT NULL DEFAULT '',
 status text NOT NULL DEFAULT 'submitted',
 created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.training_diagnostics TO authenticated;
GRANT ALL ON public.training_diagnostics TO service_role;
ALTER TABLE public.training_diagnostics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Read own diagnostics" ON public.training_diagnostics FOR SELECT TO authenticated USING (owner_id = auth.uid());
CREATE POLICY "Submit own diagnostics" ON public.training_diagnostics FOR INSERT TO authenticated WITH CHECK (owner_id = auth.uid());
CREATE TABLE public.training_ai_access (
 owner_id uuid PRIMARY KEY,
 denial_message text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.training_ai_access TO authenticated;
GRANT ALL ON public.training_ai_access TO service_role;
ALTER TABLE public.training_ai_access ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Read own AI access" ON public.training_ai_access FOR SELECT TO authenticated USING (owner_id = auth.uid());