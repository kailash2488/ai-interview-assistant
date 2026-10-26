export const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt']
export const MAX_UPLOAD_MB = 10

export function validateFile(file: File): string | null {
  const dot = file.name.lastIndexOf('.')
  const ext = dot === -1 ? '' : file.name.slice(dot).toLowerCase()
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return `${file.name}: only ${ACCEPTED_EXTENSIONS.join(', ')} files are supported`
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `${file.name}: larger than ${MAX_UPLOAD_MB} MB`
  if (file.size === 0) return `${file.name}: file is empty`
  return null
}
