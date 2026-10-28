import { useEffect, useState, type FormEvent } from "react";
import {
  Braces,
  Building2,
  Image,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Field, Input, Select, Textarea } from "../components/ui/field";
import { PageHeader } from "../components/ui/page";
import {
  api,
  systemDesignDiagramUrl,
  type CodeResult,
  type CodingStatus,
  type QuestionBank,
  type SystemDesign,
} from "../lib/api";
import { runBrowserJavaScript } from "../lib/browserRunner";

const CODING_CHALLENGES = [
  {
    title: "Warm-up: frequency map",
    prompt:
      "Return the most frequent value in an array. Discuss time and space complexity.",
    starter:
      "function mostFrequent(values) {\n  // Your solution\n}\n\nconsole.log(mostFrequent([2, 1, 2, 3, 2, 1]))",
  },
  {
    title: "Backend: request deduplication",
    prompt: "Deduplicate request IDs while preserving their first-seen order.",
    starter:
      "function deduplicate(ids) {\n  // Your solution\n}\n\nconsole.log(deduplicate(['a', 'b', 'a', 'c', 'b']))",
  },
  {
    title: "Algorithms: merge intervals",
    prompt: "Merge overlapping numeric intervals and explain the sorting cost.",
    starter:
      "function mergeIntervals(intervals) {\n  // Your solution\n}\n\nconsole.log(mergeIntervals([[1, 3], [2, 6], [8, 10]]))",
  },
];

export function LabsPage() {
  const [coding, setCoding] = useState<CodingStatus | null>(null);
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(
    'def solve():\n    print("Hello, interview!")\n\nsolve()',
  );
  const [result, setResult] = useState<CodeResult | null>(null);
  const [browserCode, setBrowserCode] = useState(
    'function solve() {\n  console.log("Hello, interview!")\n}\n\nsolve()',
  );
  const [browserResult, setBrowserResult] = useState<CodeResult | null>(null);
  const [challenge, setChallenge] = useState(0);
  const [banks, setBanks] = useState<QuestionBank[]>([]);
  const [designs, setDesigns] = useState<SystemDesign[]>([]);
  const [bankName, setBankName] = useState("");
  const [company, setCompany] = useState("");
  const [notes, setNotes] = useState("");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [designNotes, setDesignNotes] = useState("");
  const [diagram, setDiagram] = useState<File | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .codingStatus()
      .then(setCoding)
      .catch(() => undefined);
    api
      .listQuestionBanks()
      .then(setBanks)
      .catch(() => undefined);
    api
      .listSystemDesigns()
      .then(setDesigns)
      .catch(() => undefined);
  }, []);

  async function run() {
    setBusy("code");
    setError(null);
    setResult(null);
    try {
      setResult(await api.runCode(language, code));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run code");
    } finally {
      setBusy("");
    }
  }
  async function runInBrowser() {
    setBusy("browser");
    setError(null);
    setBrowserResult(null);
    try {
      setBrowserResult(await runBrowserJavaScript(browserCode));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run JavaScript");
    } finally {
      setBusy("");
    }
  }
  async function createBank(e: FormEvent) {
    e.preventDefault();
    setBusy("bank");
    setError(null);
    try {
      const bank = await api.createQuestionBank({
        name: bankName,
        company,
        notes,
      });
      setBanks((old) => [bank, ...old]);
      setBankName("");
      setCompany("");
      setNotes("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save question bank");
    } finally {
      setBusy("");
    }
  }
  async function generate(bank: QuestionBank) {
    setBusy(bank.id);
    setError(null);
    try {
      const updated = await api.generateQuestionBank(bank.id, 10);
      setBanks((old) =>
        old.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate questions");
    } finally {
      setBusy("");
    }
  }
  async function removeBank(id: string) {
    await api.deleteQuestionBank(id);
    setBanks((old) => old.filter((item) => item.id !== id));
  }
  async function createDesign(e: FormEvent) {
    e.preventDefault();
    if (!diagram) return;
    setBusy("design");
    setError(null);
    try {
      const item = await api.createSystemDesign({
        title,
        prompt,
        notes: designNotes,
        diagram,
      });
      setDesigns((old) => [item, ...old]);
      setTitle("");
      setPrompt("");
      setDesignNotes("");
      setDiagram(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save design");
    } finally {
      setBusy("");
    }
  }
  async function removeDesign(id: string) {
    await api.deleteSystemDesign(id);
    setDesigns((old) => old.filter((item) => item.id !== id));
  }
  async function reviewDesign(id: string) {
    setBusy(id);
    setError(null);
    try {
      const updated = await api.reviewSystemDesign(id);
      setDesigns((old) => old.map((item) => (item.id === id ? updated : item)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not review design");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Practice lab"
        subtitle="Coding rounds, system-design work and private company-specific question banks."
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          [
            Braces,
            "Sandboxed coding",
            "Run JavaScript safely in your browser, with an optional isolated server runner for Python.",
          ],
          [
            Image,
            "System design",
            "Keep architecture prompts, notes and validated diagram images together.",
          ],
          [
            Building2,
            "Company question banks",
            "Turn your own research notes into targeted practice questions.",
          ],
        ].map(([Icon, name, text]) => (
          <Card key={String(name)} className="p-5">
            <Icon className="size-6 text-brand-600" />
            <h2 className="mt-3 font-semibold">{String(name)}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              {String(text)}
            </p>
          </Card>
        ))}
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-xl bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </p>
      )}
      <Card className="space-y-5 border-brand-200">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.15em] text-brand-600">
              Works without server setup
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              JavaScript browser sandbox
            </h2>
          </div>
          <Badge tone="success">Ready</Badge>
        </div>
        <p className="flex gap-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
          <ShieldCheck className="size-5 shrink-0 text-emerald-600" /> Runs in a
          disposable Web Worker with DOM, cookies, network, storage and
          nested-worker APIs unavailable. It is terminated after 2.5 seconds and
          code never reaches the server.
        </p>
        <div className="grid gap-4 sm:grid-cols-[240px_1fr]">
          <Field label="Practice challenge">
            <Select
              value={challenge}
              onChange={(event) => {
                const index = Number(event.target.value);
                setChallenge(index);
                setBrowserCode(CODING_CHALLENGES[index].starter);
                setBrowserResult(null);
              }}
            >
              {CODING_CHALLENGES.map((item, index) => (
                <option key={item.title} value={index}>
                  {item.title}
                </option>
              ))}
            </Select>
          </Field>
          <p className="self-end rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm text-brand-800">
            {CODING_CHALLENGES[challenge].prompt}
          </p>
        </div>
        <Field label={`JavaScript (${browserCode.length}/20000)`}>
          <Textarea
            className="min-h-64 font-mono"
            value={browserCode}
            maxLength={20000}
            onChange={(e) => setBrowserCode(e.target.value)}
          />
        </Field>
        <Button
          onClick={runInBrowser}
          disabled={busy === "browser" || !browserCode.trim()}
        >
          {busy === "browser" ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}{" "}
          Run JavaScript
        </Button>
        {browserResult && (
          <div className="grid gap-3 md:grid-cols-2">
            <pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-emerald-300">
              {browserResult.stdout || "(no output)"}
            </pre>
            <pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-rose-300">
              {browserResult.stderr || `Exit code: ${browserResult.exit_code}`}
            </pre>
          </div>
        )}
      </Card>

      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.15em] text-brand-600">
              Coding round
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              Optional server runner (Python)
            </h2>
          </div>
          <Badge tone={coding?.enabled ? "success" : "warning"}>
            {coding?.enabled
              ? "Isolated Python runner ready"
              : "Python runner unavailable"}
          </Badge>
        </div>
        <p className="flex gap-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
          <ShieldCheck className="size-5 shrink-0 text-emerald-600" />
          <span>{coding?.detail ?? "Checking isolated runner readiness…"}</span>
        </p>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {[
            "Fresh gVisor sandbox",
            "Network disabled",
            "Non-root + read-only",
            "CPU, memory & time limits",
          ].map((item) => (
            <div
              key={item}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600"
            >
              <ShieldCheck className="mr-1.5 inline size-4 text-emerald-600" />
              {item}
            </div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-[180px_1fr]">
          <Field label="Language">
            <Select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="python">Python</option>
            </Select>
          </Field>
          <Field
            label={`Code (${code.length}/${coding?.max_code_chars ?? 20000})`}
          >
            <Textarea
              className="min-h-64 font-mono"
              value={code}
              maxLength={coding?.max_code_chars ?? 20000}
              onChange={(e) => setCode(e.target.value)}
            />
          </Field>
        </div>
        <Button
          onClick={run}
          disabled={!coding?.enabled || busy === "code" || !code.trim()}
        >
          {busy === "code" ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}{" "}
          Run safely
        </Button>
        {result && (
          <div className="grid gap-3 md:grid-cols-2">
            <pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-emerald-300">
              {result.stdout || "(no output)"}
            </pre>
            <pre className="max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-rose-300">
              {result.stderr || `Exit code: ${result.exit_code}`}
            </pre>
          </div>
        )}
      </Card>

      <div className="grid gap-8 xl:grid-cols-2">
        <Card className="space-y-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.15em] text-brand-600">
              Question banks
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              Practise for a specific company
            </h2>
          </div>
          <form onSubmit={createBank} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Bank name">
                <Input
                  required
                  maxLength={120}
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="Backend interview research"
                />
              </Field>
              <Field label="Company">
                <Input
                  maxLength={120}
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Company name"
                />
              </Field>
            </div>
            <Field
              label="Your notes"
              hint="Paste public job, engineering-blog and interview research notes. Instructions inside notes are treated as untrusted data."
            >
              <Textarea
                required
                minLength={20}
                maxLength={50000}
                className="min-h-36"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Field>
            <Button disabled={busy === "bank"}>Save private bank</Button>
          </form>
          <div className="space-y-3">
            {banks.map((bank) => (
              <div
                key={bank.id}
                className="rounded-xl border border-slate-200 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{bank.name}</p>
                    <p className="text-xs text-slate-500">
                      {bank.company || "General"} · {bank.questions_json.length}{" "}
                      questions
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Delete ${bank.name}`}
                    onClick={() => removeBank(bank.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => generate(bank)}
                    disabled={busy === bank.id}
                  >
                    {busy === bank.id ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}{" "}
                    Generate 10
                  </Button>
                </div>
                {bank.questions_json.length > 0 && (
                  <ol className="mt-4 space-y-2 text-sm text-slate-600">
                    {bank.questions_json.map((question, index) => (
                      <li key={`${question.question}-${index}`}>
                        <span className="font-medium text-slate-800">
                          {index + 1}. {question.question}
                        </span>{" "}
                        <Badge>{question.difficulty}</Badge>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            ))}
          </div>
        </Card>

        <Card className="space-y-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.15em] text-brand-600">
              System design
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              Architecture portfolio
            </h2>
          </div>
          <form onSubmit={createDesign} className="space-y-4">
            <Field label="Design title">
              <Input
                required
                maxLength={160}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Design a notification platform"
              />
            </Field>
            <Field label="Interview prompt">
              <Textarea
                required
                minLength={10}
                maxLength={10000}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </Field>
            <Field label="Trade-offs and notes">
              <Textarea
                maxLength={30000}
                value={designNotes}
                onChange={(e) => setDesignNotes(e.target.value)}
              />
            </Field>
            <Field
              label="Diagram image"
              hint="PNG, JPEG or WebP only; maximum 5 MB. SVG is rejected because it can contain scripts."
            >
              <Input
                required
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setDiagram(e.target.files?.[0] ?? null)}
              />
            </Field>
            <Button disabled={!diagram || busy === "design"}>
              {busy === "design" ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Image className="size-4" />
              )}{" "}
              Save design
            </Button>
          </form>
          <div className="grid gap-3 sm:grid-cols-2">
            {designs.map((design) => (
              <div
                key={design.id}
                className="overflow-hidden rounded-xl border border-slate-200"
              >
                <img
                  src={systemDesignDiagramUrl(design.id)}
                  alt={`${design.title} diagram`}
                  className="h-36 w-full bg-slate-50 object-contain"
                />
                <div className="p-3">
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">
                        {design.title}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {design.filename}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Delete ${design.title}`}
                      onClick={() => removeDesign(design.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  <Button
                    className="mt-3"
                    size="sm"
                    onClick={() => reviewDesign(design.id)}
                    disabled={busy === design.id}
                  >
                    {busy === design.id ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}{" "}
                    Review reasoning
                  </Button>
                  {design.feedback_json && (
                    <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                      <p>{design.feedback_json.summary}</p>
                      <p className="mt-2 font-semibold text-emerald-700">
                        Strengths
                      </p>
                      <ul className="list-disc pl-4">
                        {design.feedback_json.strengths.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                      <p className="mt-2 font-semibold text-amber-700">Risks</p>
                      <ul className="list-disc pl-4">
                        {design.feedback_json.risks.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
