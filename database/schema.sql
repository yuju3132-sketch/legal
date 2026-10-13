PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, name TEXT NOT NULL, jurisdiction TEXT NOT NULL, tier INTEGER NOT NULL, homepage TEXT NOT NULL, feed_url TEXT, enabled INTEGER DEFAULT 0, verification_status TEXT DEFAULT '확인되지 않음', last_checked TEXT);
CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, parent TEXT, keywords TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS institutions(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS authors(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, normalized_title TEXT NOT NULL,
 jurisdiction TEXT NOT NULL, publication_date TEXT, first_seen TEXT NOT NULL, last_checked TEXT,
 source_id TEXT REFERENCES sources(id), source_type TEXT NOT NULL, source_tier INTEGER NOT NULL,
 primary_topic TEXT, author_or_institution TEXT, institution TEXT, author TEXT, citation TEXT,
 case_number TEXT, document_number TEXT, doi TEXT, source_url TEXT NOT NULL UNIQUE, canonical_url TEXT NOT NULL UNIQUE,
 pdf_url TEXT, local_pdf_path TEXT, document_hash TEXT, importance_score INTEGER DEFAULT 0,
 score_reason TEXT, score_components TEXT, priority TEXT DEFAULT 'D', duplicate_status TEXT DEFAULT 'NEW', update_status TEXT DEFAULT 'NEW',
 research_relevance TEXT, legal_significance TEXT, korean_law_relevance TEXT, comparative_law_relevance TEXT,
 banking_practice_relevance TEXT, seminar_relevance TEXT, paper_relevance TEXT, research_gap TEXT,
 summary TEXT, notes TEXT, keywords TEXT, facts TEXT, what_is_new TEXT, core_legal_issue TEXT,
 difference_from_existing TEXT, governance_implication TEXT, aml_implication TEXT, sanctions_implication TEXT,
 verification_status TEXT DEFAULT '확인되지 않음', verified_at TEXT, content_hash TEXT, evidence TEXT,
 is_test INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(importance_score BETWEEN 0 AND 100), CHECK(source_tier BETWEEN 0 AND 5));
CREATE TABLE IF NOT EXISTS document_topics(document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, topic_id INTEGER REFERENCES topics(id), PRIMARY KEY(document_id,topic_id));
CREATE TABLE IF NOT EXISTS document_authors(document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, author_id INTEGER REFERENCES authors(id), PRIMARY KEY(document_id,author_id));
CREATE TABLE IF NOT EXISTS document_institutions(document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, institution_id INTEGER REFERENCES institutions(id), PRIMARY KEY(document_id,institution_id));
CREATE TABLE IF NOT EXISTS relationships(id INTEGER PRIMARY KEY, from_document INTEGER REFERENCES documents(id), to_document INTEGER REFERENCES documents(id), relation_type TEXT NOT NULL, note TEXT, UNIQUE(from_document,to_document,relation_type));
CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, period TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(kind,period));
CREATE TABLE IF NOT EXISTS report_documents(report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE, document_id INTEGER REFERENCES documents(id), version_hash TEXT NOT NULL, PRIMARY KEY(report_id,document_id));
CREATE TABLE IF NOT EXISTS research_ideas(id INTEGER PRIMARY KEY, title TEXT NOT NULL, problem TEXT, legal_issue TEXT, jurisdictions TEXT, existing_research TEXT, research_gap TEXT, korean_connection TEXT, comparative_potential TEXT, paper_fit TEXT, seminar_fit TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS idea_documents(idea_id INTEGER REFERENCES research_ideas(id), document_id INTEGER REFERENCES documents(id), PRIMARY KEY(idea_id,document_id));
CREATE TABLE IF NOT EXISTS collection_runs(id INTEGER PRIMARY KEY, kind TEXT, started_at TEXT, finished_at TEXT, status TEXT, discovered INTEGER DEFAULT 0, inserted INTEGER DEFAULT 0, updated INTEGER DEFAULT 0, duplicates INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS errors(id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES collection_runs(id), source_id TEXT, category TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(publication_date);
CREATE INDEX IF NOT EXISTS idx_documents_doi ON documents(doi);
CREATE INDEX IF NOT EXISTS idx_documents_score ON documents(importance_score);
