
import logging
from typing import Any, Dict, Text, Optional
from rasa.core.brokers.broker import EventBroker
from actions.conversation_db import log_message, log_action, log_conversation_start

logger = logging.getLogger(__name__)

class SQLServerBroker(EventBroker):
    """
    Custom Event Broker that logs events to SQL Server using conversation_db.
    """

    def __init__(self, config: Dict[Text, Any] = None) -> None:
        # Check if config is provided, though we generally rely on conversation_db internal config
        logger.info("SQLServerBroker initialized")

    @classmethod
    async def from_endpoint_config(cls, broker_config: Optional["EndpointConfig"]) -> "SQLServerBroker":
        return cls(broker_config.kwargs if broker_config else {})

    def publish(self, event: Dict[Text, Any]) -> None:
        """Publish an event to the database."""
        try:
            event_type = event.get("event")
            sender_id = event.get("sender_id")
            
            if not sender_id:
                return

            if event_type == "user":
                text = event.get("text")
                parse_data = event.get("parse_data", {})
                intent = parse_data.get("intent", {}).get("name")
                
                # Default app_id
                app_id = "General"
                
                # Extract user details from metadata
                metadata = event.get("metadata", {})
                user_id = metadata.get("user_id") or metadata.get("userId")
                
                first_name = metadata.get("firstName") or metadata.get("first_name")
                last_name = metadata.get("lastName") or metadata.get("last_name")
                username = metadata.get("username") or metadata.get("userName") or metadata.get("user_name")
                
                user_name = None
                if first_name or last_name:
                    user_name = f"{first_name or ''} {last_name or ''}".strip()
                elif username:
                    user_name = username

                log_message(
                    sender_id=sender_id,
                    message_type="user",
                    text=text,
                    intent=intent,
                    app_id=app_id,
                    user_id=user_id,
                    user_name=user_name
                )
                
            elif event_type == "bot":
                text = event.get("text")
                metadata = event.get("metadata", {})
                
                log_message(
                    sender_id=sender_id,
                    message_type="bot",
                    text=text,
                    app_id="General" # TODO: Extract from metadata if available
                )
                
            elif event_type == "action":
                action_name = event.get("name")
                if action_name:
                    log_action(
                        sender_id=sender_id,
                        action_name=action_name,
                        app_id="General"
                    )
            
            # TODO: Handle other events if needed (slot, etc)

        except Exception as e:
            logger.error(f"Failed to publish event to SQL Server: {e}")

    def is_ready(self) -> bool:
        return True

    def close(self) -> None:
        pass
