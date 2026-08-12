# CRYPT LAB — CHATBOT MODULE BRIEF
> Feed this entire file to Copilot.
> This adds a security chatbot to the existing Crypt Lab dashboard.
> The chatbot uses puter.js for free, unlimited AI — no API keys, no quota.

---

## WHAT THIS FEATURE IS

Add a floating chatbot panel to the Crypt Lab dashboard that allows the
administrator to have a conversation with the IDS system.

The chatbot can answer questions like:
- "What attacks happened in the last hour?"
- "Show me all High severity alerts"
- "What should I do about the brute force from 185.220.101.45?"
- "How many DoS attacks today?"
- "Are there any patterns in the recent logs?"
- "Is my system currently under attack?"
- "Explain the last alert to me"
- "What ports are being scanned most?"

The AI has access to live data from the system fetched from the
existing backend API endpoints. It does NOT use Gemini. It uses
puter.js which is completely free with no API key required.

---

## WHY PUTER.JS (IMPORTANT — READ THIS)

puter.js is a free JavaScript library that provides access to
400+ AI models directly from the frontend with:
  - No API key required
  - No backend setup
  - No rate limits on the developer side
  - Users cover their own AI costs ("User-Pays" model)
  - Works via a single CDN script tag

Import it with one line — no npm install needed:
  <script src="https://js.puter.com/v2/"></script>

The AI call syntax:
  await puter.ai.chat(messages, { model: "gpt-4o-mini", stream: true })

Use model: "gpt-4o-mini" — it is fast, cheap for users, and more
than capable enough for security log analysis.

This replaces ALL need for Gemini in the chatbot. Gemini is still
used for alert enrichment in the backend (ids/llm.py) but the
chatbot runs entirely on puter.js in the frontend.

---

## SECTION A — FILES TO CREATE/MODIFY

```
MODIFY:
  static/index.html     ← Add chatbot panel HTML + puter.js script tag
  static/js/app.js      ← Add chatbot JS logic (or separate file below)

CREATE:
  static/js/chatbot.js  ← All chatbot logic (keep separate from app.js)
```

No backend changes needed. The chatbot fetches data from existing
endpoints that already exist:
  GET /api/alerts       ← alert history
  GET /api/stats        ← attack counts
  GET /api/logs         ← recent log lines
  GET /api/map          ← geo data

---

## SECTION B — CHATBOT UI REQUIREMENTS

### Position
Floating panel — fixed position, bottom-right corner of the screen.
Does NOT overlap the main dashboard grid.
Has a toggle button to open/close it.

### Collapsed State (default)
A single floating button, bottom-right:
  - Dark navy background (#1e293b)
  - Cyan border glow
  - Icon: 🤖 or a shield+chat icon from lucide
  - Label: "Ask Crypt Lab"
  - Subtle pulse animation on the border

### Expanded State
A panel that slides up from the button:
  Width:  420px
  Height: 560px
  Position: fixed, bottom: 80px, right: 24px
  Background: #0f172a
  Border: 1px solid #334155 with cyan glow box-shadow
  Border-radius: 12px
  z-index: 1000 (above everything)

### Panel Structure
```
┌─────────────────────────────────────┐
│ 🔐 Crypt Lab AI    [minimize] [×]   │  ← Header
│ "Ask me about your network security" │  ← Subtitle
├─────────────────────────────────────┤
│                                     │
│  [Message bubbles scroll area]      │  ← Chat history
│                                     │
│  Welcome message on first open      │
│                                     │
├─────────────────────────────────────┤
│ [Context: 8 alerts | 30 logs] [🔄] │  ← Context bar
├─────────────────────────────────────┤
│ [Type your question...    ] [Send ▶]│  ← Input row
│ [Quick: Status][Attacks][Logs][Help]│  ← Quick buttons
└─────────────────────────────────────┘
```

### Message Bubbles
User messages:
  - Right-aligned
  - Background: #1e40af (blue)
  - White text
  - Rounded: border-radius 12px 12px 2px 12px

AI messages:
  - Left-aligned
  - Background: #1e293b (dark slate)
  - Cyan left border (3px)
  - Text: #e2e8f0
  - Rounded: border-radius 12px 12px 12px 2px
  - Streaming — text appears word by word as it generates

System messages (context updates, errors):
  - Centered
  - Small text, muted color
  - Italic
  - Example: "📡 Context refreshed — 12 alerts loaded"

### Typing Indicator
While AI is generating:
  - Show three animated dots (●●●) in an AI bubble
  - Replace with actual streamed text as it arrives

### Context Bar
Shows what data is loaded:
  "Context: {alert_count} alerts | {log_count} log events | Updated {time_ago}"
  Refresh button (🔄) to manually reload context from API

---

## SECTION C — CHATBOT LOGIC (chatbot.js)

### Step 1 — Initialize puter.js
puter.js is loaded via the script tag in index.html.
No initialization code needed — it's ready to use immediately.

### Step 2 — Fetch System Context
On chatbot open (and on refresh button click), fetch live data:

```javascript
async function fetchSystemContext() {
  const [alertsRes, statsRes, logsRes] = await Promise.all([
    fetch('/api/alerts'),
    fetch('/api/stats'),
    fetch('/api/logs')
  ]);

  const alerts = await alertsRes.json();
  const stats  = await statsRes.json();
  const logs   = await logsRes.json();

  return {
    alerts:      alerts.slice(0, 20),   // last 20 alerts only (keep prompt small)
    stats:       stats,
    recentLogs:  logs.slice(0, 30),     // last 30 log lines
    fetchedAt:   new Date().toISOString()
  };
}
```

### Step 3 — Build the System Prompt
This is injected as the "system" message so the AI knows its role
and has full context about the current system state:

```javascript
function buildSystemPrompt(context) {
  const alertSummary = context.alerts.map(a =>
    `[${a.timestamp}] ${a.attack_type} from ${a.src_ip} `+
    `(${a.geo_city || 'Unknown'}, ${a.geo_country || ''}) `+
    `Severity:${a.severity} Confidence:${(a.confidence*100).toFixed(0)}% `+
    `— ${a.alert_message}`
  ).join('\n');

  const statsSummary = Object.entries(context.stats)
    .map(([type, count]) => `${type}: ${count}`)
    .join(', ');

  const logSummary = context.recentLogs
    .slice(0, 15)
    .map(l => `[${l.log_type}] ${l.raw_line}`)
    .join('\n');

  return `You are the AI security analyst for "Crypt Lab", a real-time 
Intrusion Detection System. You have access to live system data.

Your role:
- Answer questions about current and recent network security events
- Explain alerts in plain English to non-technical administrators
- Suggest specific countermeasures for detected attacks
- Identify patterns across multiple alerts
- Be direct and actionable — this is a security operations context

CURRENT SYSTEM STATE (as of ${context.fetchedAt}):

ATTACK STATISTICS:
${statsSummary}

RECENT ALERTS (newest first):
${alertSummary || 'No alerts recorded yet.'}

RECENT SYSTEM LOGS:
${logSummary || 'No log events captured yet.'}

Rules:
- Be concise but complete — security teams need fast answers
- Always mention specific IPs, times, and severity levels when relevant
- If you see a pattern (same IP attacking multiple times), highlight it
- If asked about countermeasures, give specific actionable steps
- If the system looks clean, say so clearly
- Format lists with bullet points for readability
- Never make up data — only reference what is in the context above`;
}
```

### Step 4 — Send Message to puter.js

```javascript
// Conversation history (maintained in memory for multi-turn chat)
let conversationHistory = [];
let systemContext = null;

async function sendMessage(userMessage) {
  // Refresh context if older than 60 seconds
  if (!systemContext ||
      Date.now() - new Date(systemContext.fetchedAt) > 60000) {
    systemContext = await fetchSystemContext();
  }

  // Add user message to history
  conversationHistory.push({
    role: 'user',
    content: userMessage
  });

  // Build full messages array: system prompt + history
  const messages = [
    {
      role: 'system',
      content: buildSystemPrompt(systemContext)
    },
    ...conversationHistory
  ];

  // Keep history manageable — last 10 turns only
  if (conversationHistory.length > 20) {
    conversationHistory = conversationHistory.slice(-20);
  }

  // Call puter.js with streaming
  const response = await puter.ai.chat(messages, {
    model: 'gpt-4o-mini',
    stream: true
  });

  // Stream the response into the chat bubble
  let fullResponse = '';
  for await (const part of response) {
    if (part?.text) {
      fullResponse += part.text;
      updateStreamingBubble(fullResponse);  // update UI word by word
    }
  }

  // Add AI response to history
  conversationHistory.push({
    role: 'assistant',
    content: fullResponse
  });

  return fullResponse;
}
```

### Step 5 — Quick Action Buttons
These pre-fill and send common questions instantly:

```javascript
const QUICK_ACTIONS = [
  {
    label: '📊 Status',
    message: 'Give me a quick summary of the current security status of my system.'
  },
  {
    label: '🚨 Attacks',
    message: 'What are the most serious attacks detected recently? List them with details.'
  },
  {
    label: '📋 Logs',
    message: 'What suspicious patterns do you see in the recent system logs?'
  },
  {
    label: '🛡 Advice',
    message: 'Based on all current alerts, what are the top 3 things I should do right now?'
  },
  {
    label: '🔍 Patterns',
    message: 'Are there any recurring attackers or patterns across multiple alerts?'
  },
  {
    label: '❓ Help',
    message: 'What kinds of questions can I ask you about my network security?'
  }
];
```

### Step 6 — Welcome Message
Show this when the chatbot opens for the first time:

```
🔐 Crypt Lab AI is ready.

I have access to your live alert feed, system logs, and attack 
statistics. Ask me anything about your network security.

Try:
• "What's happening right now?"
• "Is my system under attack?"
• "What should I do about the last alert?"
• "Show me all High severity events"
```

---

## SECTION D — CONTEXT AWARENESS FEATURES

### Auto-Alert on New High Severity
When a new High severity alert arrives via the /ws/ids-feed WebSocket
(which already exists), the chatbot should:

1. Show a notification dot on the collapsed chatbot button (red badge)
2. If chatbot is open, append a system message:
   "🚨 New High Alert: [attack_type] from [src_ip] — ask me for details"
3. Do NOT auto-send a message (don't force conversation)

Implementation:
```javascript
// In the existing WebSocket handler in app.js, add:
socket.addEventListener('message', (event) => {
  const alert = JSON.parse(event.data);
  if (alert.event === 'alerts_cleared') {
    chatbot.clearNotification();
    return;
  }
  if (alert.severity === 'High') {
    chatbot.notifyNewAlert(alert);
  }
});
```

### Context Refresh Indicator
After fetching new context, briefly show:
  "📡 Context updated — [N] alerts, [N] log events loaded"
This disappears after 3 seconds.

### IP Click-to-Ask
In the main alert table, make every IP address clickable.
Clicking an IP opens the chatbot and auto-sends:
  "Tell me everything about the attacker at [IP_ADDRESS]"

Implementation — add to alert table rows:
```javascript
// Each IP in the alert table gets this:
ipCell.style.cursor = 'pointer';
ipCell.title = 'Click to ask AI about this IP';
ipCell.addEventListener('click', () => {
  chatbot.open();
  chatbot.sendMessage(`Tell me everything about attacks from ${ip}`);
});
```

---

## SECTION E — ERROR HANDLING

### puter.js Not Loaded
If puter.js CDN fails to load (no internet, blocked):
```javascript
if (typeof puter === 'undefined') {
  showChatMessage('system',
    '⚠ AI unavailable — puter.js could not be loaded. ' +
    'Check your internet connection.'
  );
  return;
}
```

### puter.js Auth Required
puter.js may show a login popup on first use if the user
is not signed in to puter.com. This is expected behavior.
The user signs in once with a free puter.com account and
then it works for all future sessions.

Add a help message when chatbot first opens:
```
ℹ First-time setup: puter.js may ask you to sign in with a 
free puter.com account. This is required once only and takes 
30 seconds. After that, the AI works indefinitely for free.
```

### API Errors
```javascript
try {
  await sendMessage(userInput);
} catch (err) {
  showChatMessage('system',
    '⚠ AI response failed. The context data is still ' +
    'available — try asking again.'
  );
  console.error('Chatbot error:', err);
}
```

---

## SECTION F — HTML TO ADD TO index.html

Add the puter.js CDN script in the <head>:
```html
<script src="https://js.puter.com/v2/"></script>
```

Add this HTML just before the closing </body> tag:
```html
<!-- Chatbot Toggle Button -->
<button id="chatbot-toggle" onclick="chatbot.toggle()">
  🤖 Ask Crypt Lab
</button>

<!-- Chatbot Panel -->
<div id="chatbot-panel" class="chatbot-hidden">
  <div id="chatbot-header">
    <span>🔐 Crypt Lab AI</span>
    <div>
      <button onclick="chatbot.refresh()">🔄</button>
      <button onclick="chatbot.close()">✕</button>
    </div>
  </div>
  <div id="chatbot-subtitle">Ask me about your network security</div>
  <div id="chatbot-messages"></div>
  <div id="chatbot-context-bar">
    <span id="chatbot-context-text">Loading context...</span>
  </div>
  <div id="chatbot-input-row">
    <input
      id="chatbot-input"
      type="text"
      placeholder="Type your question..."
      onkeydown="if(event.key==='Enter') chatbot.send()"
    />
    <button onclick="chatbot.send()">Send ▶</button>
  </div>
  <div id="chatbot-quick-buttons">
    <!-- populated by chatbot.js from QUICK_ACTIONS array -->
  </div>
</div>

<script src="/static/js/chatbot.js"></script>
```

---

## SECTION G — CSS TO ADD

Add these styles to index.html <style> or globals.css:

```css
/* Toggle Button */
#chatbot-toggle {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: #1e293b;
  color: #00b4d8;
  border: 1px solid #00b4d8;
  border-radius: 24px;
  padding: 10px 20px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  z-index: 999;
  box-shadow: 0 0 12px rgba(0, 180, 216, 0.3);
  animation: chatbot-pulse-border 2s infinite;
}

#chatbot-toggle .notification-dot {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 12px;
  height: 12px;
  background: #ef4444;
  border-radius: 50%;
  display: none;
}

#chatbot-toggle .notification-dot.visible {
  display: block;
}

/* Panel */
#chatbot-panel {
  position: fixed;
  bottom: 80px;
  right: 24px;
  width: 420px;
  height: 560px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 12px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 24px rgba(0, 180, 216, 0.15);
  transition: all 0.3s ease;
}

#chatbot-panel.chatbot-hidden {
  opacity: 0;
  pointer-events: none;
  transform: translateY(20px);
}

/* Header */
#chatbot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #334155;
  color: #00b4d8;
  font-weight: 700;
  font-size: 15px;
}

#chatbot-subtitle {
  padding: 6px 16px;
  font-size: 11px;
  color: #64748b;
  border-bottom: 1px solid #1e293b;
}

/* Messages */
#chatbot-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scroll-behavior: smooth;
}

.chat-bubble-user {
  align-self: flex-end;
  background: #1e40af;
  color: white;
  padding: 8px 12px;
  border-radius: 12px 12px 2px 12px;
  max-width: 80%;
  font-size: 13px;
  line-height: 1.5;
}

.chat-bubble-ai {
  align-self: flex-start;
  background: #1e293b;
  color: #e2e8f0;
  border-left: 3px solid #00b4d8;
  padding: 8px 12px;
  border-radius: 12px 12px 12px 2px;
  max-width: 85%;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.chat-bubble-system {
  align-self: center;
  color: #64748b;
  font-size: 11px;
  font-style: italic;
  padding: 4px 8px;
}

/* Typing dots */
.typing-dots span {
  animation: typing-dot 1.2s infinite;
  font-size: 20px;
  color: #00b4d8;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

/* Context bar */
#chatbot-context-bar {
  padding: 6px 16px;
  border-top: 1px solid #1e293b;
  border-bottom: 1px solid #1e293b;
  font-size: 11px;
  color: #475569;
}

/* Input */
#chatbot-input-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
}

#chatbot-input {
  flex: 1;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #e2e8f0;
  padding: 8px 12px;
  font-size: 13px;
  outline: none;
}

#chatbot-input:focus {
  border-color: #00b4d8;
  box-shadow: 0 0 8px rgba(0, 180, 216, 0.2);
}

#chatbot-input-row button {
  background: #00b4d8;
  color: #0f172a;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 700;
  cursor: pointer;
  font-size: 13px;
}

/* Quick buttons */
#chatbot-quick-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 12px 10px;
}

#chatbot-quick-buttons button {
  background: #1e293b;
  color: #94a3b8;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
}

#chatbot-quick-buttons button:hover {
  border-color: #00b4d8;
  color: #00b4d8;
}

/* Animations */
@keyframes chatbot-pulse-border {
  0%, 100% { box-shadow: 0 0 12px rgba(0, 180, 216, 0.3); }
  50%       { box-shadow: 0 0 20px rgba(0, 180, 216, 0.6); }
}

@keyframes typing-dot {
  0%, 60%, 100% { opacity: 0.2; }
  30%           { opacity: 1; }
}
```

---

## SECTION H — COMPLETE chatbot.js STRUCTURE

Implement the `chatbot` object with these methods:

```javascript
const chatbot = {
  isOpen:              false,
  conversationHistory: [],
  systemContext:       null,
  isStreaming:         false,

  // Open/close/toggle the panel
  toggle() {},
  open()   {},
  close()  {},

  // Fetch context from API
  async refreshContext() {},

  // Send a message (user-initiated or programmatic)
  async send(messageOverride = null) {},

  // Stream AI response into a bubble
  async streamResponse(messages) {},

  // UI helpers
  appendBubble(role, text)    {},  // role: 'user'|'ai'|'system'
  updateStreamingBubble(text) {},  // update last AI bubble during stream
  scrollToBottom()            {},
  showTypingIndicator()       {},
  hideTypingIndicator()       {},
  updateContextBar()          {},
  showContextRefreshed()      {},

  // Called from WebSocket handler in app.js
  notifyNewAlert(alert) {},   // show red dot + system message
  clearNotification()   {},   // clear red dot

  // Called when IP clicked in alert table
  askAboutIP(ip) {},
};
```

---

## SECTION I — INTEGRATION WITH EXISTING app.js

In the existing WebSocket message handler in app.js, add these
two lines to connect the chatbot to the live alert feed:

```javascript
// Find the existing WebSocket onmessage handler and add:
if (alert.severity === 'High' || alert.severity === 'Medium') {
  chatbot.notifyNewAlert(alert);
}
```

In the existing alert table rendering, make IPs clickable:
```javascript
// When building alert table rows, on the IP cell add:
ipCell.addEventListener('click', () => chatbot.askAboutIP(alert.src_ip));
ipCell.style.cursor = 'pointer';
ipCell.style.textDecoration = 'underline dotted';
ipCell.title = 'Click to ask AI about this IP';
```

---

## SECTION J — BUILD ORDER

Build in this exact order:

1. Add `<script src="https://js.puter.com/v2/"></script>` to index.html head
2. Add chatbot HTML structure to index.html body
3. Add all CSS from Section G to the stylesheet
4. Create static/js/chatbot.js with full implementation from Sections C and H
5. Add the two integration hooks to app.js from Section I
6. Test by opening dashboard, clicking "Ask Crypt Lab",
   signing in to puter.com when prompted (first time only),
   then asking: "What is the current security status?"

---

## SECTION K — RULES FOR COPILOT

1. puter.js is loaded from CDN — never install it via npm
2. Never call Gemini from the chatbot — puter.js only
3. The system prompt is rebuilt on every sendMessage call
   so it always has fresh context
4. Keep conversation history to last 20 messages to avoid
   puter.js token limits
5. Context fetch (alerts, stats, logs) runs on chatbot open
   and auto-refreshes every 60 seconds if chatbot is open
6. The chatbot is entirely frontend — zero new backend code needed
7. Streaming must be used (stream: true) so responses feel fast
8. If puter.js is undefined, show a clear error — never silently fail
9. The chatbot panel must NOT overlap the main dashboard content —
   it floats in the bottom-right corner only
10. Quick action buttons must be visible without scrolling at all times
```
