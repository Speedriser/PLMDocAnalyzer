with open(r'F:\Claude-Code\Project2\plm_digitizer\static\app.html', 'r', encoding='utf-8') as f:
    content = f.read()

reps = [
    # Confidence score colors in results table
    ("r.confidence_score>=0.8?'text-green-400':r.confidence_score>=0.5?'text-yellow-400':'text-red-400'",
     "r.confidence_score>=0.8?(theme==='light'?'text-[#137333]':'text-[#81c995]'):r.confidence_score>=0.5?(theme==='light'?'text-[#b06000]':'text-[#fdd663]'):(theme==='light'?'text-[#c5221f]':'text-[#f28b82]')"),
    # Confidence score in detail panel
    ("(selectedDetail.confidence_score||0)>=0.8?'text-green-400':(selectedDetail.confidence_score||0)>=0.5?'text-yellow-400':'text-red-400'",
     "(selectedDetail.confidence_score||0)>=0.8?(theme==='light'?'text-[#137333]':'text-[#81c995]'):(selectedDetail.confidence_score||0)>=0.5?(theme==='light'?'text-[#b06000]':'text-[#fdd663]'):(theme==='light'?'text-[#c5221f]':'text-[#f28b82]')"),
    # Connection test result panel
    ("conn.test_status==='success'?'bg-green-900/20 text-green-400':'bg-red-900/20 text-red-400'",
     "conn.test_status==='success'?(theme==='light'?'bg-[#e6f4ea] text-[#137333]':'bg-[#1e3a2a] text-[#81c995]'):(theme==='light'?'bg-[#fce8e6] text-[#c5221f]':'bg-[#3a1e1e] text-[#f28b82]')"),
    # Connection test modal result
    ("connTestResultModal.success?'bg-green-900/20 text-green-400':'bg-red-900/20 text-red-400'",
     "connTestResultModal.success?(theme==='light'?'bg-[#e6f4ea] text-[#137333]':'bg-[#1e3a2a] text-[#81c995]'):(theme==='light'?'bg-[#fce8e6] text-[#c5221f]':'bg-[#3a1e1e] text-[#f28b82]')"),
    # API key validation result panels (OpenAI + Azure + Ollama share keyValidationResult)
    ("keyValidationResult.success?'bg-green-900/20 text-green-400':'bg-red-900/20 text-red-400'",
     "keyValidationResult.success?(theme==='light'?'bg-[#e6f4ea] text-[#137333]':'bg-[#1e3a2a] text-[#81c995]'):(theme==='light'?'bg-[#fce8e6] text-[#c5221f]':'bg-[#3a1e1e] text-[#f28b82]')"),
    # connTestResult pass/fail text
    ("connTestResult?.success?'text-green-400':'text-red-400'",
     "connTestResult?.success?(theme==='light'?'text-[#137333]':'text-[#81c995]'):(theme==='light'?'text-[#c5221f]':'text-[#f28b82]')"),
    # Folder error panel
    ('class="rounded-xl border border-red-800 bg-red-900/20 p-4 text-red-400 text-sm"',
     ':class="\'rounded-xl border p-4 text-sm \' + (theme===\'light\'?\'border-[#f5c6c5] bg-[#fce8e6] text-[#c5221f]\':\'border-red-800 bg-red-900/20 text-[#f28b82]\')"'),
    # Error in result detail panel
    ('class="text-xs font-semibold text-red-400 mb-1">Error',
     ':class="\'text-xs font-semibold mb-1 \' + (theme===\'light\'?\'text-[#c5221f]\':\'text-[#f28b82]\')" >Error'),
    # Error JSON block
    ('class="text-xs text-red-400 bg-red-900/20 rounded-lg p-2 overflow-x-auto"',
     ':class="\'text-xs rounded-lg p-2 overflow-x-auto \' + (theme===\'light\'?\'text-[#c5221f] bg-[#fce8e6]\':\'text-[#f28b82] bg-red-900/20\')"'),
    # Required asterisks (red * labels)
    ('class="text-red-400">*</span>',
     ':class="\'  \' + (theme===\'light\'?\'text-[#c5221f]\':\'text-[#f28b82]\')" >*</span>'),
    # Total files big number (blue)
    ('class="text-2xl font-bold text-blue-400" x-text="runSummary.total_files || 0"',
     ':class="\'text-2xl font-bold \' + (theme===\'light\'?\'text-[#202124]\':\'text-white\')" x-text="runSummary.total_files || 0"'),
    # Warning icon and AI analysis label (always yellow - ok in dark, but bad in light)
    ('class="text-yellow-400 flex-shrink-0">⚠</span>',
     ':class="\'flex-shrink-0 \' + (theme===\'light\'?\'text-[#b06000]\':\'text-[#fdd663]\')">⚠</span>'),
    ('class="text-xs font-semibold text-yellow-400 mb-1">AI Failure Analysis',
     ':class="\'text-xs font-semibold mb-1 \' + (theme===\'light\'?\'text-[#b06000]\':\'text-[#fdd663]\')">AI Failure Analysis'),
    # Active run passed/failed/skipped counters in runs page widget
    ('class="text-2xl font-bold text-green-400" x-text="activeRun.passed || 0"',
     ':class="\'text-2xl font-bold \' + (theme===\'light\'?\'text-[#137333]\':\'text-[#81c995]\')" x-text="activeRun.passed || 0"'),
    ('class="text-2xl font-bold text-red-400" x-text="activeRun.failed || 0"',
     ':class="\'text-2xl font-bold \' + (theme===\'light\'?\'text-[#c5221f]\':\'text-[#f28b82]\')" x-text="activeRun.failed || 0"'),
    # Cancel button (active run widget)
    ('class="px-3 py-1.5 bg-red-600/20 text-red-300 border border-red-600/30 rounded-lg text-xs font-medium hover:bg-red-600/30">',
     ':class="\'px-3 py-1.5 rounded-lg text-xs font-medium \' + (theme===\'light\'?\'bg-[#fce8e6] text-[#c5221f] border border-[#f5c6c5] hover:bg-[#f8d7d6]\':\'bg-red-600/20 text-[#f28b82] border border-red-600/30 hover:bg-red-600/30\')" >'),
    # Test connection green button (OpenAI)
    ('class="flex items-center gap-2 px-4 py-2.5 bg-green-600/20 text-green-400 border border-green-600/30 rounded-xl text-sm hover:bg-green-600/30 disabled:opacity-50">',
     ':class="\'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm disabled:opacity-50 \' + (theme===\'light\'?\'bg-[#e6f4ea] text-[#137333] border border-[#ceead6] hover:bg-[#d2edd9]\':\'bg-green-600/20 text-[#81c995] border border-green-600/30 hover:bg-green-600/30\')" >'),
    # Terminal cursor blink (always in dark terminal - ok)
    # Log level colors in run details (always in dark terminal panel - ok)
    # Test Conn blue buttons in Connections page
    ('class="flex-1 px-3 py-2 text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded-xl hover:bg-blue-600/30 disabled:opacity-50">',
     ':class="\'flex-1 px-3 py-2 text-xs rounded-xl disabled:opacity-50 \' + (theme===\'light\'?\'bg-[#e8f0fe] text-[#1a73e8] border border-[#c5d8fd] hover:bg-[#d2e3fc]\':\'bg-blue-600/20 text-[#8ab4f8] border border-blue-600/30 hover:bg-blue-600/30\')" >'),
    # Test conn modal blue button
    ('class="px-4 py-2.5 text-sm bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded-xl hover:bg-blue-600/30 disabled:opacity-50">',
     ':class="\'px-4 py-2.5 text-sm rounded-xl disabled:opacity-50 \' + (theme===\'light\'?\'bg-[#e8f0fe] text-[#1a73e8] border border-[#c5d8fd] hover:bg-[#d2e3fc]\':\'bg-blue-600/20 text-[#8ab4f8] border border-blue-600/30 hover:bg-blue-600/30\')" >'),
    # Delete connection button
    ('class="px-3 py-2 text-xs bg-red-600/20 text-red-400 border border-red-600/30 rounded-xl hover:bg-red-600/30">',
     ':class="\'px-3 py-2 text-xs rounded-xl \' + (theme===\'light\'?\'bg-[#fce8e6] text-[#c5221f] border border-[#f5c6c5] hover:bg-[#f8d7d6]\':\'bg-red-600/20 text-[#f28b82] border border-red-600/30 hover:bg-red-600/30\')" >'),
    # Cancel run in dashboard history (red button)
    ('class="px-2 py-1 text-xs bg-red-600/20 text-red-400 border border-red-600/30 rounded-lg hover:bg-red-600/30">',
     ':class="\'px-2 py-1 text-xs rounded-lg \' + (theme===\'light\'?\'bg-[#fce8e6] text-[#c5221f] border border-[#f5c6c5] hover:bg-[#f8d7d6]\':\'bg-red-600/20 text-[#f28b82] border border-red-600/30 hover:bg-red-600/30\')" >'),
    # Download/export green button in results
    ('class="px-3 py-1.5 text-xs bg-green-600/20 text-green-400 border border-green-600/30 rounded-lg hover:bg-green-600/30">',
     ':class="\'px-3 py-1.5 text-xs rounded-lg \' + (theme===\'light\'?\'bg-[#e6f4ea] text-[#137333] border border-[#ceead6] hover:bg-[#d2edd9]\':\'bg-green-600/20 text-[#81c995] border border-green-600/30 hover:bg-green-600/30\')" >'),
    # Download button green (history table)
    ('class="px-2 py-1 text-xs bg-green-600/20 text-green-400 border border-green-600/30 rounded-lg hover:bg-green-600/30">⬇</button>',
     ':class="\'px-2 py-1 text-xs rounded-lg \' + (theme===\'light\'?\'bg-[#e6f4ea] text-[#137333] border border-[#ceead6] hover:bg-[#d2edd9]\':\'bg-green-600/20 text-[#81c995] border border-green-600/30 hover:bg-green-600/30\')" >⬇</button>'),
    # "failed run" empty state quick actions
    ('class="flex-1 flex items-center justify-center gap-2 p-4 rounded-2xl border-2 border-dashed border-red-600/50 text-red-400 hover:bg-red-600/10 transition-all font-medium">',
     ':class="\'flex-1 flex items-center justify-center gap-2 p-4 rounded-2xl border-2 border-dashed transition-all font-medium \' + (theme===\'light\'?\'border-[#f5c6c5] text-[#c5221f] hover:bg-[#fce8e6]\':\'border-red-600/50 text-[#f28b82] hover:bg-red-600/10\')" >'),
    # "new run" empty state green
    ('class="flex-1 flex items-center justify-center gap-2 p-4 rounded-2xl border-2 border-dashed border-green-600/50 text-green-400 hover:bg-green-600/10 transition-all font-medium">',
     ':class="\'flex-1 flex items-center justify-center gap-2 p-4 rounded-2xl border-2 border-dashed transition-all font-medium \' + (theme===\'light\'?\'border-[#ceead6] text-[#137333] hover:bg-[#e6f4ea]\':\'border-green-600/50 text-[#81c995] hover:bg-green-600/10\')" >'),
    # Log level text in run detail panel (this is in a dark-bg terminal - keep but make theme-aware for the small visible ones)
    # Validate openai button (green)
    ('class="flex items-center gap-2 px-4 py-2.5 bg-green-600/20 text-green-400 border border-green-600/30 rounded-xl text-sm hover:bg-green-600/30 disabled:opacity-50"',
     ':class="\'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm disabled:opacity-50 \' + (theme===\'light\'?\'bg-[#e6f4ea] text-[#137333] border border-[#ceead6] hover:bg-[#d2edd9]\':\'bg-green-600/20 text-[#81c995] border border-green-600/30 hover:bg-green-600/30\')"'),
    # Skipped counter (yellow)
    ('class="text-2xl font-bold text-yellow-400" x-text="activeRun.skipped || 0"',
     ':class="\'text-2xl font-bold \' + (theme===\'light\'?\'text-[#b06000]\':\'text-[#fdd663]\')" x-text="activeRun.skipped || 0"'),
    # connection test green tick
    ('class="text-green-400 text-xl">✓</span>',
     ':class="(theme===\'light\'?\'text-[#137333]\':\'text-[#81c995]\') + \' text-xl\'">✓</span>'),
    # terminal cursor (always in dark bg - fine to leave)
]

total = 0
for old, new in reps:
    c = content.count(old)
    if c:
        content = content.replace(old, new)
        total += c
        print(f'  {c}x: {old[:72]}')
    else:
        print(f'  miss: {old[:72]}')

with open(r'F:\Claude-Code\Project2\plm_digitizer\static\app.html', 'w', encoding='utf-8') as f:
    f.write(content)
print(f'\nDone. {total} replacements.')
