// Dashboard Charts - D3.js score trend & category heatmap
(function() {
    'use strict';

    // -- Theme helpers --
    function getThemeColors() {
        var style = getComputedStyle(document.documentElement);
        return {
            text1:   style.getPropertyValue('--text-1').trim()   || '#f0f2f5',
            text2:   style.getPropertyValue('--text-2').trim()   || '#94a3b8',
            text3:   style.getPropertyValue('--text-3').trim()   || '#64748b',
            accent:  style.getPropertyValue('--accent').trim()   || '#0078E8',
            border:  style.getPropertyValue('--glass-border').trim() || 'rgba(0,99,190,0.12)',
            gradeA:  style.getPropertyValue('--grade-a').trim()  || '#34d399',
            gradeB:  style.getPropertyValue('--grade-b').trim()  || '#38bdf8',
            gradeC:  style.getPropertyValue('--grade-c').trim()  || '#fbbf24',
            gradeD:  style.getPropertyValue('--grade-d').trim()  || '#fb923c',
            gradeF:  style.getPropertyValue('--grade-f').trim()  || '#f87171'
        };
    }

    // Distinct color palette for project lines
    var LINE_COLORS = [
        '#0078E8', '#34d399', '#f87171', '#fbbf24', '#a78bfa',
        '#fb923c', '#38bdf8', '#f472b6', '#06b6d4', '#84cc16',
        '#e879f9', '#22d3ee', '#facc15', '#4ade80', '#f43f5e'
    ];

    // -------------------------------------------------------------------------
    // Score Trend Line Chart
    // -------------------------------------------------------------------------
    window.renderScoreTrend = function(containerId, projects) {
        var container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        // Only include projects that have score history
        var data = projects.filter(function(p) { return p.scores && p.scores.length > 0; });
        if (data.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:2rem 0;">No score history available.</p>';
            return;
        }

        var colors = getThemeColors();
        var margin = { top: 30, right: 140, bottom: 50, left: 55 };
        var fullWidth = container.clientWidth || 800;
        var fullHeight = 350;
        var width = fullWidth - margin.left - margin.right;
        var height = fullHeight - margin.top - margin.bottom;

        // Find max analysis count across all projects
        var maxLen = d3.max(data, function(p) { return p.scores.length; });

        // Scales
        var x = d3.scaleLinear()
            .domain([0, Math.max(maxLen - 1, 1)])
            .range([0, width]);

        var y = d3.scaleLinear()
            .domain([0, 100])
            .range([height, 0]);

        // SVG
        var svg = d3.select('#' + containerId)
            .append('svg')
            .attr('width', fullWidth)
            .attr('height', fullHeight)
            .attr('viewBox', [0, 0, fullWidth, fullHeight])
            .style('font', '12px Inter, sans-serif');

        var g = svg.append('g')
            .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

        // Grid lines
        g.append('g')
            .attr('class', 'grid-y')
            .selectAll('line')
            .data(y.ticks(5))
            .join('line')
            .attr('x1', 0).attr('x2', width)
            .attr('y1', function(d) { return y(d); })
            .attr('y2', function(d) { return y(d); })
            .attr('stroke', colors.border)
            .attr('stroke-dasharray', '3,3');

        g.append('g')
            .attr('class', 'grid-x')
            .selectAll('line')
            .data(x.ticks(Math.min(maxLen, 10)))
            .join('line')
            .attr('x1', function(d) { return x(d); })
            .attr('x2', function(d) { return x(d); })
            .attr('y1', 0).attr('y2', height)
            .attr('stroke', colors.border)
            .attr('stroke-dasharray', '3,3');

        // Axes
        g.append('g')
            .attr('transform', 'translate(0,' + height + ')')
            .call(d3.axisBottom(x).ticks(Math.min(maxLen, 10)).tickFormat(function(d) { return '#' + (d + 1); }))
            .call(function(g) {
                g.select('.domain').attr('stroke', colors.text3);
                g.selectAll('.tick text').attr('fill', colors.text2).style('font-size', '11px');
                g.selectAll('.tick line').attr('stroke', colors.text3);
            });

        g.append('text')
            .attr('x', width / 2).attr('y', height + 40)
            .attr('text-anchor', 'middle')
            .attr('fill', colors.text2)
            .style('font-size', '11px')
            .text('Analysis #');

        g.append('g')
            .call(d3.axisLeft(y).ticks(5))
            .call(function(g) {
                g.select('.domain').attr('stroke', colors.text3);
                g.selectAll('.tick text').attr('fill', colors.text2).style('font-size', '11px');
                g.selectAll('.tick line').attr('stroke', colors.text3);
            });

        g.append('text')
            .attr('transform', 'rotate(-90)')
            .attr('x', -height / 2).attr('y', -40)
            .attr('text-anchor', 'middle')
            .attr('fill', colors.text2)
            .style('font-size', '11px')
            .text('Score');

        // Line generator
        var line = d3.line()
            .x(function(d, i) { return x(i); })
            .y(function(d) { return y(d); })
            .curve(d3.curveMonotoneX);

        // Draw lines + dots per project
        data.forEach(function(project, idx) {
            var color = LINE_COLORS[idx % LINE_COLORS.length];

            // Line
            g.append('path')
                .datum(project.scores)
                .attr('fill', 'none')
                .attr('stroke', color)
                .attr('stroke-width', 2.5)
                .attr('stroke-linejoin', 'round')
                .attr('stroke-linecap', 'round')
                .attr('d', line);

            // Dots
            g.selectAll('.dot-' + idx)
                .data(project.scores)
                .join('circle')
                .attr('cx', function(d, i) { return x(i); })
                .attr('cy', function(d) { return y(d); })
                .attr('r', 4)
                .attr('fill', color)
                .attr('stroke', 'var(--bg-card)')
                .attr('stroke-width', 2)
                .append('title')
                .text(function(d, i) { return project.name + ' #' + (i + 1) + ': ' + d.toFixed(1); });
        });

        // Legend
        var legend = svg.append('g')
            .attr('transform', 'translate(' + (margin.left + width + 15) + ',' + margin.top + ')');

        data.forEach(function(project, idx) {
            var color = LINE_COLORS[idx % LINE_COLORS.length];
            var ly = idx * 22;

            legend.append('line')
                .attr('x1', 0).attr('x2', 18)
                .attr('y1', ly).attr('y2', ly)
                .attr('stroke', color).attr('stroke-width', 2.5);

            legend.append('circle')
                .attr('cx', 9).attr('cy', ly)
                .attr('r', 3).attr('fill', color);

            legend.append('text')
                .attr('x', 24).attr('y', ly + 4)
                .attr('fill', colors.text2)
                .style('font-size', '11px')
                .text(project.name.length > 16 ? project.name.substring(0, 14) + '..' : project.name);
        });
    };

    // -------------------------------------------------------------------------
    // Category Heatmap
    // -------------------------------------------------------------------------
    window.renderCategoryHeatmap = function(containerId, projects) {
        var container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        // Filter projects with category_scores
        var data = projects.filter(function(p) {
            return p.category_scores && Object.keys(p.category_scores).length > 0;
        });
        if (data.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:2rem 0;">No category data available.</p>';
            return;
        }

        var colors = getThemeColors();
        var categories = ['data_model', 'dax', 'power_query', 'report'];
        var categoryLabels = {
            data_model: 'Data Model',
            dax: 'DAX',
            power_query: 'Power Query',
            report: 'Report'
        };

        var cellSize = 60;
        var labelWidth = 160;
        var headerHeight = 60;
        var margin = { top: 10, right: 80, bottom: 20, left: 10 };

        var gridWidth = categories.length * cellSize;
        var gridHeight = data.length * cellSize;
        var fullWidth = Math.min(container.clientWidth || 700, labelWidth + gridWidth + margin.left + margin.right);
        var fullHeight = headerHeight + gridHeight + margin.top + margin.bottom;

        // Color scale: red -> yellow -> green
        var colorScale = d3.scaleLinear()
            .domain([0, 50, 100])
            .range(['#f87171', '#fbbf24', '#34d399'])
            .clamp(true);

        var svg = d3.select('#' + containerId)
            .append('svg')
            .attr('width', fullWidth)
            .attr('height', fullHeight)
            .attr('viewBox', [0, 0, fullWidth, fullHeight])
            .style('font', '12px Inter, sans-serif');

        var g = svg.append('g')
            .attr('transform', 'translate(' + (margin.left + labelWidth) + ',' + (margin.top + headerHeight) + ')');

        // Column headers
        categories.forEach(function(cat, ci) {
            svg.append('text')
                .attr('x', margin.left + labelWidth + ci * cellSize + cellSize / 2)
                .attr('y', margin.top + headerHeight - 10)
                .attr('text-anchor', 'middle')
                .attr('fill', colors.text2)
                .style('font-size', '11px')
                .style('font-weight', '600')
                .text(categoryLabels[cat]);
        });

        // Row labels + cells
        data.forEach(function(project, ri) {
            // Row label
            svg.append('text')
                .attr('x', margin.left + labelWidth - 10)
                .attr('y', margin.top + headerHeight + ri * cellSize + cellSize / 2 + 4)
                .attr('text-anchor', 'end')
                .attr('fill', colors.text1)
                .style('font-size', '11px')
                .style('font-weight', '500')
                .text(project.name.length > 20 ? project.name.substring(0, 18) + '..' : project.name);

            categories.forEach(function(cat, ci) {
                var score = (project.category_scores && project.category_scores[cat] != null)
                    ? project.category_scores[cat] : null;

                var cellGroup = g.append('g');

                // Cell rectangle
                cellGroup.append('rect')
                    .attr('x', ci * cellSize + 2)
                    .attr('y', ri * cellSize + 2)
                    .attr('width', cellSize - 4)
                    .attr('height', cellSize - 4)
                    .attr('rx', 6)
                    .attr('fill', score !== null ? colorScale(score) : 'var(--glass-border)')
                    .attr('opacity', score !== null ? 0.85 : 0.3)
                    .style('transition', 'opacity 0.2s');

                // Score text inside cell
                cellGroup.append('text')
                    .attr('x', ci * cellSize + cellSize / 2)
                    .attr('y', ri * cellSize + cellSize / 2 + 5)
                    .attr('text-anchor', 'middle')
                    .attr('fill', score !== null && score < 50 ? '#fff' : '#1a202c')
                    .style('font-size', '13px')
                    .style('font-weight', '700')
                    .text(score !== null ? Math.round(score) : '-');

                // Tooltip
                if (score !== null) {
                    cellGroup.append('title')
                        .text(project.name + ' / ' + categoryLabels[cat] + ': ' + score.toFixed(1));
                }
            });
        });

        // Color legend
        var legendX = margin.left + labelWidth + gridWidth + 15;
        var legendHeight = 120;

        var defs = svg.append('defs');
        var gradient = defs.append('linearGradient')
            .attr('id', 'heatmap-gradient')
            .attr('x1', '0%').attr('y1', '100%')
            .attr('x2', '0%').attr('y2', '0%');

        gradient.append('stop').attr('offset', '0%').attr('stop-color', '#f87171');
        gradient.append('stop').attr('offset', '50%').attr('stop-color', '#fbbf24');
        gradient.append('stop').attr('offset', '100%').attr('stop-color', '#34d399');

        var lg = svg.append('g')
            .attr('transform', 'translate(' + legendX + ',' + (margin.top + headerHeight) + ')');

        lg.append('rect')
            .attr('width', 14).attr('height', legendHeight)
            .attr('rx', 3)
            .style('fill', 'url(#heatmap-gradient)');

        lg.append('text').attr('x', 20).attr('y', 10)
            .attr('fill', colors.text2).style('font-size', '10px').text('100');
        lg.append('text').attr('x', 20).attr('y', legendHeight / 2 + 4)
            .attr('fill', colors.text2).style('font-size', '10px').text('50');
        lg.append('text').attr('x', 20).attr('y', legendHeight)
            .attr('fill', colors.text2).style('font-size', '10px').text('0');
    };

    // -------------------------------------------------------------------------
    // Filter Dashboard
    // -------------------------------------------------------------------------
    window.filterDashboard = function() {
        var search = (document.getElementById('filter-search').value || '').toLowerCase();
        var grade = document.getElementById('filter-grade').value;
        var dateFrom = document.getElementById('filter-date-from').value;
        var dateTo = document.getElementById('filter-date-to').value;

        var cards = document.querySelectorAll('.project-card');
        cards.forEach(function(card) {
            var name = card.getAttribute('data-name') || '';
            var cardGrade = card.getAttribute('data-grade') || '';
            var cardDate = card.getAttribute('data-date') || '';

            var show = true;

            if (search && name.indexOf(search) === -1) show = false;
            if (grade && cardGrade !== grade) show = false;
            if (dateFrom && cardDate && cardDate < dateFrom) show = false;
            if (dateTo && cardDate && cardDate > dateTo) show = false;

            card.style.display = show ? '' : 'none';
        });
    };

    window.clearFilters = function() {
        document.getElementById('filter-search').value = '';
        document.getElementById('filter-grade').value = '';
        document.getElementById('filter-date-from').value = '';
        document.getElementById('filter-date-to').value = '';
        filterDashboard();
    };

    // -------------------------------------------------------------------------
    // Auto-init on DOMContentLoaded
    // -------------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', function() {
        var data = window._dashboardData;
        if (!data || data.length === 0) return;

        renderScoreTrend('trend-container', data);
        renderCategoryHeatmap('heatmap-container', data);
    });

})();
