import { ExternalLink, Mail, Phone } from 'lucide-react'
import { Logo } from './Logo'

const REPO = 'https://github.com/kailash2488/ai-interview-assistant'
const YEAR = new Date().getFullYear()

export function SiteFooter() {
  return <footer className="border-t border-slate-200/80 bg-white/60 py-8 backdrop-blur-sm">
    <div className="mx-auto grid w-full max-w-[1600px] gap-6 px-4 sm:px-6 md:grid-cols-[1fr_auto] md:items-center lg:px-8 xl:px-10">
      <div><Logo /><p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">Open-source, evidence-based interview practice built by Kailash Prajapati.</p></div>
      <div className="flex flex-wrap gap-x-5 gap-y-3 text-sm">
        <a href="mailto:kailashprj2209@gmail.com" className="inline-flex items-center gap-2 text-slate-600 hover:text-brand-700"><Mail className="size-4" /> kailashprj2209@gmail.com</a>
        <a href="tel:+918469849443" className="inline-flex items-center gap-2 text-slate-600 hover:text-brand-700"><Phone className="size-4" /> +91 84698 49443</a>
        <a href="https://www.linkedin.com/in/kailashprajapati2488/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-slate-600 hover:text-brand-700"><ExternalLink className="size-4" /> LinkedIn</a>
        <a href={REPO} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-slate-600 hover:text-brand-700"><ExternalLink className="size-4" /> GitHub</a>
      </div>
      <p className="text-xs text-slate-400 md:col-span-2 md:text-right">© {YEAR} Kailash Prajapati · MIT licensed</p>
    </div>
  </footer>
}
