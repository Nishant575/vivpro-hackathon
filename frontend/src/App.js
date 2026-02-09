import React, { useState } from 'react';
import './App.css';

const API_BASE = '/api';

function App() {
  // --- Core State ---
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);
  const [interpretation, setInterpretation] = useState('');
  const [entities, setEntities] = useState({});
  const [total, setTotal] = useState(0);

  // --- Results + Filter State ---
  const [allResults, setAllResults] = useState([]);
  const [filteredResults, setFilteredResults] = useState([]);
  const [showAll, setShowAll] = useState(false);
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);
  const [availableFilters, setAvailableFilters] = useState({
    statuses: [],
    phases: [],
    countries: [],
  });
  const [activeFilters, setActiveFilters] = useState({
    statuses: [],
    phases: [],
    countries: [],
  });
  const [aiSummary, setAiSummary] = useState('');
  const [summaryLoading, setSummaryLoading] = useState(false);

  const activeFilterCount =
    activeFilters.statuses.length +
    activeFilters.phases.length +
    activeFilters.countries.length;

  // --- Filter Logic ---

  const extractFilters = (trials) => {
    const statusCounts = {};
    const phaseCounts = {};
    const countryCounts = {};

    trials.forEach((trial) => {
      if (trial.overall_status) {
        statusCounts[trial.overall_status] =
          (statusCounts[trial.overall_status] || 0) + 1;
      }
      if (trial.phase) {
        phaseCounts[trial.phase] = (phaseCounts[trial.phase] || 0) + 1;
      }
      if (trial.countries && trial.countries.length > 0) {
        trial.countries.forEach((country) => {
          countryCounts[country] = (countryCounts[country] || 0) + 1;
        });
      }
    });

    const toSorted = (counts) =>
      Object.entries(counts)
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count);

    return {
      statuses: toSorted(statusCounts),
      phases: toSorted(phaseCounts),
      countries: toSorted(countryCounts).slice(0, 10),
    };
  };

  const applyFilters = (trials, filters) => {
    return trials.filter((trial) => {
      if (
        filters.statuses.length > 0 &&
        !filters.statuses.includes(trial.overall_status)
      )
        return false;
      if (filters.phases.length > 0 && !filters.phases.includes(trial.phase))
        return false;
      if (filters.countries.length > 0) {
        const trialCountries = trial.countries || [];
        if (!filters.countries.some((c) => trialCountries.includes(c)))
          return false;
      }
      return true;
    });
  };

  const toggleFilter = (filterType, value) => {
    setActiveFilters((prev) => {
      const current = prev[filterType];
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      const newFilters = { ...prev, [filterType]: updated };
      setFilteredResults(applyFilters(allResults, newFilters));
      return newFilters;
    });
  };

  const clearAllFilters = () => {
    const cleared = { statuses: [], phases: [], countries: [] };
    setActiveFilters(cleared);
    setFilteredResults(allResults);
  };

  const fetchSummary = async (searchQuery, results, entities, totalCount) => {
    setSummaryLoading(true);
    setAiSummary('');
    try {
      const res = await fetch(`${API_BASE}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          total: totalCount,
          entities: entities,
          results: results,
        }),
      });
      const data = await res.json();
      if (data.success && data.summary) {
        setAiSummary(data.summary);
      }
    } catch {
      // Silently fail — summary is non-critical
    } finally {
      setSummaryLoading(false);
    }
  };

  // --- Search ---

  const doSearch = async (searchQuery = query) => {
    const q = (searchQuery || '').trim();
    if (!q) return;

    setLoading(true);
    setError('');
    setShowAll(false);
    setShowFilterDropdown(false);

    try {
      const encoded = encodeURIComponent(q);
      const res = await fetch(
        `${API_BASE}/search/${encoded}?page=1&size=100`
      );
      const data = await res.json();

      if (data.success) {
        setInterpretation(data.interpretation);
        setEntities(data.entities);
        setTotal(data.total);
        setAllResults(data.results);
        setFilteredResults(data.results);
        setAvailableFilters(extractFilters(data.results));
        setActiveFilters({ statuses: [], phases: [], countries: [] });
        fetchSummary(q, data.results, data.entities, data.total);
      } else {
        setError(data.error || 'Search failed');
        setAllResults([]);
        setFilteredResults([]);
        
      }
    } catch {
      setError('Could not connect to the server. Is the backend running?');
      setAllResults([]);
      setFilteredResults([]);
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    doSearch();
  };

  const handleExampleClick = (text) => {
    setQuery(text);
    doSearch(text);
  };

  const handleGoHome = () => {
    setSearched(false);
    setQuery('');
    setAllResults([]);
    setFilteredResults([]);
    setInterpretation('');
    setEntities({});
    setError('');
    setAiSummary('');
  };

  // --- Helpers ---

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
      });
    } catch {
      return dateStr;
    }
  };

  const statusStyle = (status) => {
    const map = {
      RECRUITING: { bg: '#d1fae5', color: '#065f46', border: '#6ee7b7' },
      ACTIVE_NOT_RECRUITING: {
        bg: '#dbeafe',
        color: '#1e40af',
        border: '#93c5fd',
      },
      COMPLETED: { bg: '#f3f4f6', color: '#374151', border: '#d1d5db' },
      NOT_YET_RECRUITING: {
        bg: '#fef3c7',
        color: '#92400e',
        border: '#fcd34d',
      },
      SUSPENDED: { bg: '#fef3c7', color: '#92400e', border: '#fcd34d' },
      TERMINATED: { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
      WITHDRAWN: { bg: '#ede9fe', color: '#5b21b6', border: '#c4b5fd' },
    };
    return map[status] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db' };
  };

  const formatPhase = (phase) => {
    if (!phase) return 'N/A';
    return phase.replace(/PHASE/g, 'Phase ').replace(/\//g, ' / ');
  };

  const formatStatus = (status) => {
    return (status || '').replace(/_/g, ' ');
  };

  const renderTitle = (trial) => {
    if (
      trial.highlights &&
      trial.highlights.brief_title &&
      trial.highlights.brief_title.length > 0
    ) {
      return (
        <span
          dangerouslySetInnerHTML={{ __html: trial.highlights.brief_title[0] }}
        />
      );
    }
    return trial.brief_title;
  };

  const displayEntities = Object.entries(entities).filter(
    ([key]) => !key.endsWith('_confidence')
  );

  
  const isQuestion = entities.query_type === "question";

  // --- Displayed results (show 5 or all) ---
  const displayedResults = showAll
    ? filteredResults
    : filteredResults.slice(0, 5);

  // ============================
  // RENDER
  // ============================

  // --- HOME VIEW ---
  if (!searched) {
    return (
      <div className="home-view">
        <div className="home-content">
          <div className="home-header">
            <span className="home-icon">🔬</span>
            <h1 className="home-title">Clinical Trials Search</h1>
            <p className="home-subtitle">
              Search 1,000 clinical trials using natural language
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="search-container">
              <div className="search-box">
                <div className="search-top-row">
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Ask about clinical trials..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    autoFocus
                  />
                  <button
                    type="submit"
                    className="search-submit-btn"
                    disabled={loading}
                  >
                    →
                  </button>
                </div>
              </div>
            </div>
          </form>

          <div className="example-queries">
            {[
              { icon: '🧬', text: 'Lung cancer trials' },
              { icon: '💊', text: 'Diabetes treatments' },
              { icon: '🏥', text: 'Recruiting Phase 3' },
              { icon: '🧪', text: 'Breast cancer immunotherapy' },
            ].map(({ icon, text }) => (
              <button
                key={text}
                className="example-query"
                onClick={() => handleExampleClick(text)}
              >
                <span className="example-query-icon">{icon}</span>
                {text}
              </button>
            ))}
          </div>
        </div>

        <footer className="home-footer">
          Powered by Elasticsearch + NLP + MeSH
        </footer>
      </div>
    );
  }

  return (
    <div className="results-view">
      {/* Top Bar */}
      <header className="results-topbar">
        <button className="topbar-logo" onClick={handleGoHome}>
          🔬 Clinical Trials Search
        </button>
      </header>

      <div className="results-body">
        {/* Search Bar */}
        <div className="results-search-wrapper">
          <form onSubmit={handleSubmit}>
            <div className="search-container">
              <div className="search-box">
                <div className="search-top-row">
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Ask about clinical trials..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <button
                    type="submit"
                    className="search-submit-btn"
                    disabled={loading}
                  >
                    →
                  </button>
                </div>
                <div className="search-bottom-row">
                  <button
                    type="button"
                    className={`filter-toggle-btn ${
                      activeFilterCount > 0 ? 'has-filters' : ''
                    }`}
                    onClick={() => setShowFilterDropdown((p) => !p)}
                  >
                    ⚙ Filter
                    {activeFilterCount > 0 && (
                      <span className="filter-badge">{activeFilterCount}</span>
                    )}
                  </button>
                </div>
              </div>

              {/* Filter Dropdown */}
              {showFilterDropdown && (
                <>
                  <div
                    className="filter-dropdown-overlay"
                    onClick={() => setShowFilterDropdown(false)}
                  />
                  <div className="filter-dropdown">
                    <div className="filter-dropdown-header">
                      <span className="filter-dropdown-title">Filters</span>
                      {activeFilterCount > 0 && (
                        <button
                          className="filter-clear-btn"
                          onClick={clearAllFilters}
                        >
                          Clear All
                        </button>
                      )}
                    </div>

                    {availableFilters.statuses.length > 0 && (
                      <div className="filter-group">
                        <div className="filter-group-label">Status</div>
                        <div className="filter-chips">
                          {availableFilters.statuses.map(({ value, count }) => (
                            <label
                              key={value}
                              className={`filter-chip ${
                                activeFilters.statuses.includes(value)
                                  ? 'active'
                                  : ''
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={activeFilters.statuses.includes(value)}
                                onChange={() => toggleFilter('statuses', value)}
                              />
                              {formatStatus(value)}{' '}
                              <span className="filter-chip-count">
                                {count}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {availableFilters.phases.length > 0 && (
                      <div className="filter-group">
                        <div className="filter-group-label">Phase</div>
                        <div className="filter-chips">
                          {availableFilters.phases.map(({ value, count }) => (
                            <label
                              key={value}
                              className={`filter-chip ${
                                activeFilters.phases.includes(value)
                                  ? 'active'
                                  : ''
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={activeFilters.phases.includes(value)}
                                onChange={() => toggleFilter('phases', value)}
                              />
                              {formatPhase(value)}{' '}
                              <span className="filter-chip-count">
                                {count}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {availableFilters.countries.length > 0 && (
                      <div className="filter-group">
                        <div className="filter-group-label">Location</div>
                        <div className="filter-chips">
                          {availableFilters.countries.map(
                            ({ value, count }) => (
                              <label
                                key={value}
                                className={`filter-chip ${
                                  activeFilters.countries.includes(value)
                                    ? 'active'
                                    : ''
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={activeFilters.countries.includes(
                                    value
                                  )}
                                  onChange={() =>
                                    toggleFilter('countries', value)
                                  }
                                />
                                {value}{' '}
                                <span className="filter-chip-count">
                                  {count}
                                </span>
                              </label>
                            )
                          )}
                        </div>
                      </div>
                    )}

                    <button
                      className="filter-apply-btn"
                      onClick={() => setShowFilterDropdown(false)}
                    >
                      Apply Filters
                    </button>
                  </div>
                </>
              )}
            </div>
          </form>
        </div>

        {/* Loading */}
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            <p>Searching clinical trials...</p>
          </div>
        )}

        {/* Error */}
        {error && <div className="error-banner">{error}</div>}

        {/* Results Content */}
        {!loading && !error && allResults.length > 0 && (
          <>
            {/* Interpretation */}
            {interpretation && (
              <div className="interpretation-box">
                <p className="interpretation-text">{interpretation}</p>
                {displayEntities.length > 0 && (
                  <div className="entity-chips">
                    {displayEntities.map(([key, value]) => {
                      // Skip internal fields
                      if (
                              key === 'condition_synonyms' ||
                              key === 'condition_match_type' ||
                              key === 'query_type' ||
                              key.endsWith('_op') ||
                              key.endsWith('_confidence')
                            )
                              return null;

                      // Format date entity specially
                      let displayValue = value;
                      if (Array.isArray(value)) {
                        displayValue = value.join(' or ');
                      }
                      if (key === 'date' && typeof value === 'object') {
                        const start = value.start ? value.start.slice(0, 4) : '';
                        const end = value.end ? value.end.slice(0, 4) : '';
                        if (start && end) {
                          displayValue = start === end ? start : `${start}–${end}`;
                        } else if (start) {
                          displayValue = `from ${start}`;
                        } else if (end) {
                          displayValue = `before ${end}`;
                        }
                      }
                      return (
                        <span key={key} className="entity-chip">
                          {key}: {displayValue}
                        </span>
                      );
                    })}
                  </div>
                )}
                {entities.condition_synonyms &&
                  entities.condition_synonyms.length > 1 && (
                    <div className="synonym-expansion">
                      Also searching:{' '}
                      {entities.condition_synonyms.slice(0, 4).join(', ')}
                      {entities.condition_synonyms.length > 4 && (
                        <span className="more-synonyms">
                          {' '}
                          +{entities.condition_synonyms.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
              </div>
            )}

            {/* AI Summary */}
             {(summaryLoading || aiSummary) && (
              <div className={`ai-summary ${isQuestion ? 'ai-answer' : ''}`}>
                <div className="ai-summary-header">
                  <span className="ai-summary-icon">{isQuestion ? '💡' : '✨'}</span>
                  <span className="ai-summary-label">{isQuestion ? 'Answer' : 'AI Summary'}</span>
                </div>
                {summaryLoading ? (
                  <div className="ai-summary-shimmer">
                    <div className="shimmer-line" />
                    <div className="shimmer-line short" />
                  </div>
                ) : (
                  <p className="ai-summary-text">{aiSummary}</p>
                )}
              </div>
            )}

            {/* Results Header */}
            <div className="results-list-header">
             <h2 className="results-list-title">{isQuestion ? 'Supporting Trials' : 'Top Results'}</h2>
              <span className="results-list-count">
                {total} total
                {activeFilterCount > 0 && (
                  <span className="filtered-note">
                    {' '}
                    · {filteredResults.length} after filters
                  </span>
                )}
              </span>
            </div>

            {/* Result Cards */}
            {filteredResults.length > 0 ? (
              <>
                {displayedResults.map((trial) => {
                  const ss = statusStyle(trial.overall_status);
                  return (
                    <div key={trial.nct_id} className="result-card">
                      <div className="result-card-top">
                        <h3 className="result-title">{renderTitle(trial)}</h3>
                        <span className="result-nct">{trial.nct_id}</span>
                      </div>

                      <div className="result-badges">
                        {trial.overall_status && (
                          <span
                            className="badge badge-status"
                            style={{
                              backgroundColor: ss.bg,
                              color: ss.color,
                              borderColor: ss.border,
                            }}
                          >
                            {formatStatus(trial.overall_status)}
                          </span>
                        )}
                        {trial.phase && (
                          <span className="badge badge-phase">
                            {formatPhase(trial.phase)}
                          </span>
                        )}
                        {trial.enrollment && (
                          <span className="badge badge-enrollment">
                            {trial.enrollment.toLocaleString()} enrolled
                          </span>
                        )}
                      </div>

                      <div className="result-details">
                        {trial.conditions && trial.conditions.length > 0 && (
                          <div className="result-detail-row">
                            <span className="result-detail-icon">🔬</span>
                            <span>{trial.conditions.join(', ')}</span>
                          </div>
                        )}
                        {trial.sponsor && (
                          <div className="result-detail-row">
                            <span className="result-detail-icon">🏢</span>
                            <span>{trial.sponsor}</span>
                          </div>
                        )}
                        {trial.locations && trial.locations.length > 0 && (
                          <div className="result-detail-row">
                            <span className="result-detail-icon">📍</span>
                            <span>{trial.locations.join(' · ')}</span>
                          </div>
                        )}
                        {trial.start_date && (
                          <div className="result-detail-row">
                            <span className="result-detail-icon">📅</span>
                            <span>{formatDate(trial.start_date)}</span>
                          </div>
                        )}
                      </div>

                      <div className="result-footer">
                        <span className="result-score">
                          Relevance: {trial.score?.toFixed(1)}
                        </span>
                        <a
                          href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="result-link"
                        >
                          View on ClinicalTrials.gov →
                        </a>
                      </div>
                    </div>
                  );
                })}

                {/* Show More / Less */}
                {!showAll && filteredResults.length > 5 && (
                  <button
                    className="show-more-btn"
                    onClick={() => setShowAll(true)}
                  >
                    Show all {filteredResults.length} results ↓
                  </button>
                )}
                {showAll && filteredResults.length > 5 && (
                  <button
                    className="show-less-btn"
                    onClick={() => {
                      setShowAll(false);
                      window.scrollTo({ top: 0, behavior: 'smooth' });
                    }}
                  >
                    Show less ↑
                  </button>
                )}
              </>
            ) : (
              <div className="no-results-msg">
                <p>No trials match your current filters.</p>
                <button onClick={clearAllFilters}>Clear Filters</button>
              </div>
            )}
          </>
        )}

        {/* No results at all */}
        {!loading && !error && searched && allResults.length === 0 && (
          <div className="no-results-msg">
            <p>No trials found matching your query.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
