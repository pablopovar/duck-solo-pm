import { Crepe } from '@milkdown/crepe'
import '@milkdown/crepe/theme/common/style.css'
import '@milkdown/crepe/theme/frame.css'

const app =
  document.getElementById(
    'markdown-editor-app',
  )

if (app) {
  const project =
    app.dataset.project

  const defaultFile =
    app.dataset.defaultFile
    || 'dashboard.md'

  const fileSelect =
    document.getElementById(
      'editor-file',
    )

  const saveButton =
    document.getElementById(
      'editor-save',
    )

  const cancelLink =
    document.getElementById(
      'editor-cancel',
    )

  const status =
    document.getElementById(
      'editor-status',
    )

  const frontmatterPanel =
    document.getElementById(
      'frontmatter-panel',
    )

  const frontmatterInput =
    document.getElementById(
      'frontmatter-editor',
    )

  const editorRoot =
    document.getElementById(
      'crepe-editor',
    )

  let crepe = null
  let currentFile = null
  let currentHasFrontmatter = false
  let dirty = false
  let busy = false

  const apiUrl = (file) => (
    `/api/projects/${encodeURIComponent(project)}/markdown`
    + `?file=${encodeURIComponent(file)}`
  )

  const setStatus = (
    message,
    kind = '',
  ) => {
    status.textContent = message
    status.dataset.kind = kind
  }

  const setBusy = (value) => {
    busy = value
    fileSelect.disabled = value
    saveButton.disabled = value
  }

  const markDirty = () => {
    if (busy || dirty) {
      return
    }

    dirty = true

    setStatus(
      'Unsaved changes',
      'dirty',
    )
  }

  const readError = async (
    response,
  ) => {
    try {
      const data =
        await response.json()

      return (
        data.detail
        || `Request failed: ${response.status}`
      )
    } catch (_error) {
      return (
        `Request failed: ${response.status}`
      )
    }
  }

  const destroyEditor = async () => {
    if (crepe) {
      await crepe.destroy()
      crepe = null
    }

    editorRoot.replaceChildren()
  }

  const confirmDiscard = () => (
    !dirty
    || window.confirm(
      'Discard unsaved changes?',
    )
  )

  const loadFile = async (file) => {
    if (!file || busy) {
      return
    }

    if (!confirmDiscard()) {
      if (currentFile) {
        fileSelect.value =
          currentFile
      }

      return
    }

    setBusy(true)
    setStatus('Loading…')

    try {
      const response =
        await fetch(
          apiUrl(file),
          {
            headers: {
              Accept:
                'application/json',
            },
          },
        )

      if (!response.ok) {
        throw new Error(
          await readError(response),
        )
      }

      const data =
        await response.json()

      await destroyEditor()

      frontmatterInput.value =
        data.frontmatter || ''

      currentHasFrontmatter =
        Boolean(
          data.has_frontmatter,
        )

      frontmatterPanel.hidden =
        !currentHasFrontmatter

      crepe = new Crepe({
        root: editorRoot,
        defaultValue:
          data.body || '',
      })

      await crepe.create()

      currentFile = file
      fileSelect.value = file
      dirty = false
      setStatus('')
    } catch (error) {
      console.error(error)

      editorRoot.textContent =
        'The editor could not load this file.'

      setStatus(
        error.message
        || 'Load failed',
        'error',
      )
    } finally {
      setBusy(false)
    }
  }

  const saveFile = async () => {
    if (
      !crepe
      || !currentFile
      || busy
    ) {
      return
    }

    setBusy(true)
    setStatus('Saving…')

    try {
      const response =
        await fetch(
          apiUrl(currentFile),
          {
            method: 'PUT',
            headers: {
              'Content-Type':
                'application/json',
              Accept:
                'application/json',
            },
            body: JSON.stringify({
              frontmatter:
                currentHasFrontmatter
                  ? frontmatterInput.value
                  : '',
              body:
                crepe.getMarkdown(),
              has_frontmatter:
                currentHasFrontmatter,
            }),
          },
        )

      if (!response.ok) {
        throw new Error(
          await readError(response),
        )
      }

      dirty = false

      setStatus(
        'Saved',
        'saved',
      )

      window.setTimeout(
        () => {
          if (!dirty && !busy) {
            setStatus('')
          }
        },
        1400,
      )
    } catch (error) {
      console.error(error)

      setStatus(
        error.message
        || 'Save failed',
        'error',
      )
    } finally {
      setBusy(false)
    }
  }

  fileSelect.addEventListener(
    'change',
    () => {
      void loadFile(
        fileSelect.value,
      )
    },
  )

  saveButton.addEventListener(
    'click',
    () => {
      void saveFile()
    },
  )

  frontmatterInput.addEventListener(
    'input',
    markDirty,
  )

  editorRoot.addEventListener(
    'input',
    markDirty,
  )

  cancelLink.addEventListener(
    'click',
    (event) => {
      if (!confirmDiscard()) {
        event.preventDefault()
      }
    },
  )

  window.addEventListener(
    'beforeunload',
    (event) => {
      if (!dirty) {
        return
      }

      event.preventDefault()
      event.returnValue = ''
    },
  )

  document.addEventListener(
    'keydown',
    (event) => {
      if (
        (
          event.ctrlKey
          || event.metaKey
        )
        && event.key
          .toLowerCase() === 's'
      ) {
        event.preventDefault()
        void saveFile()
      }
    },
  )

  fileSelect.value =
    defaultFile

  void loadFile(
    defaultFile,
  )
}
