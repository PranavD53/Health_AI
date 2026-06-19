import os
import httpx
import json

async def call_llm(system_prompt: str, user_prompt: str, require_json: bool = True) -> dict:
    """
    Calls Groq API as primary, with HuggingFace fallback (omitted here for brevity, 
    but structured to be easy to extend).
    """
    groq_key = os.getenv("GROQ_API_KEY", "")
    
    if not groq_key or groq_key.startswith("your_groq"):
        # Fallback to dummy data if no key, just for development
        print("Warning: Missing Groq Key. Returning dummy LLM response.")
        if require_json:
            return {"severity": "MODERATE", "symptom_category": "OTHER", "reasoning": "Dummy response", "patient_facing_message": "Dummy response"}
        return {"content": "Dummy response"}

    async with httpx.AsyncClient() as client:
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        
        if require_json:
            payload["response_format"] = {"type": "json_object"}

        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10.0
        )

        if response.status_code == 200:
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            if require_json:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {}
            return {"content": content}
        else:
            print(f"LLM API Error: {response.text}")
            return {}
