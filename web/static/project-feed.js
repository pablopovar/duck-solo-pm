(() => {
  const layout = document.getElementById(
    'duck-feed-layout'
  );
  const panel = document.getElementById(
    'duck-context-panel'
  );
  const activityPanel = document.getElementById(
    'duck-activity-panel'
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
  const fileFields = document.getElementById(
    'duck-file-fields'
  );
  const fileShortcut = document.getElementById(
    'duck-file-shortcut'
  );
  const fileUploadFields = document.getElementById(
    'duck-file-upload-fields'
  );
  const fileMarkdownFields = document.getElementById(
    'duck-file-markdown-fields'
  );
  const fileUpload = document.getElementById(
    'duck-file-upload'
  );
  const fileName = document.getElementById(
    'duck-file-name'
  );
  const fileMarkdown = document.getElementById(
    'duck-file-markdown'
  );
  const fileModeInputs = Array.from(
    document.querySelectorAll('input[name="duck-file-mode"]')
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
  const convertNoteButtons = Array.from(
    document.querySelectorAll('[data-convert-note]')
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
  const chatToggle = document.getElementById('duck-chat-toggle');
  const chatPanel = document.getElementById('duck-chat-panel');
  const chatClose = document.getElementById('duck-chat-close');
  const chatModel = document.getElementById('duck-chat-model');
  const chatClear = document.getElementById('duck-chat-clear');
  const chatMessages = document.getElementById('duck-chat-messages');
  const chatForm = document.getElementById('duck-chat-form');
  const chatInput = document.getElementById('duck-chat-input');
  const chatSend = document.getElementById('duck-chat-send');
  const chatStatus = document.getElementById('duck-chat-status');
  const workspaceColumns = Array.from(
    document.querySelectorAll('[data-duck-column]')
  );

  if (
    !layout
    || !panel
    || !activityPanel
    || !chatPanel
    || !toggle
    || workspaceColumns.length < 3
  ) {
    return;
  }

  const project = document.body.dataset.project || '';
  const filterStorageKey = `duck.feed.filter.${project}`;
  const densityStorageKey = 'duck.ui.density';
  const columnStorageKey = `duck.columns.${project}`;
  const densityLevels = ['spacious', 'standard', 'compact'];
  const densityLabels = {
    spacious: 'Spacious',
    standard: 'Standard',
    compact: 'Compact',
  };

  let density = 'standard';
  let chatLoaded = false;
  let chatLoading = false;

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

  const columnIds = new Set(
    workspaceColumns.map((column) => column.dataset.duckColumn)
  );
  let draggedColumnIds = [];

  function orderedColumns() {
    return Array.from(layout.children).filter(
      (element) => element.matches('[data-duck-column]')
    );
  }

  function columnById(columnId) {
    return workspaceColumns.find(
      (column) => column.dataset.duckColumn === columnId
    );
  }

  function validColumnState(state) {
    return ['collapsed', 'normal', 'expanded'].includes(state);
  }

  function saveColumnLayout() {
    const columns = orderedColumns();
    const layoutState = {
      order: columns.map((column) => column.dataset.duckColumn),
      states: Object.fromEntries(
        columns.map((column) => [
          column.dataset.duckColumn,
          column.dataset.columnState,
        ])
      ),
    };

    try {
      localStorage.setItem(columnStorageKey, JSON.stringify(layoutState));
    } catch (_error) {
      // Column controls still work without browser storage.
    }
  }

  function updateCollapsedStacks() {
    const columns = orderedColumns();

    for (const column of columns) {
      delete column.dataset.inCollapsedStack;
      delete column.dataset.stackLeader;
      delete column.dataset.stackSize;
    }

    let index = 0;

    while (index < columns.length) {
      if (columns[index].dataset.columnState !== 'collapsed') {
        index += 1;
        continue;
      }

      const stack = [];

      while (
        index < columns.length
        && columns[index].dataset.columnState === 'collapsed'
      ) {
        stack.push(columns[index]);
        index += 1;
      }

      if (stack.length < 2) {
        continue;
      }

      for (const column of stack) {
        column.dataset.inCollapsedStack = 'true';
        column.dataset.stackSize = String(stack.length);
      }

      stack[0].dataset.stackLeader = 'true';
      const stackHandle = stack[0].querySelector(
        '.duck-column-stack-drag'
      );

      if (stackHandle) {
        stackHandle.textContent = `S${stack.length}`;
      }
    }
  }

  function syncColumnInterface() {
    updateCollapsedStacks();
    const chatState = chatPanel.dataset.columnState;

    toggle.setAttribute(
      'aria-expanded',
      String(panel.dataset.columnState === 'expanded')
    );
    toggle.title = panel.dataset.columnState === 'expanded'
      ? 'Make all columns equal'
      : 'Bring Project to front';

    if (chatToggle) {
      chatToggle.setAttribute(
        'aria-expanded',
        String(chatState !== 'collapsed')
      );
      chatToggle.textContent = chatState === 'expanded'
        ? 'Chat focused'
        : 'Ask project';
    }

    if (chatState !== 'collapsed') {
      loadChat();
    }
  }

  function applyColumnStates(states, persist = true) {
    for (const column of workspaceColumns) {
      const columnId = column.dataset.duckColumn;
      const nextState = states[columnId];

      if (validColumnState(nextState)) {
        column.dataset.columnState = nextState;
      }
    }

    const expanded = workspaceColumns.filter(
      (column) => column.dataset.columnState === 'expanded'
    );

    if (expanded.length > 1) {
      expanded.slice(1).forEach((column) => {
        column.dataset.columnState = 'collapsed';
      });
    }

    if (
      workspaceColumns.every(
        (column) => column.dataset.columnState === 'collapsed'
      )
    ) {
      activityPanel.dataset.columnState = 'expanded';
    }

    syncColumnInterface();

    if (persist) {
      saveColumnLayout();
    }
  }

  function focusColumn(columnId) {
    const selected = columnById(columnId);

    if (!selected) {
      return;
    }

    const states = {};

    for (const column of workspaceColumns) {
      states[column.dataset.duckColumn] =
        column === selected ? 'expanded' : 'collapsed';
    }

    applyColumnStates(states);

    const focusTarget = selected.querySelector(
      'textarea, input, select, button:not(.duck-column-drag)'
    );

    window.setTimeout(() => focusTarget && focusTarget.focus(), 0);
  }

  function normalizeColumns() {
    const states = Object.fromEntries(
      workspaceColumns.map((column) => [
        column.dataset.duckColumn,
        'normal',
      ])
    );
    applyColumnStates(states);
  }

  function collapseColumn(columnId) {
    const selected = columnById(columnId);

    if (!selected) {
      return;
    }

    selected.dataset.columnState = 'collapsed';

    if (
      workspaceColumns.every(
        (column) => column.dataset.columnState === 'collapsed'
      )
    ) {
      const fallback = orderedColumns().find(
        (column) => column !== selected
      ) || activityPanel;
      fallback.dataset.columnState = 'expanded';
    }

    syncColumnInterface();
    saveColumnLayout();
  }

  function restoreColumnLayout() {
    let saved = null;

    try {
      saved = JSON.parse(localStorage.getItem(columnStorageKey) || 'null');
    } catch (_error) {
      saved = null;
    }

    if (saved && Array.isArray(saved.order)) {
      const restoredOrder = saved.order.filter(
        (columnId) => columnIds.has(columnId)
      );

      for (const columnId of columnIds) {
        if (!restoredOrder.includes(columnId)) {
          restoredOrder.push(columnId);
        }
      }

      for (const columnId of restoredOrder) {
        layout.append(columnById(columnId));
      }
    }

    applyColumnStates(
      saved && saved.states ? saved.states : {
        context: 'normal',
        activity: 'expanded',
        chat: 'collapsed',
      },
      false
    );
  }

  function collapsedStackFor(column) {
    const columns = orderedColumns();
    const position = columns.indexOf(column);

    if (position < 0 || column.dataset.columnState !== 'collapsed') {
      return [column];
    }

    let start = position;
    let end = position;

    while (
      start > 0
      && columns[start - 1].dataset.columnState === 'collapsed'
    ) {
      start -= 1;
    }

    while (
      end + 1 < columns.length
      && columns[end + 1].dataset.columnState === 'collapsed'
    ) {
      end += 1;
    }

    return columns.slice(start, end + 1);
  }

  function beginColumnDrag(event, column, asStack) {
    draggedColumnIds = (
      asStack ? collapsedStackFor(column) : [column]
    ).map((item) => item.dataset.duckColumn);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData(
      'text/plain',
      draggedColumnIds.join(',')
    );
    layout.classList.add('duck-column-dragging');

    for (const columnId of draggedColumnIds) {
      columnById(columnId).classList.add('is-dragging');
    }
  }

  function finishColumnDrag() {
    draggedColumnIds = [];
    layout.classList.remove('duck-column-dragging');

    for (const column of workspaceColumns) {
      column.classList.remove(
        'is-dragging',
        'is-drop-before',
        'is-drop-after'
      );
    }
  }

  for (const column of workspaceColumns) {
    column.querySelectorAll('[data-column-action]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        const action = button.dataset.columnAction;
        const columnId = column.dataset.duckColumn;

        if (action === 'expand') {
          focusColumn(columnId);
        } else if (action === 'normal') {
          normalizeColumns();
        } else if (action === 'collapse') {
          collapseColumn(columnId);
        }
      });
    });

    const dragHandle = column.querySelector('.duck-column-drag');
    const stackHandle = column.querySelector('.duck-column-stack-drag');

    if (dragHandle) {
      dragHandle.addEventListener(
        'dragstart',
        (event) => beginColumnDrag(event, column, false)
      );
      dragHandle.addEventListener('dragend', finishColumnDrag);
    }

    if (stackHandle) {
      stackHandle.addEventListener(
        'dragstart',
        (event) => beginColumnDrag(event, column, true)
      );
      stackHandle.addEventListener('dragend', finishColumnDrag);
    }

    column.addEventListener('dragover', (event) => {
      if (
        !draggedColumnIds.length
        || draggedColumnIds.includes(column.dataset.duckColumn)
      ) {
        return;
      }

      event.preventDefault();
      const rectangle = column.getBoundingClientRect();
      const before = event.clientX < rectangle.left + rectangle.width / 2;
      column.classList.toggle('is-drop-before', before);
      column.classList.toggle('is-drop-after', !before);
    });

    column.addEventListener('dragleave', () => {
      column.classList.remove('is-drop-before', 'is-drop-after');
    });

    column.addEventListener('drop', (event) => {
      if (
        !draggedColumnIds.length
        || draggedColumnIds.includes(column.dataset.duckColumn)
      ) {
        return;
      }

      event.preventDefault();
      const moving = draggedColumnIds.map(columnById).filter(Boolean);
      const rectangle = column.getBoundingClientRect();
      const before = event.clientX < rectangle.left + rectangle.width / 2;

      if (before) {
        column.before(...moving);
      } else {
        column.after(...moving);
      }

      finishColumnDrag();
      updateCollapsedStacks();
      saveColumnLayout();
    });
  }

  restoreColumnLayout();

  function setChatStatus(message, isError = false) {
    if (!chatStatus) {
      return;
    }

    chatStatus.textContent = message;
    chatStatus.classList.toggle('is-error', isError);
  }

  function createChatMessage(message) {
    const article = document.createElement('article');
    const role = message.role === 'assistant' ? 'Duck' : 'You';
    article.className = `duck-chat-message duck-chat-message-${
      message.role === 'assistant' ? 'assistant' : 'user'
    }`;

    const label = document.createElement('strong');
    label.textContent = role;

    const content = document.createElement('div');
    if (message.role === 'assistant' && message.html) {
      content.innerHTML = message.html;
    } else {
      content.textContent = message.content || '';
    }

    article.append(label, content);
    return article;
  }

  function renderChatMessages(messages) {
    if (!chatMessages) {
      return;
    }

    chatMessages.replaceChildren();

    if (!messages.length) {
      const empty = document.createElement('p');
      empty.className = 'duck-chat-empty';
      empty.textContent =
        'Ask about any document, decision, todo, note, or project file.';
      chatMessages.append(empty);
      return;
    }

    for (const message of messages) {
      chatMessages.append(createChatMessage(message));
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function responseJson(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  async function loadChat() {
    if (chatLoaded || chatLoading || !project) {
      return;
    }

    chatLoading = true;
    setChatStatus('Loading project chat...');

    try {
      const messagesResponse = await fetch(
        `/api/projects/${encodeURIComponent(project)}/chat/messages`
      );
      const messagesResult = await responseJson(messagesResponse);

      if (!messagesResponse.ok) {
        throw new Error(
          messagesResult.detail || 'Could not load project chat.'
        );
      }

      renderChatMessages(messagesResult.messages || []);

      const modelsResponse = await fetch(
        `/api/projects/${encodeURIComponent(project)}/chat/models`
      );
      const modelsResult = await responseJson(modelsResponse);

      if (!modelsResponse.ok) {
        throw new Error(
          modelsResult.detail || 'Could not load models.'
        );
      }

      if (chatModel) {
        chatModel.replaceChildren();

        for (const model of modelsResult.models || []) {
          const option = document.createElement('option');
          option.value = model;
          option.textContent = model;
          chatModel.append(option);
        }

        chatModel.value = modelsResult.default || '';
        chatModel.disabled = chatModel.options.length === 0;
      }

      if (!chatModel || chatModel.disabled) {
        throw new Error('The model endpoint returned no models.');
      }

      chatLoaded = true;
      setChatStatus('Ready');
    } catch (error) {
      setChatStatus(
        error instanceof Error
          ? error.message
          : 'Could not load project chat.',
        true
      );
    } finally {
      chatLoading = false;
    }
  }

  function setChatOpen(open) {
    if (!chatPanel || !chatToggle) {
      return;
    }

    if (open) {
      focusColumn('chat');
      window.setTimeout(() => chatInput && chatInput.focus(), 0);
    } else {
      collapseColumn('chat');
      focusColumn('activity');
    }
  }

  if (chatToggle) {
    chatToggle.addEventListener('click', () => {
      setChatOpen(chatPanel.dataset.columnState !== 'expanded');
    });
  }

  if (chatClose) {
    chatClose.addEventListener('click', () => setChatOpen(false));
  }

  async function submitChatMessage() {
    if (
      !chatInput
      || !chatModel
      || !chatSend
      || !project
    ) {
      return;
    }

    const message = chatInput.value.trim();

    if (!message) {
      setChatStatus('Enter a message.', true);
      chatInput.focus();
      return;
    }

    if (!chatModel.value) {
      setChatStatus('Choose a model.', true);
      return;
    }

    chatSend.disabled = true;
    chatModel.disabled = true;
    setChatStatus('The model is searching and reading the project...');

    try {
      const response = await fetch(
        `/api/projects/${encodeURIComponent(project)}/chat/messages`,
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            message,
            model: chatModel.value,
          }),
        }
      );
      const result = await responseJson(response);

      if (!response.ok) {
        throw new Error(result.detail || 'The model request failed.');
      }

      if (chatMessages) {
        const empty = chatMessages.querySelector('.duck-chat-empty');
        if (empty) {
          empty.remove();
        }
        chatMessages.append(
          createChatMessage(result.user_message),
          createChatMessage(result.assistant_message)
        );
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }

      chatInput.value = '';
      const context = result.context || {};
      const accessed = Array.isArray(context.accessed_files)
        ? context.accessed_files.length
        : 0;
      setChatStatus(
        `${accessed} file${accessed === 1 ? '' : 's'} read; ${
          context.tool_calls || 0
        } project tool call${context.tool_calls === 1 ? '' : 's'}; ${
          context.available_files || 0
        } files available`
      );
    } catch (error) {
      setChatStatus(
        error instanceof Error
          ? error.message
          : 'The model request failed.',
        true
      );
    } finally {
      chatSend.disabled = false;
      chatModel.disabled = false;
      chatInput.focus();
    }
  }

  if (chatForm) {
    chatForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitChatMessage();
    });
  }

  if (chatInput) {
    chatInput.addEventListener('keydown', (event) => {
      if (
        event.key === 'Enter'
        && (event.ctrlKey || event.metaKey)
      ) {
        event.preventDefault();
        submitChatMessage();
      }
    });
  }

  if (chatClear) {
    chatClear.addEventListener('click', async () => {
      if (!window.confirm('Clear this project chat?')) {
        return;
      }

      chatClear.disabled = true;

      try {
        const response = await fetch(
          `/api/projects/${encodeURIComponent(project)}/chat/messages`,
          {method: 'DELETE'}
        );
        const result = await responseJson(response);

        if (!response.ok) {
          throw new Error(result.detail || 'Could not clear chat.');
        }

        renderChatMessages([]);
        setChatStatus('Chat cleared');
      } catch (error) {
        setChatStatus(
          error instanceof Error
            ? error.message
            : 'Could not clear chat.',
          true
        );
      } finally {
        chatClear.disabled = false;
      }
    });
  }

  toggle.addEventListener('click', (event) => {
    event.stopPropagation();
    if (panel.dataset.columnState === 'expanded') {
      normalizeColumns();
    } else {
      focusColumn('context');
    }
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
        () => {
          if (type && type.value === 'file') {
            if (composerTitle) {
              composerTitle.focus();
            }
          } else if (composer) {
            composer.focus();
          }
        },
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
    } else if (
      event.key === 'Escape'
      && chatPanel.dataset.columnState === 'expanded'
    ) {
      event.preventDefault();
      setChatOpen(false);
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

  function updateCharacterCounter() {
    if (!type || !composer || !characterCounter) {
      return;
    }

    composer.removeAttribute('maxlength');

    if (!['note', 'todo'].includes(type.value)) {
      characterCounter.hidden = true;
      characterCounter.classList.remove(
        'is-low',
        'is-over'
      );
      return;
    }

    characterCounter.hidden = false;
    const count = composer.value.length;
    characterCounter.textContent =
      `${count.toLocaleString()} character${count === 1 ? '' : 's'}`;
    characterCounter.classList.remove('is-low', 'is-over');
  }

  function selectedFileMode() {
    const selected = fileModeInputs.find((input) => input.checked);
    return selected ? selected.value : 'upload';
  }

  function updateFileMode() {
    const markdownMode = selectedFileMode() === 'markdown';

    if (fileUploadFields) {
      fileUploadFields.hidden = markdownMode;
    }

    if (fileMarkdownFields) {
      fileMarkdownFields.hidden = !markdownMode;
    }
  }

  function updateComposerForType() {
    if (!type || !composer) {
      return;
    }

    const isFile = type.value === 'file';
    composer.hidden = isFile;

    if (fileFields) {
      fileFields.hidden = !isFile;
    }

    composer.placeholder =
      placeholders[type.value]
      || 'Add project activity…';

    if (composerTitle) {
      composerTitle.placeholder =
        titlePlaceholders[type.value]
        || 'Activity title';
    }

    if (post) {
      post.textContent = isFile ? 'Save file' : 'Post';
    }

    showFeedback(
      isFile
        ? 'Upload a file or write Markdown and save it as a project file.'
        : 'Notes, todos, status updates, and links can be posted.'
    );
    updateFileMode();
    updateCharacterCounter();
  }

  if (type && composer) {
    type.addEventListener('change', updateComposerForType);

    composer.addEventListener(
      'input',
      updateCharacterCounter
    );

    updateComposerForType();
  }

  for (const input of fileModeInputs) {
    input.addEventListener('change', updateFileMode);
  }

  if (fileShortcut && type) {
    fileShortcut.addEventListener('click', () => {
      type.value = 'file';
      updateComposerForType();
      setComposerOpen(true);
    });
  }

  const supportedTypes = new Set([
    'note',
    'todo',
    'status',
    'link',
    'file',
  ]);

  const typeLabels = {
    note: 'Note',
    todo: 'Todo',
    status: 'Status update',
    link: 'Link',
    file: 'File',
  };

  function showFeedback(message) {
    if (feedback) {
      feedback.textContent = message;
    }
  }

  function explainUnavailable() {
    showFeedback(
      'Additional fields are not enabled yet.'
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

  async function convertNoteToFile(button) {
    const activityId = button.dataset.activityId || '';
    const title = button.dataset.activityTitle || 'note';
    const suggestedName = `${
      title
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9._-]+/g, '-')
        .replace(/^-+|-+$/g, '')
        || 'note'
    }.md`;
    const path = window.prompt(
      'Filename under files/:',
      suggestedName
    );

    if (!activityId || !project || path === null) {
      return;
    }

    if (!path.trim()) {
      showFeedback('Enter a filename for the converted Note.');
      return;
    }

    button.disabled = true;
    button.textContent = 'Converting…';

    try {
      const response = await fetch(
        `/api/projects/${
          encodeURIComponent(project)
        }/activity/${
          encodeURIComponent(activityId)
        }/convert-to-file`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({path: path.trim()}),
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
          result.detail || 'The Note could not be converted.'
        );
      }

      if (filter) {
        filter.value = 'file';
        rememberFilter('file');
      }

      showFeedback('Note converted to a file. Refreshing…');
      window.location.reload();
    } catch (error) {
      showFeedback(
        error instanceof Error
          ? error.message
          : 'The Note could not be converted.'
      );
      button.disabled = false;
      button.textContent = 'Convert to file';
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

  async function submitProjectFile(title) {
    if (!post || !project) {
      return;
    }

    const mode = selectedFileMode();
    const formData = new FormData();
    formData.append('title', title);
    formData.append('mode', mode);

    if (mode === 'markdown') {
      const filename = fileName ? fileName.value.trim() : '';

      if (!filename) {
        showFeedback('Enter a project-relative path for the Markdown file.');

        if (fileName) {
          fileName.focus();
        }

        return;
      }

      formData.append('path', filename);
      formData.append(
        'markdown',
        fileMarkdown ? fileMarkdown.value : ''
      );
    } else {
      const selected = fileUpload && fileUpload.files
        ? fileUpload.files[0]
        : null;

      if (!selected) {
        showFeedback('Choose a file to upload.');

        if (fileUpload) {
          fileUpload.focus();
        }

        return;
      }

      formData.append('upload', selected, selected.name);

      if (fileName && fileName.value.trim()) {
        formData.append('path', fileName.value.trim());
      }
    }

    post.disabled = true;
    post.textContent = 'Saving…';
    showFeedback('Saving file…');

    try {
      const response = await fetch(
        `/api/projects/${encodeURIComponent(project)}/files`,
        {
          method: 'POST',
          body: formData,
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
          result.detail || 'The file could not be saved.'
        );
      }

      if (composerTitle) {
        composerTitle.value = '';
      }

      if (fileUpload) {
        fileUpload.value = '';
      }

      if (fileName) {
        fileName.value = '';
      }

      if (fileMarkdown) {
        fileMarkdown.value = '';
      }

      if (filter) {
        filter.value = 'file';
        rememberFilter('file');
      }

      showFeedback('File saved. Refreshing…');
      window.location.reload();
    } catch (error) {
      showFeedback(
        error instanceof Error
          ? error.message
          : 'The file could not be saved.'
      );
      post.disabled = false;
      post.textContent = 'Save file';
    }
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
        'Choose Note, Todo, Status, Link, or File.'
      );
      return;
    }

    if (!title) {
      showFeedback('Enter a title before posting.');
      composerTitle.focus();
      return;
    }

    if (kind === 'file') {
      await submitProjectFile(title);
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

  for (const button of convertNoteButtons) {
    button.addEventListener(
      'click',
      () => convertNoteToFile(button)
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

  if (fileMarkdown) {
    fileMarkdown.addEventListener('keydown', (event) => {
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
