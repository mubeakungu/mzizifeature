"""
FIXED: app/__init__.py with defensive imports and error handling

Key improvements:
1. Try-catch blocks around optional imports
2. Better error messages if imports fail
3. Graceful degradation if some features aren't available
4. Clear logging of initialization steps
"""

import logging
from flask import Flask, redirect, url_for
from flask_login import current_user

logger = logging.getLogger(__name__)

# Import configuration
try:
    from config import config
except ImportError as e:
    logger.error(f"Failed to import config module: {e}")
    raise

# Import extensions
try:
    from app.extensions import db, login_manager, migrate, bcrypt, socketio
except ImportError as e:
    logger.error(f"Failed to import extensions: {e}")
    raise


def _seed_catalog_if_empty():
    """Populate game categories + catalog entries the first time the app
    boots against an empty database."""
    try:
        import seed_fixed
        seed_fixed.run()
        logger.info("✓ Game catalog seeding completed")
    except Exception as e:
        logger.warning(f"⚠️  Could not seed catalog: {e}")


def _update_game_thumbnails():
    """Update existing games with thumbnail URLs on startup.
    NOTE: This is handled by seed_fixed.py's run() now."""
    pass  # No longer needed - seed_fixed.py handles it


def _sync_sports_if_needed():
    """Sync sports fixtures on startup if needed."""
    try:
        from sync_sports_fixed import sync_upcoming_fixtures
        sync_upcoming_fixtures()
        logger.info("✓ Sports fixtures synced on startup")
    except Exception as e:
        logger.warning(f"⚠️  Initial sports sync failed: {e}")


# =====================================================
# SCHEDULER SETUP
# =====================================================

def init_scheduler(app):
    """Initialize APScheduler for background sports syncing."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        scheduler = BackgroundScheduler()

        # Configure scheduler
        scheduler.configure(
            jobstores={'default': {'type': 'memory'}},
            executors={'default': {'type': 'threadpool', 'max_workers': 2}},
            job_defaults={'coalesce': True, 'max_instances': 1}
        )

        # Job 1: Sync live scores every 5 minutes
        scheduler.add_job(
            func=sync_live_scores_job,
            args=(app,),
            trigger=IntervalTrigger(minutes=5),
            id='sync_live_sports',
            name='Sync live sports data',
            replace_existing=True
        )

        # Job 2: Sync upcoming fixtures every 6 hours
        scheduler.add_job(
            func=sync_upcoming_fixtures_job,
            args=(app,),
            trigger=IntervalTrigger(hours=6),
            id='sync_upcoming_sports',
            name='Sync upcoming sports fixtures',
            replace_existing=True
        )

        scheduler.start()
        logger.info("=" * 50)
        logger.info("✓ Background Scheduler Started")
        logger.info("  • Live scores: Every 5 minutes")
        logger.info("  • Upcoming fixtures: Every 6 hours")
        logger.info("=" * 50)
        
        return scheduler
    except ImportError:
        logger.warning("⚠️  APScheduler not available, background jobs disabled")
        return None
    except Exception as e:
        logger.error(f"❌ Error initializing scheduler: {e}")
        return None


def sync_live_scores_job(app):
    """Background job: Sync live sports scores."""
    with app.app_context():
        try:
            from sync_sports_fixed import sync_live_scores
            result = sync_live_scores()
            if result:
                logger.info("✓ Live scores synced successfully")
            return result
        except Exception as e:
            logger.error(f"❌ Error syncing live scores: {e}")
            return False


def sync_upcoming_fixtures_job(app):
    """Background job: Sync upcoming sports fixtures."""
    with app.app_context():
        try:
            from sync_sports_fixed import sync_upcoming_fixtures
            result = sync_upcoming_fixtures()
            if result:
                logger.info("✓ Upcoming fixtures synced successfully")
            return result
        except Exception as e:
            logger.error(f"❌ Error syncing upcoming fixtures: {e}")
            return False


# =====================================================
# CREATE APP FUNCTION
# =====================================================

def create_app(config_name="development"):
    """Application factory with error handling"""
    
    logger.info(f"Creating Flask app with config: {config_name}")
    
    try:
        app = Flask(__name__)
        app.config.from_object(config[config_name])
        logger.info("✓ Flask app instance created")
    except Exception as e:
        logger.error(f"❌ Failed to create Flask app: {e}")
        raise

    # Initialize extensions
    try:
        db.init_app(app)
        login_manager.init_app(app)
        migrate.init_app(app, db)
        bcrypt.init_app(app)
        socketio.init_app(app, cors_allowed_origins="*")
        logger.info("✓ All extensions initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize extensions: {e}")
        raise

    login_manager.login_view = "auth.login"

    # Import all model modules so SQLAlchemy knows about all tables
    try:
        from app.models.user import User
        from app.models.wallet import Wallet, Transaction  # noqa: F401
        from app.models.casino import GameCategory, Game, CasinoRound  # noqa: F401
        from app.models.sports import (  # noqa: F401
            SportsEvent, SportsMarket, SportsSelection, BetSlip, BetSlipLeg, Bet,
        )
        from app.models.crash import CrashGame, CrashBet, CrashStats  # noqa: F401
        from app.models.aviatorcrash_models import (  # noqa: F401
            AviatorCrashRound, AviatorCrashBet, AviatorCrashStats,
        )
        from app.routes.hilocard_blueprint import HiLoRound, HiloBet, HiLoStats  # noqa: F401
        from app.routes.plinkomzizi_blueprint import PlinkoRound, PlinkoBet, PlinkoStats  # noqa: F401
        logger.info("✓ All models imported successfully")
    except Exception as e:
        logger.error(f"❌ Failed to import models: {e}")
        raise

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    try:
        from app.routes.auth import auth_bp
        from app.routes.casino import casino_bp
        from app.routes.casino_games import casino_games_bp
        from app.routes.sports import sports_bp
        from app.routes.wallet import wallet_bp
        from app.routes.admin import admin_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(casino_bp)
        app.register_blueprint(casino_games_bp, url_prefix="/api/casino")
        app.register_blueprint(sports_bp)
        app.register_blueprint(wallet_bp, url_prefix="/wallet")
        app.register_blueprint(admin_bp, url_prefix="/admin")
        
        logger.info("✓ All main blueprints registered")
    except Exception as e:
        logger.error(f"❌ Failed to register blueprints: {e}")
        raise

    # Register Socket.IO game blueprints
    try:
        from app.routes.mzizicrash_blueprint import get_mzizicrash_blueprint

        mzizicrash_bp = get_mzizicrash_blueprint(socketio, app)
        if mzizicrash_bp:
            app.register_blueprint(mzizicrash_bp)
            logger.info("✓ mzizicrash blueprint registered")
        else:
            logger.warning("⚠️  mzizicrash_blueprint returned None")
    except Exception as e:
        logger.warning(f"⚠️  Error registering mzizicrash_blueprint: {e}")

    # aviator-crash-main (Unity WebGL) now backs BOTH the old aviator and
    # jetx routes — one shared provably-fair engine, two entry URLs, so
    # existing catalog/nav links to /aviator-mzizi/ and /jetx/ keep working.
    try:
        from app.routes.aviatorcrash_blueprint import get_aviatorcrash_blueprints
        aviator_bp, jetx_bp, aviatorcrash_api_bp = get_aviatorcrash_blueprints(socketio, app)
        app.register_blueprint(aviator_bp)
        app.register_blueprint(jetx_bp)
        app.register_blueprint(aviatorcrash_api_bp)
        logger.info("✓ aviatorcrash blueprints registered (serving /aviator-mzizi/ and /jetx/)")
    except Exception as e:
        logger.warning(f"⚠️  Error registering aviatorcrash blueprints: {e}")

    try:
        from app.routes.hilocard_blueprint import get_hilocard_blueprint
        hilo_bp = get_hilocard_blueprint(socketio, app)
        if hilo_bp:
            app.register_blueprint(hilo_bp)
            logger.info("✓ hilocard blueprint registered")
        else:
            logger.warning("⚠️  hilocard_blueprint returned None")
    except Exception as e:
        logger.warning(f"⚠️  Error registering hilocard_blueprint: {e}")

    try:
        from app.routes.plinkomzizi_blueprint import get_plinkomzizi_blueprint
        plinko_bp = get_plinkomzizi_blueprint(socketio, app)
        if plinko_bp:
            app.register_blueprint(plinko_bp)
            logger.info("✓ plinkomzizi blueprint registered")
        else:
            logger.warning("⚠️  plinkomzizi_blueprint returned None")
    except Exception as e:
        logger.warning(f"⚠️  Error registering plinkomzizi_blueprint: {e}")

    # Create tables and seed data
    try:
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("✓ Database tables created")
            
            _seed_catalog_if_empty()
            _update_game_thumbnails()
            _sync_sports_if_needed()
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        # Don't raise - app can still work even if seeding fails

    @app.route("/")
    def index():
        return redirect(url_for("casino.lobby"))

    @app.context_processor
    def inject_globals():
        try:
            from app.routes.sports import get_betslip_summary
            betslip_items, betslip_total_odds = get_betslip_summary()
        except Exception as e:
            logger.warning(f"⚠️  Error getting betslip summary: {e}")
            betslip_items, betslip_total_odds = [], 0

        try:
            sidebar_crash_games = (
                Game.query.join(GameCategory)
                .filter(GameCategory.slug == "crash", Game.is_active == True)  # noqa: E712
                .order_by(Game.display_order)
                .limit(6)
                .all()
            )
        except Exception as e:
            logger.warning(f"⚠️  Error loading crash games: {e}")
            sidebar_crash_games = []

        sidebar_promotions = [
            {"icon": "📈", "title": "100% Boost Bonus", "subtitle": "First deposit up to KES 10,000"},
            {"icon": "⭐", "title": "10% Daily Cashback", "subtitle": "On crash & casino games"},
        ]

        return {
            "site_name": "Mzizibet",
            "default_showcase_games": [
                {"name": "mzizicrash", "badge": "HOT", "thumbnail_url": None},
                {"name": "Aviator", "badge": "HOT", "thumbnail_url": None},
                {"name": "JetX", "badge": "HOT", "thumbnail_url": None},
                {"name": "Mines", "badge": "POPULAR", "thumbnail_url": None},
                {"name": "Plinko", "badge": "HOT", "thumbnail_url": None},
                {"name": "European Roulette", "badge": None, "thumbnail_url": None},
            ],
            "sidebar_crash_games": sidebar_crash_games,
            "sidebar_promotions": sidebar_promotions,
            "betslip_items": betslip_items,
            "betslip_total_odds": betslip_total_odds,
        }

    # Initialize scheduler
    try:
        import os
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            app.scheduler = init_scheduler(app)
        else:
            app.scheduler = None
            logger.info("⚠️  Scheduler disabled (Flask debug mode)")
    except Exception as e:
        logger.warning(f"⚠️  Scheduler initialization failed: {e}")
        app.scheduler = None

    logger.info("✓ Application initialization complete")
    return app
