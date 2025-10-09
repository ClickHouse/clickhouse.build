import json
import logging

from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """
You are a code quality validator. Your job is to approve or reject code before it's written to a file.

**Validation Rules:**

1. **Type Safety (CRITICAL)**
   - ❌ REJECT if code explicitly declares `any` type (e.g., `const foo: any`, `function bar(x: any)`)
   - ❌ REJECT if code explicitly declares `unknown` type without proper type guards
   - ✅ APPROVE implicit `any` from library calls (e.g., `response.json()`, `JSON.parse()`)
   - ✅ APPROVE if developer-written types are explicit
   - Focus on what the developer explicitly writes, not library inference

2. **Backwards Compatibility (CRITICAL)**
   - ❌ REJECT if code forces ClickHouse-only without PostgreSQL fallback
   - ❌ REJECT if code removes existing PostgreSQL functionality
   - ❌ REJECT if database routing lacks proper environment checks when switching databases
   - ✅ APPROVE if PostgreSQL remains the default or existing behavior is preserved

3. **Incremental Development**
   - ✅ APPROVE incomplete implementations IF they don't break existing functionality
   - ✅ APPROVE if partial feature implementation has proper types
   - ✅ APPROVE missing error handling, logging, or polish (non-critical issues)
   - ❌ REJECT if incomplete implementation would break existing users

4. **Focus**
   - Prioritize type safety and backwards compatibility
   - Be lenient on incomplete features that don't break things
   - Be strict on changes that would break existing functionality

**Return Format:**

Return ONLY valid JSON in this exact format:
{
  "approved": true/false,
  "reason": "Brief, succinct explanation (1-2 sentences max)"
}

Examples:
{"approved": false, "reason": "Parameter 'data' explicitly typed as 'any' on line 5. Must use explicit type."}
{"approved": false, "reason": "Forces ClickHouse-only without PostgreSQL fallback, breaking existing users."}
{"approved": true, "reason": "Developer-written types are explicit. Implicit 'any' from library calls is acceptable."}
{"approved": true, "reason": "Proper TypeScript types, incomplete implementation maintains backwards compatibility."}

Be strict on type safety and breaking changes, lenient on everything else. Return valid JSON only.
"""

model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# model_id="anthropic.claude-3-5-haiku-20241022-v1:0"


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
            name="qa_code_migrator"
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
            result_str = result_str[7:]  # Remove ```json
        elif result_str.startswith("```"):
            result_str = result_str[3:]  # Remove ```
        if result_str.endswith("```"):
            result_str = result_str[:-3]  # Remove trailing ```
        result_str = result_str.strip()

        # Try to parse as JSON to validate format
        try:
            result_json = json.loads(result_str)
            if "approved" not in result_json or "reason" not in result_json:
                # Invalid format, reject
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
