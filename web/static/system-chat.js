(() => {
  const model = document.getElementById('duck-system-chat-model');
  const fontDecrease = document.getElementById(
    'duck-system-chat-font-decrease'
  );
  const fontIncrease = document.getElementById(
    'duck-system-chat-font-increase'
  );
  const fontLabel = document.getElementById('duck-system-chat-font-label');
  const focus = document.getElementById('duck-system-chat-focus');
  const clear = document.getElementById('duck-system-chat-clear');
  const messages = document.getElementById('duck-system-chat-messages');
  const form = document.getElementById('duck-system-chat-form');
  const input = document.getElementById('duck-system-chat-input');
  const send = document.getElementById('duck-system-chat-send');
  const status = document.getElementById('duck-system-chat-status');

  if (
    !model
    || !fontDecrease
    || !fontIncrease
    || !fontLabel
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
  const chat = document.querySelector('.duck-system-chat');
  const fontScales = [0.6, 0.7, 0.85, 1, 1.15, 1.3, 1.45];
  const fontScaleKey = 'duck.system-chat.font-scale';
  let fontScaleIndex = fontScales.indexOf(1);

  function setFontScale(index) {
    fontScaleIndex = Math.max(
      0,
      Math.min(index, fontScales.length - 1)
    );

    const scale = fontScales[fontScaleIndex];

    if (chat) {
      chat.style.setProperty(
        '--duck-system-chat-font-scale',
        `${Math.round(scale * 100)}%`
      );
    }

    fontLabel.textContent = `${Math.round(scale * 100)}%`;
    fontDecrease.disabled = fontScaleIndex === 0;
    fontIncrease.disabled = fontScaleIndex === fontScales.length - 1;
    localStorage.setItem(fontScaleKey, String(scale));
  }

  function loadFontScale() {
    const stored = Number(localStorage.getItem(fontScaleKey));

    if (Number.isFinite(stored)) {
      const exact = fontScales.indexOf(stored);

      if (exact >= 0) {
        fontScaleIndex = exact;
      }
    }

    setFontScale(fontScaleIndex);
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const temporary = document.createElement('textarea');
    temporary.value = text;
    temporary.setAttribute('readonly', '');
    temporary.style.position = 'fixed';
    temporary.style.opacity = '0';
    document.body.append(temporary);
    temporary.select();

    const copied = document.execCommand('copy');
    temporary.remove();

    if (!copied) {
      throw new Error('Copy failed');
    }
  }

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
    const content = message.content || '';
    article.className = `duck-system-message duck-system-message-${role}`;

    if (role === 'assistant') {
      const actions = document.createElement('div');
      const copy = document.createElement('button');
      const rendered = document.createElement('div');

      actions.className = 'duck-system-message-actions';
      copy.className = 'duck-system-message-copy';
      copy.type = 'button';
      copy.textContent = 'Copy answer';
      rendered.className = 'duck-system-message-content';

      if (message.html) {
        rendered.innerHTML = message.html;
      } else {
        rendered.textContent = content;
      }

      copy.addEventListener('click', async () => {
        copy.disabled = true;

        try {
          await copyText(content);
          copy.textContent = 'Copied';
        } catch (_error) {
          copy.textContent = 'Copy failed';
        }

        window.setTimeout(() => {
          copy.textContent = 'Copy answer';
          copy.disabled = false;
        }, 1400);
      });

      actions.append(copy);
      article.append(actions, rendered);
    } else {
      article.textContent = content;
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

  fontDecrease.addEventListener('click', () => {
    setFontScale(fontScaleIndex - 1);
  });

  fontIncrease.addEventListener('click', () => {
    setFontScale(fontScaleIndex + 1);
  });

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
  loadFontScale();
  resizeInput();
  loadChat();
})();
