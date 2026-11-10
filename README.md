# Left Main Help Center

Public help site: https://andrewleftmain.github.io/left-main-help-center/

## Editing an existing article

1. Open `content/<category>/<article>.html` (e.g. `content/cadences/stop-cadences.html`).
2. The top of the file is a small front-matter comment:
   ```
   <!--
   title: Stop Cadences
   order: 7
   -->
   ```
   Everything after the closing `-->` is the article body — plain HTML
   (`<h2>`, `<p>`, `<ul>`, `<table>`, `<img>`, etc.). Edit the text directly.
3. Commit and push (or edit the file right on github.com and commit there —
   no local setup needed for a text-only change). The site rebuilds and
   redeploys automatically within about a minute.

## Adding a new article

1. Create a new `.html` file in the right `content/<category>/` folder,
   following the same front-matter + body pattern as an existing article in
   that folder. `order` controls where it sits in that category's article
   list (ties are broken alphabetically).
2. Commit and push.

## Adding a new category

1. Add an entry to `categories.json`: `"your-slug": {"title": "Your Title", "order": 20}`.
2. Create `content/your-slug/` and add at least one article file to it (an
   empty category folder is skipped).
3. Commit and push.

## Images and other files

Put images in `assets/images/`, other attachments (PDFs, videos) in
`assets/files/`. Reference them from any article as `assets/images/name.png`
— the build rewrites the path to the right relative depth automatically no
matter which category the article lives in.

## Building locally (optional)

Routine edits don't need this — GitHub Actions rebuilds on every push. To
preview locally before pushing:

```bash
python3 build.py        # writes the full site into _site/
python3 -m http.server 8000 --directory _site
```

`build.py` has no dependencies beyond the Python standard library.

## How this is wired up

- `content/` + `categories.json` are the source of truth.
- `build.py` renders them into a full static site (shared `styles.css` /
  `script.js`, same template on every page).
- `.github/workflows/deploy.yml` runs `build.py` and deploys the result to
  GitHub Pages on every push to `main`.
- `_site/` is a build artifact (gitignored) — never edit it directly, your
  changes will be overwritten on the next build.
