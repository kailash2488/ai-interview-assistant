import { ArrowRight, BarChart3, BrainCircuit, ClipboardCheck, FileText, LineChart, LockKeyhole, MessagesSquare, ShieldCheck, Sparkles, Target } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { buttonClasses } from '../components/ui/button'

function GithubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

const REPO = 'https://github.com/kailash2488/ai-interview-assistant'

const FEATURES = [
  { icon: Target, title: 'Built from your resume and the job', text: 'Upload your resume and the job description. The interview covers the skills the role needs, your own projects, and the gaps an interviewer would probe.' },
  { icon: MessagesSquare, title: 'Follow-ups like a real interviewer', text: 'Vague answer? You get a sharp follow-up. Strong answer? The interviewer moves on. Questions never repeat and scores stay hidden until the end.' },
  { icon: ClipboardCheck, title: 'Honest, evidence-based scoring', text: 'Every answer is scored on accuracy, depth, relevance, structure and evidence, each with a quote from what you said. A score without evidence is capped.' },
  { icon: BrainCircuit, title: 'A study plan, not just a number', text: 'Get your strengths, your weakest topics, a stronger sample answer for every question, and a concrete two-week plan.' },
  { icon: LineChart, title: 'See yourself improve', text: 'Compare any two attempts side by side. Know which skills moved and which still need work before the real thing.' },
  { icon: LockKeyhole, title: 'Private by design', text: 'Run the AI on your own computer so your resume never leaves it, or use Gemini with your own key for speed. You choose, and you can delete everything in one click.' },
]

const STEPS = [
  { n: '1', title: 'Upload', text: 'Add your resume and the job description (a file or pasted text).' },
  { n: '2', title: 'Review', text: 'Check the skills and requirements the AI found, and fix anything it got wrong.' },
  { n: '3', title: 'Interview', text: 'Answer one question at a time in a live chat that adapts to you.' },
  { n: '4', title: 'Improve', text: 'Read your report, download it as a PDF, and try again to beat your score.' },
]

const FAQ = [
  { q: 'Is it really free?', a: 'Yes. The app is open source (MIT). Running it costs nothing with a local model. If you pick Gemini, you use your own Google key, which has a free tier with rate limits.' },
  { q: 'Where does my resume go?', a: 'It is stored in the database of the server running the app, and you can delete one interview or everything from Settings. With a local model it never leaves that machine. With Gemini, the resume and job description are sent to Google for analysis, and on the free tier Google may use them to improve its products.' },
  { q: 'Do I need a powerful computer?', a: 'Not with Gemini: analysis takes seconds. Local models work too but are slow on a laptop without a GPU: expect a couple of minutes for analysis and up to a minute per question.' },
  { q: 'Can I trust the scores?', a: 'Treat them as a practice aid. A language model applies a rubric, and the app adds guards (evidence quotes must really appear in your answer, for example). They are great for comparing your own attempts over time, and they are not a hiring decision.' },
  { q: 'What roles does it support?', a: 'It works for any role you can describe with a resume and a job description. It was tuned first on Python and AI roles, so technical questions are strongest there.' },
]

function BrowserFrame({ src, alt, className = '' }: { src: string; alt: string; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lift ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-slate-100 bg-slate-50 px-4 py-2.5" aria-hidden>
        <span className="size-2.5 rounded-full bg-red-300" />
        <span className="size-2.5 rounded-full bg-amber-300" />
        <span className="size-2.5 rounded-full bg-emerald-300" />
      </div>
      <img src={src} alt={alt} loading="lazy" className="w-full" />
    </div>
  )
}

function Section({ id, eyebrow, title, intro, children }: { id: string; eyebrow: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 py-20">
      <div className="mx-auto max-w-6xl px-5">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">{eyebrow}</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">{title}</h2>
          {intro && <p className="mt-4 text-lg text-slate-600">{intro}</p>}
        </div>
        <div className="mt-14">{children}</div>
      </div>
    </section>
  )
}

export function Landing() {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-30 border-b border-slate-200/60 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Logo />
          <nav aria-label="Sections" className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#how" className="hover:text-slate-900">How it works</a>
            <a href="#privacy" className="hover:text-slate-900">Privacy</a>
            <a href="#faq" className="hover:text-slate-900">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            <span className="hidden sm:block"><Link to="/login" className={buttonClasses('ghost', 'md')}>Log in</Link></span>
            <Link to="/signup" className={buttonClasses('primary', 'md', 'px-3.5 sm:px-4')}>Get started</Link>
          </div>
        </div>
      </header>

      <section className="bg-glow relative overflow-hidden">
        <div className="mx-auto max-w-6xl px-5 pb-8 pt-16 text-center sm:pt-24">
          <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white/80 px-4 py-1.5 text-sm font-medium text-brand-700 shadow-sm">
            <Sparkles className="size-4" aria-hidden /> Free and open source
          </p>
          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight text-slate-900 sm:text-6xl">
            Practice the interview <span className="text-gradient">before the interview</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-600">
            Upload your resume and a job description. Get a mock interview written for you and that role, with follow-up questions, honest scoring and a plan to get better.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link to="/signup" className={buttonClasses('primary', 'lg', 'shadow-glow')}>
              Start practising free <ArrowRight className="size-4" aria-hidden />
            </Link>
            <a href="#how" className={buttonClasses('secondary', 'lg')}>See how it works</a>
          </div>
          <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-slate-500">
            <li className="flex items-center gap-1.5"><ShieldCheck className="size-4 text-emerald-600" aria-hidden /> Can run fully on your own computer</li>
            <li className="flex items-center gap-1.5"><ShieldCheck className="size-4 text-emerald-600" aria-hidden /> No credit card</li>
            <li className="flex items-center gap-1.5"><ShieldCheck className="size-4 text-emerald-600" aria-hidden /> Delete your data any time</li>
          </ul>
        </div>
        <div className="mx-auto max-w-5xl px-5 pb-20 pt-10">
          <BrowserFrame src="/screens/report.png" alt="A feedback report with an overall score, scores by topic and per-question feedback" className="max-h-[34rem] [&>img]:object-cover [&>img]:object-top" />
        </div>
      </section>

      <Section id="features" eyebrow="Features" title="Everything you need to prepare, nothing you don't" intro="Built around how real interviews work: they start from your resume, they react to your answers, and they leave you with something to fix.">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card transition-shadow hover:shadow-lift">
              <span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><f.icon className="size-5" aria-hidden /></span>
              <h3 className="mt-5 text-lg font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.text}</p>
            </div>
          ))}
        </div>
      </Section>

      <section id="how" className="scroll-mt-20 bg-slate-50 py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">How it works</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">From documents to feedback in four steps</h2>
          </div>
          <ol className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <li key={s.n} className="relative rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
                <span className="flex size-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-fuchsia-500 text-base font-semibold text-white">{s.n}</span>
                <h3 className="mt-5 text-lg font-semibold text-slate-900">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.text}</p>
              </li>
            ))}
          </ol>
          <div className="mt-16 grid items-center gap-10 lg:grid-cols-2">
            <div>
              <span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><FileText className="size-5" aria-hidden /></span>
              <h3 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900">You stay in control of what the AI understood</h3>
              <p className="mt-3 leading-relaxed text-slate-600">Before any question is asked, you see the skills pulled from your resume and the requirements pulled from the job. Add a missing skill or remove a wrong one and the gap analysis updates instantly.</p>
            </div>
            <BrowserFrame src="/screens/analysis.png" alt="The analysis review screen showing matching skills, gaps and editable skill lists" className="max-h-96 [&>img]:object-cover [&>img]:object-top" />
          </div>
          <div className="mt-20 grid items-center gap-10 lg:grid-cols-2">
            <BrowserFrame src="/screens/interview.png" alt="The live interview chat" className="order-2 max-h-96 lg:order-1 [&>img]:object-cover [&>img]:object-top" />
            <div className="order-1 lg:order-2">
              <span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><MessagesSquare className="size-5" aria-hidden /></span>
              <h3 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900">A conversation, not a quiz</h3>
              <p className="mt-3 leading-relaxed text-slate-600">One question at a time, streamed as it is written. Reload the page and you continue where you stopped. The interviewer never gives hints or reveals a score, so you practise under realistic pressure.</p>
            </div>
          </div>
        </div>
      </section>

      <Section id="privacy" eyebrow="Your data, your choice" title="Pick the AI that fits you" intro="Both options run the same interview and the same scoring. Switch any time in Settings.">
        <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-card">
            <span className="flex size-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600"><LockKeyhole className="size-5" aria-hidden /></span>
            <h3 className="mt-5 text-xl font-semibold text-slate-900">Local model</h3>
            <p className="text-sm text-emerald-700">Free and private</p>
            <ul className="mt-4 space-y-2 text-sm text-slate-600">
              <li>Open-source models through Ollama</li>
              <li>Your resume never leaves your computer</li>
              <li>No account with any AI company, no key</li>
              <li>Slower on a laptop without a GPU</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-brand-200 bg-gradient-to-b from-brand-50/60 to-white p-7 shadow-card">
            <span className="flex size-11 items-center justify-center rounded-xl bg-brand-100 text-brand-700"><BarChart3 className="size-5" aria-hidden /></span>
            <h3 className="mt-5 text-xl font-semibold text-slate-900">Google Gemini</h3>
            <p className="text-sm text-brand-700">Fast, with your own API key</p>
            <ul className="mt-4 space-y-2 text-sm text-slate-600">
              <li>Analysis in seconds, questions in a few</li>
              <li>A free key works (with rate limits)</li>
              <li>Your key is stored encrypted and never shown again</li>
              <li>Your documents are sent to Google</li>
            </ul>
          </div>
        </div>
      </Section>

      <section id="faq" className="scroll-mt-20 bg-slate-50 py-20">
        <div className="mx-auto max-w-3xl px-5">
          <div className="text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">FAQ</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Good questions</h2>
          </div>
          <div className="mt-10 space-y-3">
            {FAQ.map((f) => (
              <details key={f.q} className="group rounded-2xl border border-slate-200 bg-white px-6 py-4 shadow-card open:shadow-lift">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium text-slate-900">
                  {f.q}
                  <span aria-hidden className="text-xl leading-none text-slate-400 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-20">
        <div className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-fuchsia-600 px-8 py-16 text-center text-white shadow-lift">
          <div aria-hidden className="absolute -left-20 -top-20 size-72 rounded-full bg-white/10 blur-3xl" />
          <h2 className="relative text-3xl font-semibold tracking-tight sm:text-4xl">Your next interview is the one that counts. Rehearse it first.</h2>
          <p className="relative mx-auto mt-4 max-w-xl text-brand-100">Create a free account and run your first mock interview in a few minutes.</p>
          <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link to="/signup" className={buttonClasses('secondary', 'lg', 'border-transparent')}>Create your account <ArrowRight className="size-4" aria-hidden /></Link>
            <Link to="/login" className="text-sm font-medium text-white/90 underline-offset-4 hover:underline">I already have an account</Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 text-sm text-slate-500 sm:flex-row">
          <Logo />
          <p>Open source under the MIT licence.</p>
          <a href={REPO} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 font-medium text-slate-700 hover:text-slate-900">
            <GithubMark className="size-4" /> View on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
