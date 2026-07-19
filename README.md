# Headline Tracker

Collects daily headlines from the **Guardian Content API**, **Telegraph RSS
feeds**, **BBC News RSS feeds**, and **Sky News RSS feeds** into a local SQLite
database (`headlines.db`). Re-running is safe: duplicate URLs are ignored, so
the database accumulates new headlines over time.

## Sources

Each source is tagged with a `content_type` of `news`, `opinion`, or
`analysis` (see [Data stored](#data-stored)).

**Guardian** (via the Content API at `content.guardianapis.com/search`):

- `uk-news` — news
- `politics` — news
- `business` — news
- `money` — news
- `commentisfree` — opinion

**Telegraph** (RSS):

- `telegraph.co.uk/news/rss.xml` — news
- `telegraph.co.uk/politics/rss.xml` — news
- `telegraph.co.uk/business/rss.xml` — news
- `telegraph.co.uk/money/rss.xml` — news
- `telegraph.co.uk/opinion/rss.xml` — opinion

**BBC News** (RSS):

- `feeds.bbci.co.uk/news/uk/rss.xml` — news
- `feeds.bbci.co.uk/news/politics/rss.xml` — news
- `feeds.bbci.co.uk/news/business/rss.xml` — news
- `feeds.bbci.co.uk/news/bbcindepth/rss.xml` — analysis (BBC publishes no
  op-eds under its impartiality rules; InDepth is analysis/explainer content,
  tagged distinctly from opinion)

**Sky News** (RSS) — no dedicated opinion feed exists, so all are news:

- `feeds.skynews.com/feeds/rss/home.xml`
- `feeds.skynews.com/feeds/rss/politics.xml`
- `feeds.skynews.com/feeds/rss/business.xml`

## Data stored

Each headline is stored in the `headlines` table with:

| Column         | Description                                        |
| -------------- | -------------------------------------------------- |
| `outlet`       | `Guardian`, `Telegraph`, `BBC News`, or `Sky News` |
| `section`      | Source section (e.g. `politics`, `business`)       |
| `content_type` | `news`, `opinion`, or `analysis` (default `news`)   |
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

## Analysis: fightin' words

`fightin_words.py` finds words that are statistically over-represented in one
outlet's headlines versus another's, using the log-odds-ratio with an
informative Dirichlet prior (Monroe, Colaresi & Quinn, 2008). It uses only the
Python standard library — no extra dependencies.

Compare two outlets at a time. Outlet names are matched case-insensitively by
prefix, so `guardian`, `bbc` and `sky` resolve to the stored names. Filter by
`content_type` and/or `section` to keep comparisons apples-to-apples:

```bash
# Guardian vs Telegraph, opinion pieces only, top 30 words each side
python fightin_words.py --outlet1 guardian --outlet2 telegraph \
    --content-type opinion --top 30

# BBC vs Sky, news only
python fightin_words.py --outlet1 bbc --outlet2 sky --content-type news
```

Words are ranked by z-score; those with `|z| > 1.96` (roughly `p < 0.05`) are
shown per side. Results firm up as the database grows — small or lexically
diverse corpora may surface few significant words.
