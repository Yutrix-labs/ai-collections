"""
AI Insights Engine with Claude Sonnet 4 integration.
"""

import json
import uuid
import time
from typing import List, Dict, Any
from anthropic import AsyncAnthropic
from app.config import settings
from app.utils.redis_client import (
    redis_client,
    get_profile_key,
    get_insights_stream_key,
    get_insight_jobs_stream_key,
    get_rate_limit_key
)
from app.utils.prompt_builder import build_llm_prompt


# Initialize Claude client
claude_client = AsyncAnthropic(api_key=settings.claude_api_key) if settings.claude_api_key else None


async def get_customer_profile(call_id: str) -> Dict:
    """Fetch cached customer profile from Redis."""
    profile_key = get_profile_key(call_id)
    profile = await redis_client.get_json(profile_key)

    if not profile:
        # In production, fetch from database
        # For now, return empty structure
        profile = {
            "customer": {},
            "loan": {},
            "additional": {},
            "payment_history": [],
            "active_policies": {}
        }

    return profile


async def get_previous_insights(call_id: str) -> List[Dict]:
    """Get previous insights from Redis stream."""
    insights_stream = get_insights_stream_key(call_id)

    try:
        messages = await redis_client.client.xread({insights_stream: "0"}, count=100)

        insights = []
        if messages:
            for stream, msg_list in messages:
                for msg_id, data in msg_list:
                    insight = {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                             for k, v in data.items()}
                    insights.append(insight)

        return insights
    except:
        return []


async def call_claude_api(prompt: str) -> str:
    """Call Claude Sonnet 4 API."""
    if not claude_client:
        # Return mock response for development
        return json.dumps([
            {
                "type": "suggestion",
                "text": "Consider offering a restructured payment plan",
                "priority": "high",
                "reasoning": "Customer expressed willingness to pay but needs flexibility"
            }
        ])

    try:
        response = await claude_client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            system=[
                {
                    "type": "text",
                    "text": prompt,
                    "cache_control": {"type": "ephemeral"}  # Cache customer profile
                }
            ],
            messages=[
                {"role": "user", "content": "Generate insights for this conversation."}
            ],
        )

        return response.content[0].text

    except Exception as e:
        print(f"Error calling Claude API: {e}")
        return "[]"


def parse_insight_response(response: str) -> List[Dict]:
    """Parse JSON response from LLM."""
    try:
        # Try to extract JSON from response
        # Claude might wrap JSON in markdown code blocks
        response = response.strip()

        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        if response.startswith("```"):
            response = response[3:]  # Remove ```
        if response.endswith("```"):
            response = response[:-3]  # Remove trailing ```

        response = response.strip()
        insights = json.loads(response)

        if not isinstance(insights, list):
            return []

        return insights

    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        print(f"Response: {response}")
        return []


async def check_rate_limit(call_id: str, insight_type: str) -> bool:
    """Check if insight type is within rate limit."""
    rate_limits = {
        'sentiment': settings.rate_limit_sentiment,
        'intent': settings.rate_limit_intent,
        'policy': settings.rate_limit_policy,
        'suggestion': 0,  # No limit
        'alert': 0,  # No limit
    }

    limit = rate_limits.get(insight_type, 0)
    if limit == 0:
        return True

    rate_limit_key = get_rate_limit_key(call_id, insight_type)
    last_time = await redis_client.get(rate_limit_key)

    if last_time:
        elapsed = time.time() - float(last_time)
        if elapsed < limit:
            return False

    await redis_client.set(rate_limit_key, str(time.time()))
    return True


def format_time(call_elapsed_ms: int) -> str:
    """Format time as MM:SS."""
    seconds = call_elapsed_ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


async def generate_insights(call_id: str, trigger: str, transcript_window: List[Dict]) -> List[Dict]:
    """Generate insights using Claude Sonnet 4."""

    # 1. Fetch customer profile
    profile = await get_customer_profile(call_id)

    # 2. Get previous insights
    previous_insights = await get_previous_insights(call_id)

    # 3. Build LLM prompt
    prompt = build_llm_prompt(profile, transcript_window, previous_insights)

    # 4. Call Claude API
    response = await call_claude_api(prompt)

    # 5. Parse response
    insights = parse_insight_response(response)

    # 6. Filter by rate limits and publish
    published = []
    for insight in insights:
        insight_type = insight.get('type', '')

        # Check rate limit
        if not await check_rate_limit(call_id, insight_type):
            continue

        # Get call elapsed time (use last utterance time)
        call_elapsed_ms = 0
        if transcript_window:
            last_utterance = transcript_window[-1]
            call_elapsed_ms = last_utterance.get('call_elapsed_ms', 0)

        # Build insight record
        insight_record = {
            'insight_id': str(uuid.uuid4()),
            'type': insight_type,
            'text': insight.get('text', ''),
            'priority': insight.get('priority', 'medium'),
            'source_layer': 'llm',
            'call_elapsed_ms': call_elapsed_ms,
            'time': format_time(call_elapsed_ms),
            'reasoning': insight.get('reasoning', ''),
            'related_utterance_ids': []
        }

        # Publish to insights stream
        insights_stream = get_insights_stream_key(call_id)
        await redis_client.xadd(insights_stream, insight_record)

        published.append(insight_record)

    return published


async def trigger_insight_generation(call_id: str, trigger: str, transcript_window: List[Dict] = None):
    """Trigger insight generation by adding job to queue."""
    if transcript_window is None:
        transcript_window = []

    job_data = {
        'trigger': trigger,
        'transcript_window': json.dumps(transcript_window),
        'timestamp': str(time.time())
    }

    jobs_stream = get_insight_jobs_stream_key(call_id)
    await redis_client.xadd(jobs_stream, job_data)
