"""Launcher — run: python run_bot.py  (from this directory)"""
from dotenv import load_dotenv
load_dotenv()  # Load .env file

from bot.main import main
if __name__ == "__main__":
    main()
