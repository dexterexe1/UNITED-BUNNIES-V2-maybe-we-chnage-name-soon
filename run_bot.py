"""Launcher — run: python run_bot.py  (from this directory)"""
# Load .env for local development (skip if not available on server)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, using system env vars

from bot.main import main
if __name__ == "__main__":
    main()
