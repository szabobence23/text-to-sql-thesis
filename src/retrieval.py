"""
Schema retrieval: rank a database's tables by relevance to a question,
so the prompt can list a few tables instead of the whole schema.

The building blocks are shared by every retrieval method:
- TableDoc: the text a table is found by (its name and column names,
  optionally the database's own table/column descriptions);
- a ranker that orders the tables for a question (here BM25 over
  character n-grams; embedding and hybrid rankers can replace it);
- foreign-key expansion: a table that connects two selected tables is
  added, because without it the JOIN between them cannot be written.

How well a ranker works is measured without the LLM, against the tables
each ground truth reads (evaluation/retrieval_eval.py); the oracle schema
is the upper bound.
"""

import math
import re
from collections import Counter, deque
from dataclasses import dataclass, field

from schema import fetch_catalog, qualified_name


# ---------------------------------------------------------------------------
# Table documents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TableDoc:
    key: tuple[str, str]  # (schema, table), lower-case
    columns: tuple[str, ...]
    description: str = ""
    column_descriptions: tuple[str, ...] = field(default=())

    @property
    def name(self):
        return qualified_name(*self.key)

    def text(self, with_descriptions):
        """What the table is searched by."""
        parts = [self.name, *self.columns]
        if with_descriptions:
            parts += [self.description, *self.column_descriptions]
        return " ".join(p for p in parts if p)


def repair_mojibake(text):
    """
    UTF-8 text that was stored after being read as Latin-1 ('RÃ©sumÃ©' for
    'Résumé'). The AdventureWorks port loads its comments with
    CLIENT_ENCODING=latin1, so a few descriptions are affected.
    """
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text


DESCRIPTIONS_QUERY = """
SELECT n.nspname, c.relname, a.attname,
       obj_description(c.oid, 'pg_class'),
       col_description(c.oid, a.attnum)
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname = ANY(%(schemas)s)
ORDER BY n.nspname, c.relname, a.attnum;
"""


def load_table_docs(conn, schemas=("public",)):
    """
    One TableDoc per base table, from the same catalog as the prompt's
    schema text. Descriptions are the database's COMMENTs; datasets
    without comments get empty ones.
    """
    columns, _ = fetch_catalog(conn, schemas)

    table_columns = {}
    for table_schema, table_name, column_name, _ in columns:
        table_columns.setdefault((table_schema, table_name), []).append(column_name)

    with conn.cursor() as cur:
        cur.execute(DESCRIPTIONS_QUERY, {"schemas": list(schemas)})
        rows = cur.fetchall()
    conn.rollback()

    table_description = {}
    column_descriptions = {}
    for table_schema, table_name, _, table_comment, column_comment in rows:
        key = (table_schema, table_name)
        if table_comment:
            table_description[key] = repair_mojibake(table_comment)
        if column_comment:
            column_descriptions.setdefault(key, []).append(repair_mojibake(column_comment))

    return [
        TableDoc(
            key=key,
            columns=tuple(cols),
            description=table_description.get(key, ""),
            column_descriptions=tuple(column_descriptions.get(key, [])),
        )
        for key, cols in table_columns.items()
    ]


def foreign_key_graph(conn, schemas=("public",)):
    """Undirected graph {table: {neighbouring tables}} of foreign keys."""
    _, relationships = fetch_catalog(conn, schemas)

    graph = {}
    for s, t, _, fs, ft, _ in relationships:
        a, b = (s, t), (fs, ft)
        if a != b:
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    return graph


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------

def words(text):
    """
    Lower-case words. Identifiers are split at underscores and camelCase
    (order_items -> order items, raceId -> race id); identifiers written
    as one word (salesorderheader) stay whole, character n-grams handle them.
    """
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return [w for w in re.split(r"[\W_]+", text.lower()) if w]


def char_ngrams(word, n):
    """Overlapping n-character pieces; n = 0 keeps the whole word."""
    if n <= 0 or len(word) <= n:
        return [word]
    return [word[i:i + n] for i in range(len(word) - n + 1)]


def tokens(text, ngram):
    return [g for w in words(text) for g in char_ngrams(w, ngram)]


# ---------------------------------------------------------------------------
# BM25 ranker
# ---------------------------------------------------------------------------

class BM25:
    """
    Okapi BM25 with the usual defaults k1 = 1.5, b = 0.75, and the
    non-negative idf log(1 + (N - df + 0.5) / (df + 0.5)), so a term found
    in most tables (e.g. a 'modifieddate' column) still never lowers a score.
    """

    def __init__(self, documents, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.tf = [Counter(doc) for doc in documents]
        self.length = [len(doc) for doc in documents]
        self.avg_length = sum(self.length) / len(documents) if documents else 0.0

        n = len(documents)
        df = Counter(term for tf in self.tf for term in tf)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, query):
        result = []
        for tf, length in zip(self.tf, self.length):
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_length)
            score = 0.0
            for term in query:
                f = tf.get(term)
                if f:
                    score += self.idf[term] * f * (self.k1 + 1) / (f + norm)
            result.append(score)
        return result


class BM25Retriever:
    """Ranks tables by BM25 between the question and each table's text."""

    def __init__(self, docs, ngram=3, with_descriptions=False):
        self.docs = docs
        self.ngram = ngram
        self.index = BM25([tokens(d.text(with_descriptions), ngram) for d in docs])

    def rank(self, question):
        """[(table key, score)], best first; ties broken by table name."""
        scores = self.index.scores(tokens(question, self.ngram))
        ranked = sorted(zip(self.docs, scores), key=lambda p: (-p[1], p[0].name))
        return [(doc.key, score) for doc, score in ranked]


# ---------------------------------------------------------------------------
# Selection and foreign-key expansion
# ---------------------------------------------------------------------------

def _shortest_path(graph, start, goal, max_hops):
    """Tables strictly between start and goal on a shortest path, or None."""
    previous = {start: None}
    queue = deque([(start, 0)])
    while queue:
        node, hops = queue.popleft()
        if node == goal:
            path = []
            node = previous[node]
            while node != start:
                path.append(node)
                node = previous[node]
            return path[::-1]
        if hops == max_hops:
            continue
        for neighbour in sorted(graph.get(node, ())):
            if neighbour not in previous:
                previous[neighbour] = node
                queue.append((neighbour, hops + 1))
    return None


def expand_with_bridges(selected, graph, max_hops=2):
    """
    selected plus the tables on a shortest foreign-key path (at most
    max_hops edges) between any two selected tables that are not directly
    connected. max_hops = 2 adds single bridge tables, e.g. a subcategory
    between product and category.
    """
    result = list(selected)
    for i, a in enumerate(selected):
        for b in selected[i + 1:]:
            if b in graph.get(a, ()):
                continue
            path = _shortest_path(graph, a, b, max_hops)
            for table in path or ():
                if table not in result:
                    result.append(table)
    return result


def select_tables(ranking, k, graph=None, fk_expansion=False, max_hops=2):
    """The top-k tables of a ranking, optionally with bridge tables added."""
    top = [key for key, _ in ranking[:k]]
    if fk_expansion and graph is not None:
        return expand_with_bridges(top, graph, max_hops)
    return top
