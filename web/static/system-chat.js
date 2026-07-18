(() => {
  const model = document.getElementById('duck-system-chat-model');
  const focus = document.getElementById('duck-system-chat-focus');
  const clear = document.getElementById('duck-system-chat-clear');
  const messages = document.getElementById('duck-system-chat-messages');
  const form = document.getElementById('duck-system-chat-form');
  const input = document.getElementById('duck-system-chat-input');
  const send = document.getElementById('duck-system-chat-send');
  const status = document.getElementById('duck-system-chat-status');

  if (
    !model
    || !focus
    || !clear
    || !messages
    || !form
    || !input
    || !send
    || !status
  ) {
    return;
  }

  const sidebarToggle = document.getElementById('sidebar-toggle');

  function syncFocusButton() {
    const focused = document.body.classList.contains('projects-collapsed');
    focus.textContent = focused ? 'Projects' : 'Focus';
    focus.setAttribute(
      'aria-label',
      focused ? 'Show projects' : 'Focus on chat'
    );
  }

  function resizeInput() {
    input.style.height = 'auto';
    const height = Math.min(input.scrollHeight, 144);
    input.style.height = `${Math.max(height, 48)}px`;
    input.style.overflowY = input.scrollHeight > 144 ? 'auto' : 'hidden';
  }

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle('is-error', isError);
  }

  function messageElement(message) {
    const article = document.createElement('article');
    const role = message.role === 'assistant' ? 'assistant' : 'user';
    article.className = `duck-system-message duck-system-message-${role}`;

    if (role === 'assistant' && message.html) {
      article.innerHTML = message.html;
    } else {
      article.textContent = message.content || '';
    }

    return article;
  }

  function renderMessages(items) {
    messages.replaceChildren();

    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'duck-system-chat-empty';
      empty.textContent = (
        'Ask about projects, recent activity, notes, statuses, links, '
        + 'priorities, or incomplete Todos.'
      );
      messages.append(empty);
      return;
    }

    items.forEach((item) => messages.append(messageElement(item)));
    messages.scrollTop = messages.scrollHeight;
  }

  async function responseJson(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  async function loadChat() {
    setStatus('Loading Duck chat...');

    try {
      const [messagesResponse, modelsResponse] = await Promise.all([
        fetch('/api/system/chat/messages'),
        fetch('/api/system/chat/models'),
      ]);
      const messagesResult = await responseJson(messagesResponse);
      const modelsResult = await responseJson(modelsResponse);

      if (!messagesResponse.ok) {
        throw new Error(messagesResult.detail || 'Could not load Duck chat.');
      }

      if (!modelsResponse.ok) {
        throw new Error(modelsResult.detail || 'Could not load models.');
      }

      renderMessages(messagesResult.messages || []);
      model.replaceChildren();

      for (const identifier of modelsResult.models || []) {
        const option = document.createElement('option');
        option.value = identifier;
        option.textContent = identifier;
        model.append(option);
      }

      model.value = modelsResult.default || '';
      model.disabled = model.options.length === 0;
      setStatus(
        model.disabled
          ? 'No model is available.'
          : 'Duck can inspect system data and Activity across all projects.',
        model.disabled
      );
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Could not load Duck chat.',
        true
      );
    }
  }

  async function submitMessage() {
    const message = input.value.trim();

    if (!message) {
      setStatus('Enter a message.', true);
      input.focus();
      return;
    }

    if (!model.value) {
      setStatus('Choose an available model.', true);
      return;
    }

    send.disabled = true;
    model.disabled = true;
    setStatus('Duck is inspecting the project system...');

    try {
      const response = await fetch('/api/system/chat/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message, model: model.value}),
      });
      const result = await responseJson(response);

      if (!response.ok) {
        throw new Error(result.detail || 'Duck could not answer.');
      }

      const empty = messages.querySelector('.duck-system-chat-empty');
      if (empty) {
        empty.remove();
      }

      messages.append(messageElement(result.user_message));
      messages.append(messageElement(result.assistant_message));
      messages.scrollTop = messages.scrollHeight;
      input.value = '';
      resizeInput();

      const context = result.context || {};
      const inspected = Array.isArray(context.accessed_projects)
        ? context.accessed_projects.length
        : 0;
      setStatus(
        `${context.project_count || 0} projects available; `
        + `${context.tool_calls || 0} tool calls; `
        + `${inspected} projects inspected.`
      );
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Duck could not answer.',
        true
      );
    } finally {
      send.disabled = false;
      model.disabled = model.options.length === 0;
      input.focus();
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    submitMessage();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submitMessage();
    }
  });

  input.addEventListener('input', resizeInput);

  focus.addEventListener('click', () => {
    if (sidebarToggle) {
      sidebarToggle.click();
    } else {
      document.body.classList.toggle('projects-collapsed');
    }

    syncFocusButton();
  });

  new MutationObserver(syncFocusButton).observe(
    document.body,
    {attributes: true, attributeFilter: ['class']}
  );

  clear.addEventListener('click', async () => {
    if (!window.confirm('Clear the system-wide Duck chat?')) {
      return;
    }

    clear.disabled = true;

    try {
      const response = await fetch('/api/system/chat/messages', {
        method: 'DELETE',
      });
      const result = await responseJson(response);

      if (!response.ok) {
        throw new Error(result.detail || 'Could not clear Duck chat.');
      }

      renderMessages([]);
      setStatus('System chat cleared.');
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Could not clear Duck chat.',
        true
      );
    } finally {
      clear.disabled = false;
    }
  });

  syncFocusButton();
  resizeInput();
  loadChat();
})();
