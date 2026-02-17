import sys
from loguru import logger


def main():
    # Check for --paper mode
    if "--paper" in sys.argv:
        sys.argv.remove("--paper")
        from src.execution.runner import main as paper_main
        paper_main()
        return

    logger.info("Starting Analysis Engine...")
    # TODO: Initialize Message Bus (SBE Consumer)
    # TODO: Load Models


if __name__ == "__main__":
    main()
