"""Quiz Auto-Grader: upload a solved quiz and get automatic marks.

Streamlit UI + Google Gemini Flash model.
"""

import json
import os

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-flash"
MAX_FILE_MB = 10
MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
}

SYSTEM_INSTRUCTION = (
    "You are a fair and careful teacher who grades quizzes. "
    "You read a student's solved quiz (a photo or PDF) and mark every question. "
    "Never invent questions that are not in the file. "
    "Return ONLY valid JSON with no extra text and no markdown fences."
)


def get_secret(name, default=None):
    """Read a setting from Streamlit secrets first, then environment variables."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def build_prompt(marks_per_question, answer_key_text):
    """Create the grading prompt sent together with the uploaded quiz."""
    if answer_key_text.strip():
        key_part = (
            "Use this answer key as the source of truth for correct answers:\n"
            f"{answer_key_text.strip()}\n"
        )
    else:
        key_part = (
            "No answer key is provided. Work out the correct answer to each "
            "question yourself, carefully.\n"
        )

    return f"""Grade the attached quiz.

{key_part}
Rules:
1. Find every question in the file and the answer the student wrote or selected.
2. Compare the student's answer with the correct answer.
3. Each question is worth {marks_per_question} marks. Give full marks for a
   correct answer, 0 for a wrong or blank answer. Give partial marks only for
   written answers that are partly correct.
4. If a handwritten answer is unreadable, set "student_answer" to "unclear"
   and give 0 marks.
5. Keep "feedback" to one short sentence explaining the mistake or confirming
   the answer.
6. Use the same language as the quiz for feedback.

Return ONLY JSON in this exact format:
{{
  "student_name": "",
  "questions": [
    {{
      "number": 1,
      "question": "short version of the question",
      "student_answer": "",
      "correct_answer": "",
      "marks_awarded": 0,
      "feedback": ""
    }}
  ],
  "note": ""
}}
Use "note" for any problem, such as a blurry image or missing questions.
"""


def parse_json(text):
    """Extract a JSON object from the model's reply, even if it adds fences."""
    if not text:
        raise ValueError("Empty response from the model.")
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in the response.")
    return json.loads(cleaned[start : end + 1])


def to_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_results(data, marks_per_question):
    """Clean the AI output and calculate totals in Python (not by the AI)."""
    rows = []
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list):
        questions = []

    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue
        awarded = to_number(item.get("marks_awarded"))
        awarded = max(0.0, min(awarded, float(marks_per_question)))
        rows.append(
            {
                "No.": item.get("number", index),
                "Question": str(item.get("question", "")),
                "Student answer": str(item.get("student_answer", "")),
                "Correct answer": str(item.get("correct_answer", "")),
                "Marks": awarded,
                "Out of": float(marks_per_question),
                "Feedback": str(item.get("feedback", "")),
            }
        )

    total = sum(row["Marks"] for row in rows)
    maximum = sum(row["Out of"] for row in rows)
    percentage = (total / maximum * 100) if maximum else 0.0
    return {
        "student_name": str(data.get("student_name", "")) if isinstance(data, dict) else "",
        "note": str(data.get("note", "")) if isinstance(data, dict) else "",
        "rows": rows,
        "total": total,
        "maximum": maximum,
        "percentage": percentage,
    }


@st.cache_resource
def get_client(api_key):
    return genai.Client(api_key=api_key)


def grade_quiz(client, model_name, file_bytes, mime_type, prompt):
    """Send the quiz to Gemini and return parsed JSON. Retries once if JSON is bad."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0,
        response_mime_type="application/json",
    )
    contents = [types.Part.from_bytes(data=file_bytes, mime_type=mime_type), prompt]

    last_error = None
    for _ in range(2):
        response = client.models.generate_content(
            model=model_name, contents=contents, config=config
        )
        try:
            return parse_json(response.text)
        except (ValueError, json.JSONDecodeError) as error:
            last_error = error
    raise ValueError(f"Could not read the AI response: {last_error}")


def main():
    st.set_page_config(page_title="Quiz Auto-Grader", page_icon="📝")
    st.title("📝 Quiz Auto-Grader")
    st.write("Upload a solved quiz (photo or PDF) and get marks in seconds.")

    api_key = get_secret("GEMINI_API_KEY")
    model_name = get_secret("GEMINI_MODEL", DEFAULT_MODEL)
    if not api_key:
        st.error(
            "Gemini API key not found. Add GEMINI_API_KEY to Streamlit secrets "
            "or set it as an environment variable."
        )
        st.stop()

    with st.sidebar:
        st.header("Settings")
        marks_per_question = st.number_input(
            "Marks per question", min_value=0.5, max_value=100.0, value=1.0, step=0.5
        )
        answer_key_text = st.text_area(
            "Answer key (optional)",
            placeholder="1-B\n2-D\n3-A\n\nLeave empty and the AI will solve the quiz itself.",
            height=180,
        )
        st.caption("AI can make mistakes. Use an answer key for best accuracy.")

    uploaded = st.file_uploader(
        "Upload the solved quiz", type=list(MIME_TYPES.keys())
    )

    if uploaded is None:
        st.info("Upload a PNG, JPG, or PDF file to begin.")
        return

    file_bytes = uploaded.getvalue()
    if len(file_bytes) > MAX_FILE_MB * 1024 * 1024:
        st.error(f"File is too large. Please upload a file under {MAX_FILE_MB} MB.")
        return

    extension = uploaded.name.rsplit(".", 1)[-1].lower()
    mime_type = MIME_TYPES.get(extension)
    if mime_type is None:
        st.error("Unsupported file type.")
        return

    if mime_type.startswith("image/"):
        st.image(file_bytes, caption="Uploaded quiz")

    if st.button("Grade quiz", type="primary"):
        try:
            with st.spinner("Grading your quiz..."):
                client = get_client(api_key)
                prompt = build_prompt(marks_per_question, answer_key_text)
                raw = grade_quiz(client, model_name, file_bytes, mime_type, prompt)
                st.session_state["result"] = normalize_results(raw, marks_per_question)
                st.session_state["result_file"] = uploaded.name
        except Exception as error:
            st.session_state.pop("result", None)
            st.error(f"Something went wrong: {error}")
            return

    # Results live in session_state so they stay visible after the CSV download click.
    result = st.session_state.get("result")
    if result is None or st.session_state.get("result_file") != uploaded.name:
        return

    show_results(result)


def show_results(result):
    if not result["rows"]:
        st.warning(
            "No questions were found. Try a clearer photo or a different file."
            + (f" Note from AI: {result['note']}" if result["note"] else "")
        )
        return

    if result["student_name"]:
        st.subheader(f"Student: {result['student_name']}")

    col1, col2 = st.columns(2)
    col1.metric("Score", f"{result['total']:g} / {result['maximum']:g}")
    col2.metric("Percentage", f"{result['percentage']:.1f}%")

    if result["note"]:
        st.info(f"Note: {result['note']}")

    df = pd.DataFrame(result["rows"])
    st.dataframe(df, hide_index=True)

    st.download_button(
        "Download results (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="quiz_results.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
