import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), '../..')

function collectSourceFiles(dir: string): string[] {
  const results: string[] = []

  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry === 'coverage') {
      continue
    }
    const full = join(dir, entry)
    const info = statSync(full)
    if (info.isDirectory()) {
      results.push(...collectSourceFiles(full))
    } else if (/\.(ts|tsx|js|jsx|css|html|json)$/i.test(entry)) {
      results.push(full)
    }
  }
  return results
}

describe('frontend secret boundary', () => {
  it('does not read or render source API keys in frontend code', () => {
    const forbiddenTokens = [
      'VITE_' + 'GRIEVANCEHUB_API_KEY',
      'GRIEVANCEHUB_' + 'API_KEY',
      'GRIEVANCEHUB_' + 'ADMIN_API_KEY',
    ]

    const productionDirs = ['api', 'app', 'components', 'routes', 'styles']
    const files = productionDirs.flatMap((dir) =>
      collectSourceFiles(join(frontendRoot, 'src', dir)),
    )
    files.push(join(frontendRoot, 'src', 'main.tsx'))
    files.push(join(frontendRoot, 'index.html'))
    files.push(join(frontendRoot, 'vite.config.ts'))
    files.push(join(frontendRoot, 'package.json'))

    for (const file of files) {
      const contents = readFileSync(file, 'utf8')
      for (const token of forbiddenTokens) {
        expect(contents, `${file} must not contain ${token}`).not.toContain(
          token,
        )
      }
    }

    const example = readFileSync(join(frontendRoot, '.env.example'), 'utf8')
    expect(example).toMatch(/Do not put[\s\S]*GRIEVANCEHUB_API_KEY/)
    expect(example).not.toMatch(/^\s*VITE_GRIEVANCEHUB_API_KEY\s*=/m)
    expect(example).not.toMatch(/^\s*GRIEVANCEHUB_API_KEY\s*=/m)
    expect(example).not.toMatch(/^\s*GRIEVANCEHUB_ADMIN_API_KEY\s*=/m)
  })
})
