"""
FIXED: run.py with proper error handling and gunicorn compatibility

Key improvements:
1. Eventlet monkey-patching happens AFTER Flask is imported (safer)
2. Explicit app creation with error handling
3. Better error messages if something fails
4. Gunicorn-compatible WSGI export
"""

import os
import sys
import logging

# Configure logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    logger.info("Starting Mzizibet application initialization...")
    
    # Import app factory
    from app import create_app
    
    # Get environment config
    config_name = os.environ.get("FLASK_ENV", "development")
    logger.info(f"Using configuration: {config_name}")
    
    # Create Flask app
    app = create_app(config_name)
    logger.info("✓ Flask app created successfully")
    
    # NOW do eventlet patching if needed
    # This happens AFTER Flask is loaded, which is safer
    if os.environ.get("USE_EVENTLET", "false").lower() == "true":
        try:
            import eventlet
            eventlet.monkey_patch()
            logger.info("✓ Eventlet monkey-patching applied")
        except ImportError:
            logger.warning("⚠️  Eventlet not installed, skipping monkey-patching")
    
    logger.info("✓ Mzizibet application ready for gunicorn")

except ImportError as e:
    logger.critical(f"❌ Import error during app initialization: {e}")
    logger.critical(f"Python path: {sys.path}")
    sys.exit(1)

except Exception as e:
    logger.critical(f"❌ Unexpected error during app initialization: {e}")
    import traceback
    logger.critical(traceback.format_exc())
    sys.exit(1)


# Entry point for gunicorn
if __name__ == "__main__":
    # Local development only
    logger.warning("⚠️  Running in development mode. Use gunicorn for production.")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
