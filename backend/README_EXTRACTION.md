# PDF Extraction Setup Guide

## Quick Start

1. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Configure watched folders in `extraction_config.json`:
   ```json
   {
     "watched_folders": ["/path/to/your/pdf/folder"],
     "llm_provider": "openai",
     "ocr_enabled": true
   }
   ```

3. Set your LLM API key:
   ```bash
   export OPENAI_API_KEY=sk-...
   # or
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

4. Initialize the database:
   ```bash
   python -m app.init_db
   ```

5. Start the extraction watcher:
   ```bash
   python -m app.services.pdf_watcher
   ```

6. Start the API server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Hybrid Deployment

For hybrid deployment (local extraction + cloud query engine):

1. Keep the extraction service running on the hospital laptop
2. Deploy the query engine to Render.com (existing setup)
3. Use the "Export" button in the frontend to manually sync DuckDB snapshots to the cloud

## Troubleshooting

- **PDF not being processed**: Check that the file is fully written (not locked) and in the watched folder
- **OCR not working**: Install Tesseract (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Ubuntu)
- **LLM errors**: Verify your API key is set and has credits

## Security Notes

- All PHI stays on the hospital network during extraction
- Raw PDFs are never transmitted to cloud services
- Audit logs track every PDF processed for HIPAA compliance
