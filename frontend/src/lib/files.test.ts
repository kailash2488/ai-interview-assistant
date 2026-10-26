import { validateFile } from './files'

const file = (name: string, size = 10) => new File([new Uint8Array(size)], name)

describe('validateFile', () => {
  it('accepts pdf, docx and txt in any case', () => {
    for (const n of ['a.pdf', 'b.DOCX', 'c.txt']) expect(validateFile(file(n))).toBeNull()
  })
  it('rejects unsupported types and files without extension', () => {
    expect(validateFile(file('a.exe'))).toMatch(/only/)
    expect(validateFile(file('README'))).toMatch(/only/)
  })
  it('rejects empty and oversized files', () => {
    expect(validateFile(file('a.pdf', 0))).toMatch(/empty/)
    expect(validateFile(file('a.pdf', 11 * 1024 * 1024))).toMatch(/larger/)
  })
})
