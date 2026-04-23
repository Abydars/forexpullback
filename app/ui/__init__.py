from nicegui import ui
import asyncio

def build_layout():
    # Set pure dark theme matching the screenshot
    ui.add_head_html('''
    <style>
        body { 
            margin: 0; padding: 0; overflow: hidden; 
            background-color: #0d1117; color: #c9d1d9; 
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; 
        }
        .q-btn.q-btn--outline:before { border-color: #30363d !important; }
        .q-table__card { background: transparent !important; box-shadow: none !important; }
        .q-table th { border-bottom: 1px solid #30363d !important; font-size: 9px !important; color: #8b949e !important; }
        .q-table td { border-bottom: 1px solid #21262d !important; }
    </style>
    ''')
    
    with ui.row().classes('w-full h-screen m-0 p-2 gap-2 flex-nowrap'):
        from app.ui.dashboard import render_sidebar, render_main_panel
        
        # LEFT SIDEBAR
        with ui.column().classes('w-[320px] h-full flex-shrink-0 gap-2'):
            render_sidebar()
            
        # MAIN CONTENT
        with ui.column().classes('flex-grow h-full gap-2 overflow-hidden'):
            render_main_panel()
