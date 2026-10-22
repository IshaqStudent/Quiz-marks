# Quiz-marks
# 📝 Quiz Auto-Grader

Upload a solved quiz (photo or PDF) and get automatic marks. Built with
**Streamlit** for the UI and **Google Gemini Flash** for the AI.

## Features
- Upload a PNG, JPG, or PDF of a solved quiz
- Optional answer key for best accuracy (otherwise the AI solves the quiz itself)
- Set marks per question
- Score, percentage, and per-question feedback table
- Download results as CSV

## How it works
1. The quiz file is sent to Gemini Flash with a grading prompt.
2. Gemini returns the student's answers, correct answers, and marks as JSON.
3. The app calculates the total and percentage in Python, so the math is never left to the AI.

## Run locally
1. Get a free API key from https://aistudio.google.com/apikey
2. Install and run:

```bash
pip install -r requirements.txt
```

3. Set your key, then start the app.

Mac/Linux:
```bash
export GEMINI_API_KEY="your-key-here"
streamlit run app.py
```

Windows (PowerShell):
```powershell
$env:GEMINI_API_KEY="your-key-here"
streamlit run app.py
```

Or create `.streamlit/secrets.toml` (never commit this file):
```toml
GEMINI_API_KEY = "your-key-here"
```

## Change the model
The default model is `gemini-2.5-flash`. To use a different Flash model, add
`GEMINI_MODEL = "model-name"` to your secrets or environment variables.

## Deploy on Streamlit Community Cloud
1. Push this project to a GitHub repository.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, pick your repo, branch `main`, and main file `app.py`.
4. Open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   ```
5. Click **Deploy**.

## Notes
- AI can make mistakes, especially with messy handwriting. Provide an answer key for the most reliable marks.
- Files are limited to 10 MB.
