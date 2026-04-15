"""
Fix all SVG injection breakage in app.html.

The previous script put SVG strings inside x-text (which escapes them as visible text)
and inside x-html with unescaped quotes (which breaks HTML parsing).

Strategy:
- For buttons with ternary labels: use static HTML with x-show/x-if to switch states
- For notification/status icons: use static SVG with x-show conditions
- For nav items: x-html is fine since they are in JS data strings with proper escaping
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

count = 0

def rep(old, new, label=''):
    global html, count
    n = html.count(old)
    if n:
        html = html.replace(old, new)
        count += n
        print(f'  {n}x [{label}]: {repr(old[:60])}')
    else:
        print(f'  NOT FOUND [{label}]: {repr(old[:60])}')

# ─── SVG definitions ─────────────────────────────────────────────────────────
CHK  = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
XMRK = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
WARN = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
INFO = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
SPIN = '<svg class="w-4 h-4 flex-shrink-0 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
SPIN8= '<svg class="w-8 h-8 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
CONN = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><line x1="11.5" y1="10.5" x2="17" y2="6.5"/><line x1="11.5" y1="13.5" x2="17" y2="17.5"/></svg>'
DL   = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
PLAY = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none"/></svg>'
CHK6 = '<svg class="w-6 h-6 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
XMK6 = '<svg class="w-6 h-6 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
WRN6 = '<svg class="w-6 h-6 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
CHK8 = '<svg class="w-8 h-8 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
XMK8 = '<svg class="w-8 h-8 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
WRN8 = '<svg class="w-8 h-8 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
CHK35= '<svg class="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
XMK35= '<svg class="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
PLUS = '<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'

# ─── 1. Notification list icons (x-html with broken quote nesting) ────────────
# Replace entire broken x-html span with clean x-show-based spans
rep(
    """<span x-html="n.type==='success'?'<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>':n.type==='error'?'<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>':n.type==='warning'?'<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>':'<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'" class="mt-0.5 flex-shrink-0\"""",
    """<span class="mt-0.5 flex-shrink-0 w-4 h-4\"""",
    'notif icon x-html'
)
# The :class attribute follows immediately after — need to insert the x-show spans inside
# Actually insert them as children — change the approach: wrap with a div approach
# Better: use a containing span with x-show children
rep(
    """<span class="mt-0.5 flex-shrink-0 w-4 h-4"
                :class="theme==='light'
                  ? {'text-[#137333]':n.type==='success','text-[#c5221f]':n.type==='error','text-[#1a73e8]':n.type==='info','text-[#b06000]':n.type==='warning'}
                  : {'text-[#81c995]':n.type==='success','text-[#f28b82]':n.type==='error','text-[#8ab4f8]':n.type==='info','text-[#fdd663]':n.type==='warning'}"></span>""",
    f"""<span class="mt-0.5 flex-shrink-0 flex items-center"
                :class="theme==='light'
                  ? {{'text-[#137333]':n.type==='success','text-[#c5221f]':n.type==='error','text-[#1a73e8]':n.type==='info','text-[#b06000]':n.type==='warning'}}
                  : {{'text-[#81c995]':n.type==='success','text-[#f28b82]':n.type==='error','text-[#8ab4f8]':n.type==='info','text-[#fdd663]':n.type==='warning'}}">
              <span x-show="n.type==='success'">{CHK}</span>
              <span x-show="n.type==='error'">{XMRK}</span>
              <span x-show="n.type==='warning'">{WARN}</span>
              <span x-show="n.type==='info' || !['success','error','warning'].includes(n.type)">{INFO}</span>
            </span>""",
    'notif icon x-show'
)

# ─── 2. File pass/fail status icons (x-html with broken quotes) ───────────────
rep(
    """x-html="file.status==='passed'?'<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>':'<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'" >""",
    f"""x-show="true">
                            <span x-show="file.status==='passed'">{CHK35}</span>
                            <span x-show="file.status!=='passed'">{XMK35}</span>
                            <span """,
    'file status icon'
)

# ─── 3. Run live view big status icon ─────────────────────────────────────────
# Find the x-html with broken runStatus ternary
rep(
    """x-html="runStatus==='completed'?'<svg class="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>':runStatus==='cancelled'?'<svg class="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>':'<svg class="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'" """,
    f"""x-show="true">
                <span x-show="runStatus==='completed'">{CHK8}</span>
                <span x-show="runStatus==='cancelled'">{WRN8}</span>
                <span x-show="runStatus==='failed'">{XMK8}</span>
                <span """,
    'run live status icon'
)

# ─── 4. Run summary status icon ───────────────────────────────────────────────
rep(
    """x-html="runSummary.status==='completed'?'<svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>':runSummary.status==='failed'?'<svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>':'<svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'" """,
    f"""x-show="true">
                  <span x-show="runSummary.status==='completed'">{CHK6}</span>
                  <span x-show="runSummary.status==='failed'">{XMK6}</span>
                  <span x-show="runSummary.status!=='completed' && runSummary.status!=='failed'">{WRN6}</span>
                  <span """,
    'run summary status icon'
)

# ─── 5. Suggest fields button (SVG inside x-text) ─────────────────────────────
rep(
    """<span x-text="suggestingFields ? 'Suggesting...' : '<span class="flex items-center gap-1.5"><svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Suggest PLM Fields</span>'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                      <span x-show="suggestingFields">{SPIN} Suggesting...</span>
                      <span x-show="!suggestingFields">{INFO} Suggest PLM Fields</span>
                    </span>""",
    'suggest fields btn'
)

# ─── 6. Test Connection button in new connection modal ─────────────────────────
rep(
    """<span x-text="testingConn ? 'Testing...' : '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><line x1="11.5" y1="10.5" x2="17" y2="6.5"/><line x1="11.5" y1="13.5" x2="17" y2="17.5"/></svg> Test Connection'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                          <span x-show="testingConn">{SPIN} Testing...</span>
                          <span x-show="!testingConn">{CONN} Test Connection</span>
                        </span>""",
    'test conn modal btn'
)

# ─── 7. Launch Run button ──────────────────────────────────────────────────────
rep(
    """<span x-text="launching ? 'Launching...' : '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Launch'"></span>""",
    f"""<span class="flex items-center gap-2">
                      <span x-show="launching">{SPIN} Launching...</span>
                      <span x-show="!launching">{PLAY} Launch Run</span>
                    </span>""",
    'launch btn'
)

# ─── 8. Test button in connections list ───────────────────────────────────────
rep(
    """<span x-text="testingConnId===conn.id?'Testing...':'<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><line x1="11.5" y1="10.5" x2="17" y2="6.5"/><line x1="11.5" y1="13.5" x2="17" y2="17.5"/></svg> Test'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                  <span x-show="testingConnId===conn.id">{SPIN} Testing...</span>
                  <span x-show="testingConnId!==conn.id">{CONN} Test</span>
                </span>""",
    'test conn list btn'
)

# ─── 9. Test button in connections modal ──────────────────────────────────────
rep(
    """<span x-text="testingConnModal?'Testing...':'<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><line x1="11.5" y1="10.5" x2="17" y2="6.5"/><line x1="11.5" y1="13.5" x2="17" y2="17.5"/></svg> Test'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                  <span x-show="testingConnModal">{SPIN} Testing...</span>
                  <span x-show="!testingConnModal">{CONN} Test</span>
                </span>""",
    'test conn modal2 btn'
)

# ─── 10. Validate API key button (OpenAI) ─────────────────────────────────────
rep(
    """<span x-text="validatingKey?'<span class="flex items-center gap-1.5"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Validating...</span>':'✓ Test Connection'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                <span x-show="validatingKey">{SPIN} Validating...</span>
                <span x-show="!validatingKey">{CHK} Test API Key</span>
              </span>""",
    'validate openai key btn'
)

# ─── 11. Validate API key button (Azure) ──────────────────────────────────────
rep(
    """<span x-text="validatingKey?'<span class="flex items-center gap-1.5"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Testing...</span>':'✓ Test Connection'"></span>""",
    f"""<span class="flex items-center gap-1.5">
                  <span x-show="validatingKey">{SPIN} Testing...</span>
                  <span x-show="!validatingKey">{CHK} Test Azure Key</span>
                </span>""",
    'validate azure key btn'
)

# ─── 12. Suggest fields spinner (any remaining) ───────────────────────────────
rep("Suggesting...", "Suggesting...", 'suggesting noop')  # already handled above

# ─── 13. "New Run" header button still has SVG-wrapped span ──────────────────
# Check if it got double-wrapped
rep(
    '<span class="flex items-center gap-1.5"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>New Run</span>',
    f'{PLUS} New Run',
    'new run btn dedup'
)

print(f'\nTotal substitutions: {count}')
with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Done — static/app.html updated.')
