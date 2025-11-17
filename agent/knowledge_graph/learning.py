"""
Mem0 Learning Pipeline

Automatically learns from user interactions and stores memories in Mem0.
Replaces the custom KG learning pipeline with Mem0's automatic learning.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from agent.knowledge_graph.client import mem0_wrapper
from agent.knowledge_graph.config import (
    create_preference_memory,
    create_context_memory,
    create_awareness_memory,
)

logger = logging.getLogger(__name__)


def queue_conversation_to_mem0(
    user_id: str,
    business_id: str,
    conversation_id: str,
    messages: List[Dict[str, Any]],
    project_id: Optional[str] = None
):
    """Queue conversation for Mem0 learning (non-blocking)"""
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If loop is running, create task
            asyncio.create_task(
                _add_conversation_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    conversation_id=conversation_id,
                    messages=messages,
                    project_id=project_id
                )
            )
        else:
            # If loop not running, schedule for later
            loop.run_until_complete(
                _add_conversation_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    conversation_id=conversation_id,
                    messages=messages,
                    project_id=project_id
                )
            )
    except Exception as e:
        logger.debug(f"Failed to queue conversation to Mem0: {e}")


async def _add_conversation_to_mem0(
    user_id: str,
    business_id: str,
    conversation_id: str,
    messages: List[Dict[str, Any]],
    project_id: Optional[str] = None
):
    """Add conversation to Mem0 for automatic learning"""
    try:
        # Format messages for Mem0
        mem0_messages = []
        for msg in messages:
            msg_type = msg.get("type", "")
            content = msg.get("content", "")
            
            if content:
                role = "user" if msg_type.lower() in ["user", "human"] else "assistant"
                mem0_messages.append({
                    "role": role,
                    "content": content,
                    "metadata": {
                        "conversation_id": conversation_id,
                        "project_id": project_id,
                        "source": "conversation",
                    }
                })
        
        if mem0_messages:
            # Mem0 automatically extracts entities, relationships, and patterns
            await mem0_wrapper.add_memory(
                user_id=user_id,
                business_id=business_id,
                messages=mem0_messages,
                metadata={
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "source": "conversation",
                    "type": "conversation_pattern",
                }
            )
            logger.debug(f"Added conversation {conversation_id} to Mem0")
            
    except Exception as e:
        logger.error(f"Failed to add conversation to Mem0: {e}")


def queue_user_context_to_mem0(
    user_id: str,
    business_id: str,
    document_id: str,
    content: str
):
    """Queue user context document for Mem0 learning (non-blocking)"""
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            asyncio.create_task(
                _add_user_context_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    document_id=document_id,
                    content=content
                )
            )
        else:
            loop.run_until_complete(
                _add_user_context_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    document_id=document_id,
                    content=content
                )
            )
    except Exception as e:
        logger.debug(f"Failed to queue user context to Mem0: {e}")


async def _add_user_context_to_mem0(
    user_id: str,
    business_id: str,
    document_id: str,
    content: str
):
    """Add user context to Mem0"""
    try:
        messages = [create_context_memory(content, document_id=document_id, source="explicit")]
        
        await mem0_wrapper.add_memory(
            user_id=user_id,
            business_id=business_id,
            messages=messages,
            metadata={
                "document_id": document_id,
                "source": "explicit",
                "type": "user_context",
            }
        )
        logger.debug(f"Added user context document {document_id} to Mem0")
        
    except Exception as e:
        logger.error(f"Failed to add user context to Mem0: {e}")


def queue_preference_to_mem0(
    user_id: str,
    business_id: str,
    preferences: Dict[str, Any]
):
    """Queue preference update for Mem0 learning (non-blocking)"""
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            asyncio.create_task(
                _add_preferences_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    preferences=preferences
                )
            )
        else:
            loop.run_until_complete(
                _add_preferences_to_mem0(
                    user_id=user_id,
                    business_id=business_id,
                    preferences=preferences
                )
            )
    except Exception as e:
        logger.debug(f"Failed to queue preferences to Mem0: {e}")


async def _add_preferences_to_mem0(
    user_id: str,
    business_id: str,
    preferences: Dict[str, Any]
):
    """Add preferences to Mem0"""
    try:
        messages = []
        for pref_type, pref_value in preferences.items():
            if pref_type in ["responseTone", "domainFocus", "rememberLongTermContext", "showAgentInternals"]:
                messages.append(create_preference_memory(pref_type, pref_value))
        
        if messages:
            await mem0_wrapper.add_memory(
                user_id=user_id,
                business_id=business_id,
                messages=messages,
                metadata={"source": "explicit", "type": "user_preference"}
            )
            logger.debug(f"Added preferences to Mem0 for user {user_id}")
            
    except Exception as e:
        logger.error(f"Failed to add preferences to Mem0: {e}")

