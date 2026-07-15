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
  const composerTitle = document.getElementById(
    'duck-entry-title'
  );
  const post = document.getElementById(
    'duck-composer-post'
  );
  const feedback = document.getElementById(
    'duck-composer-feedback'
  );
  const characterCounter = document.getElementById(
    'duck-character-counter'
  );
  const filter = document.getElementById(
    'duck-feed-filter'
  );
  const feedItems = Array.from(
    document.querySelectorAll('[data-feed-type]')
  );
  const filterEmpty = document.getElementById(
    'duck-filter-empty'
  );
  const composerLaunch = document.getElementById(
    'duck-composer-launch'
  );
  const composerPopover = document.getElementById(
    'duck-composer-popover'
  );
  const composerClose = document.getElementById(
    'duck-composer-close'
  );
  const composerBackdrop = document.getElementById(
    'duck-composer-backdrop'
  );
  const pinButtons = Array.from(
    document.querySelectorAll('[data-pin-resource]')
  );
  const deleteButtons = Array.from(
    document.querySelectorAll('[data-delete-activity]')
  );
  const aboutEdit = document.getElementById('duck-about-edit');
  const aboutDisplay = document.getElementById('duck-about-display');
  const aboutForm = document.getElementById('duck-about-form');
  const aboutCancel = document.getElementById('duck-about-cancel');
  const aboutWhat = document.getElementById('duck-about-what');
  const aboutWhy = document.getElementById('duck-about-why');
  const aboutClass = document.getElementById('duck-about-class');
  const aboutFeedback = document.getElementById('duck-about-feedback');
  const densityDecrease = document.getElementById(
    'duck-density-decrease'
  );
  const densityIncrease = document.getElementById(
    'duck-density-increase'
  );
  const densityLabel = document.getElementById(
    'duck-density-label'
  );

  if (!layout || !panel || !toggle) {
    return;
  }

  const project = document.body.dataset.project || '';
  const storageKey = `duck.context.expanded.${project}`;
  const filterStorageKey = `duck.feed.filter.${project}`;
  const densityStorageKey = 'duck.ui.density';
  const densityLevels = ['spacious', 'standard', 'compact'];
  const densityLabels = {
    spacious: 'Spacious',
    standard: 'Standard',
    compact: 'Compact',
  };

  let density = 'standard';

  try {
    const savedDensity = localStorage.getItem(densityStorageKey);
    if (densityLevels.includes(savedDensity)) {
      density = savedDensity;
    }
  } catch (_error) {
    density = 'standard';
  }

  function applyDensity(nextDensity) {
    density = densityLevels.includes(nextDensity)
      ? nextDensity
      : 'standard';
    document.body.dataset.density = density;

    if (densityLabel) {
      densityLabel.textContent = densityLabels[density];
    }

    if (densityDecrease) {
      densityDecrease.disabled = density === 'spacious';
    }

    if (densityIncrease) {
      densityIncrease.disabled = density === 'compact';
    }

    try {
      localStorage.setItem(densityStorageKey, density);
    } catch (_error) {
      // Density still works for this page load.
    }
  }

  applyDensity(density);

  if (densityDecrease) {
    densityDecrease.addEventListener('click', () => {
      const index = densityLevels.indexOf(density);
      applyDensity(densityLevels[Math.max(0, index - 1)]);
    });
  }

  if (densityIncrease) {
    densityIncrease.addEventListener('click', () => {
      const index = densityLevels.indexOf(density);
      applyDensity(
        densityLevels[Math.min(densityLevels.length - 1, index + 1)]
      );
    });
  }

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
        'a, button, input, select, textarea, label, summary, form'
      )
    ) {
      return;
    }

    setExpanded(
      !layout.classList.contains('context-expanded')
    );
  });

  function rememberFilter(value) {
    try {
      sessionStorage.setItem(
        filterStorageKey,
        value
      );
    } catch (_error) {
      // Filtering still works when storage is unavailable.
    }
  }

  function applyFeedFilter() {
    if (!filter) {
      return;
    }

    const selected = filter.value;
    let visible = 0;

    for (const item of feedItems) {
      const matches =
        selected === 'all'
        || item.dataset.feedType === selected;

      item.hidden = !matches;

      if (matches) {
        visible += 1;
      }
    }

    if (filterEmpty) {
      filterEmpty.hidden = visible !== 0;
    }

    rememberFilter(selected);
  }

  if (filter) {
    let remembered = 'all';

    try {
      remembered =
        sessionStorage.getItem(filterStorageKey)
        || 'all';
    } catch (_error) {
      remembered = 'all';
    }

    const available = Array.from(
      filter.options
    ).some((option) => option.value === remembered);

    filter.value = available ? remembered : 'all';
    applyFeedFilter();
    filter.addEventListener(
      'change',
      applyFeedFilter
    );
  }

  function setComposerOpen(open) {
    if (
      !composerLaunch
      || !composerPopover
      || !composerBackdrop
    ) {
      return;
    }

    composerPopover.hidden = !open;
    composerBackdrop.hidden = !open;
    composerLaunch.setAttribute(
      'aria-expanded',
      String(open)
    );
    document.body.classList.toggle(
      'duck-composer-open',
      open
    );

    if (open) {
      window.setTimeout(
        () => composer && composer.focus(),
        0
      );
    } else {
      composerLaunch.focus();
    }
  }

  if (composerLaunch) {
    composerLaunch.addEventListener(
      'click',
      () => setComposerOpen(true)
    );
  }

  if (composerClose) {
    composerClose.addEventListener(
      'click',
      () => setComposerOpen(false)
    );
  }

  if (composerBackdrop) {
    composerBackdrop.addEventListener(
      'click',
      () => setComposerOpen(false)
    );
  }

  document.addEventListener('keydown', (event) => {
    if (
      event.key === 'Escape'
      && composerPopover
      && !composerPopover.hidden
    ) {
      event.preventDefault();
      setComposerOpen(false);
    }
  });

  const placeholders = {
    note: 'Write your note…',
    todo: 'What needs to be done?',
    status: 'Post a project status…',
    file: 'Add an optional note about the file…',
    link: 'Paste an http:// or https:// URL. Add an optional label before or after it.',
    'check-in': 'Write the check-in response…',
    event: 'Describe the project event…',
  };

  const titlePlaceholders = {
    note: 'Note title',
    todo: 'Todo title',
    status: 'Status title',
    link: 'Link label',
    file: 'File title',
    'check-in': 'Check-in title',
    event: 'Event title',
  };

  const characterLimits = {
    note: 2000,
    todo: 2000,
  };

  function updateCharacterCounter() {
    if (!type || !composer || !characterCounter) {
      return;
    }

    const limit = characterLimits[type.value];

    if (!limit) {
      composer.removeAttribute('maxlength');
      characterCounter.hidden = true;
      characterCounter.classList.remove(
        'is-low',
        'is-over'
      );
      return;
    }

    composer.maxLength = limit;
    characterCounter.hidden = false;

    const remaining = limit - composer.value.length;
    const displayed = Math.max(0, remaining);
    characterCounter.textContent =
      `${displayed.toLocaleString()} character${
        displayed === 1 ? '' : 's'
      } left`;
    characterCounter.classList.toggle(
      'is-low',
      remaining <= 200 && remaining >= 0
    );
    characterCounter.classList.toggle(
      'is-over',
      remaining < 0
    );
  }

  if (type && composer) {
    type.addEventListener('change', () => {
      composer.placeholder =
        placeholders[type.value]
        || 'Add project activity…';
      if (composerTitle) {
        composerTitle.placeholder =
          titlePlaceholders[type.value]
          || 'Activity title';
      }
      updateCharacterCounter();
    });

    composer.addEventListener(
      'input',
      updateCharacterCounter
    );

    updateCharacterCounter();
  }

  const supportedTypes = new Set([
    'note',
    'todo',
    'status',
    'link',
  ]);

  const typeLabels = {
    note: 'Note',
    todo: 'Todo',
    status: 'Status update',
    link: 'Link',
  };

  function showFeedback(message) {
    if (feedback) {
      feedback.textContent = message;
    }
  }

  function explainUnavailable() {
    showFeedback(
      'File attachments and additional fields are not enabled yet.'
    );
  }

  async function togglePinnedResource(button) {
    const activityId = button.dataset.activityId || '';
    const currentlyPinned = button.dataset.pinned === 'true';

    if (!activityId || !project) {
      return;
    }

    button.disabled = true;
    button.textContent = currentlyPinned
      ? 'Unpinning...'
      : 'Pinning...';

    try {
      const response = await fetch(
        `/api/projects/${
          encodeURIComponent(project)
        }/activity/${
          encodeURIComponent(activityId)
        }/pin`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pinned: !currentlyPinned,
          }),
        }
      );

      let result = {};

      try {
        result = await response.json();
      } catch (_error) {
        result = {};
      }

      if (!response.ok) {
        throw new Error(
          result.detail || 'The resource could not be updated.'
        );
      }

      window.location.reload();
    } catch (error) {
      showFeedback(
        error instanceof Error
          ? error.message
          : 'The resource could not be updated.'
      );
      button.disabled = false;
      button.textContent = currentlyPinned
        ? 'Unpin from resources'
        : 'Pin to resources';
    }
  }

  async function deleteActivity(button) {
    const activityId = button.dataset.activityId || '';
    const activityTitle = button.dataset.activityTitle || 'this item';

    if (!activityId || !project) {
      return;
    }

    if (!window.confirm(`Delete "${activityTitle}"?`)) {
      return;
    }

    button.disabled = true;
    button.textContent = 'Deleting...';

    try {
      const response = await fetch(
        `/api/projects/${
          encodeURIComponent(project)
        }/activity/${
          encodeURIComponent(activityId)
        }`,
        {
          method: 'DELETE',
        }
      );

      let result = {};

      try {
        result = await response.json();
      } catch (_error) {
        result = {};
      }

      if (!response.ok) {
        throw new Error(
          result.detail || 'The item could not be deleted.'
        );
      }

      window.location.reload();
    } catch (error) {
      showFeedback(
        error instanceof Error
          ? error.message
          : 'The item could not be deleted.'
      );
      button.disabled = false;
      button.textContent = 'Delete';
    }
  }

  function setAboutEditing(editing) {
    if (!aboutForm || !aboutDisplay || !aboutEdit) {
      return;
    }

    aboutForm.hidden = !editing;
    aboutDisplay.hidden = editing;
    aboutEdit.hidden = editing;

    if (editing && aboutWhat) {
      aboutWhat.focus();
    }
  }

  if (aboutEdit) {
    aboutEdit.addEventListener('click', () => setAboutEditing(true));
  }

  if (aboutCancel) {
    aboutCancel.addEventListener('click', () => setAboutEditing(false));
  }

  if (aboutForm) {
    aboutForm.addEventListener('submit', async (event) => {
      event.preventDefault();

      const saveButton = document.getElementById('duck-about-save');

      if (saveButton) {
        saveButton.disabled = true;
        saveButton.textContent = 'Saving...';
      }

      if (aboutFeedback) {
        aboutFeedback.textContent = 'Saving...';
      }

      try {
        const response = await fetch(
          `/api/projects/${encodeURIComponent(project)}/about`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              what: aboutWhat ? aboutWhat.value : '',
              why: aboutWhy ? aboutWhy.value : '',
              class_name: aboutClass ? aboutClass.value : '',
            }),
          }
        );

        let result = {};

        try {
          result = await response.json();
        } catch (_error) {
          result = {};
        }

        if (!response.ok) {
          throw new Error(
            result.detail || 'About could not be saved.'
          );
        }

        window.location.reload();
      } catch (error) {
        if (aboutFeedback) {
          aboutFeedback.textContent = error instanceof Error
            ? error.message
            : 'About could not be saved.';
        }

        if (saveButton) {
          saveButton.disabled = false;
          saveButton.textContent = 'Save';
        }
      }
    });
  }

  async function submitEntry() {
    if (!type || !composer || !composerTitle || !post || !project) {
      return;
    }

    const kind = type.value;
    const title = composerTitle.value.trim();
    const text = composer.value.trim();

    if (!supportedTypes.has(kind)) {
      showFeedback(
        'Choose Note, Todo, Status, or Link for now.'
      );
      return;
    }

    if (!title) {
      showFeedback('Enter a title before posting.');
      composerTitle.focus();
      return;
    }

    if ((kind === 'note' || kind === 'link') && !text) {
      showFeedback(
        kind === 'link'
          ? 'Enter the link URL before posting.'
          : 'Enter the note text before posting.'
      );
      composer.focus();
      return;
    }

    const characterLimit = characterLimits[kind];

    if (characterLimit && text.length > characterLimit) {
      showFeedback(
        `${typeLabels[kind]}s are limited to ${
          characterLimit.toLocaleString()
        } characters.`
      );
      composer.focus();
      return;
    }

    post.disabled = true;
    post.textContent = 'Posting…';
    showFeedback('Saving…');

    try {
      const response = await fetch(
        `/api/projects/${
          encodeURIComponent(project)
        }/quick-entry`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            kind,
            title,
            text,
          }),
        }
      );

      let result = {};

      try {
        result = await response.json();
      } catch (_error) {
        result = {};
      }

      if (!response.ok) {
        throw new Error(
          result.detail || 'The entry could not be saved.'
        );
      }

      composer.value = '';
      composerTitle.value = '';
      updateCharacterCounter();

      if (filter) {
        filter.value = kind;
        rememberFilter(kind);
      }

      showFeedback(
        `${typeLabels[kind]} saved. Refreshing…`
      );
      window.location.reload();
    } catch (error) {
      showFeedback(
        error instanceof Error
          ? error.message
          : 'The entry could not be saved.'
      );
      post.disabled = false;
      post.textContent = 'Post';
    }
  }

  if (post) {
    post.addEventListener('click', submitEntry);
  }

  for (const button of pinButtons) {
    button.addEventListener(
      'click',
      () => togglePinnedResource(button)
    );
  }

  for (const button of deleteButtons) {
    button.addEventListener(
      'click',
      () => deleteActivity(button)
    );
  }

  document.querySelectorAll('[data-shell-action]').forEach(
    (button) => {
      button.addEventListener(
        'click',
        explainUnavailable
      );
    }
  );

  if (composer) {
    composer.addEventListener('keydown', (event) => {
      if (
        event.key === 'Enter'
        && (event.ctrlKey || event.metaKey)
      ) {
        event.preventDefault();
        submitEntry();
      }
    });
  }
})();
