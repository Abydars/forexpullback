import re

with open('app/static/index.html', 'r') as f:
    content = f.read()

# Make MT5 modal smaller
content = content.replace('sm:w-[500px]', 'sm:w-[420px]')
content = content.replace('p-6 space-y-4', 'p-4 space-y-3')
content = content.replace('px-6 py-4 border-b', 'px-4 py-3 border-b')
content = content.replace('px-6 py-4 border-t', 'px-4 py-3 border-t')

# Make Config Modal smaller (sidebar + padding)
content = content.replace('md:w-[750px]', 'md:w-[680px]')
content = content.replace('md:w-48', 'md:w-36')
content = content.replace('p-8 flex-1', 'p-5 flex-1')
content = content.replace('p-6 border-b', 'p-4 border-b')
content = content.replace('px-6 py-4 text-[10px]', 'px-4 py-3 text-[9px]')

# Inputs inside modals
# Find input classes
content = content.replace('px-3 py-2', 'px-2.5 py-1.5')
content = content.replace('text-xs px-3 py-2.5', 'text-[10px] px-2.5 py-1.5')
content = content.replace('text-xs px-3 py-2', 'text-[10px] px-2.5 py-1.5')
content = content.replace('text-xs px-2.5 py-1.5', 'text-[10px] px-2.5 py-1.5')
content = content.replace('text-[10px] font-bold tracking-[0.1em]', 'text-[9px] font-bold tracking-[0.1em]')
content = content.replace('gap-1.5', 'gap-1')
content = content.replace('gap-x-6 gap-y-6', 'gap-x-4 gap-y-4')

# Save buttons
content = content.replace('px-5 py-3 bg-panel', 'px-4 py-2.5 bg-panel')
content = content.replace('px-5 py-3 bg-black/30', 'px-4 py-2.5 bg-black/30')

with open('app/static/index.html', 'w') as f:
    f.write(content)
