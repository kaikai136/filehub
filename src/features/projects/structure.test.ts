import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const root = new URL('../../', import.meta.url)
const read = (path: string) => readFileSync(new URL(path, root), 'utf8')

describe('project management integration', () => {
  it('loads only hosts for project management and machine selection', () => {
    for (const view of ['views/Projects.vue', 'views/FileConfigs.vue']) {
      expect(read(view)).toMatch(/file-configs\/', \{ params: \{ scope: 'hosts' \} \}/)
    }
  })

  it('has navigation and a route', () => {
    expect(read('App.vue')).toContain("path: '/projects'")
    expect(read('main.ts')).toContain("{ path: '/projects', component: Projects")
  })

  it('connects file management and file browsing to project IDs', () => {
    expect(read('views/FileConfigs.vue')).toContain('v-model="form.project_id"')
    expect(read('views/FileLists.vue')).toContain('config.project_id')
    expect(read('views/Projects.vue')).toContain('projectTree(projects.value, configs.value)')
  })
})
