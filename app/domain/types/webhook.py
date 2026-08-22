from typing import Union

from .receipt import ReceiptEvent
from .subscription import SubscriptionEvent


WebhookEvent = Union[ReceiptEvent, SubscriptionEvent]
