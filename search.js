/* ============================================
   🔍 সবুজ বই — Live Search Dropdown (FINAL)
   ============================================ */

(function() {
    'use strict';

    const DEBOUNCE_MS = 250;
    const MIN_QUERY_LENGTH = 2;
    const MAX_RESULTS = 10;

    let debounceTimer = null;
    let currentResults = [];
    let selectedIndex = -1;
    let abortController = null;
    let searchInput = null;
    let resultsContainer = null;
    let searchForm = null;

    function detectElements() {
        searchInput = document.getElementById('liveSearchInput') || document.querySelector('input[name="q"]');
        if (!searchInput) return false;

        resultsContainer = document.getElementById('liveSearchResults');
        if (!resultsContainer) {
            const parent = searchInput.closest('.nav-search-wrapper') || searchInput.parentElement;
            if (parent) {
                if (window.getComputedStyle(parent).position === 'static') {
                    parent.style.position = 'relative';
                }
                resultsContainer = document.createElement('div');
                resultsContainer.className = 'live-search-results';
                resultsContainer.id = 'liveSearchResults';
                parent.appendChild(resultsContainer);
            }
        }

        searchForm = document.getElementById('liveSearchForm') || searchInput.closest('form');
        return true;
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, c => map[c]);
    }

    function highlightText(text, query) {
        if (!query || !text) return escapeHtml(text || '');
        const escaped = escapeHtml(text);
        const words = query.trim().split(/\s+/).filter(w => w.length >= 2);
        let result = escaped;
        for (const word of words) {
            const safe = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${safe})`, 'gi');
            result = result.replace(regex, '<mark class="live-search-highlight">$1</mark>');
        }
        return result;
    }

    function getTypeInfo(type) {
        const types = {
            'book': { icon: '📖', label: 'নির্দেশিকা', color: 'green' },
            'subsection': { icon: '📌', label: 'উপানুচ্ছেদ', color: 'green' },
            'ref': { icon: '🔢', label: 'অনুচ্ছেদ', color: 'green' },
            'ppr': { icon: '📕', label: 'PPR 2025', color: 'red' },
            'challenge': { icon: '⚠️', label: 'চ্যালেঞ্জ', color: 'orange' },
            'decision': { icon: '🌳', label: 'সিদ্ধান্ত', color: 'purple' },
            'fund': { icon: '💰', label: 'অর্থ', color: 'teal' },
            'milestone': { icon: '🎯', label: 'অনুমোদন', color: 'blue' },
            'system': { icon: '🖥️', label: 'সিস্টেম', color: 'indigo' },
            'misc': { icon: '📝', label: 'বিবিধ', color: 'pink' },
            'appendix': { icon: '📎', label: 'সংযোজনী', color: 'purple' },
        };
        return types[type] || { icon: '📄', label: 'তথ্য', color: 'gray' };
    }

    function showResults() {
        if (resultsContainer) resultsContainer.style.display = 'block';
    }

    function hideResults() {
        if (resultsContainer) resultsContainer.style.display = 'none';
        selectedIndex = -1;
    }

    function renderResult(result, index, query) {
        const typeInfo = getTypeInfo(result.type);
        const title = highlightText(result.section || '', query);
        const snippet = highlightText((result.snippet || '').substring(0, 150), query);
        
        return `
            <a href="${escapeHtml(result.url || '#')}" class="live-search-result" data-index="${index}">
                <div class="live-search-result-header">
                    <span class="live-search-type live-search-type-${typeInfo.color}">
                        ${typeInfo.icon} ${typeInfo.label}
                    </span>
                    <span class="live-search-chapter">${escapeHtml(result.chapter || '')}</span>
                </div>
                <div class="live-search-result-title">${title}</div>
                ${snippet ? `<div class="live-search-result-snippet">${snippet}...</div>` : ''}
            </a>
        `;
    }

    async function performSearch(query) {
        if (abortController) abortController.abort();
        abortController = new AbortController();

        try {
            resultsContainer.innerHTML = `<div class="live-search-loading" style="padding: 15px; text-align: center;">খোঁজা হচ্ছে...</div>`;
            showResults();

            const response = await fetch(`/search?q=${encodeURIComponent(query)}&format=json`, { signal: abortController.signal });
            if (!response.ok) throw new Error('Network error');
            
            const results = await response.json();
            currentResults = results || [];

            if (currentResults.length === 0) {
                resultsContainer.innerHTML = `<div class="live-search-no-results" style="padding: 15px; text-align: center;"><div class="live-search-no-icon">🔍</div><div>"${escapeHtml(query)}" এর জন্য কিছু পাওয়া যায়নি</div></div>`;
                return;
            }

            const html = currentResults.slice(0, MAX_RESULTS).map((r, i) => renderResult(r, i, query)).join('');
            resultsContainer.innerHTML = html;
            selectedIndex = -1;

        } catch (error) {
            if (error.name !== 'AbortError') {
                resultsContainer.innerHTML = `<div class="live-search-error" style="padding: 15px; color: red; text-align: center;">⚠️ সার্চ করতে সমস্যা হয়েছে</div>`;
            }
        }
    }

    function handleInput(e) {
        const query = e.target.value.trim();
        if (debounceTimer) clearTimeout(debounceTimer);

        if (query.length < MIN_QUERY_LENGTH) {
            hideResults();
            currentResults = [];
            return;
        }
        debounceTimer = setTimeout(() => performSearch(query), DEBOUNCE_MS);
    }

    function handleKeyDown(e) {
        if (!resultsContainer || resultsContainer.style.display === 'none') return;
        const items = resultsContainer.querySelectorAll('.live-search-result');
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateSelection(items);
        } else if (e.key === 'Enter') {
            if (selectedIndex >= 0 && items[selectedIndex]) {
                e.preventDefault();
                items[selectedIndex].click();
            }
        } else if (e.key === 'Escape') {
            hideResults();
        }
    }

    function updateSelection(items) {
        items.forEach((item, i) => {
            if (i === selectedIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    function init() {
        if (!detectElements()) return;

        searchInput.addEventListener('input', handleInput);
        searchInput.addEventListener('keydown', handleKeyDown);
        
        document.addEventListener('click', (e) => {
            if (searchForm && !searchForm.contains(e.target)) {
                hideResults();
            }
        });

        console.log('✅ Live Search Activated');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();