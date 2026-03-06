# S14.3 — Web Frontend

## Context
A beautiful, responsive webpage served by FastAPI that allows users to upload prescription images and receive translations. This is an alternative to the WhatsApp interface — useful for demos, testing, and users who prefer a web browser.

## Dependencies
- S14.2 (Web upload API endpoint)
- S3.1 (SUPPORTED_LANGUAGES)

## Functional Requirements

### FR-1: Static files directory
- Create `backend/static/` directory for CSS/JS assets.
- Create `backend/templates/` directory for HTML templates.
- Mount static files in `main.py`: `app.mount("/static", StaticFiles(...))`.
- Add `jinja2` to pyproject.toml dependencies.

### FR-2: Landing page (`GET /`)
- Serve an HTML page via Jinja2 template.
- Sections:
  1. **Hero/Header**: Project name "SehatSamjho", tagline, brief description.
  2. **How It Works**: 3-step visual guide (Upload -> Select Language -> Get Results).
  3. **Upload Section**: Language dropdown + file upload + submit button.
  4. **Results Section** (hidden initially): Shows translation results after submission.
  5. **Footer**: Privacy note, tech stack mention.

### FR-3: Language selection dropdown
- Populate with all 22 supported languages.
- Show both English name and native script (e.g., "Hindi - हिन्दी").
- Default: Hindi.

### FR-4: Image upload
- Drag-and-drop zone + click-to-browse.
- Preview uploaded image before submitting.
- Accept only image files (JPEG, PNG).
- Max file size: 10MB (client-side validation).

### FR-5: Submit and loading state
- On submit: POST to `/api/translate` with FormData (image + language_code).
- Show loading spinner/animation with "Translating your prescription..." message.
- Disable submit button during processing.

### FR-6: Results display
- After successful response:
  - **Prescription Summary**: List of medicines with name, dosage, frequency, duration.
  - **Confidence indicators**: Visual badges (green/yellow/red) per medicine.
  - **Translated Text**: Full translation in the selected language.
  - **Audio Player**: HTML5 `<audio>` element with the presigned S3 URL (if available).
  - **Disclaimer**: Displayed at the bottom.
- On error: Show user-friendly error message (not stack traces).

### FR-7: Design
- Clean, modern design with a medical/health theme.
- Color scheme: Teal/green primary (health-related), white background.
- Mobile-responsive (works on phone browsers).
- No external CSS frameworks required — use vanilla CSS (or minimal Tailwind CDN).
- Accessible: proper ARIA labels, keyboard navigation, contrast ratios.

### FR-8: "Try Again" flow
- After results are shown, a "Translate Another" button resets the form.
- User can upload a new image without refreshing the page.

## Non-Functional Requirements
- Page load time < 1 second (minimal JS, no heavy frameworks).
- All JS is vanilla (no React/Vue/Angular).
- No external font loading (use system fonts).
- Works in all modern browsers.

## Test Plan
- 20 tests in `backend/tests/test_web_frontend.py`.
- Test: page loads (200), static files served, template renders, language list present, form action correct, CORS headers.
- Tests use httpx AsyncClient against the app (no browser tests).
