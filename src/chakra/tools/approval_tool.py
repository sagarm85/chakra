import logging

logger = logging.getLogger(__name__)


class ApprovalRejected(Exception):
    def __init__(self, reason: str = ""):
        self.reason = reason
        super().__init__(f"Approval rejected: {reason}")


def prompt_approval(label: str, content: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(content)
    print(f"{'=' * 60}\n")

    while True:
        response = input("Approve? [y/n]: ").strip().lower()
        if response == "y":
            logger.info("Approval granted for: %s", label)
            return True
        elif response == "n":
            reason = input("Rejection reason (optional): ").strip()
            logger.info("Approval rejected for: %s — reason: %s", label, reason)
            raise ApprovalRejected(reason)
        else:
            print("Please enter 'y' or 'n'")
