/* ═══════════════════════════════════════════════════════
   Crypt Lab AI Chatbot — powered by puter.js (gpt-4o-mini)
   Zero backend changes. Zero API keys.
   ═══════════════════════════════════════════════════════ */

'use strict';

var chatbot = (function () {

  /* ── State ── */
  var isOpen             = false;
  var isStreaming        = false;
  var conversationHistory = [];
  var systemContext      = null;
  var _contextTimer      = null;
  var _streamingBubble   = null;
  var _hasWelcomed       = false;
  var _notifVisible      = false;

  /* ── Quick actions ── */
  var QUICK_ACTIONS = [
    { label: '📊 Status',   message: 'Give me a quick summary of the current security status of my system.' },
    { label: '🚨 Attacks',  message: 'What are the most serious attacks detected recently? List them with details.' },
    { label: '📋 Logs',     message: 'What suspicious patterns do you see in the recent system logs?' },
    { label: '🛡 Advice',   message: 'Based on all current alerts, what are the top 3 things I should do right now?' },
    { label: '🔍 Patterns', message: 'Are there any recurring attackers or patterns across multiple alerts?' },
    { label: '❓ Help',     message: 'What kinds of questions can I ask you about my network security?' }
  ];

  /* ═══════════════════════════════════════
     DATA FETCHING
  ═══════════════════════════════════════ */

  async function fetchSystemContext() {
    try {
      var results = await Promise.all([
        fetch('/api/alerts').then(function(r){ return r.json(); }),
        fetch('/api/stats').then(function(r){ return r.json(); }),
        fetch('/api/logs').then(function(r){ return r.json(); })
      ]);
      var alerts = Array.isArray(results[0]) ? results[0] : (results[0].alerts || []);
      var stats  = results[1] || {};
      var logs   = Array.isArray(results[2]) ? results[2] : (results[2].logs || []);
      systemContext = {
        alerts:     alerts.slice(0, 20),
        stats:      stats,
        recentLogs: logs.slice(0, 30),
        fetchedAt:  new Date().toISOString()
      };
      updateContextBar();
      return systemContext;
    } catch (err) {
      appendBubble('system', '⚠ Could not load system context: ' + err.message);
      return null;
    }
  }

  function buildSystemPrompt(ctx) {
    var alertSummary = (ctx.alerts || []).map(function(a) {
      return '[' + (a.timestamp || '') + '] ' +
        (a.attack_type || 'Unknown') + ' from ' + (a.src_ip || '?') +
        ' (' + [a.geo_city, a.geo_country].filter(Boolean).join(', ') + ')' +
        ' Severity:' + (a.severity || '?') +
        ' Confidence:' + (typeof a.confidence === 'number' ? Math.round(a.confidence * 100) + '%' : '?') +
        ' — ' + (a.alert_message || '');
    }).join('\n');

    var statsSummary = Object.entries(ctx.stats || {})
      .map(function(e){ return e[0] + ': ' + e[1]; })
      .join(', ') || 'No statistics available.';

    var logSummary = (ctx.recentLogs || []).slice(0, 15).map(function(l) {
      return '[' + (l.log_type || 'log') + '] ' + (l.raw_line || '');
    }).join('\n');

    return 'You are the AI security analyst for "Crypt Lab", a real-time Intrusion Detection System.\n\n' +
      'Your role:\n' +
      '- Answer questions about current and recent network security events\n' +
      '- Explain alerts in plain English to non-technical administrators\n' +
      '- Suggest specific countermeasures for detected attacks\n' +
      '- Identify patterns across multiple alerts\n' +
      '- Be direct and actionable — this is a security operations context\n\n' +
      'CURRENT SYSTEM STATE (as of ' + ctx.fetchedAt + '):\n\n' +
      'ATTACK STATISTICS:\n' + statsSummary + '\n\n' +
      'RECENT ALERTS (newest first):\n' + (alertSummary || 'No alerts recorded yet.') + '\n\n' +
      'RECENT SYSTEM LOGS:\n' + (logSummary || 'No log events captured yet.') + '\n\n' +
      'Rules:\n' +
      '- Be concise but complete — security teams need fast answers\n' +
      '- Always mention specific IPs, times, and severity levels when relevant\n' +
      '- If you see a pattern (same IP attacking multiple times), highlight it\n' +
      '- If asked about countermeasures, give specific actionable steps\n' +
      '- If the system looks clean, say so clearly\n' +
      '- Format lists with bullet points for readability\n' +
      '- Never make up data — only reference what is in the context above';
  }

  /* ═══════════════════════════════════════
     MESSAGING
  ═══════════════════════════════════════ */

  async function sendMessage(userMessage) {
    if (isStreaming) return;
    if (!userMessage || !userMessage.trim()) return;

    // puter.js check
    if (typeof puter === 'undefined') {
      appendBubble('system', '⚠ AI unavailable — puter.js could not be loaded. Check your internet connection.');
      return;
    }

    // Refresh context if stale (> 60s) or missing
    if (!systemContext || (Date.now() - new Date(systemContext.fetchedAt).getTime()) > 60000) {
      appendBubble('system', '📡 Refreshing system context…');
      await fetchSystemContext();
    }

    appendBubble('user', userMessage);
    scrollToBottom();

    conversationHistory.push({ role: 'user', content: userMessage });
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }

    var messages = [
      { role: 'system', content: buildSystemPrompt(systemContext || { alerts: [], stats: {}, recentLogs: [], fetchedAt: new Date().toISOString() }) }
    ].concat(conversationHistory);

    await streamResponse(messages);
  }

  async function streamResponse(messages) {
    isStreaming = true;
    showTypingIndicator();
    var fullResponse = '';

    try {
      var response = await puter.ai.chat(messages, { model: 'gpt-4o-mini', stream: true });
      hideTypingIndicator();
      createStreamingBubble();

      for await (var part of response) {
        if (part && part.text) {
          fullResponse += part.text;
          updateStreamingBubble(fullResponse);
        }
      }

      finalizeStreamingBubble();
      conversationHistory.push({ role: 'assistant', content: fullResponse });

    } catch (err) {
      hideTypingIndicator();
      appendBubble('system', '⚠ AI response failed. Try asking again. (' + (err.message || err) + ')');
      console.error('[Chatbot] streamResponse error:', err);
    } finally {
      isStreaming = false;
      scrollToBottom();
    }
  }

  /* ═══════════════════════════════════════
     UI HELPERS
  ═══════════════════════════════════════ */

  function appendBubble(role, text) {
    var el = document.createElement('div');
    if (role === 'user') {
      el.className = 'chat-bubble-user';
      el.textContent = text;
    } else if (role === 'ai') {
      el.className = 'chat-bubble-ai';
      el.textContent = text;
    } else {
      el.className = 'chat-bubble-system';
      el.textContent = text;
    }
    document.getElementById('chatbot-messages').appendChild(el);
    scrollToBottom();
    return el;
  }

  function createStreamingBubble() {
    _streamingBubble = document.createElement('div');
    _streamingBubble.className = 'chat-bubble-ai';
    _streamingBubble.textContent = '';
    document.getElementById('chatbot-messages').appendChild(_streamingBubble);
    scrollToBottom();
  }

  function updateStreamingBubble(text) {
    if (_streamingBubble) {
      _streamingBubble.textContent = text;
      scrollToBottom();
    }
  }

  function finalizeStreamingBubble() {
    _streamingBubble = null;
  }

  function showTypingIndicator() {
    var el = document.createElement('div');
    el.className = 'chat-bubble-ai typing-dots';
    el.id = 'chatbot-typing';
    el.innerHTML = '<span>●</span><span>●</span><span>●</span>';
    document.getElementById('chatbot-messages').appendChild(el);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    var el = document.getElementById('chatbot-typing');
    if (el) el.remove();
  }

  function scrollToBottom() {
    var box = document.getElementById('chatbot-messages');
    if (box) box.scrollTop = box.scrollHeight;
  }

  function updateContextBar() {
    var el = document.getElementById('chatbot-context-text');
    if (!el) return;
    if (!systemContext) {
      el.textContent = 'No context loaded';
      return;
    }
    var alertCount = (systemContext.alerts || []).length;
    var logCount   = (systemContext.recentLogs || []).length;
    var ago = Math.round((Date.now() - new Date(systemContext.fetchedAt).getTime()) / 1000);
    var agoStr = ago < 60 ? ago + 's ago' : Math.floor(ago / 60) + 'm ago';
    el.textContent = 'Context: ' + alertCount + ' alerts | ' + logCount + ' log events | Updated ' + agoStr;
  }

  function showContextRefreshedMsg() {
    var alertCount = systemContext ? (systemContext.alerts || []).length : 0;
    var logCount   = systemContext ? (systemContext.recentLogs || []).length : 0;
    var sysEl = appendBubble('system', '📡 Context updated — ' + alertCount + ' alerts, ' + logCount + ' log events loaded');
    setTimeout(function(){ if (sysEl && sysEl.parentNode) sysEl.remove(); }, 3000);
  }

  function buildQuickButtons() {
    var container = document.getElementById('chatbot-quick-buttons');
    if (!container) return;
    container.innerHTML = '';
    QUICK_ACTIONS.forEach(function(action) {
      var btn = document.createElement('button');
      btn.textContent = action.label;
      btn.onclick = function() { sendMessage(action.message); };
      container.appendChild(btn);
    });
  }

  function showWelcome() {
    appendBubble('ai',
      '🔐 Crypt Lab AI is ready.\n\n' +
      'I have access to your live alert feed, system logs, and attack statistics. ' +
      'Ask me anything about your network security.\n\n' +
      'Try:\n' +
      '• "What\'s happening right now?"\n' +
      '• "Is my system under attack?"\n' +
      '• "What should I do about the last alert?"\n' +
      '• "Show me all High severity events"\n\n' +
      'ℹ First-time setup: puter.js may ask you to sign in with a free puter.com account. ' +
      'This is required once only and takes 30 seconds. After that, the AI works indefinitely for free.'
    );
  }

  /* ═══════════════════════════════════════
     PANEL OPEN / CLOSE / TOGGLE
  ═══════════════════════════════════════ */

  function open() {
    if (isOpen) return;
    isOpen = true;
    document.getElementById('chatbot-panel').classList.remove('chatbot-hidden');

    if (!_hasWelcomed) {
      _hasWelcomed = true;
      showWelcome();
      buildQuickButtons();
    }

    // Fetch context on open
    fetchSystemContext().then(function() {
      showContextRefreshedMsg();
    });

    // Auto-refresh context every 60s while open
    _contextTimer = setInterval(function() {
      if (isOpen) {
        fetchSystemContext().then(function() {
          updateContextBar();
        });
      }
    }, 60000);

    clearNotification();
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    document.getElementById('chatbot-panel').classList.add('chatbot-hidden');
    if (_contextTimer) { clearInterval(_contextTimer); _contextTimer = null; }
  }

  function toggle() {
    if (isOpen) { close(); } else { open(); }
  }

  async function refreshContext() {
    appendBubble('system', '🔄 Refreshing context…');
    await fetchSystemContext();
    showContextRefreshedMsg();
  }

  /* ═══════════════════════════════════════
     PUBLIC SEND (from input box or quick btn)
  ═══════════════════════════════════════ */

  function send(messageOverride) {
    var input = document.getElementById('chatbot-input');
    var msg = (typeof messageOverride === 'string' && messageOverride)
      ? messageOverride
      : (input ? input.value.trim() : '');
    if (!msg) return;
    if (input) input.value = '';
    sendMessage(msg);
  }

  /* ═══════════════════════════════════════
     WEBSOCKET / EXTERNAL HOOKS
  ═══════════════════════════════════════ */

  function notifyNewAlert(alert) {
    // Show red dot on toggle button
    var dot = document.getElementById('chatbot-notif-dot');
    if (dot) { dot.classList.add('visible'); _notifVisible = true; }

    // If panel is open, show a system message
    if (isOpen) {
      appendBubble('system',
        '🚨 New ' + (alert.severity || '') + ' Alert: ' +
        (alert.attack_type || 'Unknown') + ' from ' + (alert.src_ip || '?') +
        ' — ask me for details'
      );
    }
  }

  function clearNotification() {
    var dot = document.getElementById('chatbot-notif-dot');
    if (dot) { dot.classList.remove('visible'); }
    _notifVisible = false;
  }

  /* ═══════════════════════════════════════
     IP CLICK-TO-ASK
  ═══════════════════════════════════════ */

  function askAboutIP(ip) {
    open();
    // Small delay so welcome/context messages render first
    setTimeout(function() {
      sendMessage('Tell me everything about attacks from ' + ip);
    }, 300);
  }

  /* ═══════════════════════════════════════
     CONTEXT BAR TICKER (updates every 10s)
  ═══════════════════════════════════════ */

  setInterval(function() {
    if (isOpen) updateContextBar();
  }, 10000);

  /* ═══════════════════════════════════════
     PUBLIC API
  ═══════════════════════════════════════ */

  return {
    get isStreaming() { return isStreaming; },
    toggle:          toggle,
    open:            open,
    close:           close,
    send:            send,
    refreshContext:  refreshContext,
    notifyNewAlert:  notifyNewAlert,
    clearNotification: clearNotification,
    askAboutIP:      askAboutIP,
    sendMessage:     sendMessage
  };

})();
