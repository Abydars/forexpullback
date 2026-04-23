from nicegui import ui
from app.core.config import cfg
from app.mt5_client.client import mt5_client
from app.mt5_client.symbol_resolver import SymbolResolver

resolver = SymbolResolver(mt5_client)

def render_symbols_tab():
    symbols = cfg.get('symbols', ['XAUUSD', 'EURUSD'])
    
    with ui.row().classes('w-full items-center gap-2 mb-4'):
        new_sym = ui.input('ADD SYMBOL').classes('flex-grow text-xs').props('dense outlined dark')
        def add_sym():
            if new_sym.value and new_sym.value not in symbols:
                symbols.append(new_sym.value.upper())
                cfg.set('symbols', symbols)
                new_sym.value = ''
                chips_container.refresh()
        ui.button('ADD', on_click=add_sym).props('outline size=sm color=white').classes('h-[40px]')
        
    @ui.refreshable
    def chips_container():
        with ui.row().classes('w-full gap-2 flex-wrap'):
            for sym in symbols:
                with ui.row().classes('items-center gap-2 p-2 bg-[#161b22] border border-[#30363d]'):
                    ui.label(sym).classes('font-mono text-xs text-[#c9d1d9] font-bold')
                    resolved = resolver._cache.get(sym)
                    if resolved:
                        ui.label(f"→ {resolved}").classes('text-[#3fb950] text-[10px]')
                    elif resolver._all_symbols:
                        ui.label("✗ NOT FOUND").classes('text-[#f85149] text-[10px]')
                    else:
                        ui.label("? PENDING").classes('text-[#8b949e] text-[10px]')
                        
                    def delete_sym(s=sym):
                        symbols.remove(s)
                        cfg.set('symbols', symbols)
                        chips_container.refresh()
                    ui.button(icon='close', on_click=delete_sym).props('flat size=xs round color=white').classes('ml-2')
                        
    chips_container()
    
    async def resolve_all():
        await resolver.resolve_many(symbols)
        chips_container.refresh()
        
    with ui.row().classes('mt-4 gap-2'):
        ui.button('RESOLVE ALL', on_click=resolve_all).props('outline size=sm color=white')
        ui.button('CLEAR ALL', on_click=lambda: (symbols.clear(), cfg.set('symbols', []), chips_container.refresh())).props('outline size=sm color=red')
