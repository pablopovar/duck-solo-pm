(() => {
  const layout = document.getElementById(
    'duck-feed-layout'
  );
  const panel = document.getElementById(
    'duck-context-panel'
  );
  const toggle = document.getElementById(
    'duck-context-toggle'
  );
  const type = document.getElementById(
    'duck-entry-type'
  );
  const composer = document.getElementById(
    'duck-composer-text'
  );
  const post = document.getElementById(
    'duck-composer-post'
  );
  const feedback = document.getElementById(
    'duck-composer-feedback'
  );

  if (!layout || !panel || !toggle) {
    return;
  }

  const project = document.body.dataset.project || '';
  const storageKey = `duck.context.expanded.${project}`;

  function setExpanded(expanded) {
    layout.classList.toggle(
      'context-expanded',
      expanded
    );
    toggle.setAttribute(
      'aria-expanded',
      String(expanded)
    );
    toggle.title = expanded
      ? 'Collapse project context'
      : 'Expand project context';

    try {
      sessionStorage.setItem(
        storageKey,
        expanded ? '1' : '0'
      );
    } catch (_error) {
      // The layout still works when storage is unavailable.
    }
  }

  try {
    setExpanded(
      sessionStorage.getItem(storageKey) === '1'
    );
  } catch (_error) {
    setExpanded(false);
  }

  toggle.addEventListener('click', (event) => {
    event.stopPropagation();
    setExpanded(
      !layout.classList.contains('context-expanded')
    );
  });

  panel.addEventListener('click', (event) => {
    if (
      event.target.closest(
        'a, button, input, select, textarea, label'
      )
    ) {
      return;
    }

    setExpanded(
      !layout.classList.contains('context-expanded')
    );
  });

  const placeholders = {
    note: 'Write your note…',
    todo: 'What needs to be done?',
    status: 'Post a project status…',
    file: 'Add an optional note about the file…',
    link: 'Paste a link or add a note…',
    'check-in': 'Write the check-in response…',
    event: 'Describe the project event…',
  };

  if (type && composer) {
    type.addEventListener('change', () => {
      composer.placeholder =
        placeholders[type.value]
        || 'Add project activity…';
    });
  }

  function explainShell() {
    if (!feedback) {
      return;
    }

    feedback.textContent =
      'This is the feed-shell patch. No project data was written; posting is enabled with the activity store.';
  }

  if (post) {
    post.addEventListener('click', explainShell);
  }

  document.querySelectorAll('[data-shell-action]').forEach(
    (button) => {
      button.addEventListener('click', explainShell);
    }
  );

  if (composer) {
    composer.addEventListener('keydown', (event) => {
      if (
        event.key === 'Enter'
        && (event.ctrlKey || event.metaKey)
      ) {
        event.preventDefault();
        explainShell();
      }
    });
  }
})();
