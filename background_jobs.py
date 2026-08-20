# Background job to sync live fixture data — matches your actual SportsEvent schema
# Run every 5 minutes via APScheduler

import requests
from datetime import datetime
from app.extensions import db
from app.models.sports import SportsEvent, SportsSelection, SportsMarket
import os
import logging

logger = logging.getLogger(__name__)

ODDS_API_KEY = os.environ.get('ODDS_API_KEY')
ODDS_API_BASE = 'https://api.the-odds-api.com/v4/sports'


def sync_live_sports_from_odds_api():
    """
    Sync live game data (scores, status) from The Odds API into SportsEvent.
    
    Maps The Odds API status to your status values:
    - scheduled → upcoming
    - inprogress → live
    - completed → finished
    
    Updates:
    - Game scores (home_score, away_score)
    - Game status (is_live, status field)
    - Current odds in SportsSelection
    
    Schedule: Every 5 minutes for live updates
    """
    
    try:
        sports_to_sync = ['football', 'basketball', 'tennis', 'rugby']
        total_updated = 0
        
        for sport in sports_to_sync:
            logger.info(f"[Odds API] Syncing {sport} live data...")
            
            try:
                # Fetch from The Odds API
                url = f"{ODDS_API_BASE}/{sport}/events"
                params = {
                    'apiKey': ODDS_API_KEY,
                    'regions': 'uk',
                    'markets': 'h2h',
                }
                
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                events_from_api = response.json().get('events', [])
                
                logger.info(f"  → Received {len(events_from_api)} {sport} events")
                
                for api_event in events_from_api:
                    try:
                        external_id = api_event.get('id')
                        
                        # Find existing SportsEvent by external_id
                        event = SportsEvent.query.filter_by(external_id=external_id).first()
                        
                        if not event:
                            # New event — create it
                            event = SportsEvent(
                                external_id=external_id,
                                sport=sport.capitalize()
                            )
                            db.session.add(event)
                        
                        # --- UPDATE LIVE DATA ---
                        
                        # 1. Map API status to your status field
                        api_status = api_event.get('status', 'scheduled').lower()
                        status_map = {
                            'scheduled': 'upcoming',
                            'inprogress': 'live',
                            'completed': 'finished',
                            'cancelled': 'postponed'
                        }
                        event.status = status_map.get(api_status, 'upcoming')
                        event.is_live = (event.status == 'live')
                        
                        # 2. Extract teams
                        event.home_team = api_event.get('home_team', 'Unknown')
                        event.away_team = api_event.get('away_team', 'Unknown')
                        
                        # 3. Event time (when match starts/started)
                        commence_time = api_event.get('commence_time', '')
                        if commence_time:
                            commence_time = commence_time.replace('Z', '+00:00')
                            event.event_time = datetime.fromisoformat(commence_time)
                        
                        # 4. LIVE SCORES (critical for display)
                        scores = api_event.get('scores')
                        if scores and len(scores) >= 2:
                            event.home_score = scores[0].get('score')
                            event.away_score = scores[1].get('score')
                        
                        # 5. Set external_id if not already set
                        if not event.external_id:
                            event.external_id = external_id
                        
                        # 6. Update timestamp
                        event.updated_at = datetime.utcnow()
                        
                        # 7. UPDATE ODDS in SportsSelection
                        # (This assumes markets/selections already exist)
                        bookmakers = api_event.get('bookmakers', [])
                        if bookmakers:
                            for bookmaker in bookmakers:
                                markets = bookmaker.get('markets', [])
                                for market_data in markets:
                                    if market_data.get('key') == 'h2h':
                                        # Find or create market (e.g., "1x2")
                                        market = SportsMarket.query.filter_by(
                                            event_id=event.id,
                                            name='1x2'
                                        ).first()
                                        
                                        if not market:
                                            market = SportsMarket(
                                                event_id=event.id,
                                                name='1x2'
                                            )
                                            db.session.add(market)
                                            db.session.flush()
                                        
                                        # Update selection odds
                                        outcomes = market_data.get('outcomes', [])
                                        for outcome in outcomes:
                                            outcome_name = outcome.get('name', '')
                                            price = outcome.get('price')
                                            
                                            # Determine which selection this is
                                            if outcome_name == event.home_team:
                                                selection = SportsSelection.query.filter_by(
                                                    market_id=market.id,
                                                    name='Home'
                                                ).first()
                                                if selection:
                                                    selection.odds = price
                                            
                                            elif outcome_name == event.away_team:
                                                selection = SportsSelection.query.filter_by(
                                                    market_id=market.id,
                                                    name='Away'
                                                ).first()
                                                if selection:
                                                    selection.odds = price
                                            
                                            elif outcome_name.lower() == 'draw':
                                                selection = SportsSelection.query.filter_by(
                                                    market_id=market.id,
                                                    name='Draw'
                                                ).first()
                                                if selection:
                                                    selection.odds = price
                                        
                                        break  # Only process first h2h market
                        
                        total_updated += 1
                    
                    except Exception as e:
                        logger.warning(f"  ✗ Error processing event {api_event.get('id')}: {str(e)}")
                        continue
                
                db.session.commit()
                logger.info(f"  ✓ {sport} sync complete")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"  ✗ API error for {sport}: {str(e)}")
                db.session.rollback()
                continue
            
            except Exception as e:
                logger.error(f"  ✗ Unexpected error syncing {sport}: {str(e)}")
                db.session.rollback()
                continue
        
        logger.info(f"✓ LIVE SYNC COMPLETE — {total_updated} events updated")
        return {'status': 'success', 'events_updated': total_updated}
    
    except Exception as e:
        logger.error(f"Fatal error in sync_live_sports_from_odds_api: {str(e)}")
        return {'status': 'error', 'message': str(e)}


# ===== SCHEDULER REGISTRATION =====
#
# In your app initialization (wherever you setup APScheduler, likely app.py or __init__.py):
#
# Example:
# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.interval import IntervalTrigger
#
# def init_scheduler(app):
#     from background_jobs import sync_live_sports_from_odds_api
#     
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(
#         func=sync_live_sports_from_odds_api,
#         trigger=IntervalTrigger(minutes=5),
#         id='sync_live_sports',
#         name='Sync live sports data from Odds API',
#         replace_existing=True
#     )
#     scheduler.start()
#     return scheduler
#
# # In your main app file:
# if __name__ == '__main__':
#     scheduler = init_scheduler(app)
#     app.run()
#
# ===== MANUAL TEST =====
#
# To test the sync manually:
#
# python
# >>> from app import app
# >>> with app.app_context():
# >>>     from background_jobs import sync_live_sports_from_odds_api
# >>>     result = sync_live_sports_from_odds_api()
# >>>     print(result)
# >>>     
# >>>     # Check what was synced
# >>>     from app.models.sports import SportsEvent
# >>>     live = SportsEvent.query.filter_by(is_live=True).all()
# >>>     print(f"Live games: {len(live)}")
# >>>     for game in live:
# >>>         print(f"  {game.home_team} {game.display_score} {game.away_team}")
