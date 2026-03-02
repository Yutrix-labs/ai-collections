"""
Transcript aggregator with sentiment and topic detection.
"""

import time
from typing import List, Dict
from app.utils.redis_client import (
    redis_client,
    get_sentiment_key,
    get_topics_seen_key,
    get_last_sentiment_key
)
from app.services.ai_insights_engine import trigger_insight_generation


def classify_sentiment(text: str) -> str:
    """
    Simple rule-based sentiment classification.
    In production, use Deepgram's built-in sentiment or a local ML model.
    """
    text_lower = text.lower()

    # Negative indicators
    negative_words = ['cannot', 'can\'t', 'won\'t', 'don\'t', 'never', 'no', 'not',
                      'problem', 'issue', 'difficult', 'hard', 'impossible', 'angry',
                      'frustrated', 'upset']

    # Positive indicators
    positive_words = ['yes', 'okay', 'sure', 'will', 'can', 'able', 'help',
                     'thank', 'appreciate', 'good', 'great', 'understand',
                     'agree', 'reasonable']

    negative_count = sum(1 for word in negative_words if word in text_lower)
    positive_count = sum(1 for word in positive_words if word in text_lower)

    if positive_count > negative_count:
        return "positive"
    elif negative_count > positive_count:
        return "negative"
    else:
        return "neutral"


def detect_topics(text: str) -> List[str]:
    """
    Rule-based keyword matching for fast topic detection.
    """
    topics = []
    text_lower = text.lower()

    # Payment history
    if any(kw in text_lower for kw in ['paid', 'payment', 'already paid', 'sent money', 'transferred']):
        topics.append('payment_history')

    # Bounce
    if any(kw in text_lower for kw in ['bounce', 'ecs failed', 'auto-debit failed', 'returned']):
        topics.append('bounce')

    # Charges
    if any(kw in text_lower for kw in ['penalty', 'charges', 'fee', 'extra amount', 'why so much']):
        topics.append('charges')

    # Settlement
    if any(kw in text_lower for kw in ['settle', 'one-time', 'lump sum', 'close the loan']):
        topics.append('settlement')

    # Hardship
    if any(kw in text_lower for kw in ['lost job', 'medical', 'hospital', 'salary cut', 'business loss']):
        topics.append('hardship')

    # Legal
    if any(kw in text_lower for kw in ['legal', 'lawyer', 'court', 'consumer forum', 'ombudsman']):
        topics.append('legal')

    # Dispute
    if any(kw in text_lower for kw in ['wrong amount', 'not my loan', 'fraud', 'already closed']):
        topics.append('dispute')

    return topics


async def update_sentiment_timeline(call_id: str, utterance: Dict):
    """Update sentiment state in Redis."""
    if utterance.get('speaker') == 'customer':
        sentiment = utterance.get('sentiment', 'neutral')
        sentiment_key = get_sentiment_key(call_id)

        # Store current sentiment state
        sentiment_state = {
            'latest': sentiment,
            'timestamp': time.time()
        }
        await redis_client.set(sentiment_key, sentiment_state, ex=1800)


async def is_topic_surfaced(call_id: str, topic: str) -> bool:
    """Check if topic was already surfaced (cooldown: 30 seconds)."""
    topics_key = get_topics_seen_key(call_id)

    # Check if topic is in set
    exists = await redis_client.sismember(topics_key, topic)

    if exists:
        # Check timestamp (we store topic:timestamp)
        # For simplicity, we'll just use a 30-second cooldown
        return True

    # Add topic to set
    await redis_client.sadd(topics_key, topic)
    await redis_client.expire(topics_key, 1800)  # 30 min TTL

    return False


async def trigger_data_surface(call_id: str, topic: str, utterance: Dict):
    """
    Trigger data surfacing for detected topic.
    In production, this would fetch relevant data from database and publish via WebSocket.
    """
    print(f"Data surface triggered for call {call_id}, topic: {topic}")

    # Example: fetch payment history, bounce records, etc.
    # Then publish via connection_manager.broadcast_data_surface()


async def should_trigger_llm(call_id: str, utterance: Dict, utterance_count: int) -> bool:
    """Check if we should invoke the AI Insights Engine."""

    # Trigger every 3 new customer utterances
    if utterance.get('speaker') == 'customer' and utterance_count % 3 == 0:
        return True

    # Trigger on sentiment shift
    if utterance.get('speaker') == 'customer':
        last_sentiment_key = get_last_sentiment_key(call_id)
        prev_sentiment = await redis_client.get(last_sentiment_key)
        current_sentiment = utterance.get('sentiment')

        if prev_sentiment and prev_sentiment != current_sentiment:
            await redis_client.set(last_sentiment_key, current_sentiment)
            return True

        if not prev_sentiment:
            await redis_client.set(last_sentiment_key, current_sentiment)

    return False


async def process_utterance(call_id: str, utterance: Dict, utterance_count: int = 0):
    """
    Process a single utterance.
    Called by the transcript worker.
    """

    # 1. Assign sentiment (if not already present)
    if not utterance.get('sentiment'):
        utterance['sentiment'] = classify_sentiment(utterance.get('text', ''))

    # 2. Update sentiment timeline in Redis
    await update_sentiment_timeline(call_id, utterance)

    # 3. Topic detection (only for customer utterances)
    if utterance.get('speaker') == 'customer':
        topics = detect_topics(utterance.get('text', ''))
        for topic in topics:
            if not await is_topic_surfaced(call_id, topic):
                await trigger_data_surface(call_id, topic, utterance)

    # 4. Check LLM trigger conditions
    if await should_trigger_llm(call_id, utterance, utterance_count):
        # Fetch recent transcript window (would fetch from Redis in production)
        transcript_window = [utterance]  # Simplified
        await trigger_insight_generation(call_id, trigger='utterance_batch', transcript_window=transcript_window)

    return utterance
