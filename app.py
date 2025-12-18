import os
import re
from datetime import datetime
from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename

# Pin OpenAI python SDK to 1.x in requirements.txt (below)
from openai import OpenAI

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}

SYSTEM_PROMPT = """
You are MyQuoteMate, an Australia-focused tradie quote checker.

Goal:
Help homeowners and small businesses understand a tradie quote in plain English, identify potential red flags, and prepare smart follow-up questions before accepting or paying.

Rules:
- Do NOT provide legal advice.
- Do NOT claim exact market pricing or guaranteed savings.
- Use cautious wording such as "may", "often", "typically", and "worth confirming".
- Use Australian terminology like GST, call-out fee, licensed tradie, compliance certificate.
- Be neutral and non-accusatory. Do not imply dishonesty.

If trade type or location is missing, proceed with reasonable assumptions and state them.

Output MUST follow this structure exactly with headings:

1. Verdict (Looks reasonable | Possibly high | Needs clarification)
2. Quick summary (3–6 bullet points)
3. Quote breakdown (plain English, grouped)
4. Red flags or risks (bullets)
5. Missing or unclear scope (bullets)
6. Questions to ask the tradie (8–12)
7. Suggested email to request clarification (short, polite)
8. Disclaimer (one short paragraph)
""".strip()

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>MyQuoteMate | Check your tradie quote</title>

  <!-- Tailwind CDN for a modern UI without setup -->
  <script src="https://cdn.tailwindcss.com"></script>

  <style>
    /* Make result headings stand out even in plain text */
    .result pre { white-space: pre-wrap; word-wrap: break-word; }
  </style>
</head>

<body class="bg-slate-50 text-slate-900">
  <header class="border-b bg-white">
    <div class="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="h-10 w-10 rounded-xl bg-slate-900"></div>
        <div>
          <div class="font-extrabold leading-tight">MyQuoteMate</div>
          <div class="text-xs text-slate-500 -mt-0.5">Australia tradie quote checker</div>
        </div>
      </div>
      <nav class="hidden md:flex items-center gap-6 text-sm font-semibold">
        <a class="text-slate-600 hover:text-slate-900" href="#how">How it works</a>
        <a class="text-slate-600 hover:text-slate-900" href="#checker">Quote checker</a>
        <a class="text-slate-600 hover:text-slate-900" href="#faq">FAQ</a>
      </nav>
      <a href="#checker" class="inline-flex items-center rounded-xl bg-slate-900 px-4 py-2 text-white font-bold hover:bg-slate-800">
        Check a quote
      </a>
    </div>
  </header>

  <main class="mx-auto max-w-6xl px-4">
    <section class="py-10 md:py-14">
      <div class="grid md:grid-cols-2 gap-10 items-center">
        <div>
          <div class="inline-flex items-center gap-2 rounded-full bg-slate-900/5 px-3 py-1 text-sm font-semibold text-slate-700">
            <span class="h-2 w-2 rounded-full bg-emerald-500"></span>
            Fast. Plain English. Australia-focused.
          </div>
          <h1 class="mt-4 text-4xl md:text-5xl font-extrabold tracking-tight">
            Not sure if your tradie quote is fair?
          </h1>
          <p class="mt-4 text-lg text-slate-600">
            Paste your quote (or upload a PDF) and MyQuoteMate will explain it in plain English, flag potential red flags, and generate the right questions to ask before you accept or pay.
          </p>
          <div class="mt-6 flex flex-wrap gap-3">
            <a href="#checker" class="rounded-xl bg-slate-900 px-5 py-3 text-white font-bold hover:bg-slate-800">Run quote check</a>
            <a href="#how" class="rounded-xl border border-slate-200 bg-white px-5 py-3 font-bold hover:bg-slate-50">How it works</a>
          </div>
          <p class="mt-3 text-sm text-slate-500">
            For best results, paste the quote text. Some PDFs are scanned and may not contain selectable text.
          </p>
        </div>

        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="flex items-start gap-4">
            <div class="h-12 w-12 rounded-2xl bg-emerald-50"></div>
            <div>
              <div class="font-extrabold">What you get</div>
              <ul class="mt-2 space-y-2 text-sm text-slate-600">
                <li>• Verdict: Looks reasonable / Possibly high / Needs clarification</li>
                <li>• Line-by-line breakdown in plain English</li>
                <li>• Red flags and missing scope items</li>
                <li>• 8–12 questions to ask the tradie</li>
                <li>• A polite email template to request clarity</li>
              </ul>
            </div>
          </div>
          <div class="mt-6 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
            <div class="font-bold text-slate-800">Tip</div>
            If your quote includes GST, call-out, compliance certificates, or exclusions, paste those sections too. That’s where most surprises hide.
          </div>
        </div>
      </div>
    </section>

    <section id="how" class="pb-10 md:pb-14">
      <h2 class="text-2xl md:text-3xl font-extrabold">How it works</h2>
      <p class="mt-2 text-slate-600">Three simple steps. Built for Australian quotes and terminology.</p>

      <div class="mt-6 grid md:grid-cols-3 gap-4">
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="text-sm font-extrabold text-slate-900">1. Add your quote</div>
          <div class="mt-2 text-sm text-slate-600">Paste the quote text. PDF upload is optional.</div>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="text-sm font-extrabold text-slate-900">2. AI reviews it</div>
          <div class="mt-2 text-sm text-slate-600">We analyse scope, wording, exclusions, and common risk areas.</div>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="text-sm font-extrabold text-slate-900">3. Get clarity</div>
          <div class="mt-2 text-sm text-slate-600">A structured report with questions and a ready-to-send email.</div>
        </div>
      </div>
    </section>

    <section id="checker" class="pb-10 md:pb-16">
      <div class="grid lg:grid-cols-2 gap-6">
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 class="text-2xl font-extrabold">Quote checker</h2>
          <p class="mt-2 text-sm text-slate-600">
            Paste quote text for best accuracy. If you upload a PDF and it’s scanned, we may not be able to read it.
          </p>

          <form method="POST" enctype="multipart/form-data" class="mt-5 space-y-4">
            <div class="grid md:grid-cols-2 gap-4">
              <div>
                <label class="text-sm font-bold">Trade type</label>
                <select name="trade" class="mt-1 w-full rounded-xl border border-slate-200 bg-white p-3">
                  <option value="">Select</option>
                  <option>Plumbing</option>
                  <option>Electrical</option>
                  <option>Renovation</option>
                  <option>Hot Water</option>
                  <option>Roofing</option>
                  <option>Painting</option>
                  <option>Fencing</option>
                  <option>Other</option>
                </select>
              </div>

              <div>
                <label class="text-sm font-bold">Location (Suburb, State)</label>
                <input name="location" value="{{ location or '' }}" placeholder="Example: Hobart TAS"
                       class="mt-1 w-full rounded-xl border border-slate-200 bg-white p-3" />
              </div>
            </div>

            <div>
              <label class="text-sm font-bold">Paste quote text</label>
              <textarea name="quote_text" rows="9" placeholder="Paste the quote here"
                        class="mt-1 w-full rounded-xl border border-slate-200 bg-white p-3">{{ quote_text or '' }}</textarea>
              <div class="mt-1 text-xs text-slate-500">
                Include GST, call-out fee, inclusions/exclusions, warranty, compliance certificate notes, and payment terms if present.
              </div>
            </div>

            <div>
              <label class="text-sm font-bold">Upload quote PDF (optional, PDF only)</label>
              <input type="file" name="quote_pdf" accept="application/pdf"
                     class="mt-1 w-full rounded-xl border border-slate-200 bg-white p-3" />
              <div class="mt-1 text-xs text-slate-500">Max 10MB. If PDF has no selectable text, paste the quote instead.</div>
            </div>

            <button type="submit"
              class="w-full rounded-xl bg-slate-900 px-5 py-3 font-extrabold text-white hover:bg-slate-800">
              Check my quote
            </button>

            <p class="text-xs text-slate-500">
              Educational guidance only. Not legal or financial advice.
            </p>
          </form>

          {% if error %}
            <div class="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <b>Error:</b> {{ error }}
            </div>
          {% endif %}
        </div>

        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm result">
          <h2 class="text-2xl font-extrabold">Results</h2>
          <p class="mt-2 text-sm text-slate-600">Your analysis will appear here.</p>

          {% if result %}
            <div class="mt-4 rounded-2xl bg-slate-900 p-4 text-slate-100">
              <pre class="text-sm leading-6">{{ result }}</pre>
            </div>
            <div class="mt-3 text-xs text-slate-500">
              Generated {{ generated_at }}
            </div>
          {% else %}
            <div class="mt-4 rounded-2xl bg-slate-50 p-5 text-sm text-slate-600">
              Paste a quote on the left and click “Check my quote”.
            </div>
          {% endif %}
        </div>
      </div>
    </section>

    <section id="faq" class="pb-14">
      <h2 class="text-2xl md:text-3xl font-extrabold">FAQ</h2>
      <div class="mt-6 grid md:grid-cols-2 gap-4">
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="font-extrabold">Why paste text instead of only PDF?</div>
          <div class="mt-2 text-sm text-slate-600">Many PDFs are scanned images. Pasting text gives the most accurate analysis.</div>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div class="font-extrabold">Do you store my quote?</div>
          <div class="mt-2 text-sm text-slate-600">This demo does not intentionally store quotes long-term. For production, you can add auto-deletion and logging controls.</div>
        </div>
      </div>
    </section>
  </main>

  <footer class="border-t bg-white">
    <div class="mx-auto max-w-6xl px-4 py-8 text-sm text-slate-500">
      © {{ year }} MyQuoteMate. Educational guidance only. Not legal or financial advice.
    </div>
  </footer>
</body>
</html>
"""

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def try_extract_pdf_text(path: str) -> str:
    # Best-effort extraction from normal (non-scanned) PDFs
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
        text = "\n".join(parts).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
    except Exception:
        return ""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML, result=None, error=None, quote_text="", location="", year=datetime.utcnow().year)

    trade = (request.form.get("trade") or "").strip()
    location = (request.form.get("location") or "").strip()
    quote_text = (request.form.get("quote_text") or "").strip()

    pdf_text = ""
    f = request.files.get("quote_pdf")
    if f and f.filename:
        if not allowed_file(f.filename):
            return render_template_string(
                HTML, result=None, error="Only PDF files are allowed.", quote_text=quote_text, location=location, year=datetime.utcnow().year
            )
        filename = secure_filename(f.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        f.save(save_path)
        pdf_text = try_extract_pdf_text(save_path)

    if not quote_text and not pdf_text:
        return render_template_string(
            HTML,
            result=None,
            error="Please paste quote text. PDF upload is optional, and scanned PDFs may not be readable.",
            quote_text=quote_text,
            location=location,
            year=datetime.utcnow().year,
        )

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return render_template_string(
            HTML, result=None, error="Server is missing OPENAI_API_KEY.", quote_text=quote_text, location=location, year=datetime.utcnow().year
        )

    client = OpenAI(api_key=api_key)

    user_payload = f"""Trade: {trade or "Not provided"}
Location: {location or "Not provided"}

QUOTE TEXT:
{quote_text if quote_text else "(not provided)"}

PDF EXTRACTED TEXT:
{pdf_text if pdf_text else "(no readable text extracted from PDF)"}"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
        )
        result = resp.output_text.strip()
        return render_template_string(
            HTML,
            result=result,
            error=None,
            quote_text=quote_text,
            location=location,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            year=datetime.utcnow().year,
        )
    except Exception as e:
        return render_template_string(
            HTML, result=None, error=f"AI request failed: {e}", quote_text=quote_text, location=location, year=datetime.utcnow().year
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
