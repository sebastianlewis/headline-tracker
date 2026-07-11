# Headline Tracker

Collects daily headlines from the **Guardian Content API** and **Telegraph RSS
feeds** into a local SQLite database (`headlines.db`). Re-running is safe:
duplicate URLs are ignored, so the database accumulates new headlines over time.

## Sources

**Guardian** (via the Content API at `content.guardianapis.com/search`):

- `uk-news`
- `politics`
- `business`
- `money`

**Telegraph** (RSS):

- `telegraph.co.uk/news/rss.xml`
- `telegraph.co.uk/politics/rss.xml`
- `telegraph.co.uk/business/rss.xml`
- `telegraph.co.uk/money/rss.xml`

## Data stored

Each headline is stored in the `headlines` table with:

| Column         | Description                                        |
| -------------- | -------------------------------------------------- |
| `outlet`       | `Guardian` or `Telegraph`                          |
| `section`      | Source section (e.g. `politics`, `business`)       |
| `headline`     | The headline text                                  |
| `url`          | Article URL (**unique** — used for de-duplication) |
| `published_at` | Publication timestamp from the source              |
| `collected_at` | UTC timestamp of when the row was collected        |

Inserts use `INSERT OR IGNORE` on the unique `url` column, so running the
script repeatedly will not create duplicates.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Usage

The script reads the Guardian API key from the `GUARDIAN_API_KEY` environment
variable (get a free key at <https://open-platform.theguardian.com/access/>):

```bash
export GUARDIAN_API_KEY=your-key-here
python collect_headlines.py
```

Schedule it (e.g. with `cron`) to build up a daily archive of headlines.

## Inspecting the database

```bash
sqlite3 headlines.db "SELECT outlet, section, COUNT(*) FROM headlines GROUP BY outlet, section;"
```
