from nicegui import ui
from app.core.config import cfg
from app.mt5_client.client import mt5_client
from app.mt5_client.symbol_resolver import SymbolResolver

resolver = SymbolResolver(mt5_client)

def render_symbols_tab():
    symbols = cfg.get('symbols', ['XAUUSD', 'EURUSD'])
    
    with ui.row().classes('w-full items-center gap-2 mb-4'):
        new_sym = ui.input('Add Symbol').classes('flex-grow')
        def add_sym():
            if new_sym.value and new_sym.value not in symbols:
                symbols.append(new_sym.value)
                cfg.set('symbols', symbols)
                new_sym.value = ''
                chips_container.refresh()
        ui.button('Add', on_click=add_sym)
        
    @ui.refreshable
    def chips_container():
        with ui.row().classes('w-full gap-2 flex-wrap'):
            for sym in symbols:
                with ui.card().classes('p-2 bg-slate-800'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(sym).classes('font-mono text-sm')
                        resolved = resolver._cache.get(sym)
                        if resolved:
                            ui.label(f"→ {resolved} ✓").classes('text-emerald-400 text-sm')
                        elif resolver._all_symbols:
                            ui.label("✗ not found").classes('text-rose-400 text-sm')
                        else:
                            ui.label("? pending").classes('text-slate-400 text-sm')
                            
                        def delete_sym(s=sym):
                            symbols.remove(s)
                            cfg.set('symbols', symbols)
                            chips_container.refresh()
                        ui.button(icon='close', on_click=delete_sym).props('flat size=sm round')
                        
    chips_container()
    
    async def resolve_all():
        await resolver.resolve_many(symbols)
        chips_container.refresh()
        
    with ui.row().classes('mt-4 gap-2'):
        ui.button('Resolve All', on_click=resolve_all).classes('bg-blue-600')
        ui.button('Clear', on_click=lambda: (symbols.clear(), cfg.set('symbols', []), chips_container.refresh())).classes('bg-rose-600')
