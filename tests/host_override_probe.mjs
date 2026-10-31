// Prints the Host plugin's resolved status payload for one host.
//
// The Python suite compares these paths with lib.hosts so the Host plugin and
// the CLI can never resolve a different plugin root or memory root.
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const host = process.argv[2] || 'dsh'
const handlers = {}
const child = {
  effect(fn) { fn() },
  webServer: { register(entry) { handlers[entry.path] = entry.handler } },
}
const mod = await import(pathToFileURL(path.resolve('dsh-plugin/index.js')).href)
mod.apply({ inject(_names, fn) { fn(child) } })

const response = {
  statusCode: 0,
  body: '',
  writeHead(code) { this.statusCode = code },
  end(value) { this.body = String(value) },
}
await handlers['/programmer-workflow/status']({
  method: 'GET',
  url: `/programmer-workflow/status?host=${encodeURIComponent(host)}`,
}, response)
if (response.statusCode !== 200) {
  console.error(response.body)
  process.exit(1)
}
process.stdout.write(response.body)
