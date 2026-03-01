// Findings filter and search functionality
(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        var filterBar = document.getElementById('findings-filter-bar');
        if (!filterBar) return;

        var searchInput = document.getElementById('findings-search');
        var severityBtns = filterBar.querySelectorAll('.filter-severity-btn');
        var categoryBtns = filterBar.querySelectorAll('.filter-category-btn');
        var counterEl = document.getElementById('findings-counter');

        var activeSeverities = new Set(['error', 'warning', 'info']);
        var activeCategories = new Set(['data_model', 'dax', 'power_query', 'report']);

        function applyFilters() {
            var searchText = (searchInput.value || '').toLowerCase();
            var items = document.querySelectorAll('.finding-item[data-severity]');
            var shown = 0;
            var total = items.length;

            items.forEach(function(item) {
                var sev = item.getAttribute('data-severity');
                var cat = item.getAttribute('data-category');
                var text = item.textContent.toLowerCase();

                var matchSev = activeSeverities.has(sev);
                var matchCat = activeCategories.has(cat);
                var matchSearch = !searchText || text.indexOf(searchText) !== -1;

                if (matchSev && matchCat && matchSearch) {
                    item.style.display = '';
                    shown++;
                } else {
                    item.style.display = 'none';
                }
            });

            // Update category card visibility
            var catCards = document.querySelectorAll('.finding-category-card[data-category]');
            catCards.forEach(function(card) {
                var cat = card.getAttribute('data-category');
                if (!activeCategories.has(cat)) {
                    card.style.display = 'none';
                } else {
                    card.style.display = '';
                }
            });

            if (counterEl) {
                var template = counterEl.getAttribute('data-template') || 'Showing {x} of {y}';
                counterEl.textContent = template.replace('{x}', shown).replace('{y}', total);
            }
        }

        // Search input
        if (searchInput) {
            searchInput.addEventListener('input', applyFilters);
        }

        // Severity toggles
        severityBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var sev = this.getAttribute('data-severity');
                if (sev === 'all') {
                    if (activeSeverities.size === 3) {
                        activeSeverities.clear();
                        severityBtns.forEach(function(b) { b.classList.remove('active'); });
                    } else {
                        activeSeverities = new Set(['error', 'warning', 'info']);
                        severityBtns.forEach(function(b) { b.classList.add('active'); });
                    }
                } else {
                    if (activeSeverities.has(sev)) {
                        activeSeverities.delete(sev);
                        this.classList.remove('active');
                    } else {
                        activeSeverities.add(sev);
                        this.classList.add('active');
                    }
                }
                // Update "All" button state
                var allBtn = filterBar.querySelector('.filter-severity-btn[data-severity="all"]');
                if (allBtn) {
                    allBtn.classList.toggle('active', activeSeverities.size === 3);
                }
                applyFilters();
            });
        });

        // Category toggles
        categoryBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var cat = this.getAttribute('data-category');
                if (activeCategories.has(cat)) {
                    activeCategories.delete(cat);
                    this.classList.remove('active');
                } else {
                    activeCategories.add(cat);
                    this.classList.add('active');
                }
                applyFilters();
            });
        });
    });
})();
