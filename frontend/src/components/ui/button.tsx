import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'dark'
type Size = 'sm' | 'md' | 'lg'

export const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-gradient-to-b from-brand-500 to-brand-600 text-white shadow-sm shadow-brand-700/30 hover:from-brand-500 hover:to-brand-700 disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none',
  secondary: 'border border-slate-200 bg-white text-slate-800 shadow-sm hover:border-slate-300 hover:bg-slate-50 disabled:text-slate-400 disabled:shadow-none',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  danger: 'text-red-600 hover:bg-red-50',
  dark: 'bg-slate-900 text-white shadow-sm hover:bg-slate-800 disabled:bg-slate-300',
}
export const SIZES: Record<Size, string> = {
  sm: 'rounded-lg px-3 py-1.5 text-xs',
  md: 'rounded-xl px-4 py-2.5 text-sm',
  lg: 'rounded-xl px-6 py-3 text-base',
}

export function buttonClasses(variant: Variant = 'primary', size: Size = 'md', className?: string) {
  return cn(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-all active:translate-y-px',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:cursor-not-allowed',
    VARIANTS[variant],
    SIZES[size],
    className,
  )
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return <button className={buttonClasses(variant, size, className)} {...props} />
}
