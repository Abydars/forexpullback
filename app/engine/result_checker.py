import asyncio
from datetime import datetime, timezone

INTERVAL_MINUTES = 15

async def auto_check_results_loop():
    from app.mt5_client.client import mt5_client
    from app.ws.manager import broadcast
    from app.api.signals_routes import check_results, CheckResultsRequest

    await asyncio.sleep(INTERVAL_MINUTES * 60)

    while True:
        try:
            if mt5_client.is_connected():
                result = await check_results(CheckResultsRequest())
                updated = result.get("updated", 0)
                live_results = result.get("live_results", {})

                now_str = datetime.now(timezone.utc).isoformat()
                await broadcast({
                    "type": "signal.results_updated",
                    "updated": updated,
                    "live_results": live_results,
                    "checked_at": now_str
                })

                if updated > 0:
                    from app.db.models import Event
                    from app.db.session import AsyncSessionLocal
                    async with AsyncSessionLocal() as db:
                        db.add(Event(
                            level="INFO",
                            component="ResultChecker",
                            message=f"Auto check results: {updated} signal(s) resolved."
                        ))
                        await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ResultChecker] Error: {e}")

        await asyncio.sleep(INTERVAL_MINUTES * 60)
