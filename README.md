# SmartResume AI V2

A Flask-based Resume Analyzer with user login, admin dashboard, resume scoring, ATS checks, skill extraction and career recommendations.

## Supported files
- PDF (text-based PDFs; PyPDF2 + PyMuPDF fallback)
- DOCX (paragraphs + tables)
- TXT
- Maximum upload size: 8 MB

## Run locally
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Admin
Admin login: `/admin/login`

The bundled development account is `admin` / `admin123`. Change the password before production use.

## Deployment
The repository includes a `Procfile`, `runtime.txt`, and `render.yaml` for a Python web-service deployment. Set a strong `SECRET_KEY` environment variable in production.

> Note: SQLite is suitable for a small/demo deployment. Uploaded resumes and the SQLite database are intentionally ignored by Git so personal files and runtime data are not committed.
