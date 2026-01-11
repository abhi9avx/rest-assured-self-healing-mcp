import os
import requests
import json
from dataclasses import dataclass
from dotenv import load_dotenv
from src.security_utils import SecurityUtils

load_dotenv()

@dataclass
class FixSuggestion:
    explanation: str
    diff: str
    confidence: float

class GeminiClient:
    def __init__(self, api_key=None, model="gemini-2.0-flash-exp"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def get_fix_suggestion(self, failure_context, file_content, console_logs="") -> FixSuggestion:
        if not self.api_key:
            SecurityUtils.safe_print("No GEMINI_API_KEY provided. Returning mock response.")
            return self._mock_response()

        prompt = self._construct_prompt(failure_context, file_content, console_logs)
        
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            headers = {"Content-Type": "application/json"}
            params = {"key": self.api_key}
            
            response = requests.post(self.api_url, headers=headers, params=params, json=payload, timeout=60)
            if response.status_code != 200:
                SecurityUtils.safe_print(f"Gemini API Error ({response.status_code}): {response.text}")
            response.raise_for_status()
            
            return self._parse_response(response.json())
        except Exception as e:
            SecurityUtils.safe_print(f"Error calling Gemini: {e}")
            raise

    def _construct_prompt(self, failure, code, logs=""):
        prompt = f"""
You are an expert test automation engineer specializing in Java, RestAssured, and TestNG frameworks.
Your task is to analyze test failures and propose precise code fixes.

## Failure Context
- **Test Class**: {failure.test_class}
- **Test Method**: {failure.test_name}
- **Failure Type**: {failure.failure_type}
- **Error Message**: {failure.message}
- **File Path**: {failure.file_path}

## Stack Trace
```
{failure.stack_trace}
```

## Code Context
```java
{code}
```
"""
        if logs:
            prompt += f"""
## Console Logs (Recent Output)
Use these logs to identify runtime errors, variable values, or system state that isn't in the stack trace.
```text
{logs}
```
"""
        
        prompt += """
## Common Failure Patterns & Solutions

## Common Failure Patterns & Solutions

### 1. AssertionError (Status Code Mismatch)
- **Pattern**: `expected [X] but found [Y]`
- **Fix**: Update assertion to match actual API behavior
- **Example**: Change `assertEquals(500, ...)` to `assertEquals(200, ...)`

### 2. NoSuchElementException / Element Not Found
- **Pattern**: `no such element: Unable to locate element`
- **Fix**: Update locator strategy or wait for element
- **Example**: Change selector or add explicit wait

### 3. NullPointerException
- **Pattern**: `java.lang.NullPointerException`
- **Fix**: Add null checks or initialize objects
- **Example**: Add `if (obj != null)` before usage

### 4. TimeoutException
- **Pattern**: `timeout: Timed out after X seconds`
- **Fix**: Increase wait time or fix flaky locator
- **Example**: Change wait from 10 to 30 seconds

### 5. JSON Parsing / Deserialization Errors
- **Pattern**: `JsonParseException` or field mismatch
- **Fix**: Update DTO fields or JSON path
- **Example**: Rename field in DTO to match API response

## Instructions
1. **Analyze** the failure type and identify the root cause
2. **Locate** the exact line(s) causing the issue in the provided code
3. **Propose** a minimal, surgical fix (change only what's necessary)
4. **Generate** a valid unified diff patch

## Output Format
Return ONLY valid JSON (no markdown wrapping):
{{
  "explanation": "Brief explanation of the issue and fix",
  "diff": "Valid git diff in unified format",
  "confidence": 0.9
}}

### Diff Format Requirements
- Use standard unified diff format
- Include correct file paths (relative to repo root)
- Ensure line numbers are accurate
- Example:
--- a/src/test/java/com/example/Test.java
+++ b/src/test/java/com/example/Test.java
@@ -48,1 +48,1 @@
-    Assert.assertEquals(response.getStatusCode(), 500);
+    Assert.assertEquals(response.getStatusCode(), 200);

IMPORTANT: Return ONLY the JSON object. Do not wrap it in markdown code blocks.
"""

    def _parse_response(self, response_json) -> FixSuggestion:
        try:
            text = response_json['candidates'][0]['content']['parts'][0]['text']
            # Basic cleanup if the model wraps json in markdown code blocks
            clean_text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            return FixSuggestion(
                explanation=data.get("explanation", "No explanation"),
                diff=data.get("diff", ""),
                confidence=float(data.get("confidence", 0.0))
            )
        except Exception as e:
            SecurityUtils.safe_print(f"Failed to parse Gemini response: {e}. Raw text: {text}")
            return FixSuggestion("Failed to parse", "", 0.0)

    def _mock_response(self):
        # Return a dummy fix for testing without API usage
        return FixSuggestion(
            explanation="Mock fix: changing expected status code from 200 to 201",
            diff="""diff --git a/src/test/java/com/example/Test.java b/src/test/java/com/example/Test.java
index 1234567..89abcde 100644
--- a/src/test/java/com/example/Test.java
+++ b/src/test/java/com/example/Test.java
@@ -20,7 +20,7 @@
-        .statusCode(200);
+        .statusCode(201);
""",
            confidence=1.0
        )
