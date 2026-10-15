# Fieldnotes

Fieldnotes is a small editorial blog platform for writing, previewing, publishing, and exporting personal stories. The main app is Flask + MongoDB with a custom publisher Studio. A separate static exporter turns published posts into HTML pages for GitHub Pages.

## Highlights

- Editorial public journal with featured stories, filters, article pages, dates, authors, read time, sharing, and Markdown rendering.
- Publisher accounts with login/logout, drafts, publish/update/delete, cover image uploads, and SEO metadata.
- Full-page Studio with split Markdown editor and live preview.
- MongoDB persistence with GridFS-backed image uploads and local `upload/` copies.
- Static export in `github-pages/`, with one HTML page per published blog.
- Responsive styling using Newsreader, DM Sans, DM Mono, a paper texture, and restrained motion.

## Run locally

Requirements: Python 3.11+, MongoDB local or Atlas, and Git for publishing.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py app.py
```

Open <http://127.0.0.1:5000>.

Default `.env` values:

```text
MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB=fieldnotes
PORT=5000
```

For production, set a long random `SECRET_KEY` and use MongoDB Atlas.

## Publish with Studio

1. Open **Studio** and sign in as a publisher.
2. Write in Markdown and use the live preview.
3. Choose **Save draft** or **Publish story**.
4. Choose **Export Pages** to regenerate `github-pages/`.
5. Choose **Preview Site** to inspect the generated static version.

The command-line equivalent is:

```powershell
py export_static.py
```

The exporter reads only MongoDB posts with `status: "published"` and creates:

```text
github-pages/
├── index.html
├── static.css
├── upload/
└── posts/
    ├── first-story.html
    └── another-story.html
```

External image URLs remain external. Local `/upload/...` images are copied into `github-pages/upload/` and rewritten to work on the static site.

## GitHub Pages

Repository: <https://github.com/Adityasonar29/Blog_Post>

After exporting, commit the generated site:

```powershell
git add github-pages export_static.py publish_static.bat requirements.txt README.md LICENSE
git commit -m "Update published static journal"
git push origin master
```

GitHub Pages hosts static HTML, CSS, JavaScript, and images. It does not run Flask, MongoDB, authentication, Studio, or the exporter. Publish the contents of `github-pages/` from a dedicated `gh-pages` branch or through GitHub Actions. Re-run the exporter and push again whenever a published story changes.

## API overview

`GET /api/health` · `GET /api/posts` · `POST /api/posts` · `PUT /api/posts/<id>` · `DELETE /api/posts/<id>` · `POST /api/uploads` · `POST /api/static-export` · `GET /static-preview/`

## License

MIT — see [LICENSE](LICENSE).
