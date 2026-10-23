from typing import Protocol


class CardPublisher(Protocol):
    """Future Azure DevOps/GitLab adapters require explicit authorized authentication."""

    def publish_comment(self, card_url: str, comment: str) -> str: ...
