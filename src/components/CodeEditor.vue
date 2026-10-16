<template>
  <div ref="editorHost" class="code-editor" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { Compartment, EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit, StreamLanguage } from '@codemirror/language'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
import { xml } from '@codemirror/lang-xml'
import { markdown } from '@codemirror/lang-markdown'
import { yaml } from '@codemirror/lang-yaml'
import { shell } from '@codemirror/legacy-modes/mode/shell'
import { powerShell } from '@codemirror/legacy-modes/mode/powershell'
import { nginx } from '@codemirror/legacy-modes/mode/nginx'
import { dockerFile } from '@codemirror/legacy-modes/mode/dockerfile'
import { properties } from '@codemirror/legacy-modes/mode/properties'
import { standardSQL } from '@codemirror/legacy-modes/mode/sql'
import { toml } from '@codemirror/legacy-modes/mode/toml'

const props = defineProps<{ modelValue: string; filename: string }>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'language-change': [language: string]
  save: []
}>()

const editorHost = ref<HTMLElement>()
const languageCompartment = new Compartment()
let view: EditorView | undefined

function languageFor(filename: string): { label: string; extension: Extension } {
  const lower = filename.toLocaleLowerCase()
  const extension = lower.includes('.') ? lower.slice(lower.lastIndexOf('.')) : ''
  if (['.py', '.pyw', '.pyi'].includes(extension)) return { label: 'Python', extension: python() }
  if (['.sh', '.bash', '.zsh', '.fish', '.command'].includes(extension) || ['.bashrc', '.zshrc', '.profile'].includes(lower)) return { label: 'Shell', extension: StreamLanguage.define(shell) }
  if (['.ps1', '.psm1', '.psd1'].includes(extension)) return { label: 'PowerShell', extension: StreamLanguage.define(powerShell) }
  if (['.yaml', '.yml'].includes(extension)) return { label: 'YAML', extension: yaml() }
  if (['.json', '.jsonc'].includes(extension)) return { label: 'JSON', extension: json() }
  if (['.js', '.mjs', '.cjs'].includes(extension)) return { label: 'JavaScript', extension: javascript() }
  if (['.ts', '.mts', '.cts'].includes(extension)) return { label: 'TypeScript', extension: javascript({ typescript: true }) }
  if (['.jsx'].includes(extension)) return { label: 'JSX', extension: javascript({ jsx: true }) }
  if (['.tsx'].includes(extension)) return { label: 'TSX', extension: javascript({ jsx: true, typescript: true }) }
  if (['.html', '.htm', '.vue'].includes(extension)) return { label: extension === '.vue' ? 'Vue / HTML' : 'HTML', extension: html() }
  if (['.css', '.scss', '.sass', '.less'].includes(extension)) return { label: 'CSS', extension: css() }
  if (['.xml', '.svg'].includes(extension)) return { label: 'XML', extension: xml() }
  if (['.md', '.markdown'].includes(extension)) return { label: 'Markdown', extension: markdown() }
  if (['.sql'].includes(extension)) return { label: 'SQL', extension: StreamLanguage.define(standardSQL) }
  if (['.toml'].includes(extension)) return { label: 'TOML', extension: StreamLanguage.define(toml) }
  if (lower === 'dockerfile' || lower.startsWith('dockerfile.')) return { label: 'Dockerfile', extension: StreamLanguage.define(dockerFile) }
  if (lower === 'nginx.conf' || lower.endsWith('.nginx')) return { label: 'Nginx', extension: StreamLanguage.define(nginx) }
  if (['.ini', '.properties', '.env', '.conf'].includes(extension) || lower === '.env') return { label: '配置文件', extension: StreamLanguage.define(properties) }
  return { label: '纯文本', extension: [] }
}

function applyLanguage(filename: string) {
  const language = languageFor(filename)
  emit('language-change', language.label)
  if (view) view.dispatch({ effects: languageCompartment.reconfigure(language.extension) })
}

onMounted(() => {
  const language = languageFor(props.filename)
  emit('language-change', language.label)
  view = new EditorView({
    parent: editorHost.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        basicSetup,
        keymap.of([{ key: 'Mod-s', preventDefault: true, run: () => { emit('save'); return true } }, ...defaultKeymap, indentWithTab]),
        EditorState.tabSize.of(2),
        indentUnit.of('  '),
        EditorView.lineWrapping,
        languageCompartment.of(language.extension),
        EditorView.updateListener.of(update => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
        EditorView.theme({
          '&': { height: 'min(64vh, 720px)', minHeight: '420px', fontSize: '13px', backgroundColor: '#ffffff' },
          '.cm-scroller': { overflow: 'auto', fontFamily: 'Consolas, "Cascadia Code", "SFMono-Regular", monospace', lineHeight: '1.6' },
          '.cm-gutters': { backgroundColor: '#f7f9fc', color: '#8b98aa', borderRight: '1px solid #e5eaf2' },
          '.cm-activeLine, .cm-activeLineGutter': { backgroundColor: '#eef5ff' },
          '&.cm-focused': { outline: 'none' },
        }),
      ],
    }),
  })
  view.focus()
})

watch(() => props.modelValue, value => {
  if (!view || value === view.state.doc.toString()) return
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
})
watch(() => props.filename, applyLanguage)

onBeforeUnmount(() => view?.destroy())
</script>

<style scoped>
.code-editor { overflow: hidden; border: 1px solid #d8e0eb; border-radius: 8px; }
</style>
