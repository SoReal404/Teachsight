export type Opt = { v: string; l: string };
export type Q = { id: string; label: string; why: string; kind: "text" | "long" | "tags" | "choice" | "multi"; options?: Opt[]; required?: boolean; placeholder?: string };
const o = (...p: [string, string][]): Opt[] => p.map(([v, l]) => ({ v, l }));
const ch = (id: string, label: string, why: string, options: Opt[]): Q => ({ id, label, why, kind: "choice", options });
const mu = (id: string, label: string, why: string, options: Opt[]): Q => ({ id, label, why, kind: "multi", options });
const tg = (id: string, label: string, why: string, placeholder = "Type a name and press Enter"): Q => ({ id, label, why, kind: "tags", placeholder });
const WORSE = (id: string) => ch(id, "Which mistake is worse?", "Sets how cautious the AI is.", o(["miss", "Missing one"], ["alarm", "A false alarm"], ["equal", "Both equal"]));

export const READY = new Set(["classification", "detection"]);          // types that can be trained today
export const TYPES = [
  { id: "classification", name: "Sort pictures into groups", tech: "Image classification", example: "Which plant is this? Is this X-ray normal? Which animal is this?", icon: "M4 4h24v24H4zM10 17l4 4 8-9" },
  { id: "detection", name: "Find and box things", tech: "Object detection", example: "Is everyone wearing a helmet? Count the cars in a video.", icon: "M4 10V4h6M22 4h6v6M28 22v6h-6M10 28H4v-6M11 11h10v10H11z" },
  { id: "segmentation", name: "Outline exact shapes", tech: "Image segmentation", example: "Outline a tumor. Separate road from buildings.", icon: "M6 20c-2-8 6-14 13-12s9 9 4 14-14 5-17-2z" },
  { id: "pose", name: "Track body and hand movement", tech: "Pose estimation and tracking", example: "Check workout posture, spot a drowsy driver, read sign language.", icon: "M16 3a3 3 0 100 6 3 3 0 000-6zM16 9v10M8 13l8 2 8-2M16 19l-5 9M16 19l5 9" },
  { id: "ocr", name: "Read text in pictures", tech: "OCR and text extraction", example: "Read license plates, numbers or handwriting.", icon: "M5 9h22M5 16h22M5 23h14" },
  { id: "enhance", name: "Fix or transform pictures", tech: "Image processing and enhancement", example: "Remove a background, sharpen a blurry photo, upscale.", icon: "M16 4l2.5 7.5L26 14l-7.5 2.5L16 24l-2.5-7.5L6 14l7.5-2.5z" },
  { id: "vqa", name: "Describe or ask about pictures", tech: "Visual question answering and captioning", example: "“What is in this picture?” or “Is the door open?”", icon: "M5 7h22v14H15l-6 5v-5H5z" },
  { id: "unsure", name: "I’m not sure", tech: "Let me help you choose", example: "Two quick questions, then I’ll suggest the right one.", icon: "M16 4a12 12 0 100 24 12 12 0 000-24zM12.5 13a3.5 3.5 0 115 3.2c-1 .5-1.5 1.1-1.5 2.3M16 23v.5" },
];

export const UNSURE: Q[] = [
  ch("u_where", "What kind of answer do you want?", "This points me to the right type.", o(["whole", "One answer for the whole picture"], ["locate", "Where things are inside the picture"], ["outline", "The exact outline of things"], ["body", "How a body or hands move"])),
  ch("u_other", "Or is the goal one of these?", "Some goals need a different kind of AI.", o(["none", "None of these"], ["text", "Read text in pictures"], ["describe", "Describe pictures or answer questions"], ["improve", "Improve how pictures look"])),
];
export function resolveUnsure(a: Record<string, string>): string {
  const other = { text: "ocr", describe: "vqa", improve: "enhance" } as Record<string, string>;
  if (other[a.u_other]) return other[a.u_other];
  return ({ whole: "classification", locate: "detection", outline: "segmentation", body: "pose" } as Record<string, string>)[a.u_where] ?? "classification";
}

export const TYPE_Q: Record<string, Q[]> = {
  classification: [
    tg("categories", "What are the categories?", "These are the answer names. I compare them with your folders."),
    ch("single_label", "Does each picture have exactly one answer?", "Decides how the AI is set up to answer.", o(["one", "Yes, exactly one"], ["several", "No, it can have several"])),
    ch("sorted", "Are the pictures already sorted into folders?", "Tells me how to read your folders.", o(["sorted", "Yes, one folder per category"], ["unsorted", "No, not sorted yet"], ["file", "A file lists them"])),
    ch("none_case", "Can a picture belong to none of them?", "I can add a “none of these” answer.", o(["yes", "Yes"], ["no", "No"])),
    tg("lookalikes", "Which categories look alike?", "I pay extra attention to confusing pairs.", "Optional. Type a name and press Enter"),
    ch("object_size", "Does the thing fill the picture?", "Small things inside a scene may need “Find and box things” instead.", o(["fills", "Yes, it fills the picture"], ["small", "It is small inside a scene"], ["varies", "It varies"])),
    WORSE("worse"),
  ],
  detection: [
    tg("det_objects", "What should the AI find?", "These become the names the AI learns."),
    ch("det_count", "How many usually appear in one picture?", "Decides how many boxes the AI can draw per picture.", o(["one", "Just one"], ["few", "A few (2 to 5)"], ["many", "Many (10+)"], ["crowded", "Crowded"])),
    ch("det_size", "How big are they in the picture?", "Tiny things need bigger pictures to be seen, which takes longer.", o(["large", "Large"], ["medium", "Medium"], ["tiny", "Tiny"])),
    ch("det_boxes", "Do you already have boxes drawn?", "If not, I draw boxes with AI and you only review them.", o(["files", "Yes, I have box files"], ["propose", "No, propose them for me"], ["unsure", "Not sure"])),
    ch("det_overlap", "Can objects overlap or be partly hidden?", "Changes training pictures and how duplicate boxes are handled.", o(["yes", "Yes"], ["no", "No"])),
    ch("det_video", "Are many pictures frames from one video?", "I keep each video together when I split, so the final score stays honest.", o(["videos", "Yes, from videos"], ["photos", "No, separate photos"])),
    WORSE("det_worse"),
    ch("det_live", "Will it run on live video?", "Sets how fast the AI must be.", o(["yes", "Yes"], ["no", "No"])),
  ],
  segmentation: [
    tg("seg_regions", "What regions should be outlined?", "These become the names the AI learns."),
    ch("seg_kind", "Outline each object separately, or label areas?", "Picks the right kind of AI.", o(["instance", "Each object separately"], ["semantic", "Areas (like road vs building)"])),
    ch("seg_edges", "How precise must the edges be?", "Sets picture size and training length.", o(["rough", "Rough is fine"], ["precise", "Precise"], ["medical", "Medical-level"])),
    ch("seg_masks", "Do you already have outlines?", "Decides how I import them, or whether AI helps you outline.", o(["none", "No"], ["masks", "Yes, as mask pictures"], ["polygons", "Yes, as polygon files"])),
    ch("seg_thin", "Are the regions small or thin (cracks, vessels)?", "Changes how mistakes are scored.", o(["yes", "Yes"], ["no", "No"])),
    ch("seg_format", "What kind of pictures are they?", "Some formats need special reading.", o(["photos", "Normal photos"], ["medical", "Medical or scientific files"], ["huge", "Very large images"])),
    ch("seg_use", "What will you do with the result?", "Decides the output format.", o(["measure", "Measure areas"], ["cutout", "Cut things out"], ["overlay", "Show an overlay"])),
  ],
  pose: [
    ch("pose_what", "What should be tracked?", "Decides whether a ready-made model is enough.", o(["body", "A body"], ["hands", "Hands"], ["face", "A face"], ["animal", "An animal"], ["custom", "Custom points"])),
    ch("pose_people", "One person or several?", "Single and multi-person need different approaches.", o(["one", "One"], ["several", "Several"])),
    ch("pose_source", "Pictures, recorded video, or live camera?", "Decides tracking and speed.", o(["pictures", "Pictures"], ["video", "Recorded video"], ["live", "Live camera"])),
    ch("pose_use", "What will you do with the movement?", "Decides which rules are added after the points.", o(["reps", "Count reps"], ["posture", "Check posture"], ["drowsy", "Spot drowsiness"], ["gesture", "Recognize gestures"])),
    ch("pose_camera", "How is the camera placed?", "Changes training pictures and expectations.", o(["front", "Front"], ["side", "Side"], ["moving", "It moves"], ["varied", "It varies"])),
    ch("pose_labels", "What do you already have?", "Many cases need no training at all.", o(["points", "Labeled points"], ["videos", "Example videos"], ["nothing", "Nothing, use a ready-made model"])),
    ch("pose_consent", "Are people recorded who should give consent?", "Adds a privacy reminder.", o(["yes", "Yes"], ["no", "No"])),
  ],
  ocr: [
    ch("ocr_kind", "What kind of text?", "Picks the model family.", o(["printed", "Printed"], ["handwriting", "Handwriting"], ["plates", "License plates"], ["numbers", "Numbers only"], ["forms", "Receipts or forms"], ["ids", "ID documents"])),
    mu("ocr_langs", "Which languages?", "Loads the right language packs, including right-to-left scripts.", o(["en", "English"], ["ar", "Arabic"], ["latin", "Other Latin scripts"], ["other", "Other"])),
    ch("ocr_scope", "Whole pages, or small fields?", "Find-then-read or read-only.", o(["pages", "Whole pages"], ["fields", "Small cropped fields"])),
    { id: "ocr_pattern", label: "Does the text follow a pattern?", why: "A pattern like a plate format fixes many mistakes.", kind: "text", placeholder: "Optional, for example 3 letters then 4 digits" },
    ch("ocr_truth", "Do you have pictures with the correct text typed out?", "Lets me measure and fine-tune.", o(["yes", "Yes"], ["no", "No"])),
    mu("ocr_quality", "How good are the pictures?", "Decides cleanup steps before reading.", o(["blurry", "Blurry"], ["tilted", "Tilted"], ["dark", "Dark"], ["curved", "Curved"], ["good", "Clear"])),
    ch("ocr_output", "What happens with the result?", "Decides the export format.", o(["table", "Put in a table"], ["search", "Make searchable"], ["validate", "Check against a list"])),
    ch("ocr_sensitive", "Are the documents sensitive?", "Adds a local-only reminder.", o(["yes", "Yes"], ["no", "No"])),
  ],
  enhance: [
    ch("enh_what", "What should be done?", "Picks the model family.", o(["bg", "Remove background"], ["upscale", "Make bigger and sharper"], ["denoise", "Remove noise"], ["sharpen", "Fix blur"], ["colorize", "Add color"], ["restore", "Restore old photos"], ["style", "Change style"])),
    ch("enh_pairs", "Do you have before-and-after pairs?", "Decides how the AI is taught, or whether a ready-made model is enough.", o(["pairs", "Yes, pairs"], ["good", "Only good pictures"], ["none", "Neither"])),
    ch("enh_judge", "How will you judge success?", "Accuracy numbers do not apply here, so you compare side by side.", o(["eyes", "By looking"], ["numbers", "With numbers"])),
    ch("enh_batch", "One picture at a time, or hundreds?", "Decides speed and batch mode.", o(["one", "One at a time"], ["batch", "Hundreds at once"])),
    ch("enh_protect", "Must faces or text stay unchanged?", "Adds protective settings.", o(["yes", "Yes"], ["no", "No"])),
    ch("enh_size", "What size should the result be?", "Decides output size and memory needs.", o(["same", "Same size"], ["x2", "Twice as big"], ["x4", "Four times as big"])),
  ],
  vqa: [
    ch("vqa_goal", "What do you want?", "Sets up the task.", o(["describe", "Describe pictures"], ["answer", "Answer questions"], ["fact", "Check one fact"], ["search", "Search by words"])),
    ch("vqa_lang", "What language should answers be in?", "Picks the model.", o(["en", "English"], ["ar", "Arabic"], ["other", "Other"])),
    ch("vqa_fixed", "Free text, or a fixed choice like yes or no?", "A fixed choice is cheaper and more accurate with a classifier.", o(["free", "Free text"], ["fixed", "Fixed choices"])),
    ch("vqa_examples", "Do you have example questions and answers?", "Decides prompting with examples or light fine-tuning.", o(["none", "No"], ["some", "A few (under 100)"], ["many", "Many"])),
    { id: "vqa_vocab", label: "Any special vocabulary?", why: "Helps the model use your words.", kind: "text", placeholder: "Optional, for example medical or retail terms" },
    ch("vqa_where", "Where may it run?", "Cloud models send pictures off this PC, so I need your explicit OK.", o(["local", "This PC only"], ["cloud", "A cloud service is OK"])),
  ],
};
export const PICTURES: Q[] = [
  { id: "subject", label: "What do your pictures show?", why: "Used to explain things in your own words.", kind: "long", placeholder: "Close-up photos of phone screens on a desk." },
  ch("source", "Where do the pictures come from?", "Tells me what quality and variety to expect.", o(["phone", "A phone"], ["camera", "A camera"], ["internet", "The internet"], ["scanner", "A scanner"], ["mixed", "A mix"])),
  mu("conditions", "What are they like?", "Changes training pictures and warns about shortcuts.", o(["same", "Same place and light"], ["varied", "Different places and light"], ["closeup", "Close-ups"], ["crowded", "Several things per picture"], ["poor", "Some blurry or dark"])),
  ch("count", "About how many pictures do you have?", "Tells me which fixes are realistic.", o(["under_100", "Under 100"], ["100_1000", "100 to 1,000"], ["1000_10000", "1,000 to 10,000"], ["over_10000", "Over 10,000"])),
];
export const USE: Q[] = [
  ch("usage", "Where will the finished AI run?", "Decides model size and export.", o(["phone", "A phone or app"], ["pc", "A computer"], ["web", "A website or server"], ["test", "Just testing"])),
  ch("priority", "What matters most?", "Decides training rounds and model size.", o(["fast", "A quick first try"], ["balanced", "A good balance"], ["best", "The best accuracy"])),
  ch("time_limit", "How long can training take?", "Sets the time budget.", o(["30min", "About 30 minutes"], ["2h", "A couple of hours"], ["overnight", "Overnight"], ["none", "No limit"])),
  { id: "notes", label: "Anything else I should know?", why: "Kept with your project.", kind: "long" },
];
export type Step = { title: string; sub: string; qs: Q[] };
export function buildSteps(type: string): Step[] {
  const qs = TYPE_Q[type] ?? [], out: Step[] = [{ title: "Your goal", sub: "Tell me what you want to achieve.", qs: [
    { id: "name", label: "Project name", why: "Just a title.", kind: "text", required: true, placeholder: "For example: Phone screen checker" },
    { id: "goal", label: "What do you want to achieve?", why: "I use it to explain things in plain words.", kind: "long", required: true, placeholder: "I sell used phones and want to know which have a cracked screen." }] }];
  for (let i = 0; i < qs.length; i += 4) out.push({ title: i === 0 ? "About your project" : "A few more details", sub: "Tap your answers. Hover a card to see why I ask.", qs: qs.slice(i, i + 4) });
  out.push({ title: "Your pictures", sub: "This helps me spot problems early.", qs: PICTURES }, { title: "How you will use it", sub: "This helps me choose the right AI and training time.", qs: USE });
  return out;
}
export const allQ = (type: string): Q[] => buildSteps(type).flatMap((s) => s.qs);
export const labelOf = (q: Q, v: any): string => {
  const pick = (x: string) => q.options?.find((o) => o.v === x)?.l ?? x;
  return Array.isArray(v) ? v.map(pick).join(", ") : q.options ? pick(String(v)) : String(v);
};
