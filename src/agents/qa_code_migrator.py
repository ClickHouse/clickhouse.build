import json
import logging

from strands import Agent, tool
from strands.models import BedrockModel

from ..prompts.qa_code_migrator import QA_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"


@tool
def qa_approve(file_path: str, code_content: str, purpose: str = "code review") -> str:
    """
    Validate code before writing to a file.

    Args:
        file_path: The path where the code will be written
        code_content: The code to validate
        purpose: Brief description of what this code does

    Returns:
        JSON string with {"approved": boolean, "reason": string}
    """
    try:
        bedrock_model = BedrockModel(model_id=model_id)

        prompt = f"""
Review this code that will be written to: {file_path}

Purpose: {purpose}

Code to review:
```
{code_content}
```

Validate and return JSON with approval decision and reason.
"""

        logger.info(f"QA reviewing code for: {file_path}")

        qa_agent = Agent(
            name="qa_code_migrator",
            model=bedrock_model,
            system_prompt=QA_SYSTEM_PROMPT,
            tools=[],
            callback_handler=None,
        )

        result = qa_agent(prompt)
        result_str = str(result)

        # Strip markdown code blocks if present
        result_str = result_str.strip()
        if result_str.startswith("```json"):
            result_str = result_str[7:]
        elif result_str.startswith("```"):
            result_str = result_str[3:]
        if result_str.endswith("```"):
            result_str = result_str[:-3]
        result_str = result_str.strip()

        # Try to parse as JSON to validate format
        try:
            result_json = json.loads(result_str)
            if "approved" not in result_json or "reason" not in result_json:
                logger.warning(
                    f"QA returned invalid format for {file_path}: {result_str[:200]}"
                )
                return json.dumps(
                    {
                        "approved": False,
                        "reason": "QA validator returned invalid format",
                    }
                )

            # Log the decision
            if result_json["approved"]:
                logger.info(f"✅ QA APPROVED: {file_path}")
                logger.info(f"   Reason: {result_json['reason']}")
            else:
                logger.warning(f"❌ QA REJECTED: {file_path}")
                logger.warning(f"   Reason: {result_json['reason']}")

            return json.dumps(result_json)
        except json.JSONDecodeError:
            # Not valid JSON, reject
            logger.error(
                f"QA returned invalid JSON for {file_path}: {result_str[:200]}"
            )
            return json.dumps(
                {"approved": False, "reason": "QA validator returned invalid JSON"}
            )

    except Exception as e:
        logger.error(f"Error in qa_approve: {e}")
        return json.dumps(
            {
                "approved": False,
                "reason": f"QA validation error: {str(e)}",
            }
        )
